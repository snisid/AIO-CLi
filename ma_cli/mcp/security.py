"""
MCP Security Layer.

Enforces security policies for MCP tool execution.
All MCP tools MUST pass through this security choke point.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from ..security.core import PermissionLevel, SecurityPolicy


class MCPSecurityError(Exception):
    """MCP security violation."""


class MCPRiskLevel(Enum):
    """Risk classification for MCP tools."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MCPToolSecurityContext:
    """Security context for an MCP tool invocation."""

    server_id: str
    tool_name: str
    arguments: dict[str, Any]
    risk_level: MCPRiskLevel = MCPRiskLevel.MEDIUM
    requires_human_approval: bool = False
    workspace_path: Path | None = None
    blocked_reason: str | None = None


class MCPSecurityLayer:
    """
    Security choke point for all MCP tool executions.

    CRITICAL: This layer must never be bypassed.
    All MCP tool calls MUST pass through this security check.
    """

    # Patterns indicating dangerous operations
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.\\",
        r"^/etc/",
        r"^/proc/",
        r"^/sys/",
        r"^C:\\Windows",
    ]

    DANGEROUS_COMMANDS = [
        "rm -rf",
        "del /s",
        "format",
        "mkfs",
        "dd if=",
        "chmod 777",
        "chown root",
    ]

    SENSITIVE_PATHS = [
        "/etc/passwd",
        "/etc/shadow",
        "/root/",
        "/home/*/.ssh/",
        "C:\\Windows\\System32",
        "*.pem",
        "*.key",
        "*.env",
    ]

    def __init__(self, security_policy: SecurityPolicy | None = None):
        self._policy = security_policy or SecurityPolicy()
        self._audit_log: list[dict[str, Any]] = []

    def classify_risk(
        self, server_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> MCPRiskLevel:
        """
        Classify the risk level of an MCP tool invocation.

        Args:
            server_id: MCP server ID
            tool_name: Tool name
            arguments: Tool arguments

        Returns:
            Risk level classification
        """
        # Check for destructive operations
        destructive_keywords = ["delete", "remove", "destroy", "drop", "format"]
        if any(kw in tool_name.lower() for kw in destructive_keywords):
            return MCPRiskLevel.HIGH

        # Check for write operations
        write_keywords = ["write", "create", "update", "modify", "set"]
        if any(kw in tool_name.lower() for kw in write_keywords):
            return MCPRiskLevel.MEDIUM

        # Check arguments for dangerous patterns
        arg_str = str(arguments).lower()

        # Path traversal attempts
        if "../" in arg_str or "..\\" in arg_str:
            return MCPRiskLevel.CRITICAL

        # Dangerous commands
        for cmd in self.DANGEROUS_COMMANDS:
            if cmd.lower() in arg_str:
                return MCPRiskLevel.CRITICAL

        # Read operations are generally lower risk
        read_keywords = ["read", "get", "list", "show", "inspect"]
        if any(kw in tool_name.lower() for kw in read_keywords):
            return MCPRiskLevel.LOW

        return MCPRiskLevel.MEDIUM

    def validate_arguments(
        self, server_id: str, tool_name: str, arguments: dict[str, Any], schema: dict[str, Any] | None = None
    ) -> tuple[bool, str | None]:
        """
        Validate tool arguments against security policies.

        Args:
            server_id: MCP server ID
            tool_name: Tool name
            arguments: Tool arguments
            schema: Optional tool input schema

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check for path traversal
        for key, value in arguments.items():
            if isinstance(value, str):
                # Path traversal check
                if "../" in value or "..\\" in value:
                    return False, f"Path traversal detected in argument '{key}'"

                # Absolute path check (Unix)
                if value.startswith("/etc/") or value.startswith("/proc/") or value.startswith("/sys/"):
                    return False, f"Access to sensitive path denied: {value}"

                # Check for sensitive file patterns
                for pattern in self.SENSITIVE_PATHS:
                    if pattern.startswith("*.") and value.endswith(pattern[1:]):
                        return False, f"Access to sensitive file type denied: {value}"
                    elif "*" not in pattern and pattern in value:
                        return False, f"Access to sensitive path denied: {value}"

                # Dangerous command check
                for cmd in self.DANGEROUS_COMMANDS:
                    if cmd.lower() in value.lower():
                        return False, f"Dangerous command detected in argument '{key}': {cmd}"

        return True, None

    def check_workspace_boundary(
        self, path: str, workspace_path: Path
    ) -> tuple[bool, str | None]:
        """
        Check if a path is within the workspace boundary.

        Args:
            path: Path to check
            workspace_path: Workspace root path

        Returns:
            Tuple of (is_allowed, error_message)
        """
        try:
            # Resolve to absolute path
            resolved = Path(path).resolve()
            workspace_resolved = workspace_path.resolve()

            # Check if path is within workspace
            try:
                resolved.relative_to(workspace_resolved)
                return True, None
            except ValueError:
                return False, f"Path escapes workspace boundary: {path}"

        except Exception as e:
            return False, f"Path validation error: {e}"

    def enforce(
        self,
        server_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        schema: dict[str, Any] | None = None,
        workspace_path: Path | None = None,
    ) -> MCPToolSecurityContext:
        """
        Enforce security policies on an MCP tool invocation.

        This is the MAIN SECURITY CHOKE POINT.
        All MCP tool calls MUST pass through this method.

        Args:
            server_id: MCP server ID
            tool_name: Tool name
            arguments: Tool arguments
            schema: Optional tool input schema
            workspace_path: Optional workspace path for boundary checks

        Returns:
            Security context with enforcement decision

        Raises:
            MCPSecurityError: If security policy is violated
        """
        # Create security context
        context = MCPToolSecurityContext(
            server_id=server_id,
            tool_name=tool_name,
            arguments=arguments,
            workspace_path=workspace_path,
        )

        # Classify risk
        context.risk_level = self.classify_risk(server_id, tool_name, arguments)

        # Determine if human approval is required
        if context.risk_level in (MCPRiskLevel.HIGH, MCPRiskLevel.CRITICAL):
            context.requires_human_approval = True

        # Validate arguments
        is_valid, error_msg = self.validate_arguments(server_id, tool_name, arguments, schema)
        if not is_valid:
            context.blocked_reason = error_msg
            self._log_audit(context, allowed=False, reason=error_msg)
            raise MCPSecurityError(f"Security violation: {error_msg}")

        # Check workspace boundary if applicable
        if workspace_path:
            for key, value in arguments.items():
                if isinstance(value, str) and ("/" in value or "\\" in value):
                    is_allowed, error_msg = self.check_workspace_boundary(value, workspace_path)
                    if not is_allowed:
                        context.blocked_reason = error_msg
                        self._log_audit(context, allowed=False, reason=error_msg)
                        raise MCPSecurityError(f"Workspace boundary violation: {error_msg}")

        # Log successful security check
        self._log_audit(context, allowed=True)

        return context

    def _log_audit(self, context: MCPToolSecurityContext, allowed: bool, reason: str | None = None):
        """Log security audit event."""
        self._audit_log.append({
            "timestamp": time.time(),
            "server_id": context.server_id,
            "tool_name": context.tool_name,
            "risk_level": context.risk_level.value,
            "allowed": allowed,
            "reason": reason or context.blocked_reason,
            "requires_human_approval": context.requires_human_approval,
        })

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Get security audit log."""
        return self._audit_log.copy()

    def clear_audit_log(self):
        """Clear audit log."""
        self._audit_log.clear()


# Import time for audit logging
import time

# Global security layer instance
_security_layer: MCPSecurityLayer | None = None


def get_mcp_security_layer() -> MCPSecurityLayer:
    """Get global MCP security layer instance."""
    global _security_layer
    if _security_layer is None:
        _security_layer = MCPSecurityLayer()
    return _security_layer
