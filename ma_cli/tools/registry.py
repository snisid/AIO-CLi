"""Secure native tool registry and execution choke-point."""
from __future__ import annotations

import asyncio
import inspect
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..browser import BrowserEngine
from ..mcp import MCPClient
from ..security.runtime_policy import RuntimeSecurity


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    risk: str = "standard"
    permissions: frozenset[str] = frozenset()
    required_args: frozenset[str] = frozenset()
    timeout_seconds: int = 120


class ToolRegistry:
    """Single security choke-point for model-requested tool execution."""

    def __init__(self, workspace: Path | None = None, *, browser: BrowserEngine | None = None,
                 mcp_clients: dict[str, MCPClient] | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.security = RuntimeSecurity(self.workspace)
        self.browser = browser
        self.mcp_clients = mcp_clients or {}
        self._tools: dict[str, ToolSpec] = {}
        self._audit: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self.register(ToolSpec("read_file", "Read a UTF-8 file inside the workspace.", self.read_file,
                               required_args=frozenset({"path"}), permissions=frozenset({"read"})))
        self.register(ToolSpec("write_file", "Write a UTF-8 file inside the workspace.", self.write_file,
                               permissions=frozenset({"write"}), required_args=frozenset({"path", "content"})))
        self.register(ToolSpec("list_dir", "List a directory inside the workspace.", self.list_dir,
                               permissions=frozenset({"read"})))
        self.register(ToolSpec("search_text", "Search text recursively inside the workspace.", self.search_text,
                               permissions=frozenset({"read"}), required_args=frozenset({"query"})))
        self.register(ToolSpec("apply_patch", "Apply a unified diff limited to workspace files.", self.apply_patch,
                               permissions=frozenset({"write"}), required_args=frozenset({"patch"})))
        self.register(ToolSpec("run_command", "Run an explicitly approved command in the workspace.", self.run_command,
                               "high", frozenset({"execute"}), frozenset({"command"}), 900))
        self.register(ToolSpec("browser_navigate", "Navigate the controlled browser to an approved URL.", self.browser_navigate,
                               "external", frozenset({"network", "external"}), frozenset({"url"}), 60))
        self.register(ToolSpec("browser_snapshot", "Read the current controlled browser page.", self.browser_snapshot,
                               "external", frozenset({"network"}), frozenset(), 60))
        self.register(ToolSpec("browser_screenshot", "Capture the current controlled browser page.", self.browser_screenshot,
                               "external", frozenset({"network"}), frozenset(), 60))
        self.register(ToolSpec("browser_click", "Click an element in the controlled browser.", self.browser_click,
                               "external", frozenset({"network"}), frozenset({"selector"}), 60))
        self.register(ToolSpec("browser_type", "Type into an element in the controlled browser.", self.browser_type,
                               "external", frozenset({"network"}), frozenset({"selector", "text"}), 60))
        self.register(ToolSpec("browser_press", "Press a key in the controlled browser.", self.browser_press,
                               "external", frozenset({"network"}), frozenset({"selector", "key"}), 60))
        self.register(ToolSpec("mcp_call", "Call a validated tool exposed by an MCP server.", self.mcp_call,
                               "external", frozenset({"external"}), frozenset({"server", "tool"}), 120))

    def register(self, spec: ToolSpec) -> None:
        if not spec.name or not spec.name.replace("_", "").isalnum():
            raise ValueError("invalid tool name")
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def list(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "description": s.description, "risk": s.risk,
                 "permissions": sorted(s.permissions), "required_args": sorted(s.required_args),
                 "timeout_seconds": s.timeout_seconds} for s in self.list()]

    def resolve(self, path: str) -> Path:
        return self.security.resolve_workspace_path(path)

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
        for key in ("path", "content", "url", "selector", "text", "key", "server", "tool"):
            if key in kwargs and not isinstance(kwargs[key], str):
                raise TypeError(f"{key} must be a string")

    def _permission_check(self, spec: ToolSpec, kwargs: dict[str, Any]) -> None:
        if spec.name == "run_command":
            if not bool(kwargs.get("approved", False)):
                raise PermissionError("explicit approval required for command execution")
            decision = self.security.authorize_command(kwargs["command"], approved=True)
            if not decision.allowed:
                raise PermissionError(decision.reason)
        elif spec.risk == "external" and not bool(kwargs.get("approved", False)):
            raise PermissionError(f"explicit approval required for external tool '{spec.name}'")

    def read_file(self, path: str) -> str:
        return self.resolve(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def list_dir(self, path: str = ".") -> list[str]:
        return sorted(p.name for p in self.resolve(path).iterdir())

    def search_text(self, query: str, path: str = ".", max_results: int = 100) -> list[dict[str, Any]]:
        if not query:
            raise ValueError("query cannot be empty")
        root = self.resolve(path)
        results: list[dict[str, Any]] = []
        for file in root.rglob("*"):
            if not file.is_file() or file.is_symlink():
                continue
            try:
                text = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if query.casefold() in line.casefold():
                    results.append({"path": str(file.relative_to(self.workspace)), "line": lineno, "text": line[:500]})
                    if len(results) >= max(1, min(max_results, 1000)):
                        return results
        return results

    def apply_patch(self, patch: str) -> dict[str, Any]:
        if not patch.strip():
            raise ValueError("patch cannot be empty")
        decision = self.security.authorize_command("git apply --whitespace=nowarn", approved=True)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        proc = subprocess.run(["git", "apply", "--whitespace=nowarn", "-"], cwd=self.workspace,
                              input=patch, text=True, capture_output=True, timeout=120, shell=False)
        return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}

    def run_command(self, command: str, timeout: int = 120, approved: bool = False) -> dict[str, Any]:
        if not approved:
            raise PermissionError("explicit approval required for command execution")
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

    def _require_browser(self) -> BrowserEngine:
        if self.browser is None:
            self.browser = BrowserEngine()
        return self.browser

    async def browser_navigate(self, url: str, approved: bool = False) -> dict[str, object]:
        browser = self._require_browser()
        await browser.start()
        return await browser.navigate(url)

    async def browser_snapshot(self, approved: bool = False) -> dict[str, object]:
        return await self._require_browser().snapshot()

    async def browser_screenshot(self, path: str | None = None, approved: bool = False) -> dict[str, object]:
        data = await self._require_browser().screenshot(path)
        return {"bytes": len(data), "path": path}

    async def browser_click(self, selector: str, approved: bool = False) -> dict[str, object]:
        await self._require_browser().click(selector)
        return {"selector": selector, "status": "clicked"}

    async def browser_type(self, selector: str, text: str, approved: bool = False) -> dict[str, object]:
        await self._require_browser().type_text(selector, text)
        return {"selector": selector, "status": "typed"}

    async def browser_press(self, selector: str, key: str, approved: bool = False) -> dict[str, object]:
        await self._require_browser().press(selector, key)
        return {"selector": selector, "key": key, "status": "pressed"}

    async def mcp_call(self, server: str, tool: str, arguments: dict[str, Any] | None = None,
                       approved: bool = False) -> dict[str, Any]:
        client = self.mcp_clients.get(server)
        if client is None:
            raise KeyError(f"unknown MCP server: {server}")
        if not client.connected:
            await client.connect()
        result = await client.call_tool(tool, arguments or {})
        return result

    async def execute_async(self, name: str, **kwargs: Any) -> Any:
        spec = self.get(name)
        if spec is None:
            raise KeyError(f"unknown tool: {name}")
        self._validate(spec, kwargs)
        self._permission_check(spec, kwargs)
        started = time.monotonic()
        try:
            result = spec.handler(**kwargs)
            if inspect.isawaitable(result):
                result = await asyncio.wait_for(result, timeout=max(1, spec.timeout_seconds))
            self._record(tool=name, risk=spec.risk, status="success",
                         duration_ms=int((time.monotonic() - started) * 1000))
            return result
        except Exception as exc:
            self._record(tool=name, risk=spec.risk, status="failed", error=str(exc),
                         duration_ms=int((time.monotonic() - started) * 1000))
            raise

    async def execute_many(self, calls: list[dict[str, Any]], max_concurrency: int = 4) -> list[Any]:
        semaphore = asyncio.Semaphore(max(1, min(max_concurrency, 16)))
        async def one(call: dict[str, Any]) -> Any:
            async with semaphore:
                return await self.execute_async(call["name"], **call.get("arguments", {}))
        return await asyncio.gather(*(one(c) for c in calls), return_exceptions=True)

    def execute(self, name: str, **kwargs: Any) -> Any:
        spec = self.get(name)
        if spec is None:
            self._record(tool=name, status="failed", error="unknown tool")
            raise KeyError(f"unknown tool: {name}")
        if inspect.iscoroutinefunction(spec.handler):
            raise RuntimeError("async tool handlers must be invoked through execute_async")
        started = time.monotonic()
        try:
            self._validate(spec, kwargs)
            self._permission_check(spec, kwargs)
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
