"""
Tool Registry Module

Central registry for all tools with permission enforcement.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Tool:
    """A tool definition."""

    name: str
    description: str
    func: Callable
    parameters: dict[str, Any] = field(default_factory=dict)
    permission_level: str = "standard"
    requires_approval: bool = False
    timeout_seconds: int = 60
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result of a tool execution."""

    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: int = 0
    tool_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """
    Central registry for all tools.

    Features:
    - Tool registration and discovery
    - Permission enforcement
    - Timeout handling
    - Execution tracking
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._execution_log: list[dict[str, Any]] = []

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_all(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        """List all tool names."""
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    async def execute(
        self, tool_name: str, *args, permissionGranted: bool = True, **kwargs
    ) -> ToolResult:
        """
        Execute a tool with permission checking.

        Args:
            tool_name: Name of the tool to execute
            *args: Positional arguments for the tool
            permissionGranted: Whether permission was granted
            **kwargs: Keyword arguments for the tool

        Returns:
            ToolResult with execution outcome
        """
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found",
                tool_name=tool_name,
            )

        # Check permission
        if tool.requires_approval and not permissionGranted:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' requires approval",
                tool_name=tool_name,
            )

        start_time = datetime.utcnow()

        try:
            # Execute with timeout
            if asyncio.iscoroutinefunction(tool.func):
                result = await asyncio.wait_for(
                    tool.func(*args, **kwargs), timeout=tool.timeout_seconds
                )
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: tool.func(*args, **kwargs)),
                    timeout=tool.timeout_seconds,
                )

            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Log execution
            self._log_execution(tool_name, True, duration_ms)

            return ToolResult(
                success=True,
                output=result,
                duration_ms=duration_ms,
                tool_name=tool_name,
            )

        except TimeoutError:
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            self._log_execution(tool_name, False, duration_ms, "Timeout")

            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' timed out after {tool.timeout_seconds}s",
                duration_ms=duration_ms,
                tool_name=tool_name,
            )

        except Exception as e:
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            self._log_execution(tool_name, False, duration_ms, str(e))

            return ToolResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
                tool_name=tool_name,
            )

    def _log_execution(
        self, tool_name: str, success: bool, duration_ms: int, error: str | None = None
    ) -> None:
        """Log a tool execution."""
        self._execution_log.append(
            {
                "tool_name": tool_name,
                "success": success,
                "duration_ms": duration_ms,
                "error": error,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def get_execution_log(self) -> list[dict[str, Any]]:
        """Get the execution log."""
        return self._execution_log.copy()

    def clear_log(self) -> None:
        """Clear the execution log."""
        self._execution_log.clear()


# Global registry instance
_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_builtin_tools(_registry)
    return _registry


def _register_builtin_tools(registry: ToolRegistry) -> None:
    """Register built-in tools."""
    from . import builtins

    # Register file operations
    registry.register(
        Tool(
            name="read_file",
            description="Read contents of a file",
            func=builtins.read_file,
            permission_level="read_only",
            timeout_seconds=30,
        )
    )

    registry.register(
        Tool(
            name="write_file",
            description="Write contents to a file",
            func=builtins.write_file,
            permission_level="standard",
            requires_approval=False,
            timeout_seconds=30,
        )
    )

    registry.register(
        Tool(
            name="edit_file",
            description="Edit a file with search/replace",
            func=builtins.edit_file,
            permission_level="standard",
            timeout_seconds=60,
        )
    )

    # Register shell
    registry.register(
        Tool(
            name="shell",
            description="Execute a shell command",
            func=builtins.shell,
            permission_level="elevated",
            requires_approval=True,
            timeout_seconds=120,
        )
    )

    # Register test
    registry.register(
        Tool(
            name="test",
            description="Run tests",
            func=builtins.test,
            permission_level="standard",
            timeout_seconds=300,
        )
    )

    # Register search
    registry.register(
        Tool(
            name="search",
            description="Search for files or content",
            func=builtins.search,
            permission_level="read_only",
            timeout_seconds=60,
        )
    )

    # Register git
    registry.register(
        Tool(
            name="git",
            description="Execute git operations",
            func=builtins.git,
            permission_level="elevated",
            requires_approval=True,
            timeout_seconds=60,
        )
    )
