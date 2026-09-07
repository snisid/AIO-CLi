"""Runtime security policy and workspace sandbox boundary."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class SecurityDecision:
    allowed: bool
    risk: str
    reason: str


class RuntimeSecurity:
    """Fail-closed security policy used before native tool execution."""

    HIGH_RISK_PATTERNS = (
        r"\b(remove-item|rm|rmdir|del|format|diskpart)\b",
        r"\b(invoke-webrequest|curl|wget)\b.*\|.*\b(iex|invoke-expression)\b",
        r"\b(reg\s+(add|delete)|sc\s+(create|delete)|bcdedit)\b",
        r"\b(shutdown|restart-computer)\b",
    )

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()

    def resolve_workspace_path(self, path: str) -> Path:
        raw = Path(path)
        target = (raw if raw.is_absolute() else self.workspace / raw).resolve()
        try:
            target.relative_to(self.workspace)
        except ValueError as exc:
            raise PermissionError("path escapes workspace sandbox") from exc
        return target

    def classify_command(self, command: str) -> SecurityDecision:
        normalized = command.strip().lower()
        if not normalized:
            return SecurityDecision(False, "critical", "empty command")
        for pattern in self.HIGH_RISK_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return SecurityDecision(False, "critical", "command matches blocked high-risk policy")
        if any(token in normalized for token in ("git push", "docker", "npm publish", "pip install")):
            return SecurityDecision(False, "high", "external or state-changing command requires explicit approval")
        return SecurityDecision(True, "standard", "command allowed by baseline policy")

    def authorize_command(self, command: str, approved: bool = False) -> SecurityDecision:
        decision = self.classify_command(command)
        if not decision.allowed:
            return decision
        if decision.risk == "high" and not approved:
            return SecurityDecision(False, "high", "explicit approval required")
        return decision
