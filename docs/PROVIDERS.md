# MA-CLI Providers Documentation

## Multi-Agent Autonomous CLI

**Version:** 1.0.0  
**Document Type:** Provider Architecture  

---

## 1. Overview

MA-CLI supports multiple model providers through a unified abstraction layer. This document describes the provider architecture, supported providers, and integration patterns.

---

## 2. Provider Interface

All providers implement the following interface:

```python
class Provider(ABC):
    @property
    def name(self) -> str:
        """Unique provider identifier"""
    
    @property
    def type(self) -> str:
        """Provider type (openai-compatible, anthropic, etc.)"""
    
    @property
    def base_url(self) -> str:
        """API base URL"""
    
    @property
    def enabled(self) -> bool:
        """Whether provider is enabled"""
    
    async def discover_models(self) -> list[ModelInfo]:
        """Discover available models from this provider"""
    
    async def chat(
        self, 
        messages: list[Message], 
        model: str,
        **kwargs
    ) -> ChatResponse:
        """Send chat completion request"""
    
    async def health_check(self) -> HealthStatus:
        """Check provider health and connectivity"""
```

---

## 3. Supported Providers

### 3.1 Ollama

**Type:** OpenAI-compatible  
**Priority:** P0  
**Status:** Required

**Configuration:**
```yaml
providers:
  ollama:
    type: openai-compatible
    enabled: true
    base_url: http://localhost:11434/v1
    api_key: null  # Not required for local
```

**Features:**
- Local model execution
- No API costs
- Full privacy
- Model pull/push support

**Models:**
- qwen2.5-coder (recommended for coding)
- deepseek-coder
- llama3
- mistral
- Custom models

---

### 3.2 OmniRoute

**Type:** OpenAI-compatible  
**Priority:** P0  
**Status:** Required

**Configuration:**
```yaml
providers:
  omniroute:
    type: openai-compatible
    enabled: true
    base_url: http://localhost:20128/v1
    api_key: ${OMNIROUTE_API_KEY}
```

**Features:**
- Multi-provider aggregation
- Intelligent routing
- Cost optimization
- Fallback support
- Model alias resolution

**Installation:**
```bash
git clone https://github.com/diegosouzapw/OmniRoute.git
cd OmniRoute
# Follow installation instructions
```

---

### 3.3 9router

**Type:** OpenAI-compatible  
**Priority:** P0  
**Status:** Required

**Configuration:**
```yaml
providers:
  9router:
    type: openai-compatible
    enabled: true
    base_url: ${NINEROUTER_BASE_URL}
    api_key: ${NINEROUTER_API_KEY}
```

**Features:**
- Alternative router to OmniRoute
- Fallback provider
- Cost-effective routing

---

### 3.4 Anthropic

**Type:** Anthropic API  
**Priority:** P0  
**Status:** Required

**Configuration:**
```yaml
providers:
  anthropic:
    type: anthropic
    enabled: true
    api_key: ${ANTHROPIC_API_KEY}
```

**Features:**
- Direct Claude access
- Latest Claude models
- Tool use support
- Extended context

**Models:**
- claude-3-5-sonnet-20241022
- claude-3-opus-20240229
- claude-3-haiku-20240307

---

### 3.5 OpenAI

**Type:** OpenAI-compatible  
**Priority:** P0  
**Status:** Required

**Configuration:**
```yaml
providers:
  openai:
    type: openai-compatible
    enabled: true
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}
```

**Features:**
- GPT-4 and later models
- Tool use support
- Function calling
- JSON mode

**Models:**
- gpt-4o
- gpt-4-turbo
- gpt-3.5-turbo

---

### 3.6 Google (Gemini)

**Type:** Gemini API  
**Priority:** P1  
**Status:** Optional

**Configuration:**
```yaml
providers:
  google:
    type: gemini
    enabled: true
    api_key: ${GOOGLE_API_KEY}
```

**Features:**
- Gemini Pro/Ultra models
- Multimodal support
- Large context windows

---

### 3.7 DeepSeek

**Type:** OpenAI-compatible  
**Priority:** P1  
**Status:** Optional

**Configuration:**
```yaml
providers:
  deepseek:
    type: openai-compatible
    enabled: true
    base_url: https://api.deepseek.com/v1
    api_key: ${DEEPSEEK_API_KEY}
```

**Features:**
- DeepSeek Coder models
- Cost-effective coding
- Large context

---

### 3.8 Qwen

**Type:** OpenAI-compatible  
**Priority:** P1  
**Status:** Optional

**Configuration:**
```yaml
providers:
  qwen:
    type: openai-compatible
    enabled: true
    base_url: ${QWEN_BASE_URL}
    api_key: ${QWEN_API_KEY}
```

---

## 4. Model Aliases

MA-CLI uses configurable model aliases to abstract actual model IDs:

```yaml
models:
  aliases:
    # Anthropic models
    claude-opus-5:
      provider: omniroute
      model_id: auto-discovered
    
    claude-fable-5:
      provider: omniroute
      model_id: auto-discovered
    
    # OpenAI models
    gpt-5.5:
      provider: omniroute
      model_id: auto-discovered
    
    gpt-5.6:
      provider: omniroute
      model_id: auto-discovered
    
    # Zcode/GLM models
    glm-5:
      provider: 9router
      model_id: auto-discovered
    
    glm-5.2:
      provider: 9router
      model_id: auto-discovered
    
    # DeepSeek models
    deepseek-v4-pro:
      provider: omniroute
      model_id: auto-discovered
    
    # Qwen models
    qwen-3.7:
      provider: ollama
      model_id: auto-discovered
    
    qwen-3.8:
      provider: ollama
      model_id: auto-discovered
```

### Alias Resolution Flow

1. User requests model by alias (e.g., `claude-opus-5`)
2. Model Router identifies target provider
3. Provider discovers actual model ID
4. If model unavailable, report as unavailable (never fake)
5. Map alias to discovered ID for future requests

---

## 5. Provider Fallback Chain

MA-CLI implements intelligent provider fallback:

```
Primary → OmniRoute
    ↓ (if unavailable)
Fallback 1 → 9router
    ↓ (if unavailable)
Fallback 2 → Ollama (local)
    ↓ (if unavailable)
Fallback 3 → Direct Provider
```

### Fallback Rules

1. **Capability Matching**: Fallback must support required capabilities
2. **Model Availability**: Target model must exist on fallback
3. **User Policy**: Respect user's allowed providers
4. **Cost Policy**: Don't exceed cost limits
5. **Privacy Policy**: Respect data handling requirements
6. **Latency**: Consider response time requirements
7. **Reliability**: Prefer reliable providers

### Never Do

- Never switch to inferior model without reporting
- Never bypass user's provider restrictions
- Never expose credentials in fallback
- Never silently change providers during critical operations

---

## 6. Provider Discovery

At startup, MA-CLI discovers available providers:

```python
async def discover_providers() -> ProviderDiscoveryResult:
    results = []
    
    # Check Ollama
    if await check_ollama_available():
        models = await ollama.list_models()
        results.append(ProviderInfo(
            name="ollama",
            status="connected",
            models=models
        ))
    
    # Check OmniRoute
    if await check_omniroute_available():
        models = await omniroute.list_models()
        results.append(ProviderInfo(
            name="omniroute",
            status="connected",
            models=models
        ))
    
    # ... check other providers
    
    return ProviderDiscoveryResult(providers=results)
```

---

## 7. Health Checking

Providers are health-checked periodically:

```python
async def health_check_provider(provider: Provider) -> HealthStatus:
    try:
        # Simple ping request
        response = await provider.chat(
            messages=[{"role": "user", "content": "ping"}],
            model="test-model"
        )
        return HealthStatus(
            healthy=True,
            latency_ms=response.latency_ms,
            last_check=datetime.now()
        )
    except Exception as e:
        return HealthStatus(
            healthy=False,
            error=str(e),
            last_check=datetime.now()
        )
```

---

## 8. Configuration Schema

Full provider configuration:

```yaml
version: 1

providers:
  ollama:
    type: openai-compatible
    enabled: true
    base_url: http://localhost:11434/v1
    timeout: 120
    retry_count: 3
    models:
      - qwen2.5-coder:32b
      - deepseek-coder:33b
    
  omniroute:
    type: openai-compatible
    enabled: true
    base_url: http://localhost:20128/v1
    api_key: ${OMNIROUTE_API_KEY}
    timeout: 60
    retry_count: 3
    fallback_enabled: true
    
  9router:
    type: openai-compatible
    enabled: true
    base_url: ${NINEROUTER_BASE_URL}
    api_key: ${NINEROUTER_API_KEY}
    timeout: 60
    
  anthropic:
    type: anthropic
    enabled: true
    api_key: ${ANTHROPIC_API_KEY}
    timeout: 120
    max_tokens: 8192
    
  openai:
    type: openai-compatible
    enabled: true
    base_url: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}
    timeout: 60

models:
  default: claude-opus-5
  fallback: gpt-5.5
  aliases:
    # ... alias definitions
```

---

## 9. Provider Comparison

| Provider | Type | Cost | Latency | Privacy | Best For |
|----------|------|------|---------|---------|----------|
| Ollama | Local | Free | Low | Maximum | Local dev, privacy |
| OmniRoute | Gateway | Variable | Medium | Medium | Multi-provider |
| 9router | Gateway | Variable | Medium | Medium | Fallback |
| Anthropic | Direct | High | Low-Med | Medium | Complex reasoning |
| OpenAI | Direct | High | Low | Medium | General purpose |
| Google | Direct | Medium | Medium | Medium | Multimodal |
| DeepSeek | Direct | Low | Medium | Medium | Coding |
| Qwen | Direct | Low | Medium | Medium | Coding, multilingual |

---

## 10. Best Practices

### Security

1. **Never hardcode API keys** - Use environment variables or secrets manager
2. **Use HTTPS** - All provider communications encrypted
3. **Validate certificates** - Don't disable SSL verification
4. **Rotate keys** - Periodic credential rotation
5. **Monitor usage** - Detect unusual API activity

### Performance

1. **Connection pooling** - Reuse HTTP connections
2. **Streaming** - Use streaming for long responses
3. **Timeout tuning** - Balance reliability vs. responsiveness
4. **Retry logic** - Handle transient failures
5. **Caching** - Cache model lists, common responses

### Cost Management

1. **Set budgets** - Define spending limits
2. **Monitor usage** - Track API calls and tokens
3. **Use cheaper models** - When appropriate for task
4. **Optimize prompts** - Reduce token usage
5. **Batch requests** - Where supported

---

## 11. Troubleshooting

### Common Issues

**Provider not connecting:**
- Check network connectivity
- Verify base URL
- Check API key validity
- Review firewall rules

**Models not discovered:**
- Check provider status
- Verify API permissions
- Review provider logs
- Test with curl/postman

**High latency:**
- Check network conditions
- Review provider status page
- Consider alternative provider
- Enable caching

**Authentication failures:**
- Verify API key format
- Check key expiration
- Review permission scopes
- Regenerate if needed

---

**Document Owner:** MA-CLI Core Team  
**Last Updated:** Phase 1 Initiation
