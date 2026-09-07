"""Provider-neutral MCP lifecycle and schema validation primitives.

Transport implementations can plug into this contract without bypassing the
runtime security/tool registry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class MCPTool:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MCPResource:
    uri: str
    name: str = ""
    description: str = ""


@dataclass
class MCPSession:
    server: str
    connected: bool = False
    authenticated: bool = False
    tools: list[MCPTool] = field(default_factory=list)
    resources: list[MCPResource] = field(default_factory=list)


class MCPTransport(Protocol):
    async def connect(self) -> None: ...
    async def authenticate(self) -> None: ...
    async def list_tools(self) -> list[dict[str, Any]]: ...
    async def list_resources(self) -> list[dict[str, Any]]: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...
    async def close(self) -> None: ...


class MCPEngine:
    """Lifecycle coordinator; execution must be delegated to a secured transport."""

    def __init__(self, transport: MCPTransport, server: str):
        self.transport = transport
        self.session = MCPSession(server=server)

    @staticmethod
    def validate_schema(schema: dict[str, Any], arguments: dict[str, Any]) -> tuple[bool, str]:
        if not isinstance(schema, dict) or not isinstance(arguments, dict):
            return False, "schema and arguments must be objects"
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        missing = [key for key in required if key not in arguments]
        if missing:
            return False, f"missing required fields: {missing}"
        if isinstance(properties, dict):
            for key, value in arguments.items():
                spec = properties.get(key, {})
                expected = spec.get("type") if isinstance(spec, dict) else None
                if expected == "string" and not isinstance(value, str):
                    return False, f"{key} must be string"
                if expected == "object" and not isinstance(value, dict):
                    return False, f"{key} must be object"
                if expected == "array" and not isinstance(value, list):
                    return False, f"{key} must be array"
                if expected == "boolean" and not isinstance(value, bool):
                    return False, f"{key} must be boolean"
                if expected == "number" and not isinstance(value, (int, float)):
                    return False, f"{key} must be number"
        return True, "valid"

    async def connect(self) -> MCPSession:
        await self.transport.connect()
        self.session.connected = True
        await self.transport.authenticate()
        self.session.authenticated = True
        self.session.tools = [MCPTool(t.get("name", ""), t.get("description", ""), t.get("inputSchema", {}))
                              for t in await self.transport.list_tools()]
        self.session.resources = [MCPResource(r.get("uri", ""), r.get("name", ""), r.get("description", ""))
                                  for r in await self.transport.list_resources()]
        return self.session

    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        if not self.session.connected or not self.session.authenticated:
            raise RuntimeError("MCP session is not connected/authenticated")
        tool = next((t for t in self.session.tools if t.name == name), None)
        if tool is None:
            raise KeyError(f"unknown MCP tool: {name}")
        valid, reason = self.validate_schema(tool.input_schema, arguments)
        if not valid:
            raise ValueError(reason)
        return await self.transport.call_tool(name, arguments)

    async def close(self) -> None:
        try:
            await self.transport.close()
        finally:
            self.session.connected = False
            self.session.authenticated = False
