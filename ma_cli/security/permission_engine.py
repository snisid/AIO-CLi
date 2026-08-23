"""
Permission Engine for MA-CLI.

This module handles permission checking, approval gates, and security policies.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PermissionLevel(Enum):
    """Permission levels for operations."""

    READ_ONLY = "read_only"  # No modifications
    STANDARD = "standard"  # Normal development operations
    ELEVATED = "elevated"  # Requires additional verification
    DANGEROUS = "dangerous"  # Requires explicit approval
    CRITICAL = "critical"  # Requires human intervention


class ApprovalStatus(Enum):
    """Status of an approval request."""

    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class PermissionRule:
    """A single permission rule."""

    action: str
    level: PermissionLevel
    allowed_patterns: list[str] = field(default_factory=list)
    denied_patterns: list[str] = field(default_factory=list)
    requires_approval: bool = False
    max_resource_usage: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def check_path(self, path: str) -> bool:
        """Check if a path is allowed by this rule."""
        path_str = str(path)

        # Check denied patterns first
        for pattern in self.denied_patterns:
            if re.match(pattern, path_str):
                return False

        # If no allowed patterns, everything not denied is allowed
        if not self.allowed_patterns:
            return True

        # Check allowed patterns
        for pattern in self.allowed_patterns:
            if re.match(pattern, path_str):
                return True

        return False

    def check_command(self, command: str) -> bool:
        """Check if a command is allowed by this rule."""
        return self.check_path(command)


@dataclass
class ApprovalRequest:
    """Represents an approval request."""

    id: str
    action: str
    description: str
    level: PermissionLevel
    requested_at: datetime
    requested_by: str
    details: dict[str, Any] = field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    responded_at: datetime | None = None
    responded_by: str | None = None
    response_reason: str | None = None

    def approve(self, responder: str, reason: str | None = None) -> None:
        """Mark request as approved."""
        self.status = ApprovalStatus.GRANTED
        self.responded_at = datetime.utcnow()
        self.responded_by = responder
        self.response_reason = reason or "Approved"

    def deny(self, responder: str, reason: str | None = None) -> None:
        """Mark request as denied."""
        self.status = ApprovalStatus.DENIED
        self.responded_at = datetime.utcnow()
        self.responded_by = responder
        self.response_reason = reason or "Denied"

    def is_approved(self) -> bool:
        """Check if request is approved."""
        return self.status == ApprovalStatus.GRANTED


@dataclass
class PermissionPolicy:
    """Security policy defining permission rules."""

    name: str
    description: str = ""
    default_level: PermissionLevel = PermissionLevel.STANDARD
    rules: list[PermissionRule] = field(default_factory=list)
    approval_required_actions: list[str] = field(default_factory=list)
    dangerous_commands: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    denied_paths: list[str] = field(default_factory=list)

    # Critical operations that always require approval
    CRITICAL_ACTIONS = [
        "delete_database",
        "drop_table",
        "deploy_production",
        "modify_production_config",
        "rotate_secrets",
        "delete_repository",
        "mass_delete_files",
        "format_disk",
        "modify_system_config",
        "install_system_package",
        "modify_firewall",
        "expose_credentials",
    ]

    # Dangerous shell commands
    DANGEROUS_COMMANDS = [
        r"rm\s+(-[rf]+\s+)?/",  # rm -rf /
        r"dd\s+if=/dev/zero",  # dd destructive
        r":\(\)\{\s*:\|:&\s*\};:",  # fork bomb
        r"mkfs",  # format filesystem
        r">\s*/dev/sd",  # overwrite disk
        r"chmod\s+777\s+/",  # dangerous permissions
        r"chown\s+-R\s+root:/",  # dangerous ownership
    ]

    def __post_init__(self):
        # Add critical actions to approval list
        for action in self.CRITICAL_ACTIONS:
            if action not in self.approval_required_actions:
                self.approval_required_actions.append(action)

        # Add dangerous commands
        for cmd in self.DANGEROUS_COMMANDS:
            if cmd not in self.dangerous_commands:
                self.dangerous_commands.append(cmd)

    def get_rule(self, action: str) -> PermissionRule | None:
        """Get rule for an action."""
        for rule in self.rules:
            if rule.action == action:
                return rule
        return None

    def check_permission(
        self, action: str, path: str | None = None, command: str | None = None
    ) -> tuple[bool, PermissionLevel, bool]:
        """
        Check permission for an action.

        Returns:
            Tuple of (allowed, required_level, requires_approval)
        """
        rule = self.get_rule(action)

        if rule is None:
            # Use default level
            level = self.default_level
            requires_approval = action in self.approval_required_actions

            # Check path restrictions
            if path:
                for denied in self.denied_paths:
                    if path.startswith(denied):
                        return False, level, requires_approval

                if self.allowed_paths:
                    allowed = any(path.startswith(p) for p in self.allowed_paths)
                    if not allowed:
                        return False, level, requires_approval

            return True, level, requires_approval

        # Check rule-specific permissions
        if path and not rule.check_path(path):
            return False, rule.level, rule.requires_approval

        if command and not rule.check_command(command):
            return False, rule.level, rule.requires_approval

        return True, rule.level, rule.requires_approval

    def requires_approval(self, action: str) -> bool:
        """Check if action requires approval."""
        if action in self.approval_required_actions:
            return True

        rule = self.get_rule(action)
        if rule and rule.requires_approval:
            return True

        return False

    def is_dangerous_command(self, command: str) -> bool:
        """Check if command matches dangerous patterns."""
        for pattern in self.dangerous_commands:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    def add_rule(self, rule: PermissionRule) -> None:
        """Add a permission rule."""
        # Remove existing rule for same action
        self.rules = [r for r in self.rules if r.action != rule.action]
        self.rules.append(rule)


class PermissionEngine:
    """
    Permission checking and approval management engine.
    """

    def __init__(self, policy: PermissionPolicy | None = None):
        self.policy = policy or PermissionPolicy(name="default")
        self._pending_approvals: dict[str, ApprovalRequest] = {}
        self._approval_callbacks: list[Callable[[ApprovalRequest], None]] = []
        self._approval_history: list[ApprovalRequest] = []

    def set_policy(self, policy: PermissionPolicy) -> None:
        """Set the active permission policy."""
        self.policy = policy

    def check(
        self, action: str, path: str | None = None, command: str | None = None
    ) -> tuple[bool, PermissionLevel, bool]:
        """
        Check if an action is permitted.

        Args:
            action: Action being performed
            path: Optional file/system path
            command: Optional shell command

        Returns:
            Tuple of (allowed, level, requires_approval)
        """
        # Check for dangerous commands
        if command and self.policy.is_dangerous_command(command):
            return False, PermissionLevel.CRITICAL, True

        return self.policy.check_permission(action, path, command)

    def request_approval(
        self,
        action: str,
        description: str,
        details: dict[str, Any] | None = None,
        requested_by: str = "system",
    ) -> ApprovalRequest:
        """
        Request approval for an action.

        Args:
            action: Action requiring approval
            description: Human-readable description
            details: Additional context
            requested_by: Entity requesting approval

        Returns:
            ApprovalRequest object
        """
        import uuid

        request = ApprovalRequest(
            id=str(uuid.uuid4())[:8],
            action=action,
            description=description,
            level=self._get_action_level(action),
            requested_at=datetime.utcnow(),
            requested_by=requested_by,
            details=details or {},
        )

        self._pending_approvals[request.id] = request
        self._approval_history.append(request)

        # Notify callbacks
        for callback in self._approval_callbacks:
            try:
                callback(request)
            except Exception:
                pass

        return request

    def _get_action_level(self, action: str) -> PermissionLevel:
        """Determine permission level for an action."""
        if action in self.policy.CRITICAL_ACTIONS:
            return PermissionLevel.CRITICAL

        rule = self.policy.get_rule(action)
        if rule:
            return rule.level

        return self.policy.default_level

    def approve(self, request_id: str, responder: str, reason: str | None = None) -> bool:
        """Approve a pending request."""
        request = self._pending_approvals.get(request_id)
        if not request:
            return False

        request.approve(responder, reason)
        return True

    def deny(self, request_id: str, responder: str, reason: str | None = None) -> bool:
        """Deny a pending request."""
        request = self._pending_approvals.get(request_id)
        if not request:
            return False

        request.deny(responder, reason)
        return True

    def get_pending_approvals(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        return list(self._pending_approvals.values())

    def get_approval_status(self, request_id: str) -> ApprovalStatus | None:
        """Get status of an approval request."""
        request = self._pending_approvals.get(request_id)
        if request:
            return request.status
        return None

    def register_approval_callback(self, callback: Callable[[ApprovalRequest], None]) -> None:
        """Register a callback for new approval requests."""
        self._approval_callbacks.append(callback)

    def get_approval_history(self, limit: int = 50) -> list[ApprovalRequest]:
        """Get recent approval history."""
        return list(reversed(self._approval_history[-limit:]))

    def cleanup_expired_requests(self, hours: int = 24) -> int:
        """Clean up old approval requests."""
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        expired = []

        for request_id, request in self._pending_approvals.items():
            if request.requested_at < cutoff:
                request.status = ApprovalStatus.EXPIRED
                expired.append(request_id)

        for request_id in expired:
            del self._pending_approvals[request_id]

        return len(expired)

    def export_audit_log(self) -> list[dict[str, Any]]:
        """Export audit log of all permission checks and approvals."""
        return [
            {
                "id": req.id,
                "action": req.action,
                "description": req.description,
                "level": req.level.value,
                "status": req.status.value,
                "requested_at": req.requested_at.isoformat(),
                "requested_by": req.requested_by,
                "responded_at": req.responded_at.isoformat() if req.responded_at else None,
                "responded_by": req.responded_by,
                "response_reason": req.response_reason,
            }
            for req in self._approval_history
        ]


# Default permission policies
DEFAULT_POLICIES = {
    "restrictive": PermissionPolicy(
        name="restrictive",
        description="Highly restrictive policy requiring approval for most actions",
        default_level=PermissionLevel.READ_ONLY,
        allowed_paths=["/workspace", "/tmp"],
        denied_paths=["/etc", "/var", "/home", "/root"],
    ),
    "standard": PermissionPolicy(
        name="standard",
        description="Standard development policy",
        default_level=PermissionLevel.STANDARD,
        allowed_paths=["/workspace", "/tmp", ".ma-cli"],
        denied_paths=["/etc/passwd", "/etc/shadow", "/root"],
    ),
    "permissive": PermissionPolicy(
        name="permissive",
        description="Permissive policy for trusted environments",
        default_level=PermissionLevel.ELEVATED,
        approval_required_actions=PermissionPolicy.CRITICAL_ACTIONS,
    ),
}


def get_default_policy(name: str = "standard") -> PermissionPolicy:
    """Get a default permission policy by name."""
    return DEFAULT_POLICIES.get(name, DEFAULT_POLICIES["standard"])


# Global permission engine instance
_permission_engine: PermissionEngine | None = None


def get_permission_engine(policy_name: str = "standard") -> PermissionEngine:
    """Get global permission engine instance."""
    global _permission_engine
    if _permission_engine is None:
        _permission_engine = PermissionEngine(get_default_policy(policy_name))
    return _permission_engine
