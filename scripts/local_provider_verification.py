"""Credentialed local provider E2E verification for AIO-CLi.

This command is intentionally local-only. It reads endpoint/API credentials from
process environment variables, performs real model discovery and a minimal
inference call, and never prints secret values. Missing credentials/services are
reported as UNVERIFIED rather than PASS.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any

from ma_cli.config.engine import ConfigurationEngine
from ma_cli.providers import ChatMessage, get_provider_registry


TARGETS = ("openrouter", "omniroute", "9router", "ollama")


@dataclass(frozen=True)
class Result:
    provider: str
    status: str
    endpoint: str
    model: str | None = None
    latency_ms: float | None = None
    detail: str = ""


def _redacted_endpoint(value: str) -> str:
    return value.split("/v1", 1)[0] + ("/v1" if "/v1" in value else "")


async def verify_provider(name: str) -> Result:
    config = ConfigurationEngine().load().providers.get(name)
    if config is None:
        return Result(name, "UNVERIFIED", "", detail="provider not configured")
    registry = get_provider_registry()
    registry.initialize(None)
    provider = registry.get(name)
    if provider is None:
        return Result(name, "UNVERIFIED", _redacted_endpoint(config.base_url), detail="provider not registered")
    if not provider.enabled:
        return Result(name, "UNVERIFIED", _redacted_endpoint(provider.base_url), detail="provider disabled or credential missing")
    started = time.monotonic()
    try:
        models = await provider.discover_models()
        if not models:
            return Result(name, "FAIL", _redacted_endpoint(provider.base_url), detail="no models discovered")
        model = next((item for item in models if item.available), models[0])
        response = await provider.safe_chat(
            [ChatMessage(role="user", content="Reply with exactly AIO-CLI-OK.")],
            model.model_id,
            max_tokens=8,
        )
        latency = (time.monotonic() - started) * 1000
        content = response.content.strip()
        if not content:
            return Result(name, "FAIL", _redacted_endpoint(provider.base_url), model.model_id,
                          latency, "empty model response")
        return Result(name, "PASS", _redacted_endpoint(provider.base_url), model.model_id,
                      latency, "real discovery + inference succeeded")
    except Exception as exc:  # noqa: BLE001 - provider boundary is the diagnostic target
        return Result(name, "FAIL", _redacted_endpoint(provider.base_url), detail=str(exc))


async def main() -> int:
    results = await asyncio.gather(*(verify_provider(name) for name in TARGETS))
    print("AIO-CLi local provider verification")
    print("====================================")
    for item in results:
        latency = f" {item.latency_ms:.0f}ms" if item.latency_ms is not None else ""
        model = f" model={item.model}" if item.model else ""
        detail = f" - {item.detail}" if item.detail else ""
        print(f"{item.provider:10} {item.status:10} endpoint={item.endpoint}{model}{latency}{detail}")
    passed = [item for item in results if item.status == "PASS"]
    failed = [item for item in results if item.status == "FAIL"]
    print(f"\nPASS={len(passed)} FAIL={len(failed)} UNVERIFIED={len(results) - len(passed) - len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
