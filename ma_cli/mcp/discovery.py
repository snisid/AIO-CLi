"""
MCP Server Discovery and Registry.

Handles discovery, registration, and state management of MCP servers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

from ..config.engine import MCPServerConfig


class MCPServerState(Enum):
    """MCP server lifecycle states."""

    DISCOVERED = auto()
    CONNECTING = auto()
    AUTHENTICATING = auto()
    INITIALIZING = auto()
    CONNECTED = auto()
    READY = auto()
    DEGRADED = auto()
    FAILED = auto()
    STOPPING = auto()
    DISCONNECTED = auto()


@dataclass
class MCPServerDefinition:
    """Definition of an MCP server."""

    server_id: str
    config: MCPServerConfig
    state: MCPServerState = MCPServerState.DISCOVERED
    capabilities: dict[str, Any] = field(default_factory=dict)
    tools: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    prompts: list[dict[str, Any]] = field(default_factory=list)
    error_message: str | None = None
    last_error: Exception | None = None
    connected_at: float | None = None
    initialized_at: float | None = None

    def is_ready(self) -> bool:
        """Check if server is ready for tool execution."""
        return self.state == MCPServerState.READY

    def is_connected(self) -> bool:
        """Check if server is connected."""
        return self.state in (
            MCPServerState.CONNECTED,
            MCPServerState.READY,
            MCPServerState.DEGRADED,
        )

    def is_failed(self) -> bool:
        """Check if server has failed."""
        return self.state == MCPServerState.FAILED


class MCPDiscovery:
    """
    Discovers and registers MCP servers from configuration.

    Does not automatically trust discovered servers.
    All servers remain subject to central security policy.
    """

    def __init__(self):
        self._registry: dict[str, MCPServerDefinition] = {}
        self._lock = asyncio.Lock()

    async def discover(self, servers_config: dict[str, MCPServerConfig]) -> list[MCPServerDefinition]:
        """
        Discover MCP servers from configuration.

        Args:
            servers_config: Dictionary of server configurations

        Returns:
            List of discovered server definitions
        """
        async with self._lock:
            discovered = []
            for server_id, config in servers_config.items():
                if not config.enabled:
                    continue

                definition = MCPServerDefinition(server_id=server_id, config=config)
                self._registry[server_id] = definition
                discovered.append(definition)

            return discovered

    async def get_server(self, server_id: str) -> MCPServerDefinition | None:
        """Get a server definition by ID."""
        async with self._lock:
            return self._registry.get(server_id)

    async def list_servers(self) -> list[MCPServerDefinition]:
        """List all discovered servers."""
        async with self._lock:
            return list(self._registry.values())

    async def remove_server(self, server_id: str) -> bool:
        """Remove a server from the registry."""
        async with self._lock:
            if server_id in self._registry:
                del self._registry[server_id]
                return True
            return False

    async def clear(self):
        """Clear all discovered servers."""
        async with self._lock:
            self._registry.clear()


class MCPServerRegistry:
    """
    Global registry for MCP servers.

    Provides thread-safe access to discovered servers.
    """

    _instance: MCPServerRegistry | None = None

    def __init__(self):
        self._discovery = MCPDiscovery()

    @classmethod
    def get_instance(cls) -> MCPServerRegistry:
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = MCPServerRegistry()
        return cls._instance

    async def discover(self, servers_config: dict[str, MCPServerConfig]) -> list[MCPServerDefinition]:
        """Discover servers from configuration."""
        return await self._discovery.discover(servers_config)

    async def get_server(self, server_id: str) -> MCPServerDefinition | None:
        """Get server by ID."""
        return await self._discovery.get_server(server_id)

    async def list_servers(self) -> list[MCPServerDefinition]:
        """List all servers."""
        return await self._discovery.list_servers()

    async def remove_server(self, server_id: str) -> bool:
        """Remove a server."""
        return await self._discovery.remove_server(server_id)

    async def clear(self):
        """Clear all servers."""
        await self._discovery.clear()
