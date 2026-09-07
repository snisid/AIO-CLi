from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse


ROOT = Path(__file__).resolve().parent
SPLASH_HTML = ROOT / "ui" / "splash" / "splash.html"
SPLASH_CSS = ROOT / "ui" / "splash" / "ma-cli-splash.css"
DASHBOARD_HTML = ROOT / "ui" / "dashboard" / "dashboard.html"
DASHBOARD_CSS = ROOT / "ui" / "dashboard" / "dashboard.css"
DASHBOARD_JS = ROOT / "ui" / "dashboard" / "dashboard.js"
LOGO_SVG = ROOT / "assets" / "logo" / "ma-cli-animated.svg"

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
    """Serve the operational dashboard at the deployment root."""
    return _html_file(
        DASHBOARD_HTML,
        "<h1>AIO-CLi</h1><p>Runtime online.</p><p><a href='/dashboard'>Open dashboard</a></p>",
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return _html_file(DASHBOARD_HTML, "<h1>AIO-CLi</h1><p>Dashboard unavailable.</p>")


@app.get("/splash", response_class=HTMLResponse)
async def splash() -> HTMLResponse:
    """Keep the original splash screen available as a dedicated route."""
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


@app.get("/ui/splash/ma-cli-splash.css")
async def splash_css() -> FileResponse:
    return FileResponse(SPLASH_CSS, media_type="text/css")


@app.get("/ui/dashboard/dashboard.css")
async def dashboard_css() -> FileResponse:
    return FileResponse(DASHBOARD_CSS, media_type="text/css")


@app.get("/ui/dashboard/dashboard.js")
async def dashboard_js() -> FileResponse:
    return FileResponse(DASHBOARD_JS, media_type="application/javascript")


@app.get("/assets/logo/ma-cli-animated.svg")
async def logo_svg() -> FileResponse:
    return FileResponse(LOGO_SVG, media_type="image/svg+xml")
