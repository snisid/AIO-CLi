# MA-CLI Model Routing Documentation

## Multi-Agent Autonomous CLI

**Version:** 1.0.0  
**Document Type:** Model Routing Architecture  

---

## 1. Overview

MA-CLI implements an intelligent Model Router that selects the best model for each task based on capabilities, availability, cost, and user preferences.

---

## 2. Model Router Interface

```python
class ModelRouter:
    """Intelligent model selection and routing"""
    
    def __init__(
        self,
        providers: list[Provider],
        config: ModelRoutingConfig
    ):
        self.providers = {p.name: p for p in providers}
        self.config = config
        self._model_cache: dict[str, list[ModelInfo]] = {}
        self._alias_map: dict[str, ResolvedModel] = {}
    
    async def resolve_alias(self, alias: str) -> ResolvedModel:
        """Resolve a model alias to an actual model"""
    
    async def select_model(
        self,
        task: Task,
        constraints: ModelConstraints
    ) -> ModelSelection:
        """Select the best model for a task"""
    
    async def discover_all_models(self) -> list[ModelInfo]:
        """Discover models from all providers"""
    
    async def health_check(self) -> ModelRouterHealth:
        """Check router and provider health"""
```

---

## 3. Model Resolution Flow

### Step 1: User Request

User specifies model by alias:
```bash
ma-cli run "Build auth system" --model claude-opus-5
```

### Step 2: Alias Lookup

Router looks up alias in configuration:
```yaml
models:
  aliases:
    claude-opus-5:
      provider: omniroute
      # model_id will be auto-discovered
```

### Step 3: Provider Discovery

Router queries the specified provider for available models:
```python
models = await provider.discover_models()
# Returns: ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", ...]
```

### Step 4: Alias Mapping

Router maps alias to discovered model ID:
```python
# If "claude-3-5-sonnet-20241022" matches criteria for "claude-opus-5"
resolved = ResolvedModel(
    alias="claude-opus-5",
    provider="omniroute",
    model_id="claude-3-5-sonnet-20241022",
    status="available"
)
```

### Step 5: Availability Check

If model is not found:
```python
resolved = ResolvedModel(
    alias="claude-opus-5",
    provider="omniroute",
    model_id=None,
    status="unavailable",
    reason="Model not found in provider's catalog"
)
# Never fake availability or silently substitute!
```

### Step 6: Return Result

Return resolved model or error:
```python
if resolved.status == "unavailable":
    raise ModelUnavailableError(f"Model {alias} is not available")
return resolved
```

---

## 4. Target Model Aliases

These are the configured model aliases (actual IDs discovered at runtime):

### Anthropic Models

| Alias | Provider | Notes |
|-------|----------|-------|
| claude-opus-5 | omniroute | Auto-discovered |
| claude-fable-5 | omniroute | Auto-discovered |

### OpenAI Models

| Alias | Provider | Notes |
|-------|----------|-------|
| gpt-5.5 | omniroute | Auto-discovered |
| gpt-5.6 | omniroute | Auto-discovered |

### Zcode/GLM Models

| Alias | Provider | Notes |
|-------|----------|-------|
| glm-5 | 9router | Auto-discovered |
| glm-5.2 | 9router | Auto-discovered |

### DeepSeek Models

| Alias | Provider | Notes |
|-------|----------|-------|
| deepseek-v4-pro | omniroute | Auto-discovered |

### Qwen Models

| Alias | Provider | Notes |
|-------|----------|-------|
| qwen-3.7 | ollama | Auto-discovered |
| qwen-3.8 | ollama | Auto-discovered |

---

## 5. Model Selection Algorithm

```python
async def select_model(
    self,
    task: Task,
    constraints: ModelConstraints
) -> ModelSelection:
    """
    Select the best model for a task.
    
    Factors considered:
    1. Task requirements (capabilities needed)
    2. Model capabilities
    3. Model availability
    4. Cost constraints
    5. Latency requirements
    6. User preferences
    7. Provider health
    """
    
    candidates = []
    
    # Get all available models
    all_models = await self.discover_all_models()
    
    # Filter by constraints
    for model in all_models:
        if not model.available:
            continue
        if constraints.max_cost and model.cost_per_token > constraints.max_cost:
            continue
        if constraints.required_capabilities:
            if not model.has_capabilities(constraints.required_capabilities):
                continue
        if constraints.exclude_providers and model.provider in constraints.exclude_providers:
            continue
        
        # Score the model
        score = await self._score_model(model, task, constraints)
        candidates.append((score, model))
    
    if not candidates:
        raise NoSuitableModelError("No models match requirements")
    
    # Sort by score (highest first)
    candidates.sort(reverse=True, key=lambda x: x[0])
    
    # Return best match
    score, model = candidates[0]
    return ModelSelection(
        model=model,
        score=score,
        alternatives=[m for _, m in candidates[1:5]]  # Top 5 alternatives
    )
```

### Scoring Function

```python
async def _score_model(
    self,
    model: ModelInfo,
    task: Task,
    constraints: ModelConstraints
) -> float:
    score = 0.0
    
    # Capability match (40%)
    capability_score = model.match_capabilities(task.required_capabilities)
    score += capability_score * 0.4
    
    # Cost efficiency (20%)
    if constraints.max_cost:
        cost_score = 1.0 - (model.cost_per_token / constraints.max_cost)
        score += max(0, cost_score) * 0.2
    
    # Latency (20%)
    latency_score = await self._estimate_latency(model)
    score += latency_score * 0.2
    
    # Reliability (10%)
    reliability = await self._get_provider_reliability(model.provider)
    score += reliability * 0.1
    
    # User preference bonus (10%)
    if model.name in constraints.preferred_models:
        score += 0.1
    
    return score
```

---

## 6. Provider Fallback Chain

When primary provider is unavailable:

```
┌─────────────────┐
│   OmniRoute     │ ← Primary
│   (if healthy)  │
└────────┬────────┘
         │ UNHEALTHY
         ▼
┌─────────────────┐
│    9router      │ ← Fallback 1
│   (if healthy)  │
└────────┬────────┘
         │ UNHEALTHY
         ▼
┌─────────────────┐
│    Ollama       │ ← Fallback 2 (local)
│   (if running)  │
└────────┬────────┘
         │ UNAVAILABLE
         ▼
┌─────────────────┐
│ Direct Provider │ ← Fallback 3
│  (Anthropic,    │
│   OpenAI, etc.) │
└─────────────────┘
```

### Fallback Rules

```python
class FallbackPolicy:
    def should_fallback(
        self,
        from_provider: str,
        to_provider: str,
        reason: str
    ) -> bool:
        # Never fallback if user explicitly blocked it
        if to_provider in self.user_blocked_providers:
            return False
        
        # Never fallback to lower security without approval
        if self._security_level(to_provider) < self._security_level(from_provider):
            if not self.user_approved_security_downgrade:
                return False
        
        # Log the fallback
        logger.info(f"Falling back from {from_provider} to {to_provider}: {reason}")
        
        return True
```

---

## 7. Model Discovery

```python
async def discover_all_models(self) -> list[ModelInfo]:
    """Discover models from all enabled providers."""
    all_models = []
    
    for provider_name, provider in self.providers.items():
        if not provider.enabled:
            continue
        
        try:
            models = await provider.discover_models()
            for model in models:
                model.provider = provider_name
                all_models.append(model)
            
            self._model_cache[provider_name] = models
            
        except Exception as e:
            logger.error(f"Failed to discover models from {provider_name}: {e}")
            # Mark provider as unhealthy
            await self._mark_provider_unhealthy(provider_name)
    
    return all_models
```

---

## 8. Configuration Schema

```yaml
version: 1

models:
  # Default model for unspecified tasks
  default: claude-opus-5
  
  # Fallback when default unavailable
  fallback: gpt-5.5
  
  # Model aliases
  aliases:
    claude-opus-5:
      provider: omniroute
      description: "Best Claude model for complex reasoning"
      capabilities:
        - coding
        - reasoning
        - analysis
        - tool_use
      
    claude-fable-5:
      provider: omniroute
      description: "Claude fable variant"
      
    gpt-5.5:
      provider: omniroute
      description: "GPT-5.5 for general tasks"
      capabilities:
        - coding
        - general
      
    gpt-5.6:
      provider: omniroute
      description: "GPT-5.6 enhanced"
      
    glm-5:
      provider: 9router
      description: "GLM-5 model"
      
    glm-5.2:
      provider: 9router
      description: "GLM-5.2 enhanced"
      
    deepseek-v4-pro:
      provider: omniroute
      description: "DeepSeek V4 Pro for coding"
      capabilities:
        - coding
        - math
      
    qwen-3.7:
      provider: ollama
      description: "Qwen 3.7 local"
      
    qwen-3.8:
      provider: ollama
      description: "Qwen 3.8 local enhanced"
  
  # Selection preferences
  preferences:
    # Prefer these models when capable
    preferred:
      - claude-opus-5
      - qwen-3.8
    
    # Avoid these unless necessary
    avoid: []
    
    # Maximum cost per token (in USD)
    max_cost_per_token: 0.0001
    
    # Maximum latency (in ms)
    max_latency_ms: 10000
  
  # Provider priorities (for fallback)
  provider_priority:
    - omniroute
    - 9router
    - ollama
    - anthropic
    - openai
```

---

## 9. Model Health Tracking

```python
@dataclass
class ModelHealth:
    model_id: str
    provider: str
    healthy: bool
    last_check: datetime
    consecutive_failures: int
    avg_latency_ms: float
    success_rate: float

class ModelHealthTracker:
    def __init__(self):
        self._health: dict[str, ModelHealth] = {}
        self._check_interval = 60  # seconds
    
    async def start_monitoring(self, models: list[ModelInfo]):
        for model in models:
            key = f"{model.provider}:{model.model_id}"
            self._health[key] = ModelHealth(
                model_id=model.model_id,
                provider=model.provider,
                healthy=True,
                last_check=datetime.now(),
                consecutive_failures=0,
                avg_latency_ms=0,
                success_rate=1.0
            )
        
        # Start background monitoring
        asyncio.create_task(self._monitor_loop())
    
    async def _monitor_loop(self):
        while True:
            for key, health in self._health.items():
                result = await self._check_health(health)
                self._update_health(health, result)
            
            await asyncio.sleep(self._check_interval)
    
    def is_healthy(self, provider: str, model_id: str) -> bool:
        key = f"{provider}:{model_id}"
        health = self._health.get(key)
        if not health:
            return True  # Unknown models assumed healthy
        return health.healthy
```

---

## 10. Critical Rules

### NEVER Do

1. **Never fake model availability**
   - If a model doesn't exist, report it as unavailable
   - Don't pretend a different model is the requested one

2. **Never silently substitute models**
   - Always inform the user if using a different model
   - Require explicit approval for substitutions

3. **Never bypass user policies**
   - Respect blocked providers
   - Respect cost limits
   - Respect privacy requirements

4. **Never expose credentials**
   - Don't log API keys
   - Don't include secrets in error messages

### ALWAYS Do

1. **Always verify before use**
   - Check model exists
   - Check provider is healthy
   - Check permissions allow usage

2. **Always report accurately**
   - Report actual model IDs
   - Report actual costs
   - Report actual latencies

3. **Always respect aliases**
   - Map aliases correctly
   - Document the mapping
   - Update mappings when models change

4. **Always handle failures gracefully**
   - Implement retry logic
   - Have fallback options
   - Provide clear error messages

---

## 11. Error Handling

```python
class ModelRouterError(Exception):
    """Base exception for model router errors"""

class ModelNotFoundError(ModelRouterError):
    """Requested model not found"""
    def __init__(self, alias: str, provider: str):
        super().__init__(f"Model '{alias}' not found on provider '{provider}'")
        self.alias = alias
        self.provider = provider

class ModelUnavailableError(ModelRouterError):
    """Model exists but is currently unavailable"""
    def __init__(self, model_id: str, reason: str):
        super().__init__(f"Model '{model_id}' unavailable: {reason}")
        self.model_id = model_id
        self.reason = reason

class NoSuitableModelError(ModelRouterError):
    """No models match the requirements"""
    def __init__(self, message: str, requirements: dict):
        super().__init__(message)
        self.requirements = requirements

class ProviderHealthError(ModelRouterError):
    """Provider is unhealthy"""
    def __init__(self, provider: str, health_status: str):
        super().__init__(f"Provider '{provider}' is {health_status}")
        self.provider = provider
        self.health_status = health_status
```

---

**Document Owner:** MA-CLI Core Team  
**Last Updated:** Phase 1 Initiation
