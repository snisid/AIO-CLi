"""
MCP Client for Tool and Resource Operations.

Provides high-level interface for interacting with MCP servers.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from mcp import ClientSession

from .connection import MCPConnection, MCPConnectionManager
from .discovery import MCPServerRegistry


class MCPClient:
    """
    High-level MCP client for tool and resource operations.

    Handles tool discovery, validation, and execution.
    """

    def __init__(self, connection_manager: MCPConnectionManager | None = None):
        self._connection_manager = connection_manager or MCPConnectionManager()
        self._tool_cache: dict[str, dict[str, Any]] = {}
        self._resource_cache: dict[str, dict[str, Any]] = {}

    async def connect(self, server_id: str) -> bool:
        """
        Connect to an MCP server.

        Args:
            server_id: Server ID to connect to

        Returns:
            True if connection successful
        """
        registry = MCPServerRegistry.get_instance()
        server_def = await registry.get_server(server_id)

        if not server_def:
            return False

        try:
            connection = await self._connection_manager.connect(server_def)

            # Discover tools
            if connection.session:
                tools_result = await connection.session.list_tools()
                self._tool_cache[server_id] = [
                    {"name": t.name, "description": t.description, "inputSchema": t.inputSchema}
                    for t in tools_result.tools
                ]

                # Discover resources
                resources_result = await connection.session.list_resources()
                self._resource_cache[server_id] = [
                    {"uri": r.uri, "name": r.name, "description": r.description}
                    for r in resources_result.resources
                ]

            return True

        except Exception:
            return False

    async def disconnect(self, server_id: str) -> bool:
        """Disconnect from a server."""
        return await self._connection_manager.disconnect(server_id)

    async def get_tools(self, server_id: str) -> list[dict[str, Any]]:
        """Get cached tools for a server."""
        return self._tool_cache.get(server_id, [])

    async def get_resources(self, server_id: str) -> list[dict[str, Any]]:
        """Get cached resources for a server."""
        return self._resource_cache.get(server_id, [])

    async def call_tool(
        self, server_id: str, tool_name: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Call an MCP tool.

        Args:
            server_id: Server ID
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool execution result

        Raises:
            ConnectionError: If not connected
            ToolError: If tool execution fails
        """
        connection = await self._connection_manager.get_connection(server_id)

        if not connection or not connection.session:
            raise ConnectionError(f"Not connected to server {server_id}")

        start_time = time.time()
        try:
            result = await connection.session.call_tool(tool_name, arguments or {})
            duration = time.time() - start_time

            return {
                "success": True,
                "result": result,
                "duration_ms": int(duration * 1000),
                "server_id": server_id,
                "tool_name": tool_name,
            }

        except Exception as e:
            duration = time.time() - start_time
            return {
                "success": False,
                "error": str(e),
                "duration_ms": int(duration * 1000),
                "server_id": server_id,
                "tool_name": tool_name,
            }

    async def read_resource(self, server_id: str, uri: str) -> dict[str, Any]:
        """
        Read an MCP resource.

        Args:
            server_id: Server ID
            uri: Resource URI

        Returns:
            Resource content
        """
        connection = await self._connection_manager.get_connection(server_id)

        if not connection or not connection.session:
            raise ConnectionError(f"Not connected to server {server_id}")

        try:
            result = await connection.session.read_resource(uri)
            return {"success": True, "content": result.contents}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def shutdown(self):
        """Shutdown all connections."""
        await self._connection_manager.shutdown()


# Global client instance
_client: MCPClient | None = None


def get_mcp_client() -> MCPClient:
    """Get global MCP client instance."""
    global _client
    if _client is None:
        _client = MCPClient()
    return _client
