"""Secure, schema-driven tool registry.

Every tool invocation follows:
registry -> schema -> validation -> permission -> risk -> sandbox -> execution
-> timeout/cancellation -> output capture -> audit -> result validation.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ..security.permission_engine import PermissionEngine, PermissionLevel, PermissionPolicy, get_permission_engine


@dataclass(frozen=True)
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, dict[str, Any]] = field(default_factory=dict)
    returns: str = "object"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    risk: str = "standard"
    schema: ToolSchema | None = None
    timeout_seconds: int = 120
    action: str = "tool"


@dataclass
class ToolAudit:
    invocation_id: str
    tool: str
    risk: str
    allowed: bool
    started: float
    duration_ms: int
    status: str
    error: str | None = None


class ToolRegistry:
    def __init__(self, workspace: Path | None = None, permission_engine: PermissionEngine | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.permission_engine = permission_engine or self._workspace_policy()
        self._tools: dict[str, ToolSpec] = {}
        self._audit: list[ToolAudit] = []
        self._register_builtin_tools()

    def _workspace_policy(self) -> PermissionEngine:
        # The workspace is the only filesystem root exposed to native tools.
        # Command danger patterns remain active from PermissionPolicy.
        policy = PermissionPolicy(name="workspace-bound", default_level=PermissionLevel.STANDARD)
        escaped = re.escape(str(self.workspace))
        policy.allowed_paths = [str(self.workspace)]
        policy.denied_paths = []
        policy.add_rule(__import__("ma_cli.security.permission_engine", fromlist=["PermissionRule"]).PermissionRule("read_file", PermissionLevel.READ_ONLY, [f"^{escaped}(?:$|.*)"], []))
        policy.add_rule(__import__("ma_cli.security.permission_engine", fromlist=["PermissionRule"]).PermissionRule("write_file", PermissionLevel.STANDARD, [f"^{escaped}(?:$|.*)"], []))
        policy.add_rule(__import__("ma_cli.security.permission_engine", fromlist=["PermissionRule"]).PermissionRule("list_dir", PermissionLevel.READ_ONLY, [f"^{escaped}(?:$|.*)"], []))
        policy.add_rule(__import__("ma_cli.security.permission_engine", fromlist=["PermissionRule"]).PermissionRule("run_command", PermissionLevel.STANDARD, [], [], False))
        return PermissionEngine(policy)

    def _register_builtin_tools(self) -> None:
        self.register(ToolSpec("read_file", "Read a UTF-8 file.", self.read_file, "standard", ToolSchema("read_file", "Read a UTF-8 file.", {"path": {"type": "string", "required": True}}), action="read_file"))
        self.register(ToolSpec("write_file", "Write a UTF-8 file.", self.write_file, "elevated", ToolSchema("write_file", "Write a UTF-8 file.", {"path": {"type": "string", "required": True}, "content": {"type": "string", "required": True}}), action="write_file"))
        self.register(ToolSpec("list_dir", "List a directory.", self.list_dir, "standard", ToolSchema("list_dir", "List a directory.", {"path": {"type": "string"}}), action="list_dir"))
        self.register(ToolSpec("run_command", "Run a command inside the workspace policy boundary.", self.run_command, "high", ToolSchema("run_command", "Run a command.", {"command": {"type": "string", "required": True}, "timeout": {"type": "integer", "minimum": 1, "maximum": 900}}), 900, "run_command"))

    def register(self, spec: ToolSpec) -> None:
        if not spec.name or not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", spec.name):
            raise ValueError("invalid tool name")
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        if not callable(spec.handler):
            raise TypeError("tool handler must be callable")
        self._tools[spec.name] = spec

    def list(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def schemas(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "description": s.description, "parameters": s.schema.parameters if s.schema else {}} for s in self._tools.values()]

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def resolve(self, path: str) -> Path:
        if not isinstance(path, str) or not path.strip():
            raise ValueError("path cannot be empty")
        raw = Path(path)
        target = (raw if raw.is_absolute() else self.workspace / raw).resolve(strict=False)
        if target != self.workspace and self.workspace not in target.parents:
            raise PermissionError(f"path escapes workspace: {path}")
        real = target.resolve(strict=False)
        if real != self.workspace and self.workspace not in real.parents:
            raise PermissionError(f"symlink escapes workspace: {path}")
        return real

    @staticmethod
    def _validate(spec: ToolSpec, kwargs: dict[str, Any]) -> None:
        schema = spec.schema
        if not schema:
            return
        for name, definition in schema.parameters.items():
            if definition.get("required") and name not in kwargs:
                raise ValueError(f"missing required argument: {name}")
            if name not in kwargs:
                continue
            value = kwargs[name]
            expected = definition.get("type")
            if expected == "string" and not isinstance(value, str):
                raise TypeError(f"{name} must be a string")
            if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
                raise TypeError(f"{name} must be an integer")
            if expected == "integer" and (value < definition.get("minimum", value) or value > definition.get("maximum", value)):
                raise ValueError(f"{name} outside allowed range")
        unknown = set(kwargs) - set(schema.parameters)
        if unknown:
            raise ValueError(f"unknown arguments: {sorted(unknown)}")

    def _security_check(self, spec: ToolSpec, kwargs: dict[str, Any]) -> None:
        path = kwargs.get("path")
        command = kwargs.get("command")
        if path:
            path = str(self.resolve(path))
        allowed, level, approval = self.permission_engine.check(spec.action, path=path, command=command)
        if not allowed:
            raise PermissionError(f"tool denied by policy: {spec.name}")
        if approval or level in (PermissionLevel.CRITICAL, PermissionLevel.DANGEROUS):
            raise PermissionError(f"tool requires explicit approval: {spec.name}")

    async def execute_async(self, name: str, **kwargs: Any) -> Any:
        spec = self.get(name)
        if not spec:
            raise KeyError(f"unknown tool: {name}")
        invocation_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        started = loop.time()
        status, error = "failed", None
        try:
            self._validate(spec, kwargs)
            self._security_check(spec, kwargs)
            handler = spec.handler
            if inspect.iscoroutinefunction(handler):
                result = await asyncio.wait_for(handler(**kwargs), timeout=spec.timeout_seconds)
            else:
                result = await asyncio.wait_for(asyncio.to_thread(handler, **kwargs), timeout=spec.timeout_seconds)
            self._validate_result(result)
            status = "success"
            return result
        except asyncio.TimeoutError:
            error = f"tool timed out after {spec.timeout_seconds}s"
            raise TimeoutError(error) from None
        except Exception as exc:
            error = str(exc)
            raise
        finally:
            duration_ms = int((loop.time() - started) * 1000)
            self._audit.append(ToolAudit(invocation_id, name, spec.risk, status == "success", started, duration_ms, status, error))

    def execute(self, name: str, **kwargs: Any) -> Any:
        return asyncio.run(self.execute_async(name, **kwargs))

    @staticmethod
    def _validate_result(result: Any) -> None:
        if result is None:
            raise ValueError("tool returned no result")
        try:
            json.dumps(result, default=str)
        except (TypeError, ValueError) as exc:
            raise ValueError("tool result is not serializable") from exc

    def audit_log(self) -> list[dict[str, Any]]:
        return [a.__dict__.copy() for a in self._audit]

    def read_file(self, path: str) -> str:
        return self.resolve(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        temp.write_text(content, encoding="utf-8")
        os.replace(temp, target)
        return str(target)

    def list_dir(self, path: str = ".") -> list[str]:
        return sorted(p.name for p in self.resolve(path).iterdir())

    def run_command(self, command: str, timeout: int = 120) -> dict[str, Any]:
        if not command.strip():
            raise ValueError("command cannot be empty")
        if os.name == "nt":
            argv = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
        else:
            argv = ["bash", "-lc", command]
        proc = subprocess.Popen(argv, cwd=self.workspace, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False)
        try:
            stdout, stderr = proc.communicate(timeout=max(1, min(timeout, 900)))
        except subprocess.TimeoutExpired:
            proc.kill(); stdout, stderr = proc.communicate()
            raise TimeoutError(f"command timed out after {timeout}s")
        return {"returncode": proc.returncode, "stdout": stdout, "stderr": stderr}

    def clear_audit(self) -> None:
        self._audit.clear()


_registry: ToolRegistry | None = None

def get_tool_registry(workspace: Path | None = None) -> ToolRegistry:
    global _registry
    target = (workspace or Path.cwd()).resolve()
    if _registry is None or _registry.workspace != target:
        _registry = ToolRegistry(target)
    return _registry
