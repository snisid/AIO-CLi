"""Capability normalization and reasoning-level selection."""
from __future__ import annotations

from .models import Capability, CapabilityProfile, ReasoningLevel, TaskCapabilityRequest


class CapabilityEngine:
    """Converts task intent into deterministic, typed capability requirements."""

    _reasoning_order = {
        ReasoningLevel.FAST: 0, ReasoningLevel.LOW: 1, ReasoningLevel.MEDIUM: 2,
        ReasoningLevel.HIGH: 3, ReasoningLevel.XHIGH: 4, ReasoningLevel.MAX: 5,
    }

    def infer(self, task_type: str, *, complexity: int = 3, risk: int = 1) -> TaskCapabilityRequest:
        key = task_type.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "coder": "coding", "developer": "coding", "dev": "coding",
            "tester": "testing", "qa": "testing", "reviewer": "security",
            "debugger": "debugging", "researcher": "research", "architect": "architecture",
            "planner": "architecture", "computer_use": "computer", "data": "data_analysis",
        }
        key = aliases.get(key, key)
        mapping = {
            "coding": {Capability.CODING, Capability.PATCH, Capability.STRUCTURED_OUTPUT},
            "debugging": {Capability.CODING, Capability.TERMINAL, Capability.PATCH},
            "architecture": {Capability.REASONING, Capability.CODING, Capability.STRUCTURED_OUTPUT},
            "research": {Capability.RESEARCH, Capability.FILE_SEARCH},
            "testing": {Capability.CODING, Capability.TERMINAL, Capability.STRUCTURED_OUTPUT},
            "security": {Capability.REASONING, Capability.CODING, Capability.TERMINAL},
            "browser": {Capability.BROWSER, Capability.STRUCTURED_OUTPUT},
            "computer": {Capability.COMPUTER_USE, Capability.STEERING},
            "mcp": {Capability.MCP, Capability.STRUCTURED_OUTPUT},
            "data_analysis": {Capability.DATA_ANALYSIS, Capability.FILE_SEARCH},
        }
        required = mapping.get(key, {Capability.REASONING, Capability.STRUCTURED_OUTPUT})
        return TaskCapabilityRequest(required=frozenset(required), reasoning=self.select_reasoning_level(complexity, risk))

    def select_reasoning_level(self, complexity: int, risk: int) -> ReasoningLevel:
        score = max(0, min(10, complexity)) + max(0, min(10, risk))
        if score <= 3: return ReasoningLevel.FAST
        if score <= 6: return ReasoningLevel.MEDIUM
        if score <= 10: return ReasoningLevel.HIGH
        if score <= 15: return ReasoningLevel.XHIGH
        return ReasoningLevel.MAX

    def can_satisfy(self, profile: CapabilityProfile, request: TaskCapabilityRequest) -> bool:
        if not profile.supports(request.required): return False
        if request.context_tokens and profile.max_context_tokens < request.context_tokens: return False
        supported = profile.supports_reasoning_levels
        if supported and self._reasoning_order[request.reasoning] > max(self._reasoning_order[level] for level in supported):
            return False
        return True
