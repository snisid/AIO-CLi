"""
MCP Connection and Authentication Layer.

Handles connection management, authentication, and transport for MCP servers.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..config.engine import MCPServerConfig, MCPAuthConfig
from .discovery import MCPServerDefinition, MCPServerState


class MCPConnectionState(Enum):
    """Connection lifecycle states."""

    DISCONNECTED = auto()
    CONNECTING = auto()
    AUTHENTICATING = auto()
    INITIALIZING = auto()
    CONNECTED = auto()
    READY = auto()
    DEGRADED = auto()
    FAILED = auto()
    STOPPING = auto()


@dataclass
class MCPTransport:
    """Abstract transport layer for MCP connections."""

    config: MCPServerConfig
    _read_stream: Any = None
    _write_stream: Any = None
    _process: asyncio.Process | None = None
    _session: ClientSession | None = None

    async def connect(self) -> tuple[Any, Any]:
        """
        Establish transport connection.

        Returns:
            Tuple of (read_stream, write_stream)
        """
        if self.config.transport == "stdio":
            return await self._connect_stdio()
        elif self.config.transport in ("http", "streamable_http"):
            return await self._connect_http()
        else:
            raise ValueError(f"Unsupported transport: {self.config.transport}")

    async def _connect_stdio(self) -> tuple[Any, Any]:
        """Connect using stdio transport."""
        if not self.config.command:
            raise ValueError("stdio transport requires command")

        # Build environment with auth if needed
        env = os.environ.copy()
        if self.config.auth and self.config.auth.type == "api_key":
            if self.config.auth.api_key_env:
                env[self.config.auth.api_key_env] = os.environ.get(
                    self.config.auth.api_key_env, ""
                )

        server_params = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=env,
        )

        stdio_transport = stdio_client(server_params)
        self._read_stream, self._write_stream = await stdio_transport.__aenter__()
        return self._read_stream, self._write_stream

    async def _connect_http(self) -> tuple[Any, Any]:
        """Connect using HTTP transport."""
        if not self.config.url:
            raise ValueError("HTTP transport requires URL")

        # HTTP transport implementation would use mcp.client.http
        # For now, raise NotImplementedError to indicate it's not yet implemented
        raise NotImplementedError("HTTP transport not yet implemented")

    async def disconnect(self):
        """Close transport connection."""
        if self._read_stream and hasattr(self._read_stream, "aclose"):
            await self._read_stream.aclose()
        if self._write_stream and hasattr(self._write_stream, "aclose"):
            await self._write_stream.aclose()


class MCPAuthenticator:
    """
    Handles MCP server authentication.

    Never logs credentials directly.
    Uses environment variables for secret storage.
    """

    def __init__(self, auth_config: MCPAuthConfig | None):
        self.auth_config = auth_config
        self._token: str | None = None

    async def authenticate(self) -> bool:
        """
        Perform authentication.

        Returns:
            True if authentication successful or not required
        """
        if not self.auth_config or self.auth_config.type == "none":
            return True

        if self.auth_config.type == "bearer":
            return await self._authenticate_bearer()
        elif self.auth_config.type == "api_key":
            return await self._authenticate_api_key()
        else:
            return False

    async def _authenticate_bearer(self) -> bool:
        """Authenticate using bearer token."""
        if not self.auth_config.token_env:
            return False

        token = os.environ.get(self.auth_config.token_env)
        if not token:
            return False

        self._token = token
        return True

    async def _authenticate_api_key(self) -> bool:
        """Authenticate using API key."""
        if not self.auth_config.api_key_env:
            return False

        api_key = os.environ.get(self.auth_config.api_key_env)
        if not api_key:
            return False

        self._token = api_key
        return True

    def get_token(self) -> str | None:
        """Get authenticated token (for internal use only)."""
        return self._token


@dataclass
class MCPConnection:
    """Represents a single MCP connection."""

    server_id: str
    config: MCPServerConfig
    state: MCPConnectionState = MCPConnectionState.DISCONNECTED
    transport: MCPTransport | None = None
    authenticator: MCPAuthenticator | None = None
    session: ClientSession | None = None
    error_message: str | None = None
    connected_at: float | None = None
    last_activity: float | None = None

    def is_connected(self) -> bool:
        """Check if connection is active."""
        return self.state in (
            MCPConnectionState.CONNECTED,
            MCPConnectionState.READY,
            MCPConnectionState.DEGRADED,
        )


class MCPConnectionManager:
    """
    Manages MCP server connections.

    Handles connection lifecycle, reconnection, and health monitoring.
    """

    def __init__(self):
        self._connections: dict[str, MCPConnection] = {}
        self._lock = asyncio.Lock()
        self._health_check_interval = 30  # seconds
        self._connection_timeout = 30  # seconds
        self._initialization_timeout = 60  # seconds

    async def connect(
        self, server_def: MCPServerDefinition
    ) -> MCPConnection:
        """
        Establish connection to an MCP server.

        Args:
            server_def: Server definition from discovery

        Returns:
            MCPConnection object

        Raises:
            ConnectionError: If connection fails
            TimeoutError: If connection times out
            AuthenticationError: If authentication fails
        """
        async with self._lock:
            # Create connection object
            connection = MCPConnection(
                server_id=server_def.server_id,
                config=server_def.config,
                state=MCPConnectionState.CONNECTING,
            )
            self._connections[server_def.server_id] = connection

            try:
                # Create transport
                transport = MCPTransport(config=server_def.config)
                connection.transport = transport

                # Connect transport with timeout
                try:
                    read_stream, write_stream = await asyncio.wait_for(
                        transport.connect(),
                        timeout=self._connection_timeout,
                    )
                except asyncio.TimeoutError:
                    connection.state = MCPConnectionState.FAILED
                    connection.error_message = "Connection timeout"
                    raise TimeoutError(f"Connection to {server_def.server_id} timed out")

                # Create authenticator
                connection.authenticator = MCPAuthenticator(auth_config=server_def.config.auth)

                # Authenticate if required
                if server_def.config.auth and server_def.config.auth.type != "none":
                    connection.state = MCPConnectionState.AUTHENTICATING
                    if not await connection.authenticator.authenticate():
                        connection.state = MCPConnectionState.FAILED
                        connection.error_message = "Authentication failed"
                        raise PermissionError(f"Authentication failed for {server_def.server_id}")

                # Create session
                connection.state = MCPConnectionState.INITIALIZING
                session = ClientSession(read_stream, write_stream)

                try:
                    await asyncio.wait_for(
                        session.initialize(),
                        timeout=self._initialization_timeout,
                    )
                except asyncio.TimeoutError:
                    connection.state = MCPConnectionState.FAILED
                    connection.error_message = "Initialization timeout"
                    raise TimeoutError(f"Initialization of {server_def.server_id} timed out")

                connection.session = session
                connection.state = MCPConnectionState.READY
                connection.connected_at = time.time()
                connection.last_activity = time.time()

                # Update server definition
                server_def.state = MCPServerState.READY
                server_def.connected_at = connection.connected_at
                server_def.initialized_at = connection.connected_at

                return connection

            except Exception as e:
                connection.state = MCPConnectionState.FAILED
                connection.error_message = str(e)
                server_def.state = MCPServerState.FAILED
                server_def.last_error = e
                raise

    async def disconnect(self, server_id: str) -> bool:
        """
        Disconnect from a server.

        Args:
            server_id: Server ID to disconnect

        Returns:
            True if disconnected successfully
        """
        async with self._lock:
            if server_id not in self._connections:
                return False

            connection = self._connections[server_id]

            try:
                connection.state = MCPConnectionState.STOPPING

                if connection.session:
                    await connection.session.__aexit__(None, None, None)

                if connection.transport:
                    await connection.transport.disconnect()

                connection.state = MCPConnectionState.DISCONNECTED
                del self._connections[server_id]

                return True

            except Exception as e:
                connection.error_message = str(e)
                return False

    async def get_connection(self, server_id: str) -> MCPConnection | None:
        """Get connection by server ID."""
        async with self._lock:
            return self._connections.get(server_id)

    async def list_connections(self) -> list[MCPConnection]:
        """List all active connections."""
        async with self._lock:
            return list(self._connections.values())

    async def health_check(self, server_id: str) -> bool:
        """
        Perform health check on a connection.

        Returns:
            True if connection is healthy
        """
        async with self._lock:
            if server_id not in self._connections:
                return False

            connection = self._connections[server_id]

            if not connection.is_connected():
                return False

            # Ping the server
            try:
                if connection.session:
                    await connection.session.send_ping()
                    connection.last_activity = time.time()
                    return True
            except Exception:
                connection.state = MCPConnectionState.DEGRADED
                return False

            return True

    async def reconnect(self, server_id: str, max_attempts: int = 3) -> bool:
        """
        Attempt to reconnect to a server.

        Args:
            server_id: Server ID to reconnect
            max_attempts: Maximum retry attempts

        Returns:
            True if reconnection successful
        """
        # Get server definition from registry
        from .discovery import MCPServerRegistry

        registry = MCPServerRegistry.get_instance()
        server_def = await registry.get_server(server_id)

        if not server_def:
            return False

        # Disconnect existing connection
        await self.disconnect(server_id)

        # Attempt reconnection with exponential backoff
        for attempt in range(max_attempts):
            try:
                await self.connect(server_def)
                return True
            except Exception:
                if attempt < max_attempts - 1:
                    backoff = min(2**attempt * 1, 30)  # Exponential backoff, max 30s
                    await asyncio.sleep(backoff)

        return False

    async def shutdown(self):
        """Shutdown all connections gracefully."""
        async with self._lock:
            server_ids = list(self._connections.keys())
            for server_id in server_ids:
                await self.disconnect(server_id)


# Global connection manager instance
_connection_manager: MCPConnectionManager | None = None


def get_connection_manager() -> MCPConnectionManager:
    """Get global connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = MCPConnectionManager()
    return _connection_manager
