"""Workspace-bounded Git engine with explicit approval for destructive ops."""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class GitError(RuntimeError):
    """Raised when a Git operation is blocked or fails."""


@dataclass
class GitResult:
    success: bool
    command: list[str]
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


_DESTRUCTIVE_PREFIXES = (
    ("push", "--force"),
    ("push", "-f"),
    ("reset", "--hard"),
    ("clean", "-fd"),
    ("clean", "-xfd"),
    ("branch", "-D"),
    ("checkout", "."),
)


class GitEngine:
    """Run Git inside a workspace with fail-closed destructive-operation policy."""

    def __init__(self, workspace: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.git_bin = shutil.which("git")

    def available(self) -> bool:
        return self.git_bin is not None

    def _argv(self, args: list[str]) -> list[str]:
        if not self.git_bin:
            raise GitError("git executable not found on PATH")
        if not args:
            raise GitError("git arguments cannot be empty")
        if any(part in ("|", ";", "&&", "||") for part in args):
            raise GitError("shell metacharacters are not allowed in git arguments")
        return [self.git_bin, *args]

    def _requires_approval(self, args: list[str]) -> bool:
        lowered = tuple(a.lower() for a in args)
        for prefix in _DESTRUCTIVE_PREFIXES:
            if lowered[: len(prefix)] == prefix:
                return True
        return "push" in lowered and any(a in lowered for a in ("--force", "-f", "--force-with-lease"))

    def run(self, args: list[str], *, approved: bool = False, timeout: int = 60) -> GitResult:
        if self._requires_approval(args) and not approved:
            raise GitError(f"destructive git operation requires approval: git {' '.join(args)}")
        argv = self._argv(args)
        try:
            completed = subprocess.run(
                argv,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=max(1, min(timeout, 300)),
                check=False,
                shell=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            return GitResult(False, argv, stdout=stdout, stderr="git command timed out", returncode=-1)
        return GitResult(
            success=completed.returncode == 0,
            command=argv,
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )

    def status(self) -> GitResult:
        return self.run(["status", "--porcelain=v1", "-b"])

    def diff(self, staged: bool = False) -> GitResult:
        return self.run(["diff", "--cached"] if staged else ["diff"])

    def current_branch(self) -> str:
        result = self.run(["rev-parse", "--abbrev-ref", "HEAD"])
        if not result.success:
            raise GitError(result.stderr or "unable to resolve current branch")
        return result.stdout.strip()

    def checkout(self, branch: str, create: bool = False, approved: bool = False) -> GitResult:
        args = ["checkout", "-b", branch] if create else ["checkout", branch]
        return self.run(args, approved=approved)

    def add(self, paths: list[str] | None = None) -> GitResult:
        return self.run(["add", "--", *(paths or ["."])])

    def commit(self, message: str, approved: bool = False) -> GitResult:
        if not message.strip():
            raise GitError("commit message cannot be empty")
        return self.run(["commit", "-m", message], approved=approved)

    def rollback(self, ref: str = "HEAD~1", hard: bool = False, approved: bool = False) -> GitResult:
        args = ["reset", "--hard" if hard else "--mixed", ref]
        return self.run(args, approved=approved or not hard)

    def stash(self, pop: bool = False) -> GitResult:
        return self.run(["stash", "pop"] if pop else ["stash", "push", "-u", "-m", "ma-cli"])


_engine: GitEngine | None = None


def get_git_engine(workspace: Path | None = None) -> GitEngine:
    global _engine
    resolved = (workspace or Path.cwd()).resolve()
    if _engine is None or _engine.workspace != resolved:
        _engine = GitEngine(resolved)
    return _engine
