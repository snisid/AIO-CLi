"""Policy-aware filesystem and command tools."""
from __future__ import annotations
import os, subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable[..., Any]
    risk: str = "standard"

class ToolRegistry:
    def __init__(self, workspace: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self._tools = {}
        self.register(ToolSpec("read_file", "Read a UTF-8 file.", self.read_file))
        self.register(ToolSpec("write_file", "Write a UTF-8 file.", self.write_file))
        self.register(ToolSpec("list_dir", "List a directory.", self.list_dir))
        self.register(ToolSpec("run_command", "Run a command in the workspace.", self.run_command, "high"))

    def register(self, spec: ToolSpec) -> None: self._tools[spec.name] = spec
    def list(self) -> list[ToolSpec]: return list(self._tools.values())
    def get(self, name: str) -> ToolSpec | None: return self._tools.get(name)

    def resolve(self, path: str) -> Path:
        p = Path(path)
        target = (p if p.is_absolute() else self.workspace / p).resolve()
        if target != self.workspace and self.workspace not in target.parents:
            raise PermissionError(f"path escapes workspace: {path}")
        return target

    def read_file(self, path: str) -> str:
        return self.resolve(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def list_dir(self, path: str = ".") -> list[str]:
        return [p.name for p in self.resolve(path).iterdir()]

    def run_command(self, command: str, timeout: int = 120) -> dict[str, Any]:
        if not command.strip(): raise ValueError("command cannot be empty")
        argv = ["powershell.exe","-NoProfile","-NonInteractive","-Command",command] if os.name == "nt" else ["bash","-lc",command]
        r = subprocess.run(argv, cwd=self.workspace, capture_output=True, text=True,
                           timeout=max(1, min(timeout, 900)), shell=False)
        return {"returncode": r.returncode, "stdout": r.stdout, "stderr": r.stderr}

    def execute(self, name: str, **kwargs: Any) -> Any:
        spec = self.get(name)
        if not spec: raise KeyError(f"unknown tool: {name}")
        return spec.handler(**kwargs)

_registry = None
def get_tool_registry(workspace: Path | None = None) -> ToolRegistry:
    global _registry
    if _registry is None or (workspace and _registry.workspace != workspace.resolve()):
        _registry = ToolRegistry(workspace)
    return _registry
