from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse


class GitHubWorkspaceError(RuntimeError):
    """Raised when a repository cannot be imported into the local workspace."""


def validate_github_repository_url(repository_url: str) -> str:
    parsed = urlparse(repository_url.strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise GitHubWorkspaceError("Repository must use https://github.com/owner/repo")
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    if len(parts) != 2 or not all(parts):
        raise GitHubWorkspaceError("Repository must be https://github.com/owner/repo")
    return f"https://github.com/{parts[0]}/{parts[1]}.git"


def import_repository(repository_url: str, workspace_root: str | Path, folder_name: str | None = None) -> dict[str, str]:
    remote = validate_github_repository_url(repository_url)
    root = Path(workspace_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    repo_name = folder_name or remote.rsplit("/", 1)[-1].removesuffix(".git")
    target = (root / repo_name).resolve()
    if root not in target.parents and target != root:
        raise GitHubWorkspaceError("Import destination escapes the configured workspace")
    if target.exists() and any(target.iterdir()):
        raise GitHubWorkspaceError(f"Destination already exists and is not empty: {target}")

    completed = subprocess.run(
        ["git", "clone", "--origin", "origin", remote, str(target)],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip() or "git clone failed"
        raise GitHubWorkspaceError(detail)

    return {"repository_url": remote, "path": str(target), "status": "imported"}


__all__ = ["GitHubWorkspaceError", "import_repository", "validate_github_repository_url"]
