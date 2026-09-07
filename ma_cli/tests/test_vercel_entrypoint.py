from __future__ import annotations

import httpx
import pytest

from app import app


@pytest.mark.asyncio
async def test_vercel_entrypoint_health_and_status() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health")
        status = await client.get("/api/status")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "aio-cli"}
    assert status.status_code == 200
    assert status.json()["runtime"] == "online"
