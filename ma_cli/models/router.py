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

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..config.engine import Config, ConfigurationEngine
from ..core.models import HealthStatus
from ..providers import (
    ModelInfo,
    Provider,
    get_provider_registry,
)


class TaskType(Enum):
    """Task types for model routing."""
    CODING = "coding"
    DEBUGGING = "debugging"
    ARCHITECTURE = "architecture"
    REFACTORING = "refactoring"
    RESEARCH = "research"
    TESTING = "testing"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    FAST_TASK = "fast_task"
    LONG_CONTEXT = "long_context"
    REASONING = "reasoning"
    GENERAL = "general"


class RoutingStrategy(Enum):
    """Strategy for model selection."""
    COST_OPTIMIZED = "cost_optimized"      # Lowest cost capable model
    PERFORMANCE = "performance"            # Best performance regardless of cost
    PRIVACY = "privacy"                    # Local/private models only
    BALANCED = "balanced"                  # Balance of cost and performance
    LATENCY = "latency"                    # Lowest latency
    QUALITY = "quality"                    # Highest quality output


@dataclass
class ModelSpec:
    """
    Complete model specification with all routing metadata.
    
    Extends ModelInfo with additional fields for intelligent routing.
    """
    model_id: str
    name: str
    provider: str
    capabilities: list[str] = field(default_factory=list)
    context_window: int = 0
    max_output: int = 0
    speed: float = 0.0  # tokens/second (higher is faster)
    cost: float = 0.0  # cost per 1M tokens
    quality: float = 0.0  # 0.0-1.0 quality score
    reasoning_level: str = "basic"  # basic, medium, advanced
    coding_score: float = 0.0  # 0.0-1.0 coding capability
    availability: float = 1.0  # 0.0-1.0 availability
    health: HealthStatus = HealthStatus.UNKNOWN
    latency_ms: float = 0.0
    last_checked: datetime | None = None
    
    @classmethod
    def from_model_info(cls, info: ModelInfo) -> ModelSpec:
        """Create ModelSpec from ModelInfo."""
        return cls(
            model_id=info.model_id,
            name=info.name,
            provider=info.provider,
            capabilities=info.capabilities,
            context_window=info.max_context_tokens,
            cost=info.cost_per_token,
            availability=1.0 if info.available else 0.0
        )
    
    def to_model_info(self) -> ModelInfo:
        """Convert to ModelInfo."""
        return ModelInfo(
            model_id=self.model_id,
            name=self.name,
            provider=self.provider,
            capabilities=self.capabilities,
            max_context_tokens=self.context_window,
            cost_per_token=self.cost,
            available=self.availability > 0.5
        )
    
    def has_capabilities(self, required: list[str]) -> bool:
        """Check if model has all required capabilities."""
        if not required:
            return True
        return all(cap in self.capabilities for cap in required)


@dataclass
class AgentContext:
    """Context for agent-aware routing."""
    agent_type: str
    task_type: TaskType
    required_tools: list[str] = field(default_factory=list)
    required_context: int = 0
    quality_requirement: float = 0.5  # 0.0-1.0
    latency_requirement: float = 1.0  # seconds max
    cost_limit: float = 0.0  # 0.0 means no limit
    privacy_required: bool = False


@dataclass
class ModelAlias:
    """Configuration for a model alias."""
    alias: str
    provider: str
    model_id: str | None = None  # None means auto-discover
    fallback: list[str] = field(default_factory=list)
    capabilities_required: list[str] = field(default_factory=list)
    max_cost_per_token: float = 0.0
    privacy_required: bool = False
    status: str = "unknown"  # available, unavailable, unknown
    discovered_model_id: str | None = None


@dataclass
class ModelSelectionResult:
    """Result of model selection."""
    success: bool
    selected_model: ModelInfo | None = None
    alias_used: str | None = None
    provider_used: str | None = None
    fallback_chain: list[str] = field(default_factory=list)
    error: str | None = None
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
    
    _instance: ModelRouter | None = None
    
    def __new__(cls) -> ModelRouter:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._aliases: dict[str, ModelAlias] = {}
            cls._instance._discovered_models: dict[str, list[ModelInfo]] = {}
            cls._instance._last_discovery: dict[str, datetime] = {}
            cls._instance._discovery_cache_ttl = 300  # 5 minutes
        return cls._instance
    
    def initialize(self, config: Config | None = None) -> None:
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
        required_capabilities: list[str] | None = None
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
        required_capabilities: list[str] | None,
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
        required_capabilities: list[str] | None,
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
    
    async def select_for_task(
        self,
        task_type: TaskType,
        agent_context: AgentContext | None = None,
        strategy: RoutingStrategy = RoutingStrategy.BALANCED
    ) -> ModelSelectionResult:
        """
        Select the best model for a specific task type.
        
        Uses intelligent scoring based on task requirements, model capabilities,
        health status, and routing strategy.
        
        Args:
            task_type: Type of task (CODING, DEBUGGING, ARCHITECTURE, etc.)
            agent_context: Optional agent context for additional constraints
            strategy: Routing strategy to use
            
        Returns:
            ModelSelectionResult with best model or error
        """
        start_time = datetime.now(timezone.utc)
        fallback_chain = []
        
        # Ensure discovery is done
        await self.discover_all_models()
        
        # Build capability requirements based on task type
        required_capabilities = self._get_capabilities_for_task(task_type)
        
        # Get all available models as ModelSpec objects
        candidates: list[ModelSpec] = []
        for provider_name, models in self._discovered_models.items():
            for model in models:
                if model.available:
                    spec = ModelSpec.from_model_info(model)
                    # Enhance with provider-specific metadata
                    spec = self._enrich_model_spec(spec, provider_name, task_type)
                    candidates.append(spec)
        
        if not candidates:
            return ModelSelectionResult(
                success=False,
                error="No models available from any provider"
            )
        
        # Score each candidate
        scored_candidates = []
        for spec in candidates:
            # Check basic requirements
            if agent_context:
                if agent_context.privacy_required and spec.provider != "ollama":
                    continue
                if agent_context.cost_limit > 0 and spec.cost > agent_context.cost_limit:
                    continue
                if spec.context_window < agent_context.required_context:
                    continue
            
            # Calculate composite score
            score = self._calculate_routing_score(
                spec,
                task_type,
                required_capabilities,
                agent_context,
                strategy
            )
            
            if score > 0:  # Only consider viable candidates
                scored_candidates.append((score, spec))
        
        if not scored_candidates:
            return ModelSelectionResult(
                success=False,
                error=f"No models match requirements for task type {task_type.value}"
            )
        
        # Sort by score (highest first)
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_spec = scored_candidates[0]
        
        elapsed_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        
        return ModelSelectionResult(
            success=True,
            selected_model=best_spec.to_model_info(),
            provider_used=best_spec.provider,
            fallback_chain=fallback_chain,
            latency_ms=elapsed_ms
        )
    
    def _get_capabilities_for_task(self, task_type: TaskType) -> list[str]:
        """Get required capabilities for a task type."""
        capability_map = {
            TaskType.CODING: ["code", "chat"],
            TaskType.DEBUGGING: ["code", "reasoning", "chat"],
            TaskType.ARCHITECTURE: ["reasoning", "chat", "code"],
            TaskType.REFACTORING: ["code", "reasoning", "chat"],
            TaskType.RESEARCH: ["chat", "reasoning"],
            TaskType.TESTING: ["code", "chat"],
            TaskType.SECURITY: ["security", "code", "reasoning", "chat"],
            TaskType.DOCUMENTATION: ["chat"],
            TaskType.FAST_TASK: ["chat"],
            TaskType.LONG_CONTEXT: ["long_context", "chat"],
            TaskType.REASONING: ["reasoning", "chat"],
            TaskType.GENERAL: ["chat"],
        }
        return capability_map.get(task_type, ["chat"])
    
    def _enrich_model_spec(
        self,
        spec: ModelSpec,
        provider_name: str,
        task_type: TaskType
    ) -> ModelSpec:
        """Enrich ModelSpec with provider/task-specific metadata."""
        # Set health status
        registry = get_provider_registry()
        provider = registry.get(provider_name)
        if provider:
            # Could do actual health check, but for now use availability
            spec.health = HealthStatus.HEALTHY if spec.availability > 0.5 else HealthStatus.UNHEALTHY
        
        # Set quality scores based on known provider characteristics
        quality_profiles = {
            "anthropic": {"quality": 0.95, "reasoning_level": "advanced", "coding_score": 0.92},
            "openai": {"quality": 0.90, "reasoning_level": "advanced", "coding_score": 0.88},
            "omniroute": {"quality": 0.85, "reasoning_level": "medium", "coding_score": 0.80},
            "9router": {"quality": 0.80, "reasoning_level": "medium", "coding_score": 0.75},
            "ollama": {"quality": 0.70, "reasoning_level": "basic", "coding_score": 0.65},
        }
        
        profile = quality_profiles.get(provider_name, {})
        if profile:
            spec.quality = profile.get("quality", spec.quality)
            spec.reasoning_level = profile.get("reasoning_level", spec.reasoning_level)
            spec.coding_score = profile.get("coding_score", spec.coding_score)
        
        # Boost coding_score for coding tasks if model has code capability
        if task_type in [TaskType.CODING, TaskType.DEBUGGING, TaskType.REFACTORING]:
            if "code" in spec.capabilities:
                spec.coding_score = min(1.0, spec.coding_score + 0.1)
        
        return spec
    
    def _calculate_routing_score(
        self,
        spec: ModelSpec,
        task_type: TaskType,
        required_capabilities: list[str],
        agent_context: AgentContext | None,
        strategy: RoutingStrategy
    ) -> float:
        """
        Calculate routing score for a model.
        
        Score formula:
        score = (capability_score * 0.3)
              + (quality_score * 0.25)
              + (health_score * 0.15)
              + (availability_score * 0.1)
              - (latency_penalty * 0.1)
              - (cost_penalty * 0.1)
        
        Returns 0 if model doesn't meet minimum requirements.
        """
        # Capability matching (binary: either has it or not)
        if not spec.has_capabilities(required_capabilities):
            return 0.0
        
        capability_score = len(set(spec.capabilities) & set(required_capabilities)) / max(len(required_capabilities), 1)
        
        # Quality score (normalized 0-1)
        quality_score = spec.quality
        
        # Health score
        health_scores = {
            HealthStatus.HEALTHY: 1.0,
            HealthStatus.DEGRADED: 0.5,
            HealthStatus.UNHEALTHY: 0.0,
            HealthStatus.UNKNOWN: 0.5,
        }
        health_score = health_scores.get(spec.health, 0.5)
        
        # Availability score
        availability_score = spec.availability
        
        # Latency penalty (higher latency = lower score)
        # Normalize: assume 100ms is excellent, 5000ms is terrible
        latency_penalty = min(1.0, spec.latency_ms / 5000.0)
        
        # Cost penalty (higher cost = lower score)
        # Only apply if strategy is cost-sensitive
        if strategy in [RoutingStrategy.COST_OPTIMIZED, RoutingStrategy.BALANCED]:
            # Normalize: assume $0.1/1M tokens is cheap, $10/1M is expensive
            cost_penalty = min(1.0, spec.cost / 10.0)
        else:
            cost_penalty = 0.0
        
        # Apply strategy weights
        if strategy == RoutingStrategy.COST_OPTIMIZED:
            weights = {"capability": 0.2, "quality": 0.15, "health": 0.15, "availability": 0.1, "latency": 0.1, "cost": 0.3}
        elif strategy == RoutingStrategy.PERFORMANCE:
            weights = {"capability": 0.25, "quality": 0.35, "health": 0.15, "availability": 0.1, "latency": 0.1, "cost": 0.05}
        elif strategy == RoutingStrategy.PRIVACY:
            # Privacy handled by filtering, not scoring
            weights = {"capability": 0.3, "quality": 0.2, "health": 0.2, "availability": 0.15, "latency": 0.15, "cost": 0.0}
        elif strategy == RoutingStrategy.LATENCY:
            weights = {"capability": 0.2, "quality": 0.15, "health": 0.15, "availability": 0.1, "latency": 0.3, "cost": 0.1}
        elif strategy == RoutingStrategy.QUALITY:
            weights = {"capability": 0.25, "quality": 0.4, "health": 0.15, "availability": 0.1, "latency": 0.05, "cost": 0.05}
        else:  # BALANCED
            weights = {"capability": 0.25, "quality": 0.25, "health": 0.15, "availability": 0.1, "latency": 0.1, "cost": 0.15}
        
        score = (
            capability_score * weights["capability"] +
            quality_score * weights["quality"] +
            health_score * weights["health"] +
            availability_score * weights["availability"] -
            latency_penalty * weights["latency"] -
            cost_penalty * weights["cost"]
        )
        
        # Apply agent context adjustments
        if agent_context:
            # Penalize if doesn't meet quality requirement
            if spec.quality < agent_context.quality_requirement:
                score *= 0.5
            
            # Penalize if latency exceeds requirement
            if spec.latency_ms > agent_context.latency_requirement * 1000:
                score *= 0.5
        
        return max(0.0, score)

    async def _strategy_fallback(
        self,
        original_alias: str,
        strategy: RoutingStrategy,
        required_capabilities: list[str] | None,
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


_router: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    """Get the global model router instance."""
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
