"""Code and security review engine used as a hard quality gate."""
from __future__ import annotations

from pathlib import Path

from ..core.models import ReviewResult

_SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", ".ma-cli"}
_CODE_SMELLS = ("eval(", "exec(", "os.system(", "subprocess.Popen(", "shell=True")
_SECRET_MARKERS = ("api_key", "secret_key", "private_key", "BEGIN RSA PRIVATE KEY", "sk-live-", "AKIA")
_INJECTION = ("ignore previous instructions", "you are now dan", "reveal the system prompt")


class ReviewEngine:
    """Static review of workspace sources. Never skipped silently."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()

    def _iter_files(self) -> list[Path]:
        files: list[Path] = []
        for path in self.workspace.rglob("*"):
            if not path.is_file():
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            if path.suffix.lower() not in {".py", ".js", ".ts", ".ps1", ".sh", ".md", ".yml", ".yaml", ".json"}:
                continue
            if path.stat().st_size > 1_000_000:
                continue
            files.append(path)
        return files

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return ""

    def review_workspace(self, workspace: Path | None = None) -> ReviewResult:
        root = (workspace or self.workspace).resolve()
        previous = self.workspace
        self.workspace = root
        try:
            issues: list[str] = []
            files = self._iter_files()
            for path in files:
                text = self._read(path)
                rel = str(path.relative_to(root))
                for smell in _CODE_SMELLS:
                    if smell in text:
                        issues.append(f"{rel}: {smell}")
            if not files:
                return ReviewResult(passed=True, issues=[], score=1.0, severity="info",
                                    details={"files": 0, "note": "no reviewable sources"})
            passed = not issues
            return ReviewResult(
                passed=passed,
                issues=issues,
                score=1.0 if passed else max(0.0, 1.0 - 0.2 * len(issues)),
                severity="info" if passed else "error",
                details={"files": len(files)},
                skipped=False,
            )
        finally:
            self.workspace = previous

    def security_review(self, workspace: Path | None = None) -> ReviewResult:
        root = (workspace or self.workspace).resolve()
        previous = self.workspace
        self.workspace = root
        try:
            issues: list[str] = []
            files = self._iter_files()
            for path in files:
                text = self._read(path)
                lowered = text.lower()
                rel = str(path.relative_to(root))
                for marker in _SECRET_MARKERS:
                    if marker.lower() in lowered:
                        issues.append(f"{rel}: possible secret marker {marker}")
                for pattern in _INJECTION:
                    if pattern in lowered:
                        issues.append(f"{rel}: injection pattern {pattern}")
                if "shell=True" in text:
                    issues.append(f"{rel}: unbounded shell execution")
            passed = not issues
            return ReviewResult(
                passed=passed,
                issues=issues,
                score=1.0 if passed else 0.2,
                severity="info" if passed else "critical",
                details={"files": len(files)},
                skipped=False,
            )
        finally:
            self.workspace = previous

    def review_code(self, code: str) -> ReviewResult:
        issues = [smell for smell in _CODE_SMELLS if smell in code]
        return ReviewResult(passed=not issues, issues=issues, score=1.0 if not issues else 0.4, skipped=False)


def get_review_engine(workspace: Path | None = None) -> ReviewEngine:
    return ReviewEngine(workspace)
