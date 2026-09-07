"""Native MCP client with stdio and streamable HTTP transports.

The engine intentionally keeps transport, protocol, schema validation and
security separate so every MCP tool call can pass through an auditable policy
boundary before execution.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import shlex
import socket
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import httpx


class MCPError(RuntimeError):
    """Protocol, configuration or remote MCP error."""


class MCPTransportError(MCPError):
    """Transport-level MCP error."""


@dataclass
class MCPServerConfig:
    name: str
    transport: str = "stdio"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 30.0
    reconnect_attempts: int | None = None
    reconnect_backoff_seconds: float = 1.0
    allow_private_networks: bool = False
    allowed_hosts: set[str] = field(default_factory=set)
    allow_command: bool = False


@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    annotations: dict[str, Any] = field(default_factory=dict)
    server: str = ""


@dataclass(frozen=True)
class MCPResource:
    uri: str
    name: str
    description: str = ""
    mime_type: str | None = None
    server: str = ""


class _Transport:
    async def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


class _StdioTransport(_Transport):
    def __init__(self, config: MCPServerConfig):
        if not config.command or not config.allow_command:
            raise MCPTransportError("MCP stdio requires an explicit allowed command")
        self.config = config
        self.process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._counter = 0

    async def connect(self) -> None:
        argv = [config_part for config_part in shlex.split(self.config.command)]
        argv.extend(self.config.args)
        if not argv:
            raise MCPTransportError("MCP stdio command is empty")
        env = os.environ.copy()
        env.update(self.config.env)
        self.process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

    async def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.process is None or self.process.stdin is None or self.process.stdout is None:
            raise MCPTransportError("MCP stdio transport is not connected")
        async with self._lock:
            self._counter += 1
            request_id = self._counter
            request = {"jsonrpc": "2.0", "id": request_id, "method": method}
            if params is not None:
                request["params"] = params
            self.process.stdin.write((json.dumps(request) + "\n").encode())
            await self.process.stdin.drain()
            while True:
                line = await asyncio.wait_for(self.process.stdout.readline(), self.config.timeout_seconds)
                if not line:
                    raise MCPTransportError("MCP stdio server closed stdout")
                message = json.loads(line.decode())
                if message.get("id") == request_id:
                    if "error" in message:
                        raise MCPError(str(message["error"]))
                    return message.get("result", {})

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        if self.process is None or self.process.stdin is None:
            raise MCPTransportError("MCP stdio transport is not connected")
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        await self.process.stdin.drain()

    async def close(self) -> None:
        if self.process is not None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 3)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            self.process = None


class _HTTPTransport(_Transport):
    def __init__(self, config: MCPServerConfig):
        if not config.url:
            raise MCPTransportError("MCP HTTP transport requires a URL")
        self.config = config
        self.client: httpx.AsyncClient | None = None
        self.session_id: str | None = None
        self._counter = 0

    @staticmethod
    def _validate_url(config: MCPServerConfig) -> None:
        parsed = urlparse(config.url or "")
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise MCPTransportError("MCP HTTP URL must use http or https")
        host = parsed.hostname.lower().rstrip(".")
        if config.allowed_hosts and host not in {h.lower().rstrip(".") for h in config.allowed_hosts}:
            raise MCPTransportError(f"MCP host '{host}' is not allowlisted")
        if not config.allow_private_networks:
            try:
                records = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
            except OSError as exc:
                raise MCPTransportError(f"Cannot resolve MCP host '{host}'") from exc
            for record in {item[4][0] for item in records}:
                ip = ipaddress.ip_address(record)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                    raise MCPTransportError(f"Private MCP endpoint blocked: {record}")

    async def connect(self) -> None:
        self._validate_url(self.config)
        self.client = httpx.AsyncClient(timeout=self.config.timeout_seconds, headers=self.config.headers)

    async def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.client is None:
            raise MCPTransportError("MCP HTTP transport is not connected")
        self._counter += 1
        payload = {"jsonrpc": "2.0", "id": self._counter, "method": method}
        if params is not None:
            payload["params"] = params
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        response = await self.client.post(self.config.url or "", json=payload, headers=headers)
        if "Mcp-Session-Id" in response.headers:
            self.session_id = response.headers["Mcp-Session-Id"]
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    return json.loads(line[5:].strip())
            raise MCPTransportError("MCP SSE response did not contain data")
        message = response.json()
        if "error" in message:
            raise MCPError(str(message["error"]))
        return message.get("result", {})

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        if self.client is None:
            raise MCPTransportError("MCP HTTP transport is not connected")
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        headers = {"Content-Type": "application/json"}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        await self.client.post(self.config.url or "", json=payload, headers=headers)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None


SecurityCallback = Callable[[MCPTool, dict[str, Any]], Awaitable[None] | None]
AuditCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


def _validate_schema(value: Any, schema: dict[str, Any], path: str = "$", root: dict[str, Any] | None = None) -> None:
    """Validate the JSON-Schema subset required for MCP tool arguments."""
    root = root or schema
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref.startswith("#/$defs/"):
            key = ref.split("/", 2)[-1]
            target = root.get("$defs", {}).get(key)
            if target is None:
                raise MCPError(f"Unknown JSON schema reference {ref}")
            return _validate_schema(value, target, path, root)
    schema_type = schema.get("type")
    types = schema_type if isinstance(schema_type, list) else [schema_type]
    if schema_type and not _matches_type(value, types):
        raise MCPError(f"Invalid MCP argument at {path}: expected {schema_type}")
    if "enum" in schema and value not in schema["enum"]:
        raise MCPError(f"Invalid MCP argument at {path}: value is not in enum")
    if isinstance(value, dict):
        for required in schema.get("required", []):
            if required not in value:
                raise MCPError(f"Missing required MCP argument: {path}.{required}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = set(value) - set(props)
            if unknown:
                raise MCPError(f"Unknown MCP arguments at {path}: {sorted(unknown)}")
        for key, child in props.items():
            if key in value:
                _validate_schema(value[key], child, f"{path}.{key}", root)
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _validate_schema(item, schema["items"], f"{path}[{index}]", root)


def _matches_type(value: Any, types: list[Any]) -> bool:
    mapping = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool, "null": type(None)}
    for item in types:
        if item == "integer" and isinstance(value, bool):
            continue
        expected = mapping.get(item)
        if expected and isinstance(value, expected):
            return True
    return not types or types == [None]


class MCPClient:
    """Complete MCP client surface for initialization, tools, resources and prompts."""

    PROTOCOL_VERSION = "2025-06-18"

    def __init__(self, config: MCPServerConfig, *, security: SecurityCallback | None = None,
                 audit: AuditCallback | None = None):
        self.config = config
        self.security = security
        self.audit = audit
        self.transport: _Transport | None = None
        self.server_info: dict[str, Any] = {}
        self.server_capabilities: dict[str, Any] = {}
        self.tools: dict[str, MCPTool] = {}
        self.resources: dict[str, MCPResource] = {}
        self.resource_templates: list[dict[str, Any]] = []
        self.prompts: dict[str, dict[str, Any]] = {}
        self.connected = False
        self._lock = asyncio.Lock()

    async def connect(self) -> dict[str, Any]:
        async with self._lock:
            self.transport = _StdioTransport(self.config) if self.config.transport == "stdio" else _HTTPTransport(self.config)
            attempts = 0
            while True:
                try:
                    if hasattr(self.transport, "connect"):
                        await self.transport.connect()  # type: ignore[attr-defined]
                    result = await self._request("initialize", {
                        "protocolVersion": self.PROTOCOL_VERSION,
                        "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
                        "clientInfo": {"name": "AIO-CLi", "version": "1.0.0"},
                    }, audit=False)
                    self.server_info = result.get("serverInfo", {})
                    self.server_capabilities = result.get("capabilities", {})
                    await self._notify("notifications/initialized", {})
                    await self.refresh()
                    self.connected = True
                    return result
                except Exception:
                    await self.close()
                    attempts += 1
                    max_attempts = self.config.reconnect_attempts
                    if max_attempts is not None and attempts > max_attempts:
                        raise
                    await asyncio.sleep(self.config.reconnect_backoff_seconds * min(attempts, 8))

    async def reconnect(self) -> dict[str, Any]:
        await self.close()
        return await self.connect()

    async def close(self) -> None:
        if self.transport is not None:
            await self.transport.close()
        self.transport = None
        self.connected = False

    async def _request(self, method: str, params: dict[str, Any] | None = None, *, audit: bool = True) -> dict[str, Any]:
        if self.transport is None:
            raise MCPTransportError("MCP client is not connected")
        result = await self.transport.request(method, params)
        if audit and self.audit:
            event = {"id": str(uuid.uuid4()), "server": self.config.name, "method": method, "status": "success"}
            maybe = self.audit(event)
            if asyncio.iscoroutine(maybe):
                await maybe
        return result

    async def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        if self.transport is None:
            raise MCPTransportError("MCP client is not connected")
        await self.transport.notify(method, params)

    async def refresh(self) -> None:
        if "tools" in self.server_capabilities:
            result = await self._request("tools/list")
            self.tools = {
                item["name"]: MCPTool(
                    name=item["name"],
                    description=item.get("description", ""),
                    input_schema=item.get("inputSchema", {"type": "object"}),
                    annotations=item.get("annotations", {}),
                    server=self.config.name,
                )
                for item in result.get("tools", [])
            }
        if "resources" in self.server_capabilities:
            result = await self._request("resources/list")
            self.resources = {
                item["uri"]: MCPResource(
                    uri=item["uri"], name=item.get("name", item["uri"]),
                    description=item.get("description", ""), mime_type=item.get("mimeType"), server=self.config.name,
                )
                for item in result.get("resources", [])
            }
            self.resource_templates = result.get("resourceTemplates", [])
        if "prompts" in self.server_capabilities:
            result = await self._request("prompts/list")
            self.prompts = {item["name"]: item for item in result.get("prompts", [])}

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        tool = self.tools.get(name)
        if tool is None:
            raise MCPError(f"MCP tool not found: {name}")
        args = arguments or {}
        _validate_schema(args, tool.input_schema)
        if self.security:
            decision = self.security(tool, args)
            if asyncio.iscoroutine(decision):
                await decision
        result = await self._request("tools/call", {"name": name, "arguments": args})
        if self.audit:
            event = {"id": str(uuid.uuid4()), "server": self.config.name, "tool": name, "status": "success"}
            maybe = self.audit(event)
            if asyncio.iscoroutine(maybe):
                await maybe
        return result

    async def read_resource(self, uri: str) -> dict[str, Any]:
        if not uri:
            raise ValueError("resource uri is required")
        return await self._request("resources/read", {"uri": uri})

    async def get_prompt(self, name: str, arguments: dict[str, str] | None = None) -> dict[str, Any]:
        if name not in self.prompts:
            raise MCPError(f"MCP prompt not found: {name}")
        return await self._request("prompts/get", {"name": name, "arguments": arguments or {}})

    async def ping(self) -> dict[str, Any]:
        return await self._request("ping", {})
