"""Provider interfaces and shared resilience primitives for AIO-CLi."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..core.models import HealthStatus


@dataclass
class ModelInfo:
    """Information about a model advertised by a provider."""
    model_id: str
    name: str
    provider: str = ""
    capabilities: list[str] = field(default_factory=list)
    max_context_tokens: int = 0
    cost_per_token: float = 0.0
    available: bool = True

    def has_capabilities(self, required: list[str]) -> bool:
        return not required or all(cap in self.capabilities for cap in required)


@dataclass
class ChatMessage:
    """A chat message, including optional tool-call metadata."""
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


@dataclass
class ChatResponse:
    """Normalized provider chat response."""
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


class Provider(ABC):
    """Universal asynchronous provider contract.

    Older provider subclasses may omit ``super().__init__``; the circuit
    breaker is therefore initialized lazily and remains available uniformly.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider identifier."""

    @property
    @abstractmethod
    def type(self) -> str:
        """Provider protocol/type."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Provider API base URL."""

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Whether the provider is enabled."""

    @property
    def circuit_breaker(self):
        """Return a lazily-created per-provider circuit breaker."""
        breaker = getattr(self, "_circuit_breaker", None)
        if breaker is None:
            from .circuit_breaker import CircuitBreaker, CircuitConfig

            breaker = CircuitBreaker(
                name=f"provider_{self.name}",
                config=CircuitConfig(
                    failure_threshold=5,
                    success_threshold=3,
                    timeout_seconds=60,
                    half_open_max_calls=3,
                ),
            )
            self._circuit_breaker = breaker
        return breaker

    @abstractmethod
    async def discover_models(self) -> list[ModelInfo]:
        """Discover currently available models."""

    @abstractmethod
    async def chat(self, messages: list[ChatMessage], model: str, **kwargs: Any) -> ChatResponse:
        """Execute one model completion."""

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Return provider health."""

    async def safe_chat(self, messages: list[ChatMessage], model: str, **kwargs: Any) -> ChatResponse:
        """Execute chat through the provider circuit breaker."""
        return await self.circuit_breaker.call_async(self.chat, messages, model, **kwargs)

    def get_info(self) -> dict[str, Any]:
        """Return non-secret provider diagnostics."""
        return {
            "name": self.name,
            "type": self.type,
            "base_url": self.base_url,
            "enabled": self.enabled,
            "circuit_state": self.circuit_breaker.state.value,
            "circuit_stats": self.circuit_breaker.stats.failure_rate,
        }


@dataclass
class ProviderConfig:
    """Runtime configuration for a provider."""
    name: str
    type: str
    enabled: bool = True
    base_url: str = ""
    api_key: str | None = None
    timeout: int = 60
    retry_count: int = 3
    headers: dict[str, str] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)
