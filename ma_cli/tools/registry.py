"""Secure, policy-aware tool registry for the MA-CLI runtime."""
from __future__ import annotations

import inspect
import os
import shlex
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..security.runtime_policy import RuntimeSecurity

_SHELL_META = set("|;&<>`$()\n")


class RuntimeGrant:
    """Unforgeable in-process grant. JSON/tool-call payloads cannot produce this."""


RUNTIME_GRANT = RuntimeGrant()


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    risk: str = "standard"
    permissions: frozenset[str] = frozenset()
    required_args: frozenset[str] = frozenset()


class ToolRegistry:
    """Single security choke-point for model-requested tool execution."""

    def __init__(self, workspace: Path | None = None, sandbox: Any | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.security = RuntimeSecurity(self.workspace)
        self.sandbox = sandbox
        self._tools: dict[str, ToolSpec] = {}
        self._audit: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self.register(ToolSpec("read_file", "Read a UTF-8 file inside the workspace.", self.read_file,
                               required_args=frozenset({"path"})))
        self.register(ToolSpec("write_file", "Write a UTF-8 file inside the workspace.", self.write_file,
                               permissions=frozenset({"write"}), required_args=frozenset({"path", "content"})))
        self.register(ToolSpec("edit_file", "Replace text in a workspace file.", self.edit_file,
                               permissions=frozenset({"write"}),
                               required_args=frozenset({"path", "old_text", "new_text"})))
        self.register(ToolSpec("delete_file", "Delete a file inside the workspace.", self.delete_file,
                               "high", frozenset({"write"}), frozenset({"path"})))
        self.register(ToolSpec("list_dir", "List a directory inside the workspace.", self.list_dir))
        self.register(ToolSpec("search", "Search workspace files for a query string.", self.search,
                               required_args=frozenset({"query"})))
        self.register(ToolSpec("glob", "Find files by glob pattern inside the workspace.", self.glob,
                               required_args=frozenset({"pattern"})))
        self.register(ToolSpec("run_command", "Run an approved command in the workspace.", self.run_command,
                               "high", frozenset({"execute"}), frozenset({"command"})))
        self.register(ToolSpec("git", "Run a workspace-bounded git command.", self.git,
                               "high", frozenset({"execute"}), frozenset({"args"})))
        self.register(ToolSpec("http_get", "GET an http(s) URL and return a truncated body.", self.http_get,
                               "high", frozenset({"network"}), frozenset({"url"})))

    def register(self, spec: ToolSpec) -> None:
        if not spec.name or not spec.name.replace("_", "").isalnum():
            raise ValueError("invalid tool name")
        self._tools[spec.name] = spec

    def list(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "description": s.description, "risk": s.risk,
                 "permissions": sorted(s.permissions), "required_args": sorted(s.required_args)}
                for s in self.list()]

    def resolve(self, path: str) -> Path:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("path must be a non-empty string")
        raw = Path(path)
        target = (raw if raw.is_absolute() else self.workspace / raw).resolve()
        try:
            target.relative_to(self.workspace)
        except ValueError as exc:
            raise PermissionError(f"path escapes workspace: {path}") from exc
        return target

    def _record(self, **entry: Any) -> None:
        with self._lock:
            self._audit.append({"timestamp": time.time(), **entry})
            self._audit[:] = self._audit[-1000:]

    def audit_log(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._audit]

    def _validate(self, spec: ToolSpec, kwargs: dict[str, Any]) -> None:
        missing = spec.required_args - kwargs.keys()
        if missing:
            raise ValueError(f"missing required arguments: {sorted(missing)}")
        if spec.name == "run_command" and not isinstance(kwargs.get("command"), str):
            raise TypeError("command must be a string")
        if "path" in kwargs and not isinstance(kwargs["path"], str):
            raise TypeError("path must be a string")
        if "content" in kwargs and not isinstance(kwargs["content"], str):
            raise TypeError("content must be a string")

    def _permission_check(self, spec: ToolSpec, kwargs: dict[str, Any], granted: bool) -> None:
        if spec.risk == "high" and not granted:
            raise PermissionError(f"tool '{spec.name}' requires explicit approval")
        if spec.name == "run_command":
            decision = self.security.authorize_command(kwargs["command"], granted)
            if not decision.allowed:
                raise PermissionError(decision.reason)

    def read_file(self, path: str) -> str:
        return self.resolve(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def edit_file(self, path: str, old_text: str, new_text: str) -> str:
        target = self.resolve(path)
        content = target.read_text(encoding="utf-8")
        if old_text not in content:
            raise ValueError("old_text not found in file")
        target.write_text(content.replace(old_text, new_text, 1), encoding="utf-8")
        return str(target)

    def delete_file(self, path: str) -> str:
        target = self.resolve(path)
        if not target.is_file():
            raise FileNotFoundError(path)
        target.unlink()
        return str(target)

    def list_dir(self, path: str = ".") -> list[str]:
        return [p.name for p in self.resolve(path).iterdir()]

    def search(self, query: str, path: str = ".") -> list[dict[str, Any]]:
        if not query:
            raise ValueError("query cannot be empty")
        root = self.resolve(path)
        hits: list[dict[str, Any]] = []
        for file in root.rglob("*"):
            if not file.is_file() or file.stat().st_size > 1_000_000:
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                if query in line:
                    hits.append({
                        "path": str(file.relative_to(self.workspace)),
                        "line": line_no,
                        "text": line[:200],
                    })
                    if len(hits) >= 200:
                        return hits
        return hits

    def glob(self, pattern: str) -> list[str]:
        if not pattern or ".." in Path(pattern).parts:
            raise ValueError("invalid glob pattern")
        return [str(path.relative_to(self.workspace)) for path in self.workspace.glob(pattern) if path.exists()]

    def run_command(self, command: str, timeout: int = 120, use_sandbox: bool = False) -> dict[str, Any]:
        if not command.strip():
            raise ValueError("command cannot be empty")
        timeout = max(1, min(int(timeout), 900))
        if any(ch in command for ch in _SHELL_META):
            raise PermissionError("shell metacharacters are not allowed")
        if use_sandbox:
            if self.sandbox is None:
                raise PermissionError("sandbox requested but no sandbox manager is attached")
            import asyncio

            from ..sandbox.manager import SandboxUnavailableError
            try:
                result = asyncio.run(self.sandbox.execute("tool-run", command, self.workspace, timeout))
            except SandboxUnavailableError as exc:
                raise PermissionError(str(exc)) from exc
            return {"returncode": result.exit_code, "stdout": result.stdout, "stderr": result.stderr}
        if os.name == "nt":
            argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
        else:
            argv = shlex.split(command, posix=True)
            if not argv:
                raise ValueError("command cannot be empty")
        try:
            r = subprocess.run(argv, cwd=self.workspace, capture_output=True, text=True,
                               timeout=timeout, shell=False, check=False)
            return {"returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr}
        except subprocess.TimeoutExpired as exc:
            return {"returncode": -1, "stdout": exc.stdout or "", "stderr": "command timed out"}

    def git(self, args: str | list[str], timeout: int = 60, granted: bool = False) -> dict[str, Any]:
        from ..git_engine.engine import GitEngine, GitError
        argv = args.split() if isinstance(args, str) else list(args)
        try:
            result = GitEngine(self.workspace).run(argv, approved=granted, timeout=timeout)
        except GitError as exc:
            raise PermissionError(str(exc)) from exc
        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr,
                "success": result.success}

    def http_get(self, url: str, timeout: int = 15) -> dict[str, Any]:
        if not url.startswith(("http://", "https://")):
            raise PermissionError("only http(s) URLs are allowed")
        import httpx
        response = httpx.get(url, timeout=timeout, follow_redirects=False)
        body = response.text[:8000]
        return {"status_code": response.status_code, "body": body, "url": str(response.url)}

    async def execute_async(self, name: str, **kwargs: Any) -> Any:
        import asyncio
        return await asyncio.to_thread(self.execute, name, **kwargs)

    def execute(self, name: str, **kwargs: Any) -> Any:
        started = time.monotonic()
        spec = self.get(name)
        if spec is None:
            self._record(tool=name, status="failed", error="unknown tool")
            raise KeyError(f"unknown tool: {name}")
        grant = kwargs.pop("grant", None)
        kwargs.pop("approved", None)
        granted = grant is RUNTIME_GRANT
        try:
            self._validate(spec, kwargs)
            self._permission_check(spec, kwargs, granted)
            if spec.name == "git":
                kwargs = {**kwargs, "granted": granted}
            result = spec.handler(**kwargs)
            if inspect.isawaitable(result):
                raise RuntimeError("async handlers must be invoked through execute_async")
            self._record(tool=name, risk=spec.risk, status="success",
                         duration_ms=int((time.monotonic() - started) * 1000))
            return result
        except Exception as exc:
            self._record(tool=name, risk=spec.risk, status="failed", error=str(exc),
                         duration_ms=int((time.monotonic() - started) * 1000))
            raise


_registry: ToolRegistry | None = None


def get_tool_registry(workspace: Path | None = None) -> ToolRegistry:
    global _registry
    resolved = workspace.resolve() if workspace else Path.cwd().resolve()
    if _registry is None or _registry.workspace != resolved:
        _registry = ToolRegistry(resolved)
    return _registry
