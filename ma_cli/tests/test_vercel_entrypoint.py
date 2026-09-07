from __future__ import annotations

import httpx
import pytest

from app import app


@pytest.mark.asyncio
async def test_vercel_entrypoint_and_dashboard() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = await client.get("/")
        dashboard = await client.get("/dashboard")
        dashboard_slash = await client.get("/dashboard/")
        health = await client.get("/health")
        status = await client.get("/api/status")
        css = await client.get("/ui/dashboard/dashboard.css")
        js = await client.get("/ui/dashboard/dashboard.js")
        splash_css = await client.get("/ui/splash/ma-cli-splash.css")
        logo = await client.get("/assets/logo/ma-cli-animated.svg")

    assert responses.status_code == 200
    assert "AIO-CLi Dashboard" in responses.text
    assert dashboard.status_code == 200
    assert "AIO-CLi Dashboard" in dashboard.text
    assert dashboard_slash.status_code == 307
    assert dashboard_slash.headers["location"] == "/dashboard"
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "aio-cli"}
    assert status.status_code == 200
    assert status.json()["runtime"] == "online"
    assert status.json()["dashboard"] == "/dashboard"
    assert css.status_code == 200
    assert "desktop-shell" in css.text
    assert "single-panel" in css.text
    assert js.status_code == 200
    assert "configureMultiScreen" in js.text
    assert "openModal" in js.text
    assert splash_css.status_code == 200
    assert "--ma-cyan" in splash_css.text
    assert logo.status_code == 200
    assert "<svg" in logo.text
