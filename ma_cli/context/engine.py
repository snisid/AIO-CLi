"""Context assembly with a hard token budget and workspace bounds."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache", ".ma-cli"}
_PREFERRED = ("README.md", "pyproject.toml", "package.json", "AGENTS.md")


@dataclass
class ContextBundle:
    files: list[dict[str, Any]] = field(default_factory=list)
    tokens: int = 0
    truncated: bool = False

    def as_prompt(self) -> str:
        parts = []
        for item in self.files:
            parts.append(f"# {item['path']}\n{item['content']}")
        return "\n\n".join(parts)


class ContextEngine:
    def __init__(self, workspace: Path | None = None, max_tokens: int = 8000):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.max_tokens = max(256, int(max_tokens))

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def collect(self, query: str | None = None, max_tokens: int | None = None) -> ContextBundle:
        budget = max_tokens or self.max_tokens
        bundle = ContextBundle()
        candidates: list[Path] = []
        for name in _PREFERRED:
            path = self.workspace / name
            if path.is_file():
                candidates.append(path)
        for path in sorted(self.workspace.rglob("*")):
            if not path.is_file() or any(part in _SKIP_DIRS for part in path.parts):
                continue
            if path.suffix.lower() not in {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".txt"}:
                continue
            if path not in candidates:
                candidates.append(path)
        needle = (query or "").lower()
        for path in candidates:
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if needle and needle not in text.lower() and needle not in str(path).lower():
                continue
            snippet = text[:8000]
            cost = self._estimate_tokens(snippet)
            if bundle.tokens + cost > budget:
                bundle.truncated = True
                break
            bundle.files.append({"path": str(path.relative_to(self.workspace)), "content": snippet})
            bundle.tokens += cost
        return bundle


def get_context_engine(workspace: Path | None = None) -> ContextEngine:
    return ContextEngine(workspace)
