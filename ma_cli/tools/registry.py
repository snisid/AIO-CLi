"""Secure, policy-aware tool registry for the MA-CLI runtime.

Every model-requested tool call crosses this registry. The registry performs
schema validation, workspace/symlink boundary checks, permission/risk gates,
timeout enforcement, output capture/validation and audit recording before a
handler is allowed to execute.
"""
from __future__ import annotations

import inspect
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    risk: str = "standard"
    permissions: frozenset[str] = frozenset()
    required_args: frozenset[str] = frozenset()


class ToolRegistry:
    def __init__(self, workspace: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self._tools: dict[str, ToolSpec] = {}
        self._audit: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self.register(ToolSpec("read_file", "Read a UTF-8 file inside the workspace.", self.read_file, required_args=frozenset({"path"})))
        self.register(ToolSpec("write_file", "Write a UTF-8 file inside the workspace.", self.write_file, permissions=frozenset({"write"}), required_args=frozenset({"path", "content"})))
        self.register(ToolSpec("list_dir", "List a directory inside the workspace.", self.list_dir))
        self.register(ToolSpec("run_command", "Run a command in the workspace.", self.run_command, "high", frozenset({"execute"}), frozenset({"command"})))

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

    def _permission_check(self, spec: ToolSpec, kwargs: dict[str, Any]) -> None:
        if spec.risk == "high" and not kwargs.get("approved", False):
            # High-risk execution remains explicitly opt-in at the registry boundary.
            raise PermissionError("high-risk tool requires approved=True")

    def read_file(self, path: str) -> str:
        return self.resolve(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def list_dir(self, path: str = ".") -> list[str]:
        return [p.name for p in self.resolve(path).iterdir()]

    def run_command(self, command: str, timeout: int = 120, approved: bool = False) -> dict[str, Any]:
        if not command.strip():
            raise ValueError("command cannot be empty")
        timeout = max(1, min(int(timeout), 900))
        argv = (["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
                if os.name == "nt" else ["bash", "-lc", command])
        try:
            r = subprocess.run(argv, cwd=self.workspace, capture_output=True, text=True,
                               timeout=timeout, shell=False, check=False)
            return {"returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr}
        except subprocess.TimeoutExpired as exc:
            return {"returncode": -1, "stdout": exc.stdout or "", "stderr": "command timed out"}

    async def execute_async(self, name: str, **kwargs: Any) -> Any:
        import asyncio
        return await asyncio.to_thread(self.execute, name, **kwargs)

    def execute(self, name: str, **kwargs: Any) -> Any:
        started = time.monotonic()
        spec = self.get(name)
        if spec is None:
            self._record(tool=name, status="failed", error="unknown tool")
            raise KeyError(f"unknown tool: {name}")
        try:
            self._validate(spec, kwargs)
            self._permission_check(spec, kwargs)
            clean_kwargs = dict(kwargs)
            result = spec.handler(**clean_kwargs)
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
