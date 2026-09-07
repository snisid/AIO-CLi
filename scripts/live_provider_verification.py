"""Live provider verification.

The script never turns missing credentials/services into PASS. When credentials
are available it performs model discovery and a minimal real inference request.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx


PROVIDERS = {
    "ollama": {
        "url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        "key": None,
        "models": "/api/tags",
        "chat": "/v1/chat/completions",
    },
    "omniroute": {
        "url": os.getenv("OMNIROUTE_BASE_URL", ""),
        "key": os.getenv("OMNIROUTE_API_KEY"),
        "models": "/v1/models",
        "chat": "/v1/chat/completions",
    },
    "9router": {
        "url": os.getenv("NINEROUTER_BASE_URL", ""),
        "key": os.getenv("NINEROUTER_API_KEY"),
        "models": "/v1/models",
        "chat": "/v1/chat/completions",
    },
    "openrouter": {
        "url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api"),
        "key": os.getenv("OPENROUTER_API_KEY"),
        "models": "/v1/models",
        "chat": "/v1/chat/completions",
    },
    "openai": {
        "url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com"),
        "key": os.getenv("OPENAI_API_KEY"),
        "models": "/v1/models",
        "chat": "/v1/chat/completions",
    },
}


def _model_id(data: dict[str, Any], provider: str) -> str | None:
    items = data.get("data") if isinstance(data.get("data"), list) else data.get("models")
    if provider == "ollama":
        return (items or [{}])[0].get("name") if items else None
    return (items or [{}])[0].get("id") if items else None


async def probe(name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    if not cfg["key"] and name != "ollama":
        return {"provider": name, "status": "UNVERIFIED", "reason": "API credential not configured"}
    if not cfg["url"]:
        return {"provider": name, "status": "UNVERIFIED", "reason": "base URL not configured"}
    headers = {"Authorization": f"Bearer {cfg['key']}"} if cfg["key"] else {}
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(cfg["url"].rstrip("/") + cfg["models"], headers=headers)
            response.raise_for_status()
            data = response.json()
            model = _model_id(data, name)
            if not model:
                return {"provider": name, "status": "FAIL", "reason": "no model advertised"}
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly OK."}],
                "max_tokens": 4,
                "stream": False,
            }
            chat = await client.post(cfg["url"].rstrip("/") + cfg["chat"], json=payload, headers=headers)
            chat.raise_for_status()
        elapsed = round((time.monotonic() - started) * 1000, 1)
        return {
            "provider": name,
            "status": "PASS",
            "latency_ms": elapsed,
            "model": model,
            "inference": True,
        }
    except Exception as exc:
        return {"provider": name, "status": "FAIL", "reason": str(exc)}


async def main() -> int:
    results = await asyncio.gather(*(probe(name, cfg) for name, cfg in PROVIDERS.items()))
    for result in results:
        print(result)
    return 0 if all(r["status"] in {"PASS", "UNVERIFIED"} for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
