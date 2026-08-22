"""
Model Router for MA-CLI.

The Model Router is responsible for:
- Mapping user-friendly model aliases to actual provider model IDs
- Discovering available models from providers
- Implementing intelligent fallback strategies
- Selecting optimal models based on task requirements
- Respecting capability, cost, privacy, and latency policies
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from enum import Enum

from ..core.models import HealthStatus
from ..providers import (
    Provider,
    ModelInfo,
    ProviderRegistry,
    get_provider_registry,
)
from ..config.engine import ConfigurationEngine, Config


class RoutingStrategy(Enum):
    """Strategy for model selection."""
    COST_OPTIMIZED = "cost_optimized"      # Lowest cost capable model
    PERFORMANCE = "performance"            # Best performance regardless of cost
    PRIVACY = "privacy"                    # Local/private models only
    BALANCED = "balanced"                  # Balance of cost and performance
    LATENCY = "latency"                    # Lowest latency


@dataclass
class ModelAlias:
    """Configuration for a model alias."""
    alias: str
    provider: str
    model_id: Optional[str] = None  # None means auto-discover
    fallback: list[str] = field(default_factory=list)
    capabilities_required: list[str] = field(default_factory=list)
    max_cost_per_token: float = 0.0
    privacy_required: bool = False
    status: str = "unknown"  # available, unavailable, unknown
    discovered_model_id: Optional[str] = None


@dataclass
class ModelSelectionResult:
    """Result of model selection."""
    success: bool
    selected_model: Optional[ModelInfo] = None
    alias_used: Optional[str] = None
    provider_used: Optional[str] = None
    fallback_chain: list[str] = field(default_factory=list)
    error: Optional[str] = None
    latency_ms: float = 0.0


class ModelRouter:
    """
    Routes model requests to appropriate providers.
    
    Handles:
    - Alias resolution
    - Model discovery
    - Fallback logic
    - Capability matching
    - Policy enforcement
    """
    
    _instance: Optional["ModelRouter"] = None
    
    def __new__(cls) -> "ModelRouter":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._aliases: dict[str, ModelAlias] = {}
            cls._instance._discovered_models: dict[str, list[ModelInfo]] = {}
            cls._instance._last_discovery: dict[str, datetime] = {}
            cls._instance._discovery_cache_ttl = 300  # 5 minutes
        return cls._instance
    
    def initialize(self, config: Optional[Config] = None) -> None:
        """Initialize router with configuration."""
        if self._initialized:
            return
        
        if config is None:
            config_engine = ConfigurationEngine()
            config = config_engine.load()
        
        # Load model aliases from config
        for alias_name, alias_config in config.models.items():
            self._aliases[alias_name] = ModelAlias(
                alias=alias_name,
                provider=alias_config.provider,
                model_id=alias_config.model_id,
                fallback=alias_config.fallback or [],
                capabilities_required=alias_config.capabilities_required or [],
                max_cost_per_token=alias_config.max_cost_per_token or 0.0,
                privacy_required=alias_config.privacy_required or False,
            )
        
        self._initialized = True
    
    async def discover_all_models(self, force: bool = False) -> None:
        """Discover models from all enabled providers."""
        registry = get_provider_registry()
        registry.initialize(None)
        
        providers = registry.get_enabled()
        
        for provider in providers:
            await self._discover_provider_models(provider, force)
    
    async def _discover_provider_models(
        self,
        provider: Provider,
        force: bool = False
    ) -> None:
        """Discover models from a specific provider."""
        now = datetime.utcnow()
        
        # Check cache
        if not force and provider.name in self._last_discovery:
            last_check = self._last_discovery[provider.name]
            if (now - last_check).total_seconds() < self._discovery_cache_ttl:
                return  # Use cached results
        
        try:
            models = await provider.discover_models()
            self._discovered_models[provider.name] = models
            self._last_discovery[provider.name] = now
        except Exception:
            self._discovered_models[provider.name] = []
    
    async def resolve_alias(
        self,
        alias: str,
        strategy: RoutingStrategy = RoutingStrategy.BALANCED,
        required_capabilities: Optional[list[str]] = None
    ) -> ModelSelectionResult:
        """
        Resolve a model alias to an actual model.
        
        Args:
            alias: User-friendly model alias (e.g., "claude-opus-5")
            strategy: Routing strategy to use
            required_capabilities: Capabilities the model must have
        
        Returns:
            ModelSelectionResult with selected model or error
        """
        start_time = datetime.utcnow()
        fallback_chain = []
        
        # Ensure discovery is done
        await self.discover_all_models()
        
        # Get alias configuration
        alias_config = self._aliases.get(alias)
        
        if alias_config is None:
            # Try to find a matching model directly
            return await self._find_model_by_id(
                alias,
                strategy,
                required_capabilities,
                fallback_chain
            )
        
        # Try primary provider
        result = await self._try_provider(
            alias_config.provider,
            alias_config.model_id or alias,
            alias_config.capabilities_required or required_capabilities,
            alias_config.max_cost_per_token,
            alias_config.privacy_required
        )
        
        if result.success:
            return self._build_success_result(
                result, alias, alias_config.provider, fallback_chain, start_time
            )
        
        fallback_chain.append(f"{alias_config.provider}:{alias_config.model_id or alias}")
        
        # Try fallbacks from alias config
        for fallback_alias in alias_config.fallback:
            fallback_config = self._aliases.get(fallback_alias)
            if fallback_config:
                result = await self._try_provider(
                    fallback_config.provider,
                    fallback_config.model_id or fallback_alias,
                    fallback_config.capabilities_required or required_capabilities,
                    fallback_config.max_cost_per_token,
                    fallback_config.privacy_required
                )
                
                if result.success:
                    return self._build_success_result(
                        result, alias, fallback_config.provider, fallback_chain, start_time
                    )
                
                fallback_chain.append(
                    f"{fallback_config.provider}:{fallback_config.model_id or fallback_alias}"
                )
        
        # Try intelligent fallback based on strategy
        result = await self._strategy_fallback(
            alias,
            strategy,
            required_capabilities,
            fallback_chain
        )
        
        if result.success:
            return self._build_success_result(
                result, alias, result.provider_used, fallback_chain, start_time
            )
        
        # All attempts failed
        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return ModelSelectionResult(
            success=False,
            alias_used=alias,
            fallback_chain=fallback_chain,
            error=result.error or f"No available model found for alias '{alias}'",
            latency_ms=elapsed_ms
        )
    
    async def _try_provider(
        self,
        provider_name: str,
        model_id: str,
        required_capabilities: Optional[list[str]],
        max_cost: float,
        privacy_required: bool
    ) -> ModelSelectionResult:
        """Try to get a model from a specific provider."""
        registry = get_provider_registry()
        provider = registry.get(provider_name)
        
        if provider is None:
            return ModelSelectionResult(
                success=False,
                error=f"Provider '{provider_name}' not found"
            )
        
        if not provider.enabled:
            return ModelSelectionResult(
                success=False,
                error=f"Provider '{provider_name}' is disabled"
            )
        
        # Check privacy requirement
        if privacy_required and provider_name not in ["ollama"]:
            return ModelSelectionResult(
                success=False,
                error=f"Provider '{provider_name}' does not meet privacy requirements"
            )
        
        # Get discovered models
        models = self._discovered_models.get(provider_name, [])
        
        # If we have a specific model ID, look for it
        if model_id:
            for model in models:
                if model.model_id == model_id or model.name == model_id:
                    # Check capabilities
                    if required_capabilities:
                        if not model.has_capabilities(required_capabilities):
                            continue
                    
                    # Check cost
                    if max_cost > 0 and model.cost_per_token > max_cost:
                        continue
                    
                    if not model.available:
                        continue
                    
                    return ModelSelectionResult(
                        success=True,
                        selected_model=model,
                        provider_used=provider_name
                    )
            
            # Model not found in discovered list
            # For some providers (like Anthropic), we may need to assume availability
            if provider_name == "anthropic" and "claude" in model_id.lower():
                # Create a synthetic model entry
                synthetic_model = ModelInfo(
                    model_id=model_id,
                    name=model_id,
                    provider=provider_name,
                    capabilities=["chat", "reasoning", "code"],
                    max_context_tokens=200000,
                    available=True
                )
                return ModelSelectionResult(
                    success=True,
                    selected_model=synthetic_model,
                    provider_used=provider_name
                )
        
        # If no specific model ID, find best match
        if models:
            for model in models:
                if not model.available:
                    continue
                
                if required_capabilities:
                    if not model.has_capabilities(required_capabilities):
                        continue
                
                if max_cost > 0 and model.cost_per_token > max_cost:
                    continue
                
                return ModelSelectionResult(
                    success=True,
                    selected_model=model,
                    provider_used=provider_name
                )
        
        return ModelSelectionResult(
            success=False,
            error=f"No suitable model found on provider '{provider_name}'"
        )
    
    async def _find_model_by_id(
        self,
        model_id: str,
        strategy: RoutingStrategy,
        required_capabilities: Optional[list[str]],
        fallback_chain: list[str]
    ) -> ModelSelectionResult:
        """Find a model by its ID across all providers."""
        # Search through discovered models
        for provider_name, models in self._discovered_models.items():
            for model in models:
                if model.model_id == model_id or model.name == model_id:
                    if not model.available:
                        continue
                    
                    if required_capabilities:
                        if not model.has_capabilities(required_capabilities):
                            continue
                    
                    return ModelSelectionResult(
                        success=True,
                        selected_model=model,
                        provider_used=provider_name
                    )
        
        return ModelSelectionResult(
            success=False,
            error=f"Model '{model_id}' not found on any provider"
        )
    
    async def _strategy_fallback(
        self,
        original_alias: str,
        strategy: RoutingStrategy,
        required_capabilities: Optional[list[str]],
        fallback_chain: list[str]
    ) -> ModelSelectionResult:
        """Apply strategy-based fallback logic."""
        registry = get_provider_registry()
        
        if strategy == RoutingStrategy.PRIVACY:
            # Only try local providers
            ollama = registry.get("ollama")
            if ollama and ollama.enabled:
                models = self._discovered_models.get("ollama", [])
                for model in models:
                    if model.available and (
                        not required_capabilities or
                        model.has_capabilities(required_capabilities)
                    ):
                        return ModelSelectionResult(
                            success=True,
                            selected_model=model,
                            provider_used="ollama"
                        )
        
        elif strategy == RoutingStrategy.COST_OPTIMIZED:
            # Try 9router first, then OmniRoute, then Ollama
            for provider_name in ["9router", "omniroute", "ollama"]:
                provider = registry.get(provider_name)
                if provider and provider.enabled:
                    models = self._discovered_models.get(provider_name, [])
                    # Sort by cost
                    sorted_models = sorted(
                        [m for m in models if m.available],
                        key=lambda m: m.cost_per_token
                    )
                    for model in sorted_models:
                        if not required_capabilities or model.has_capabilities(required_capabilities):
                            return ModelSelectionResult(
                                success=True,
                                selected_model=model,
                                provider_used=provider_name
                            )
        
        elif strategy == RoutingStrategy.PERFORMANCE:
            # Try Anthropic, OpenAI, then others
            for provider_name in ["anthropic", "openai", "omniroute"]:
                provider = registry.get(provider_name)
                if provider and provider.enabled:
                    models = self._discovered_models.get(provider_name, [])
                    for model in models:
                        if model.available and (
                            not required_capabilities or
                            model.has_capabilities(required_capabilities)
                        ):
                            return ModelSelectionResult(
                                success=True,
                                selected_model=model,
                                provider_used=provider_name
                            )
        
        else:  # BALANCED or LATENCY
            # Try OmniRoute first (balanced), then Ollama (low latency)
            for provider_name in ["omniroute", "ollama", "9router"]:
                provider = registry.get(provider_name)
                if provider and provider.enabled:
                    models = self._discovered_models.get(provider_name, [])
                    for model in models:
                        if model.available and (
                            not required_capabilities or
                            model.has_capabilities(required_capabilities)
                        ):
                            return ModelSelectionResult(
                                success=True,
                                selected_model=model,
                                provider_used=provider_name
                            )
        
        return ModelSelectionResult(
            success=False,
            error=f"No model available with strategy {strategy.value}"
        )
    
    def _build_success_result(
        self,
        result: ModelSelectionResult,
        alias: str,
        provider: str,
        fallback_chain: list[str],
        start_time: datetime
    ) -> ModelSelectionResult:
        """Build a successful result with metadata."""
        elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return ModelSelectionResult(
            success=True,
            selected_model=result.selected_model,
            alias_used=alias,
            provider_used=provider,
            fallback_chain=fallback_chain,
            latency_ms=elapsed_ms
        )
    
    def get_alias_status(self, alias: str) -> dict[str, Any]:
        """Get the status of a model alias."""
        alias_config = self._aliases.get(alias)
        
        if alias_config is None:
            return {
                "alias": alias,
                "status": "not_configured",
                "message": f"Alias '{alias}' is not configured"
            }
        
        # Check if resolved
        if alias_config.status == "available" and alias_config.discovered_model_id:
            return {
                "alias": alias,
                "status": "available",
                "provider": alias_config.provider,
                "model_id": alias_config.discovered_model_id,
                "fallback": alias_config.fallback
            }
        
        # Try to check current availability
        registry = get_provider_registry()
        provider = registry.get(alias_config.provider)
        
        if provider is None or not provider.enabled:
            return {
                "alias": alias,
                "status": "unavailable",
                "message": f"Provider '{alias_config.provider}' is not available"
            }
        
        models = self._discovered_models.get(alias_config.provider, [])
        
        target_id = alias_config.model_id or alias
        for model in models:
            if model.model_id == target_id or model.name == target_id:
                if model.available:
                    return {
                        "alias": alias,
                        "status": "available",
                        "provider": alias_config.provider,
                        "model_id": model.model_id
                    }
        
        return {
            "alias": alias,
            "status": "unavailable",
            "message": f"Model '{target_id}' not found on provider '{alias_config.provider}'"
        }
    
    def list_aliases(self) -> list[dict[str, Any]]:
        """List all configured model aliases with their status."""
        result = []
        
        for alias_name, alias_config in self._aliases.items():
            status_info = self.get_alias_status(alias_name)
            result.append({
                "alias": alias_name,
                "provider": alias_config.provider,
                "configured_model_id": alias_config.model_id,
                "fallback": alias_config.fallback,
                "capabilities_required": alias_config.capabilities_required,
                "status": status_info.get("status", "unknown"),
                "message": status_info.get("message", "")
            })
        
        return result
    
    def list_discovered_models(self) -> list[dict[str, Any]]:
        """List all discovered models from all providers."""
        result = []
        
        for provider_name, models in self._discovered_models.items():
            for model in models:
                result.append({
                    "provider": provider_name,
                    "model_id": model.model_id,
                    "name": model.name,
                    "capabilities": model.capabilities,
                    "max_context_tokens": model.max_context_tokens,
                    "cost_per_token": model.cost_per_token,
                    "available": model.available
                })
        
        return result


_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Get the global model router instance."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
