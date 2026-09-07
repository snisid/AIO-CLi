"""Task-aware intelligent routing layered on the provider registry.

The selector is deterministic, health-aware and policy-first. It never invents a
provider endpoint; it only scores models actually discovered by configured providers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..capabilities import CapabilityEngine, CapabilityProfile, TaskCapabilityRequest
from ..providers import ModelInfo, get_provider_registry


@dataclass(frozen=True)
class RoutingDecision:
    model: ModelInfo | None
    provider: str | None
    score: float
    reason: str
    candidates: tuple[dict[str, Any], ...] = ()


class IntelligentRouter:
    """Select the best discovered model for a task without hard-coded provider order."""

    def __init__(self, capability_engine: CapabilityEngine | None = None):
        self.capabilities = capability_engine or CapabilityEngine()
        self._latency: dict[tuple[str, str], float] = {}
        self._failures: dict[tuple[str, str], int] = {}

    def record_outcome(self, provider: str, model: str, *, latency_ms: float | None = None,
                       success: bool = True) -> None:
        key = (provider, model)
        if latency_ms is not None:
            old = self._latency.get(key)
            self._latency[key] = latency_ms if old is None else old * .7 + latency_ms * .3
        self._failures[key] = 0 if success else self._failures.get(key, 0) + 1

    def _score(self, model: ModelInfo, task_type: str, request: TaskCapabilityRequest) -> float:
        caps = {c.casefold() for c in model.capabilities}
        required = {c.value.casefold() for c in request.required}
        coverage = len(required & caps) / max(1, len(required))
        if coverage < 1.0 or not model.available:
            return float("-inf")
        score = 55.0 + coverage * 20.0
        task = task_type.casefold()
        if task in {"coding", "debugging", "refactoring"} and {"code", "coding"} & caps:
            score += 12
        if task in {"reasoning", "architecture", "security"} and "reasoning" in caps:
            score += 12
        if request.context_tokens and model.max_context_tokens:
            ratio = request.context_tokens / model.max_context_tokens
            if ratio > 1:
                return float("-inf")
            score += max(0.0, 8.0 * (1.0 - ratio))
        key = (model.provider, model.model_id)
        score -= min(30.0, self._failures.get(key, 0) * 10.0)
        latency = self._latency.get(key)
        if latency is not None:
            score += max(-10.0, 10.0 - latency / 500.0)
            if request.max_latency_ms and latency > request.max_latency_ms:
                score -= 20.0
        if request.max_cost_per_token and model.cost_per_token > request.max_cost_per_token:
            return float("-inf")
        score -= min(10.0, model.cost_per_token * 1_000_000)
        return score

    async def select(self, task_type: str, *, complexity: int = 3, risk: int = 1,
                     context_tokens: int = 0, privacy: bool = False) -> RoutingDecision:
        request = self.capabilities.infer(task_type, complexity=complexity, risk=risk)
        request.context_tokens = context_tokens
        registry = get_provider_registry()
        registry.initialize(None)
        candidates: list[tuple[float, ModelInfo]] = []
        diagnostics: list[dict[str, Any]] = []
        for provider in registry.get_enabled():
            if privacy and provider.name != "ollama":
                continue
            try:
                models = await provider.discover_models()
            except Exception as exc:
                diagnostics.append({"provider": provider.name, "error": str(exc)})
                continue
            for model in models:
                score = self._score(model, task_type, request)
                diagnostics.append({"provider": model.provider, "model": model.model_id,
                                    "score": score})
                if score != float("-inf"):
                    candidates.append((score, model))
        candidates.sort(key=lambda x: x[0], reverse=True)
        if not candidates:
            return RoutingDecision(None, None, float("-inf"),
                                   f"no discovered model satisfies task '{task_type}'", tuple(diagnostics))
        score, model = candidates[0]
        return RoutingDecision(model, model.provider, score,
                               f"selected for {task_type} using capability, context, health, latency and cost",
                               tuple(diagnostics))
