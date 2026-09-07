"""Allow-listed plugin loader. Plugins are data-only; source is never executed."""
from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_FORBIDDEN = {
    "eval", "exec", "compile", "__import__", "open", "input",
    "os", "subprocess", "socket", "shutil", "ctypes", "pathlib", "sys",
    "builtins", "importlib", "pty", "pickle", "marshal",
}


class PluginError(RuntimeError):
    """Raised when a plugin cannot be loaded safely."""


@dataclass
class PluginSpec:
    name: str
    path: Path
    version: str = "0.0.0"
    description: str = ""
    enabled: bool = False
    loaded: bool = False


class PluginEngine:
    def __init__(self, plugin_dir: Path | None = None, allow_unsigned: bool = False):
        self.plugin_dir = plugin_dir or (Path.home() / ".ma-cli" / "plugins")
        self.allow_unsigned = allow_unsigned
        self._loaded: dict[str, dict[str, Any]] = {}

    def discover(self) -> list[PluginSpec]:
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        specs: list[PluginSpec] = []
        for path in sorted(self.plugin_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            module = self.plugin_dir / str(data.get("module", path.stem + ".py"))
            specs.append(PluginSpec(
                name=str(data.get("name") or path.stem),
                path=module,
                version=str(data.get("version", "0.0.0")),
                description=str(data.get("description", "")),
                enabled=bool(data.get("enabled", False)),
            ))
        return specs

    def validate(self, source: Path) -> None:
        if not source.exists():
            raise PluginError(f"plugin module missing: {source}")
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in _FORBIDDEN:
                        raise PluginError(f"plugin imports forbidden module: {root}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0]
                if root in _FORBIDDEN:
                    raise PluginError(f"plugin imports forbidden module: {root}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN:
                raise PluginError(f"plugin uses forbidden call: {node.func.id}")
            elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                raise PluginError("plugin uses forbidden dunder attribute")

    def _extract_plugin_dict(self, source: Path) -> dict[str, Any]:
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PLUGIN":
                    try:
                        value = ast.literal_eval(node.value)
                    except (ValueError, TypeError) as exc:
                        raise PluginError("PLUGIN must be a literal dict; code is not executed") from exc
                    if not isinstance(value, dict):
                        raise PluginError("PLUGIN must be a dict literal")
                    return value
        raise PluginError("plugin must define a PLUGIN dict literal")

    def load(self, spec: PluginSpec) -> dict[str, Any]:
        if not spec.enabled and not self.allow_unsigned:
            raise PluginError(f"plugin '{spec.name}' is not enabled")
        self.validate(spec.path)
        plugin = self._extract_plugin_dict(spec.path)
        self._loaded[spec.name] = plugin
        spec.loaded = True
        return plugin

    def unload(self, name: str) -> bool:
        return self._loaded.pop(name, None) is not None

    def loaded(self) -> dict[str, dict[str, Any]]:
        return dict(self._loaded)


def get_plugin_engine(plugin_dir: Path | None = None) -> PluginEngine:
    return PluginEngine(plugin_dir=plugin_dir)
