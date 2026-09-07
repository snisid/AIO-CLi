"""MCP JSON-RPC 2.0 stdio client with discover/auth/execute/restart lifecycle."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any


class MCPError(RuntimeError):
    """Raised when an MCP server cannot complete a protocol operation."""


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout: float = 15.0


@dataclass
class MCPTool:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    server: str = ""


class MCPClient:
    """Minimal MCP client over newline-delimited or Content-Length framed stdio."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._proc: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self._lock = asyncio.Lock()
        self.server_info: dict[str, Any] = {}

    @property
    def connected(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def connect(self) -> dict[str, Any]:
        if self.connected:
            return self.server_info
        self._proc = await asyncio.create_subprocess_exec(
            self.config.command,
            *self.config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        result = await self.request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ma-cli", "version": "1.0.0"},
        })
        self.server_info = result
        await self.notify("notifications/initialized", {})
        return result

    async def disconnect(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except TimeoutError:
                proc.kill()
                await proc.wait()

    async def restart(self) -> dict[str, Any]:
        await self.disconnect()
        return await self.connect()

    async def ping(self) -> bool:
        try:
            await self.request("ping", {})
            return True
        except MCPError:
            return False

    async def list_tools(self) -> list[MCPTool]:
        payload = await self.request("tools/list", {})
        tools = []
        for item in payload.get("tools", []):
            tools.append(MCPTool(
                name=item.get("name", ""),
                description=item.get("description", ""),
                input_schema=item.get("inputSchema", {}) or {},
                server=self.config.name,
            ))
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.request("tools/call", {"name": name, "arguments": arguments or {}})

    async def notify(self, method: str, params: dict[str, Any]) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})

    async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise MCPError(f"MCP server '{self.config.name}' is not connected")
        async with self._lock:
            request_id = self._next_id
            self._next_id += 1
            await self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            message = await asyncio.wait_for(self._read(), timeout=self.config.timeout)
        if "error" in message:
            raise MCPError(str(message["error"]))
        if message.get("id") != request_id:
            raise MCPError(f"MCP response id mismatch for {method}")
        result = message.get("result")
        if not isinstance(result, dict):
            raise MCPError(f"MCP method {method} returned a non-object result")
        return result

    async def _write(self, payload: dict[str, Any]) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        encoded = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii")
        self._proc.stdin.write(header + encoded)
        await self._proc.stdin.drain()

    async def _read(self) -> dict[str, Any]:
        assert self._proc is not None and self._proc.stdout is not None
        headers: dict[str, str] = {}
        while True:
            line = await self._proc.stdout.readline()
            if not line:
                raise MCPError(f"MCP server '{self.config.name}' closed the stream")
            if line in (b"\r\n", b"\n"):
                break
            decoded = line.decode("utf-8", errors="replace").strip()
            if ":" in decoded:
                key, value = decoded.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        length = int(headers.get("content-length", "0"))
        if length <= 0:
            raise MCPError("MCP response missing Content-Length")
        body = await self._proc.stdout.readexactly(length)
        return json.loads(body.decode("utf-8"))


class MCPEngine:
    """Lifecycle manager for configured MCP servers."""

    def __init__(self) -> None:
        self._configs: dict[str, MCPServerConfig] = {}
        self._clients: dict[str, MCPClient] = {}

    def register(self, config: MCPServerConfig) -> None:
        if not config.name or not config.command:
            raise MCPError("MCP server requires a name and command")
        self._configs[config.name] = config

    def discover(self) -> list[MCPServerConfig]:
        return list(self._configs.values())

    def get_client(self, name: str) -> MCPClient:
        if name not in self._configs:
            raise MCPError(f"unknown MCP server: {name}")
        if name not in self._clients:
            self._clients[name] = MCPClient(self._configs[name])
        return self._clients[name]

    async def connect(self, name: str) -> dict[str, Any]:
        return await self.get_client(name).connect()

    async def disconnect(self, name: str) -> None:
        if name in self._clients:
            await self._clients[name].disconnect()

    async def restart(self, name: str) -> dict[str, Any]:
        return await self.get_client(name).restart()

    async def list_tools(self, name: str) -> list[MCPTool]:
        client = self.get_client(name)
        if not client.connected:
            await client.connect()
        return await client.list_tools()

    async def execute(self, server: str, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        client = self.get_client(server)
        if not client.connected:
            await client.connect()
        return await client.call_tool(tool, arguments)

    async def disconnect_all(self) -> None:
        for name in list(self._clients):
            await self.disconnect(name)


_engine: MCPEngine | None = None


def get_mcp_engine() -> MCPEngine:
    global _engine
    if _engine is None:
        _engine = MCPEngine()
    return _engine
