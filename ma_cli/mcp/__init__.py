"""
MCP (Model Context Protocol) Subsystem for AIO-CLi.

This module provides MCP server discovery, connection management,
tool/resource registration, and secure execution.
"""

from .discovery import MCPServerDefinition, MCPServerState, MCPDiscovery, MCPServerRegistry

__all__ = [
    "MCPServerDefinition",
    "MCPServerState",
    "MCPDiscovery",
    "MCPServerRegistry",
]
