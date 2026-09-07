"""Adapt MA-CLI providers to the NativeAgent complete() contract."""
from __future__ import annotations

from typing import Any

from ..providers.base import ChatMessage, ChatResponse, Provider


class ProviderModel:
    """Thin adapter: NativeAgent calls complete(); providers expose chat()."""

    def __init__(self, provider: Provider, model_id: str):
        if not model_id or model_id == "auto":
            raise ValueError("model_id must be a concrete discovered or configured id")
        self.provider = provider
        self.model_id = model_id

    async def complete(self, messages: list[dict[str, Any] | ChatMessage], **kwargs: Any) -> ChatResponse:
        converted: list[ChatMessage] = []
        for message in messages:
            if isinstance(message, ChatMessage):
                converted.append(message)
            else:
                converted.append(ChatMessage(
                    role=str(message.get("role", "user")),
                    content=str(message.get("content", "")),
                    tool_calls=message.get("tool_calls"),
                ))
        extra = {key: value for key, value in kwargs.items() if key in {"temperature", "max_tokens", "top_p"}}
        return await self.provider.chat(converted, self.model_id, **extra)


def attach_default_model() -> ProviderModel | None:
    """Return a live provider model when a concrete model_id is configured.

    Never fabricates availability and never uses model_id='auto'.
    Missing or undiscovered providers stay unattached.
    """
    try:
        from ..config.engine import ConfigurationEngine
        from ..providers.implementations import get_provider_registry
        registry = get_provider_registry()
        registry.initialize(None)
        config = ConfigurationEngine().load()
        for name in ("ollama", "omniroute", "9router", "openai", "anthropic"):
            provider = registry.get(name)
            if provider is None or not provider.enabled:
                continue
            for alias in config.models.values():
                if alias.provider == name and alias.model_id and alias.model_id != "auto":
                    return ProviderModel(provider, model_id=alias.model_id)
            cache = getattr(provider, "_models_cache", []) or []
            for model in cache:
                model_id = getattr(model, "model_id", None)
                if model_id and model_id != "auto":
                    return ProviderModel(provider, model_id=model_id)
    except Exception:  # noqa: BLE001 - missing providers stay unattached
        return None
    return None
