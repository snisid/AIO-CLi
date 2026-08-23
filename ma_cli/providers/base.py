"""
Provider Interface for MA-CLI.

This module defines the provider abstraction for model providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..core.models import HealthStatus


@dataclass
class ModelInfo:
    """Information about a model."""

    model_id: str
    name: str
    provider: str = ""  # Will be set by provider discovery
    capabilities: list[str] = None
    max_context_tokens: int = 0
    cost_per_token: float = 0.0
    available: bool = True

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []

    def has_capabilities(self, required: list[str]) -> bool:
        """Check if model has all required capabilities."""
        if not required:
            return True
        return all(cap in self.capabilities for cap in required)


@dataclass
class ChatMessage:
    """A message in a chat conversation."""

    role: str  # 'system', 'user', 'assistant'
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


@dataclass
class ChatResponse:
    """Response from a chat completion."""

    content: str
    model: str
    usage: dict[str, int] = None
    tool_calls: list[dict[str, Any]] = None
    finish_reason: str = "stop"
    latency_ms: float = 0.0

    def __post_init__(self):
        if self.usage is None:
            self.usage = {}
        if self.tool_calls is None:
            self.tool_calls = []


class Provider(ABC):
    """
    Universal Provider Interface.

    All model providers (Ollama, OmniRoute, Anthropic, etc.) must implement
    this interface to be used by MA-CLI.

    Uses circuit breaker pattern for resilience.
    """

    def __init__(self):
        from .circuit_breaker import CircuitBreaker, CircuitConfig

        self._circuit_breaker = CircuitBreaker(
            name=f"provider_{self.name}",
            config=CircuitConfig(failure_threshold=5, success_threshold=3, timeout_seconds=60),
        )

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider identifier."""

    @property
    @abstractmethod
    def type(self) -> str:
        """Provider type (e.g., 'openai-compatible', 'anthropic')."""

    @property
    @abstractmethod
    def base_url(self) -> str:
        """API base URL."""

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Whether provider is enabled."""

    @property
    def circuit_breaker(self):
        """Get the circuit breaker for this provider."""
        return self._circuit_breaker

    @abstractmethod
    async def discover_models(self) -> list[ModelInfo]:
        """
        Discover available models from this provider.

        Returns:
            List of available models
        """

    @abstractmethod
    async def chat(self, messages: list[ChatMessage], model: str, **kwargs: Any) -> ChatResponse:
        """
        Send chat completion request.

        Args:
            messages: List of chat messages
            model: Model ID to use
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            ChatResponse with model output
        """

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """
        Check provider health and connectivity.

        Returns:
            Current health status
        """

    async def safe_chat(
        self, messages: list[ChatMessage], model: str, **kwargs: Any
    ) -> ChatResponse:
        """
        Send chat request through circuit breaker.

        This method wraps the chat call with circuit breaker protection.
        Raises CircuitOpenError if the circuit is open.
        """
        return await self._circuit_breaker.call_async(self.chat, messages, model, **kwargs)

    def get_info(self) -> dict[str, Any]:
        """Get provider information including circuit status."""
        return {
            "name": self.name,
            "type": self.type,
            "base_url": self.base_url,
            "enabled": self.enabled,
            "circuit_state": self._circuit_breaker.state.value,
            "circuit_stats": self._circuit_breaker.stats.failure_rate,
        }


@dataclass
class ProviderConfig:
    """Configuration for a provider."""

    name: str
    type: str
    enabled: bool = True
    base_url: str = ""
    api_key: str | None = None
    timeout: int = 60
    retry_count: int = 3
    headers: dict[str, str] = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
