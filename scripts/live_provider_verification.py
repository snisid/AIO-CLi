"""Live provider verification.

This script never converts an unavailable credential/service into PASS. It emits
PASS, UNVERIFIED, or FAIL for every configured provider and performs a real HTTP
health/model request where possible.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from typing import Any

import httpx


PROVIDERS = {
    "ollama": {"url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), "key": None, "models": "/api/tags"},
    "omniroute": {"url": os.getenv("OMNIROUTE_BASE_URL", ""), "key": os.getenv("OMNIROUTE_API_KEY"), "models": "/v1/models"},
    "9router": {"url": os.getenv("NINEROUTER_BASE_URL", ""), "key": os.getenv("NINEROUTER_API_KEY"), "models": "/v1/models"},
    "openai": {"url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com"), "key": os.getenv("OPENAI_API_KEY"), "models": "/v1/models"},
    "anthropic": {"url": os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"), "key": os.getenv("ANTHROPIC_API_KEY"), "models": "/v1/models"},
}


async def probe(name: str, cfg: dict[str, Any]) -> dict[str, Any]:
    if name != "ollama" and not cfg["key"]:
        return {"provider": name, "status": "UNVERIFIED", "reason": "API credential not configured"}
    if not cfg["url"]:
        return {"provider": name, "status": "UNVERIFIED", "reason": "base URL not configured"}
    headers = {"Authorization": f"Bearer {cfg['key']}"} if cfg["key"] else {}
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(cfg["url"].rstrip("/") + cfg["models"], headers=headers)
        elapsed = round((time.monotonic() - started) * 1000, 1)
        if response.status_code == 200:
            return {"provider": name, "status": "PASS", "latency_ms": elapsed}
        return {"provider": name, "status": "FAIL", "http_status": response.status_code,
                "latency_ms": elapsed}
    except Exception as exc:
        return {"provider": name, "status": "FAIL", "reason": str(exc)}


async def main() -> int:
    results = await asyncio.gather(*(probe(name, cfg) for name, cfg in PROVIDERS.items()))
    for result in results:
        print(result)
    return 0 if all(r["status"] in {"PASS", "UNVERIFIED"} for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
