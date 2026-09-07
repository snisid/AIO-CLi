# AIO-CLi local provider verification

AIO-CLi supports local credentialed verification without committing API keys.
Credentials are read from environment variables and are never persisted by the
configuration serializer.

## PowerShell

```powershell
$env:OPENROUTER_API_KEY="<your-key>"
$env:OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"

$env:OMNIROUTE_API_KEY="<your-key>"
$env:OMNIROUTE_BASE_URL="http://localhost:20128/v1"

$env:NINEROUTER_API_KEY="<your-key>"
$env:NINEROUTER_BASE_URL="http://localhost:9090/v1"

$env:OLLAMA_BASE_URL="http://localhost:11434/v1"

python scripts/local_provider_verification.py
```

## Bash

```bash
export OPENROUTER_API_KEY="<your-key>"
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
export OMNIROUTE_API_KEY="<your-key>"
export OMNIROUTE_BASE_URL="http://localhost:20128/v1"
export NINEROUTER_API_KEY="<your-key>"
export NINEROUTER_BASE_URL="http://localhost:9090/v1"
export OLLAMA_BASE_URL="http://localhost:11434/v1"

python scripts/local_provider_verification.py
```

The verifier performs **real model discovery plus real inference** for
OpenRouter, OmniRoute, 9router and Ollama. `PASS` means that both discovery and
inference succeeded. `FAIL` means the service was configured but the real check
failed. `UNVERIFIED` means that the provider is absent, disabled, or missing a
required credential/service.

Do not paste API keys into GitHub issues, commits, logs, or chat. Keep them only
in the local process environment or a local secret manager.

OpenRouter uses its OpenAI-compatible `/api/v1/chat/completions` endpoint. Its
own API can also provide model fallback through a `models` array, while AIO-CLi
adds cross-provider failover above that layer.
