from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parent
UI_ROOT = ROOT / "ui"
ASSETS_ROOT = ROOT / "assets"
SPLASH_HTML = UI_ROOT / "splash" / "splash.html"
DASHBOARD_HTML = UI_ROOT / "dashboard" / "dashboard.html"

app = FastAPI(
    title="AIO-CLi",
    version="1.0.0",
    description="Multi-Agent Autonomous Coding Platform",
)


def _html_file(path: Path, fallback: str) -> HTMLResponse:
    if not path.is_file():
        return HTMLResponse(fallback, status_code=200)
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """Serve the dashboard at the deployment root."""
    return _html_file(
        DASHBOARD_HTML,
        "<h1>AIO-CLi</h1><p>Runtime online.</p><p><a href='/dashboard'>Open dashboard</a></p>",
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return _html_file(
        DASHBOARD_HTML,
        "<h1>AIO-CLi</h1><p>Dashboard unavailable.</p>",
    )


@app.get("/dashboard/", include_in_schema=False)
async def dashboard_trailing_slash() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@app.get("/splash", response_class=HTMLResponse)
async def splash() -> HTMLResponse:
    """Keep the original splash screen available."""
    if not SPLASH_HTML.is_file():
        return HTMLResponse("<h1>AIO-CLi</h1><p>Runtime online.</p>", status_code=200)
    html = SPLASH_HTML.read_text(encoding="utf-8")
    html = html.replace('href="ma-cli-splash.css"', 'href="/ui/splash/ma-cli-splash.css"')
    html = html.replace(
        'src="../../assets/logo/ma-cli-animated.svg"',
        'src="/assets/logo/ma-cli-animated.svg"',
    )
    return HTMLResponse(html)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "aio-cli"}


@app.get("/api/status")
async def api_status() -> dict[str, str]:
    return {
        "service": "AIO-CLi",
        "runtime": "online",
        "deployment": "vercel",
        "dashboard": "/dashboard",
    }


# Mount static directories instead of routing individual files through FileResponse.
# This avoids Vercel serverless path-resolution issues for dashboard assets.
app.mount("/ui", StaticFiles(directory=UI_ROOT, check_dir=True), name="ui")
app.mount("/assets", StaticFiles(directory=ASSETS_ROOT, check_dir=True), name="assets")
