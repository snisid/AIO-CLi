"""Task-aware intelligent routing and completion over the provider registry."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..capabilities import CapabilityEngine, TaskCapabilityRequest
from ..providers import ChatMessage, ChatResponse, ModelInfo, get_provider_registry


@dataclass(frozen=True)
class RoutingDecision:
    model: ModelInfo | None
    provider: str | None
    score: float
    reason: str
    candidates: tuple[dict[str, Any], ...] = ()


@dataclass
class CompletionTrace:
    decision: RoutingDecision | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)


class IntelligentRouter:
    """Select and execute against the best discovered model for a task."""

    PROVIDER_PREFERENCE = ("openrouter", "omniroute", "9router", "ollama")
    SYNONYMS = {
        "coding": {"coding", "code", "programming"},
        "reasoning": {"reasoning", "analysis", "thinking"},
        "research": {"research", "web", "search"},
        "file_search": {"file_search", "files", "documents"},
        "data_analysis": {"data_analysis", "data", "code_interpreter"},
        "terminal": {"terminal", "shell", "code_execution"},
        "browser": {"browser", "web"},
        "computer_use": {"computer_use", "computer"},
        "mcp": {"mcp", "tools", "function_calling"},
        "patch": {"patch", "apply_patch", "editing"},
        "structured_output": {"structured_output", "json", "function_calling"},
        "streaming": {"streaming"},
        "async_tools": {"async_tools", "parallel_tools"},
        "steering": {"steering"},
        "checkpoints": {"checkpoints", "state"},
        "long_running": {"long_running", "durable_execution"},
    }

    def __init__(self, capability_engine: CapabilityEngine | None = None):
        self.capabilities = capability_engine or CapabilityEngine()
        self._latency: dict[tuple[str, str], float] = {}
        self._failures: dict[tuple[str, str], int] = {}
        self.last_trace = CompletionTrace()

    def record_outcome(self, provider: str, model: str, *, latency_ms: float | None = None,
                       success: bool = True) -> None:
        key = (provider, model)
        if latency_ms is not None:
            old = self._latency.get(key)
            self._latency[key] = latency_ms if old is None else old * .7 + latency_ms * .3
        self._failures[key] = 0 if success else self._failures.get(key, 0) + 1

    def _capability_coverage(self, model: ModelInfo, request: TaskCapabilityRequest) -> float:
        caps = {c.casefold().replace("-", "_") for c in model.capabilities}
        if not request.required:
            return 1.0
        matched = 0
        for required in request.required:
            key = getattr(required, "value", str(required)).casefold().replace("-", "_")
            if caps.intersection(self.SYNONYMS.get(key, {key})):
                matched += 1
        return matched / len(request.required)

    def _score(self, model: ModelInfo, task_type: str, request: TaskCapabilityRequest) -> float:
        coverage = self._capability_coverage(model, request)
        if coverage < 1.0 or not model.available:
            return float("-inf")
        score = 55.0 + coverage * 20.0
        task = task_type.casefold().replace("-", "_")
        caps = {c.casefold().replace("-", "_") for c in model.capabilities}
        if task in {"coding", "debugging", "refactoring"} and {"code", "coding", "programming"} & caps:
            score += 12
        if task in {"reasoning", "architecture", "security"} and {"reasoning", "analysis", "thinking"} & caps:
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
        if model.cost_per_token == 0:
            score += 5.0
        else:
            score -= min(10.0, model.cost_per_token * 1_000_000)
        return score

    async def _discover(self) -> list[tuple[Any, ModelInfo]]:
        registry = get_provider_registry()
        registry.initialize(None)
        rank = {name: len(self.PROVIDER_PREFERENCE) - i for i, name in enumerate(self.PROVIDER_PREFERENCE)}
        providers = sorted(registry.get_enabled(), key=lambda p: rank.get(p.name, 0), reverse=True)
        discovered: list[tuple[Any, ModelInfo]] = []
        for provider in providers:
            try:
                models = await provider.discover_models()
            except Exception:
                continue
            for model in models:
                discovered.append((provider, model))
        return discovered

    async def select(self, task_type: str, *, complexity: int = 3, risk: int = 1,
                     context_tokens: int = 0, privacy: bool = False) -> RoutingDecision:
        request = self.capabilities.infer(task_type, complexity=complexity, risk=risk)
        request.context_tokens = context_tokens
        diagnostics: list[dict[str, Any]] = []
        candidates: list[tuple[float, ModelInfo]] = []
        registry = get_provider_registry()
        discovered = await self._discover()
        for provider, model in discovered:
            if privacy and provider.name != "ollama":
                continue
            if not provider.circuit_breaker.allow_request():
                continue
            score = self._score(model, task_type, request)
            diagnostics.append({"provider": provider.name, "model": model.model_id, "score": score})
            if score != float("-inf"):
                candidates.append((score, model))
        candidates.sort(key=lambda x: x[0], reverse=True)
        if not candidates:
            return RoutingDecision(None, None, float("-inf"),
                                   f"no discovered model satisfies task '{task_type}'", tuple(diagnostics))
        score, model = candidates[0]
        return RoutingDecision(
            model, model.provider, score,
            f"selected for {task_type} using capabilities, context, failures, latency and cost",
            tuple(diagnostics),
        )

    async def complete(self, messages: list[dict[str, Any]], *, task_type: str = "coding",
                       complexity: int = 5, risk: int = 1,
                       tools: list[dict[str, Any]] | None = None,
                       **kwargs: Any) -> ChatResponse:
        """Complete a turn and automatically fail over across healthy candidates."""
        request = self.capabilities.infer(task_type, complexity=complexity, risk=risk)
        registry = get_provider_registry()
        registry.initialize(None)
        discovered = await self._discover()
        candidates: list[tuple[float, Any, ModelInfo]] = []
        diagnostics: list[dict[str, Any]] = []
        for provider, model in discovered:
            if not model.available or not provider.circuit_breaker.allow_request():
                continue
            score = self._score(model, task_type, request)
            diagnostics.append({"provider": provider.name, "model": model.model_id, "score": score})
            if score != float("-inf"):
                candidates.append((score, provider, model))
        candidates.sort(key=lambda item: item[0], reverse=True)
        trace = CompletionTrace()
        if not candidates:
            raise RuntimeError(f"no model can satisfy task '{task_type}'")

        chat = [ChatMessage(
            role=str(m.get("role", "user")),
            content=str(m.get("content", "")),
            tool_calls=m.get("tool_calls"),
            tool_call_id=m.get("tool_call_id"),
        ) for m in messages]
        errors: list[str] = []
        for score, provider, model in candidates[:8]:
            started = time.monotonic()
            try:
                response = await provider.safe_chat(
                    chat,
                    model.model_id,
                    tools=tools,
                    temperature=kwargs.get("temperature"),
                    max_tokens=kwargs.get("max_tokens"),
                    reasoning=kwargs.get("reasoning") or request.reasoning.value,
                    stream=False,
                )
                latency = (time.monotonic() - started) * 1000
                self.record_outcome(provider.name, model.model_id, latency_ms=latency, success=True)
                trace.decision = RoutingDecision(model, provider.name, score,
                                                  f"selected for {task_type}", tuple(diagnostics))
                trace.attempts.append({"provider": provider.name, "model": model.model_id,
                                       "status": "success", "latency_ms": int(latency)})
                self.last_trace = trace
                return response
            except Exception as exc:
                latency = (time.monotonic() - started) * 1000
                self.record_outcome(provider.name, model.model_id, latency_ms=latency, success=False)
                error = str(exc)
                errors.append(f"{provider.name}/{model.model_id}: {error}")
                trace.attempts.append({"provider": provider.name, "model": model.model_id,
                                       "status": "failed", "error": error, "latency_ms": int(latency)})
        self.last_trace = trace
        raise RuntimeError("all model candidates failed: " + " | ".join(errors))
