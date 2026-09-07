"""Runtime security policy and fail-closed workspace sandbox boundary."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import os


@dataclass(frozen=True)
class SecurityDecision:
    allowed: bool
    risk: str
    reason: str


class RuntimeSecurity:
    """Central policy gate for paths, commands and external side effects."""

    HIGH_RISK_PATTERNS = (
        r"\b(remove-item|rm|rmdir|del|erase|format|diskpart)\b",
        r"\b(invoke-webrequest|curl|wget)\b.*\|.*\b(iex|invoke-expression)\b",
        r"\b(reg\s+(add|delete)|sc\s+(create|delete)|bcdedit)\b",
        r"\b(shutdown|restart-computer|stop-computer)\b",
        r"\b(git\s+push|npm\s+publish|twine\s+upload)\b",
    )
    REVIEW_PATTERNS = (
        r"\b(pip|pip3|npm|pnpm|yarn|cargo|go)\s+(install|add|get)\b",
        r"\b(docker|podman)\b",
        r"\b(git\s+(checkout|reset|clean|commit|merge|rebase))\b",
    )

    def __init__(self, workspace: Path):
        self.workspace = workspace.expanduser().resolve(strict=False)

    def resolve_workspace_path(self, path: str) -> Path:
        if not isinstance(path, str) or not path.strip():
            raise PermissionError("path must be a non-empty string")
        raw = Path(path).expanduser()
        target = (raw if raw.is_absolute() else self.workspace / raw).resolve(strict=False)
        try:
            target.relative_to(self.workspace)
        except ValueError as exc:
            raise PermissionError("path escapes workspace sandbox") from exc
        # Existing symlinks/junctions are resolved above. For a new target, every
        # existing parent is still checked to prevent a link from escaping later.
        probe = target
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        resolved_probe = probe.resolve(strict=False)
        try:
            resolved_probe.relative_to(self.workspace)
        except ValueError as exc:
            raise PermissionError("path parent escapes workspace sandbox") from exc
        return target

    def classify_command(self, command: str) -> SecurityDecision:
        if not isinstance(command, str) or not command.strip():
            return SecurityDecision(False, "critical", "empty command")
        normalized = re.sub(r"\s+", " ", command.strip().lower())
        for pattern in self.HIGH_RISK_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return SecurityDecision(False, "critical", "command matches blocked high-risk policy")
        for pattern in self.REVIEW_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return SecurityDecision(False, "high", "external or state-changing command requires explicit approval")
        if any(token in normalized for token in ("http://", "https://", "ssh ", "scp ")):
            return SecurityDecision(False, "high", "network/external side effect requires explicit approval")
        return SecurityDecision(True, "standard", "command allowed by baseline policy")

    def authorize_command(self, command: str, approved: bool = False) -> SecurityDecision:
        decision = self.classify_command(command)
        if not decision.allowed and decision.risk != "high":
            return decision
        if decision.risk == "high" and not approved:
            return SecurityDecision(False, "high", "explicit approval required")
        return SecurityDecision(True, decision.risk, "approved by runtime policy")
