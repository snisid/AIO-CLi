"""Native OpenRouter provider.

OpenRouter exposes an OpenAI-compatible API. AIO-CLi keeps this provider
explicit so routing, health and OpenRouter-specific controls remain observable.
"""
from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

import httpx

from ..core.models import HealthStatus
from .base import ChatMessage, ChatResponse, ModelInfo, Provider, ProviderConfig


class OpenRouterProvider(Provider):
    """Provider for the OpenRouter OpenAI-compatible API."""

    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, config: ProviderConfig):
        self._config = config
        self._base_url = (config.base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._api_key = config.api_key or os.getenv("OPENROUTER_API_KEY")
        self._models_cache: list[ModelInfo] = []
        self._last_discovery: datetime | None = None

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def type(self) -> str:
        return "openai-compatible"

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def enabled(self) -> bool:
        return self._config.enabled and bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        headers.update(self._config.headers)
        return headers

    @staticmethod
    def _capabilities(item: dict[str, Any]) -> list[str]:
        model_id = str(item.get("id") or "").casefold()
        name = str(item.get("name") or "").casefold()
        text = f"{model_id} {name}"
        capabilities = ["chat"]
        code_markers = ("code", "coder", "coding", "qwen", "deepseek", "glm", "devstral", "codestral")
        reasoning_markers = ("reason", "thinking", "think", "r1", "o1", "o3", "o4", "deepseek", "qwq")
        if any(marker in text for marker in code_markers):
            capabilities.append("code")
        if any(marker in text for marker in reasoning_markers):
            capabilities.append("reasoning")
        architecture = item.get("architecture") or {}
        modality = str(architecture.get("modality", ""))
        if "image" in modality.casefold():
            capabilities.append("vision")
        return capabilities

    async def discover_models(self) -> list[ModelInfo]:
        if not self.enabled:
            return []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._base_url}/models", headers=self._headers())
                response.raise_for_status()
                data = response.json()
            models: list[ModelInfo] = []
            for item in data.get("data", []):
                model_id = str(item.get("id", "")).strip()
                if not model_id:
                    continue
                pricing = item.get("pricing") or {}
                try:
                    cost = float(pricing.get("prompt", 0) or 0)
                except (TypeError, ValueError):
                    cost = 0.0
                models.append(ModelInfo(
                    model_id=model_id,
                    name=str(item.get("name") or model_id),
                    provider=self.name,
                    capabilities=self._capabilities(item),
                    max_context_tokens=int(item.get("context_length") or 0),
                    cost_per_token=cost,
                    available=True,
                    raw_data=item,
                ))
            self._models_cache = models
            self._last_discovery = datetime.utcnow()
            return models
        except (httpx.HTTPError, ValueError):
            return []

    async def chat(self, messages: list[ChatMessage], model: str, **kwargs: Any) -> ChatResponse:
        if not self.enabled:
            raise RuntimeError("OpenRouter is disabled or OPENROUTER_API_KEY is missing")
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                    **({"tool_calls": message.tool_calls} if message.tool_calls else {}),
                }
                for message in messages
            ],
            "stream": False,
        }
        for key in ("temperature", "top_p", "max_tokens", "max_completion_tokens",
                    "response_format", "tool_choice", "seed", "tools", "provider", "models"):
            if kwargs.get(key) is not None:
                payload[key] = kwargs[key]
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=float(self._config.timeout)) as client:
            response = await client.post(f"{self._base_url}/chat/completions", json=payload, headers=self._headers())
            response.raise_for_status()
            data = response.json()
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        usage = data.get("usage") or {}
        return ChatResponse(
            content=str(message.get("content") or ""),
            model=str(data.get("model") or model),
            usage={k: int(v) for k, v in usage.items() if isinstance(v, (int, float))},
            tool_calls=message.get("tool_calls") or [],
            finish_reason=str(choice.get("finish_reason") or "stop"),
            latency_ms=(time.monotonic() - started) * 1000,
            raw=data,
        )

    async def health_check(self) -> HealthStatus:
        if not self.enabled:
            return HealthStatus.UNHEALTHY
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/models", headers=self._headers())
            if response.status_code == 200:
                return HealthStatus.HEALTHY
            if response.status_code == 429:
                return HealthStatus.DEGRADED
            if response.status_code in (401, 403):
                return HealthStatus.UNHEALTHY
            return HealthStatus.DEGRADED
        except httpx.ConnectError:
            return HealthStatus.UNHEALTHY
        except httpx.HTTPError:
            return HealthStatus.UNKNOWN
