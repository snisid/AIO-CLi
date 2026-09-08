from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass
class RuntimeTarget:
    id: str
    name: str
    kind: str
    endpoint: str | None
    status: str = "configured"
    workspace: str | None = None
    command: str | None = None


@dataclass
class InstalledExtension:
    id: str
    name: str
    kind: str
    version: str
    source: str
    status: str


class RuntimeControlError(RuntimeError):
    pass


class RuntimeController:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.targets: dict[str, RuntimeTarget] = {
            "local": RuntimeTarget("local", "Local", "local", None, "ready", str(self.workspace_root)),
            "cloud": RuntimeTarget("cloud", "Cloud", "cloud", os.getenv("AIO_CLI_CLOUD_ENDPOINT")),
            "ssh": RuntimeTarget("ssh", "SSH", "ssh", None),
            "wsl": RuntimeTarget("wsl", "WSL", "wsl", None),
        }
        self.installed: dict[str, InstalledExtension] = {}
        self.remote_jobs: dict[str, dict[str, Any]] = {}

    def environments(self) -> list[dict[str, Any]]:
        return [asdict(t) for t in self.targets.values()]

    def configure_ssh(self, host: str, user: str, port: int = 22) -> dict[str, Any]:
        host = host.strip()
        user = user.strip()
        if not host or not user or not 1 <= port <= 65535:
            raise RuntimeControlError("SSH host, user and valid port are required")
        target = self.targets["ssh"]
        target.endpoint = f"ssh://{user}@{host}:{port}"
        target.status = "configured"
        target.command = f"ssh -p {port} {user}@{host}"
        return asdict(target)

    async def ssh_check(self) -> dict[str, Any]:
        target = self.targets["ssh"]
        if not target.endpoint:
            raise RuntimeControlError("SSH target is not configured")
        parsed = urlparse(target.endpoint)
        command = ["ssh", "-p", str(parsed.port or 22), f"{parsed.username}@{parsed.hostname}", "printf", "AIO-CLI-REMOTE-OK"]
        try:
            completed = await asyncio.to_thread(
                subprocess.run,
                command,
                capture_output=True,
                text=True,
                timeout=12,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeControlError(f"SSH check failed: {exc}") from exc
        target.status = "ready" if completed.returncode == 0 and completed.stdout.strip() == "AIO-CLI-REMOTE-OK" else "unreachable"
        return {"target": asdict(target), "returncode": completed.returncode, "output": completed.stdout[-4000:], "error": completed.stderr[-4000:]}

    def configure_cloud(self, endpoint: str) -> dict[str, Any]:
        endpoint = endpoint.strip().rstrip("/")
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeControlError("Cloud endpoint must be an absolute http(s) URL")
        self.targets["cloud"].endpoint = endpoint
        self.targets["cloud"].status = "configured"
        return asdict(self.targets["cloud"])

    async def cloud_check(self) -> dict[str, Any]:
        import httpx

        endpoint = self.targets["cloud"].endpoint
        if not endpoint:
            return {"target": asdict(self.targets["cloud"]), "reachable": False, "message": "No cloud endpoint configured"}
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(f"{endpoint}/health")
            reachable = response.status_code < 500
        except httpx.HTTPError as exc:
            return {"target": asdict(self.targets["cloud"]), "reachable": False, "message": str(exc)}
        self.targets["cloud"].status = "ready" if reachable else "degraded"
        return {"target": asdict(self.targets["cloud"]), "reachable": reachable, "status_code": response.status_code}

    def dispatch_remote(self, target_id: str, task: str) -> dict[str, Any]:
        if target_id not in self.targets or target_id == "local":
            raise RuntimeControlError("A remote target must be selected")
        task = task.strip()
        if not task:
            raise RuntimeControlError("Remote task cannot be empty")
        job_id = f"remote-{len(self.remote_jobs) + 1}"
        job = {"id": job_id, "target": target_id, "task": task, "status": "queued"}
        self.remote_jobs[job_id] = job
        return job

    def remote_jobs_list(self) -> list[dict[str, Any]]:
        return list(self.remote_jobs.values())

    def install_extension(self, extension_id: str, name: str, kind: str, version: str, source: str) -> dict[str, Any]:
        allowed_kinds = {"plugin", "skill", "connector"}
        if kind not in allowed_kinds:
            raise RuntimeControlError("Unsupported extension kind")
        extension_id = extension_id.strip().lower()
        if not extension_id or not name.strip():
            raise RuntimeControlError("Extension id and name are required")
        record = InstalledExtension(extension_id, name.strip(), kind, version.strip() or "0.0.0", source.strip() or "local", "installed")
        self.installed[extension_id] = record
        marker = self.workspace_root / ".aio-cli" / "extensions" / f"{extension_id}.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(__import__("json").dumps(asdict(record), indent=2), encoding="utf-8")
        return asdict(record)

    def uninstall_extension(self, extension_id: str) -> dict[str, Any]:
        record = self.installed.pop(extension_id, None)
        marker = self.workspace_root / ".aio-cli" / "extensions" / f"{extension_id}.json"
        if marker.exists():
            marker.unlink()
        if not record:
            raise RuntimeControlError("Extension is not installed")
        return {"id": extension_id, "status": "removed"}

    def extensions(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in self.installed.values()]
