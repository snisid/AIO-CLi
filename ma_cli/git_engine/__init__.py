"""Git engine for workspace-bounded version control."""

from .engine import GitEngine, GitError, GitResult, get_git_engine

__all__ = ["GitEngine", "GitError", "GitResult", "get_git_engine"]
