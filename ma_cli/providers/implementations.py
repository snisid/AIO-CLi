"""
Provider implementations for MA-CLI.

This module contains concrete provider implementations:
- OllamaProvider
- OmniRouteProvider
- NineRouterProvider
- AnthropicProvider
- OpenAIProvider
- GenericOpenAICompatibleProvider
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from ..core.models import HealthStatus
from .base import ChatMessage, ChatResponse, ModelInfo, Provider, ProviderConfig


@dataclass
class DiscoveredModel(ModelInfo):
    """Model info extended with discovery metadata."""
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    last_checked: datetime | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Ollama Provider
# ============================================================================

class OllamaProvider(Provider):
    """
    Ollama provider for local model serving.
    
    Supports OpenAI-compatible endpoint at /v1/chat/completions
    and native endpoint at /api/generate
    """
    
    def __init__(self, config: ProviderConfig):
        self._config = config
        self._base_url = config.base_url or "http://localhost:11434"
        self._models_cache: list[DiscoveredModel] = []
        self._last_discovery: datetime | None = None
    
    @property
    def name(self) -> str:
        return "ollama"
    
    @property
    def type(self) -> str:
        return "openai-compatible"
    
    @property
    def base_url(self) -> str:
        return self._base_url
    
    @property
    def enabled(self) -> bool:
        return self._config.enabled
    
    async def discover_models(self) -> list[ModelInfo]:
        """Discover models from Ollama."""
        if not self.enabled:
            return []
        
        models = []
        
        # Try native Ollama API first
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    for model_data in data.get("models", []):
                        model = DiscoveredModel(
                            model_id=model_data.get("name", ""),
                            name=model_data.get("name", ""),
                            provider=self.name,
                            capabilities=self._infer_capabilities(model_data),
                            max_context_tokens=model_data.get("details", {}).get("context_length", 4096),
                            available=True,
                            raw_data=model_data
                        )
                        models.append(model)
        except Exception:
            pass
        
        # Fallback to OpenAI-compatible endpoint
        if not models:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{self._base_url}/v1/models")
                    if response.status_code == 200:
                        data = response.json()
                        for model_data in data.get("data", []):
                            model = DiscoveredModel(
                                model_id=model_data.get("id", ""),
                                name=model_data.get("id", ""),
                                provider=self.name,
                                available=True,
                                raw_data=model_data
                            )
                            models.append(model)
            except Exception:
                pass
        
        self._models_cache = models
        self._last_discovery = datetime.utcnow()
        return models
    
    def _infer_capabilities(self, model_data: dict[str, Any]) -> list[str]:
        """Infer capabilities from model metadata."""
        capabilities = []
        details = model_data.get("details", {})
        family = details.get("family", "").lower()
        
        if "vision" in family or "llava" in family.lower():
            capabilities.append("vision")
        
        # All modern models support chat
        capabilities.append("chat")
        
        # Check parameter count for reasoning capability inference
        param_count = details.get("parameter_size", "")
        if param_count:
            try:
                params = float(param_count.replace("B", "").replace("M", ""))
                if "B" in param_count and float(params) >= 7:
                    capabilities.append("reasoning")
            except ValueError:
                pass
        
        return capabilities
    
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        **kwargs: Any
    ) -> ChatResponse:
        """Send chat completion to Ollama."""
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=float(self._config.timeout)) as client:
            # Use OpenAI-compatible endpoint
            payload = {
                "model": model,
                "messages": [
                    {"role": m.role, "content": m.content}
                    for m in messages
                ],
                "stream": False
            }
            
            # Add optional parameters
            if "temperature" in kwargs:
                payload["temperature"] = kwargs["temperature"]
            if "max_tokens" in kwargs:
                payload["max_tokens"] = kwargs["max_tokens"]
            if "top_p" in kwargs:
                payload["top_p"] = kwargs["top_p"]
            
            response = await client.post(
                f"{self._base_url}/v1/chat/completions",
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            
            latency_ms = (time.time() - start_time) * 1000
            
            return ChatResponse(
                content=message.get("content", ""),
                model=data.get("model", model),
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason", "stop"),
                latency_ms=latency_ms
            )
    
    async def health_check(self) -> HealthStatus:
        """Check Ollama health."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                if response.status_code == 200:
                    return HealthStatus.HEALTHY
                return HealthStatus.DEGRADED
        except httpx.ConnectError:
            return HealthStatus.UNHEALTHY
        except Exception:
            return HealthStatus.UNKNOWN
    
    def is_installed(self) -> bool:
        """Check if Ollama is installed locally."""
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def get_version(self) -> str | None:
        """Get Ollama version."""
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None


# ============================================================================
# OmniRoute Provider
# ============================================================================

class OmniRouteProvider(Provider):
    """
    OmniRoute provider for model routing.
    
    OmniRoute acts as a gateway that routes requests to optimal models
    based on cost, latency, and capability requirements.
    
    Repository: https://github.com/diegosouzapw/OmniRoute.git
    """
    
    DEFAULT_BASE_URL = "http://localhost:20128/v1"
    
    def __init__(self, config: ProviderConfig):
        self._config = config
        self._base_url = config.base_url or self.DEFAULT_BASE_URL
        self._models_cache: list[DiscoveredModel] = []
        self._last_discovery: datetime | None = None
        self._routing_info: dict[str, Any] = {}
    
    @property
    def name(self) -> str:
        return "omniroute"
    
    @property
    def type(self) -> str:
        return "openai-compatible"
    
    @property
    def base_url(self) -> str:
        return self._base_url
    
    @property
    def enabled(self) -> bool:
        return self._config.enabled
    
    async def discover_models(self) -> list[ModelInfo]:
        """Discover available models from OmniRoute."""
        if not self.enabled:
            return []
        
        models = []
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._base_url}/models")
                if response.status_code == 200:
                    data = response.json()
                    
                    # Handle both /models and /v1/models response formats
                    model_list = data.get("models", data.get("data", []))
                    
                    for model_data in model_list:
                        # Extract model ID from various formats
                        model_id = model_data.get("id", model_data.get("name", ""))
                        
                        model = DiscoveredModel(
                            model_id=model_id,
                            name=model_data.get("name", model_id),
                            provider=self.name,
                            capabilities=model_data.get("capabilities", ["chat"]),
                            max_context_tokens=model_data.get("context_length", 4096),
                            cost_per_token=model_data.get("cost_per_token", 0.0),
                            available=model_data.get("available", True),
                            raw_data=model_data
                        )
                        models.append(model)
                    
                    # Store routing information if available
                    if "routing" in data:
                        self._routing_info = data["routing"]
                        
        except httpx.ConnectError:
            pass
        except Exception:
            pass
        
        self._models_cache = models
        self._last_discovery = datetime.utcnow()
        return models
    
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        **kwargs: Any
    ) -> ChatResponse:
        """Send chat completion through OmniRoute."""
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=float(self._config.timeout)) as client:
            payload = {
                "model": model,
                "messages": [
                    {"role": m.role, "content": m.content}
                    for m in messages
                ],
                "stream": False
            }
            
            # Add routing hints if provided
            if "routing_strategy" in kwargs:
                payload["routing_strategy"] = kwargs.pop("routing_strategy")
            if "max_cost" in kwargs:
                payload["max_cost"] = kwargs.pop("max_cost")
            
            # Add standard parameters
            if "temperature" in kwargs:
                payload["temperature"] = kwargs["temperature"]
            if "max_tokens" in kwargs:
                payload["max_tokens"] = kwargs["max_tokens"]
            
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            
            data = response.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            
            latency_ms = (time.time() - start_time) * 1000
            
            return ChatResponse(
                content=message.get("content", ""),
                model=data.get("model", model),
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason", "stop"),
                latency_ms=latency_ms
            )
    
    async def health_check(self) -> HealthStatus:
        """Check OmniRoute health."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/models")
                if response.status_code == 200:
                    return HealthStatus.HEALTHY
                return HealthStatus.DEGRADED
        except httpx.ConnectError:
            return HealthStatus.UNHEALTHY
        except Exception:
            return HealthStatus.UNKNOWN
    
    def is_installed(self) -> bool:
        """Check if OmniRoute is installed/running."""
        try:
            result = subprocess.run(
                ["omniroute", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            # Also check if service is responding
            try:
                import httpx
                response = httpx.get(f"{self._base_url}/models", timeout=5)
                return response.status_code == 200
            except Exception:
                return False
    
    def get_version(self) -> str | None:
        """Get OmniRoute version."""
        try:
            result = subprocess.run(
                ["omniroute", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None
    
    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        headers.update(self._config.headers)
        return headers


# ============================================================================
# 9router Provider
# ============================================================================

class NineRouterProvider(Provider):
    """
    9router provider for cost-optimized model routing.
    
    9router provides intelligent routing to minimize costs while
    maintaining quality requirements.
    """
    
    DEFAULT_BASE_URL = "http://localhost:9000/v1"
    
    def __init__(self, config: ProviderConfig):
        self._config = config
        self._base_url = config.base_url or self.DEFAULT_BASE_URL
        self._models_cache: list[DiscoveredModel] = []
        self._last_discovery: datetime | None = None
    
    @property
    def name(self) -> str:
        return "9router"
    
    @property
    def type(self) -> str:
        return "openai-compatible"
    
    @property
    def base_url(self) -> str:
        return self._base_url
    
    @property
    def enabled(self) -> bool:
        return self._config.enabled
    
    async def discover_models(self) -> list[ModelInfo]:
        """Discover available models from 9router."""
        if not self.enabled:
            return []
        
        models = []
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._base_url}/models")
                if response.status_code == 200:
                    data = response.json()
                    model_list = data.get("models", data.get("data", []))
                    
                    for model_data in model_list:
                        model_id = model_data.get("id", model_data.get("name", ""))
                        
                        model = DiscoveredModel(
                            model_id=model_id,
                            name=model_data.get("name", model_id),
                            provider=self.name,
                            capabilities=model_data.get("capabilities", ["chat"]),
                            cost_per_token=model_data.get("cost_per_token", 0.0),
                            available=model_data.get("available", True),
                            raw_data=model_data
                        )
                        models.append(model)
                        
        except httpx.ConnectError:
            pass
        except Exception:
            pass
        
        self._models_cache = models
        self._last_discovery = datetime.utcnow()
        return models
    
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        **kwargs: Any
    ) -> ChatResponse:
        """Send chat completion through 9router."""
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=float(self._config.timeout)) as client:
            payload = {
                "model": model,
                "messages": [
                    {"role": m.role, "content": m.content}
                    for m in messages
                ],
                "stream": False
            }
            
            # 9router specific options
            if "cost_optimization" in kwargs:
                payload["cost_optimization"] = kwargs.pop("cost_optimization")
            if "quality_tier" in kwargs:
                payload["quality_tier"] = kwargs.pop("quality_tier")
            
            # Standard parameters
            if "temperature" in kwargs:
                payload["temperature"] = kwargs["temperature"]
            if "max_tokens" in kwargs:
                payload["max_tokens"] = kwargs["max_tokens"]
            
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            
            data = response.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            
            latency_ms = (time.time() - start_time) * 1000
            
            return ChatResponse(
                content=message.get("content", ""),
                model=data.get("model", model),
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason", "stop"),
                latency_ms=latency_ms
            )
    
    async def health_check(self) -> HealthStatus:
        """Check 9router health."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/models")
                if response.status_code == 200:
                    return HealthStatus.HEALTHY
                return HealthStatus.DEGRADED
        except httpx.ConnectError:
            return HealthStatus.UNHEALTHY
        except Exception:
            return HealthStatus.UNKNOWN
    
    def _get_headers(self) -> dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        headers.update(self._config.headers)
        return headers


# ============================================================================
# Anthropic Provider
# ============================================================================

class AnthropicProvider(Provider):
    """
    Anthropic provider for Claude models.
    
    Uses the official Anthropic API.
    """
    
    BASE_URL = "https://api.anthropic.com"
    
    def __init__(self, config: ProviderConfig):
        self._config = config
        self._api_key = config.api_key
        self._base_url = config.base_url or self.BASE_URL
        self._models_cache: list[DiscoveredModel] = []
    
    @property
    def name(self) -> str:
        return "anthropic"
    
    @property
    def type(self) -> str:
        return "anthropic"
    
    @property
    def base_url(self) -> str:
        return self._base_url
    
    @property
    def enabled(self) -> bool:
        return self._config.enabled and self._api_key is not None
    
    async def discover_models(self) -> list[ModelInfo]:
        """Discover available Claude models."""
        if not self.enabled:
            return []
        
        # Anthropic doesn't have a models endpoint, use known models
        known_models = [
            DiscoveredModel(
                model_id="claude-sonnet-4-20250514",
                name="Claude Sonnet 4",
                provider=self.name,
                capabilities=["chat", "reasoning", "code"],
                max_context_tokens=200000,
                available=True
            ),
            DiscoveredModel(
                model_id="claude-opus-4-20250514",
                name="Claude Opus 4",
                provider=self.name,
                capabilities=["chat", "reasoning", "code", "vision"],
                max_context_tokens=200000,
                available=True
            ),
            DiscoveredModel(
                model_id="claude-3-5-sonnet-20241022",
                name="Claude 3.5 Sonnet",
                provider=self.name,
                capabilities=["chat", "reasoning", "code", "vision"],
                max_context_tokens=200000,
                available=True
            ),
            DiscoveredModel(
                model_id="claude-3-5-haiku-20241022",
                name="Claude 3.5 Haiku",
                provider=self.name,
                capabilities=["chat", "reasoning"],
                max_context_tokens=200000,
                available=True
            ),
        ]
        
        self._models_cache = known_models
        return known_models
    
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        **kwargs: Any
    ) -> ChatResponse:
        """Send chat completion to Anthropic."""
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=float(self._config.timeout)) as client:
            # Convert messages to Anthropic format
            system_message = ""
            anthropic_messages = []
            
            for msg in messages:
                if msg.role == "system":
                    system_message = msg.content
                else:
                    anthropic_messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
            
            payload = {
                "model": model,
                "messages": anthropic_messages,
                "max_tokens": kwargs.get("max_tokens", 4096)
            }
            
            if system_message:
                payload["system"] = system_message
            
            if "temperature" in kwargs:
                payload["temperature"] = kwargs["temperature"]
            
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01"
            }
            
            response = await client.post(
                f"{self._base_url}/v1/messages",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            content = data.get("content", [{}])[0].get("text", "")
            
            latency_ms = (time.time() - start_time) * 1000
            
            return ChatResponse(
                content=content,
                model=data.get("model", model),
                usage={
                    "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                    "completion_tokens": data.get("usage", {}).get("output_tokens", 0)
                },
                finish_reason=data.get("stop_reason", "end_turn"),
                latency_ms=latency_ms
            )
    
    async def health_check(self) -> HealthStatus:
        """Check Anthropic API health."""
        if not self._api_key:
            return HealthStatus.UNHEALTHY
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Test with a minimal request
                response = await client.post(
                    f"{self._base_url}/v1/messages",
                    json={
                        "model": "claude-3-5-haiku-20241022",
                        "messages": [{"role": "user", "content": "Hi"}],
                        "max_tokens": 1
                    },
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": "2023-06-01"
                    }
                )
                if response.status_code in [200, 400]:  # 400 is OK for invalid request
                    return HealthStatus.HEALTHY
                return HealthStatus.DEGRADED
        except Exception:
            return HealthStatus.UNKNOWN


# ============================================================================
# OpenAI Provider
# ============================================================================

class OpenAIProvider(Provider):
    """
    OpenAI provider for GPT models.
    
    Uses the official OpenAI API.
    """
    
    BASE_URL = "https://api.openai.com/v1"
    
    def __init__(self, config: ProviderConfig):
        self._config = config
        self._api_key = config.api_key
        self._base_url = config.base_url or self.BASE_URL
        self._models_cache: list[DiscoveredModel] = []
    
    @property
    def name(self) -> str:
        return "openai"
    
    @property
    def type(self) -> str:
        return "openai-compatible"
    
    @property
    def base_url(self) -> str:
        return self._base_url
    
    @property
    def enabled(self) -> bool:
        return self._config.enabled and self._api_key is not None
    
    async def discover_models(self) -> list[ModelInfo]:
        """Discover available OpenAI models."""
        if not self.enabled:
            return []
        
        models = []
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Authorization": f"Bearer {self._api_key}"}
                response = await client.get(
                    f"{self._base_url}/models",
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    for model_data in data.get("data", []):
                        model_id = model_data.get("id", "")
                        
                        # Filter to chat models
                        if "gpt" in model_id.lower() or "o1" in model_id.lower():
                            model = DiscoveredModel(
                                model_id=model_id,
                                name=model_id,
                                provider=self.name,
                                capabilities=self._infer_capabilities(model_id),
                                available=True,
                                raw_data=model_data
                            )
                            models.append(model)
        except Exception:
            pass
        
        # Fallback to known models if API call fails
        if not models and self._api_key:
            known_models = [
                DiscoveredModel(
                    model_id="gpt-4o",
                    name="GPT-4o",
                    provider=self.name,
                    capabilities=["chat", "reasoning", "code", "vision"],
                    available=True
                ),
                DiscoveredModel(
                    model_id="gpt-4o-mini",
                    name="GPT-4o Mini",
                    provider=self.name,
                    capabilities=["chat", "reasoning", "code"],
                    available=True
                ),
                DiscoveredModel(
                    model_id="o1-preview",
                    name="o1 Preview",
                    provider=self.name,
                    capabilities=["chat", "reasoning", "code"],
                    available=True
                ),
            ]
            models = known_models
        
        self._models_cache = models
        return models
    
    def _infer_capabilities(self, model_id: str) -> list[str]:
        """Infer capabilities from model ID."""
        capabilities = ["chat"]
        
        if "vision" in model_id.lower() or "gpt-4o" in model_id.lower():
            capabilities.append("vision")
        
        if "o1" in model_id.lower() or "opus" in model_id.lower():
            capabilities.append("reasoning")
        
        capabilities.append("code")
        
        return capabilities
    
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        **kwargs: Any
    ) -> ChatResponse:
        """Send chat completion to OpenAI."""
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=float(self._config.timeout)) as client:
            payload = {
                "model": model,
                "messages": [
                    {"role": m.role, "content": m.content}
                    for m in messages
                ],
                "stream": False
            }
            
            if "temperature" in kwargs:
                payload["temperature"] = kwargs["temperature"]
            if "max_tokens" in kwargs:
                payload["max_tokens"] = kwargs["max_tokens"]
            if "top_p" in kwargs:
                payload["top_p"] = kwargs["top_p"]
            
            headers = {"Authorization": f"Bearer {self._api_key}"}
            
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            
            latency_ms = (time.time() - start_time) * 1000
            
            return ChatResponse(
                content=message.get("content", ""),
                model=data.get("model", model),
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason", "stop"),
                latency_ms=latency_ms
            )
    
    async def health_check(self) -> HealthStatus:
        """Check OpenAI API health."""
        if not self._api_key:
            return HealthStatus.UNHEALTHY
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"}
                )
                if response.status_code == 200:
                    return HealthStatus.HEALTHY
                return HealthStatus.DEGRADED
        except Exception:
            return HealthStatus.UNKNOWN


# ============================================================================
# Generic OpenAI-Compatible Provider
# ============================================================================

class GenericOpenAICompatibleProvider(Provider):
    """
    Generic provider for any OpenAI-compatible API.
    
    Useful for custom endpoints, local deployments, etc.
    """
    
    def __init__(self, config: ProviderConfig):
        self._config = config
        self._base_url = config.base_url
        self._models_cache: list[DiscoveredModel] = []
    
    @property
    def name(self) -> str:
        return self._config.name
    
    @property
    def type(self) -> str:
        return self._config.type
    
    @property
    def base_url(self) -> str:
        return self._base_url
    
    @property
    def enabled(self) -> bool:
        return self._config.enabled
    
    async def discover_models(self) -> list[ModelInfo]:
        """Discover models from generic OpenAI-compatible endpoint."""
        if not self.enabled or not self._base_url:
            return []
        
        models = []
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self._base_url}/models")
                if response.status_code == 200:
                    data = response.json()
                    model_list = data.get("models", data.get("data", []))
                    
                    for model_data in model_list:
                        model_id = model_data.get("id", model_data.get("name", ""))
                        model = DiscoveredModel(
                            model_id=model_id,
                            name=model_data.get("name", model_id),
                            provider=self.name,
                            available=True,
                            raw_data=model_data
                        )
                        models.append(model)
        except Exception:
            pass
        
        self._models_cache = models
        return models
    
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        **kwargs: Any
    ) -> ChatResponse:
        """Send chat completion to generic endpoint."""
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=float(self._config.timeout)) as client:
            payload = {
                "model": model,
                "messages": [
                    {"role": m.role, "content": m.content}
                    for m in messages
                ],
                "stream": False
            }
            
            # Add optional parameters
            for key in ["temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty"]:
                if key in kwargs:
                    payload[key] = kwargs[key]
            
            headers = {"Content-Type": "application/json"}
            if self._config.api_key:
                headers["Authorization"] = f"Bearer {self._config.api_key}"
            headers.update(self._config.headers)
            
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            
            latency_ms = (time.time() - start_time) * 1000
            
            return ChatResponse(
                content=message.get("content", ""),
                model=data.get("model", model),
                usage=data.get("usage", {}),
                finish_reason=choice.get("finish_reason", "stop"),
                latency_ms=latency_ms
            )
    
    async def health_check(self) -> HealthStatus:
        """Check generic endpoint health."""
        if not self._base_url:
            return HealthStatus.UNHEALTHY
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/models")
                if response.status_code == 200:
                    return HealthStatus.HEALTHY
                return HealthStatus.DEGRADED
        except httpx.ConnectError:
            return HealthStatus.UNHEALTHY
        except Exception:
            return HealthStatus.UNKNOWN


# ============================================================================
# Provider Registry
# ============================================================================

class ProviderRegistry:
    """
    Registry for managing provider instances.
    
    Singleton pattern for global access.
    """
    
    _instance: ProviderRegistry | None = None
    
    def __new__(cls) -> ProviderRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers = {}
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self, config: Any) -> None:
        """Initialize providers from configuration."""
        if self._initialized:
            return
        
        from ..config.engine import ConfigurationEngine
        
        if config is None:
            config_engine = ConfigurationEngine()
            config = config_engine.load()
        
        # Create provider instances
        provider_classes = {
            "ollama": OllamaProvider,
            "omniroute": OmniRouteProvider,
            "9router": NineRouterProvider,
            "anthropic": AnthropicProvider,
            "openai": OpenAIProvider,
        }
        
        for name, provider_config in config.providers.items():
            if not provider_config.enabled:
                continue
            
            provider_class = provider_classes.get(name)
            
            # Fall back to generic provider
            if provider_class is None:
                provider_class = GenericOpenAICompatibleProvider
            
            try:
                provider = provider_class(provider_config)
                self._providers[name] = provider
            except Exception:
                pass
        
        self._initialized = True
    
    def get(self, name: str) -> Provider | None:
        """Get a provider by name."""
        return self._providers.get(name)
    
    def list_all(self) -> list[Provider]:
        """List all registered providers."""
        return list(self._providers.values())
    
    def get_enabled(self) -> list[Provider]:
        """List all enabled providers."""
        return [p for p in self._providers.values() if p.enabled]
    
    def register(self, name: str, provider: Provider) -> None:
        """Register a provider instance."""
        self._providers[name] = provider
    
    def unregister(self, name: str) -> None:
        """Unregister a provider."""
        self._providers.pop(name, None)


_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry."""
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
