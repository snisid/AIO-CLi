from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ma_cli.github import GitHubAPIError, GitHubClient
from ma_cli.github.workspace import GitHubWorkspaceError, import_repository
from ma_cli.runtime.connectors import ConnectorControlError, ConnectorRegistry
from ma_cli.runtime.control import RuntimeController, RuntimeControlError


ROOT = Path(__file__).resolve().parent
UI_ROOT = ROOT / "ui"
ASSETS_ROOT = ROOT / "assets"
SPLASH_HTML = UI_ROOT / "splash" / "splash.html"
DASHBOARD_HTML = UI_ROOT / "dashboard" / "dashboard.html"
WORKSPACE_ROOT = Path(os.getenv("AIO_CLI_WORKSPACE_ROOT", ROOT / ".aio-workspaces")).expanduser()
runtime_controller = RuntimeController(WORKSPACE_ROOT)
connector_registry = ConnectorRegistry()

app = FastAPI(title="AIO-CLi", version="1.0.0", description="Multi-Agent Autonomous Coding Platform")


class GitHubImportRequest(BaseModel):
    repository_url: str = Field(min_length=1, max_length=500)
    folder_name: str | None = Field(default=None, max_length=120)


class GitHubPullRequestRequest(BaseModel):
    repository: str = Field(min_length=3, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    head: str = Field(min_length=1, max_length=200)
    base: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=10000)
    draft: bool = False


class SSHConfigureRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    user: str = Field(min_length=1, max_length=120)
    port: int = Field(default=22, ge=1, le=65535)


class CloudConfigureRequest(BaseModel):
    endpoint: str = Field(min_length=8, max_length=500)


class RemoteDispatchRequest(BaseModel):
    target: str = Field(min_length=1, max_length=32)
    task: str = Field(min_length=1, max_length=10000)


class ExtensionInstallRequest(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    kind: str = Field(pattern="^(plugin|skill|connector)$")
    version: str = Field(default="0.0.0", max_length=40)
    source: str = Field(default="marketplace", max_length=500)


class ExtensionRemoveRequest(BaseModel):
    id: str = Field(min_length=1, max_length=120)


class ConnectorConfigureRequest(BaseModel):
    base_url: str | None = Field(default=None, max_length=500)


class ConnectorRequest(BaseModel):
    path: str = Field(default="", max_length=500)
    method: str = Field(default="GET", pattern="^(GET|POST|PUT|PATCH|DELETE)$")
    payload: dict[str, Any] | None = None


def _html_file(path: Path, fallback: str) -> HTMLResponse:
    if not path.is_file():
        return HTMLResponse(fallback, status_code=200)
    html = path.read_text(encoding="utf-8")
    if path == DASHBOARD_HTML:
        html = html.replace('</body>', '<script src="/ui/dashboard/runtime-control.js?v=runtime1"></script>\n</body>')
    return HTMLResponse(html)


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    return _html_file(DASHBOARD_HTML, "<h1>AIO-CLi</h1><p>Runtime online.</p><p><a href='/dashboard'>Open dashboard</a></p>")


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return _html_file(DASHBOARD_HTML, "<h1>AIO-CLi</h1><p>Dashboard unavailable.</p>")


@app.get("/dashboard/", include_in_schema=False)
async def dashboard_trailing_slash() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@app.get("/splash", response_class=HTMLResponse)
async def splash() -> HTMLResponse:
    if not SPLASH_HTML.is_file():
        return HTMLResponse("<h1>AIO-CLi</h1><p>Runtime online.</p>", status_code=200)
    html = SPLASH_HTML.read_text(encoding="utf-8")
    html = html.replace('href="ma-cli-splash.css"', 'href="/ui/splash/ma-cli-splash.css"')
    html = html.replace('src="../../assets/logo/ma-cli-animated.svg"', 'src="/assets/logo/ma-cli-animated.svg"')
    return HTMLResponse(html)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "aio-cli"}


@app.get("/api/status")
async def api_status() -> dict[str, str]:
    return {"service": "AIO-CLi", "runtime": "online", "deployment": "vercel", "dashboard": "/dashboard"}


@app.get("/api/runtime/environments")
async def runtime_environments() -> list[dict[str, Any]]:
    return runtime_controller.environments()


@app.post("/api/runtime/cloud/configure")
async def runtime_cloud_configure(request: CloudConfigureRequest) -> dict[str, Any]:
    try:
        return runtime_controller.configure_cloud(request.endpoint)
    except RuntimeControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/runtime/cloud/check")
async def runtime_cloud_check() -> dict[str, Any]:
    try:
        return await runtime_controller.cloud_check()
    except RuntimeControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/runtime/ssh/configure")
async def runtime_ssh_configure(request: SSHConfigureRequest) -> dict[str, Any]:
    try:
        return runtime_controller.configure_ssh(request.host, request.user, request.port)
    except RuntimeControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/runtime/ssh/check")
async def runtime_ssh_check() -> dict[str, Any]:
    try:
        return await runtime_controller.ssh_check()
    except RuntimeControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/runtime/remote/dispatch")
async def runtime_remote_dispatch(request: RemoteDispatchRequest) -> dict[str, Any]:
    try:
        return runtime_controller.dispatch_remote(request.target, request.task)
    except RuntimeControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runtime/remote/jobs")
async def runtime_remote_jobs() -> list[dict[str, Any]]:
    return runtime_controller.remote_jobs_list()


@app.get("/api/extensions")
async def list_extensions() -> list[dict[str, Any]]:
    return runtime_controller.extensions()


@app.post("/api/extensions/install")
async def install_extension(request: ExtensionInstallRequest) -> dict[str, Any]:
    try:
        return runtime_controller.install_extension(request.id, request.name, request.kind, request.version, request.source)
    except RuntimeControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/extensions/remove")
async def remove_extension(request: ExtensionRemoveRequest) -> dict[str, Any]:
    try:
        return runtime_controller.uninstall_extension(request.id)
    except RuntimeControlError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/connectors")
async def connectors() -> list[dict[str, Any]]:
    return connector_registry.list()


@app.post("/api/connectors/{connector_id}/configure")
async def configure_connector(connector_id: str, request: ConnectorConfigureRequest) -> dict[str, Any]:
    try:
        return connector_registry.configure(connector_id, request.base_url)
    except ConnectorControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/connectors/{connector_id}/check")
async def check_connector(connector_id: str) -> dict[str, Any]:
    try:
        return await connector_registry.check(connector_id)
    except ConnectorControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/connectors/{connector_id}/request")
async def connector_request(connector_id: str, request: ConnectorRequest) -> dict[str, Any]:
    try:
        return await connector_registry.request(connector_id, request.path, request.method, request.payload)
    except ConnectorControlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/github/status")
async def github_status() -> dict[str, Any]:
    client = GitHubClient()
    try:
        return await client.status()
    except GitHubAPIError as exc:
        return {"connected": False, "authenticated": True, "provider": "GitHub", "message": str(exc), "status_code": exc.status_code}


@app.get("/api/github/repository")
async def github_repository(repository: str = Query(min_length=3, max_length=500)) -> dict[str, Any]:
    try:
        repo = await GitHubClient().repository(repository)
    except (GitHubAPIError, ValueError) as exc:
        raise HTTPException(status_code=getattr(exc, "status_code", 400) or 400, detail=str(exc)) from exc
    return {"full_name": repo.full_name, "default_branch": repo.default_branch, "private": repo.private, "html_url": repo.html_url, "clone_url": repo.clone_url, "description": repo.description}


@app.get("/api/github/pulls")
async def github_pulls(repository: str = Query(min_length=3, max_length=200), state: str = Query(default="open", pattern="^(open|closed|all)$"), limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
    try:
        return await GitHubClient().pull_requests(repository, state=state, limit=limit)
    except (GitHubAPIError, ValueError) as exc:
        raise HTTPException(status_code=getattr(exc, "status_code", 400) or 400, detail=str(exc)) from exc


@app.get("/api/github/issues")
async def github_issues(repository: str = Query(min_length=3, max_length=200), state: str = Query(default="open", pattern="^(open|closed|all)$"), limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
    try:
        return await GitHubClient().issues(repository, state=state, limit=limit)
    except (GitHubAPIError, ValueError) as exc:
        raise HTTPException(status_code=getattr(exc, "status_code", 400) or 400, detail=str(exc)) from exc


@app.post("/api/github/import")
async def github_import(request: GitHubImportRequest) -> dict[str, str]:
    try:
        return import_repository(request.repository_url, WORKSPACE_ROOT, request.folder_name)
    except (GitHubWorkspaceError, OSError, subprocess.SubprocessError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/github/pulls")
async def github_create_pull_request(request: GitHubPullRequestRequest) -> dict[str, Any]:
    try:
        return await GitHubClient().create_pull_request(request.repository, request.title, request.head, request.base, request.body, request.draft)
    except (GitHubAPIError, ValueError) as exc:
        raise HTTPException(status_code=getattr(exc, "status_code", 400) or 400, detail=str(exc)) from exc


app.mount("/ui", StaticFiles(directory=UI_ROOT, check_dir=True), name="ui")
app.mount("/assets", StaticFiles(directory=ASSETS_ROOT, check_dir=True), name="assets")
