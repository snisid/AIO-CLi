"""High-level capability negotiation used by runtime and model routing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .engine import CapabilityEngine
from .models import CapabilityProfile, TaskCapabilityRequest


@dataclass(frozen=True)
class NegotiationResult:
    accepted: bool
    request: TaskCapabilityRequest
    missing: tuple[str, ...] = ()
    reason: str = ""


class CapabilityNegotiator:
    """Converts runtime task requirements into a deterministic capability gate."""

    def __init__(self, engine: CapabilityEngine | None = None):
        self.engine = engine or CapabilityEngine()

    def request_for(self, task_type: str, *, complexity: int = 3, risk: int = 1,
                    context_tokens: int = 0, execution_mode: Any | None = None) -> TaskCapabilityRequest:
        request = self.engine.infer(task_type, complexity=complexity, risk=risk)
        if context_tokens:
            request.context_tokens = context_tokens
        if execution_mode is not None:
            request.execution_mode = execution_mode
        return request

    def negotiate(self, profile: CapabilityProfile, request: TaskCapabilityRequest) -> NegotiationResult:
        missing = [c.value for c in request.required if c not in profile.capabilities]
        if request.context_tokens > profile.max_context_tokens:
            return NegotiationResult(False, request, tuple(missing), "context window is insufficient")
        if missing:
            return NegotiationResult(False, request, tuple(missing), "required capabilities are unavailable")
        return NegotiationResult(True, request, (), "capability contract satisfied")
