from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class GitHubUser:
    login: str
    name: str | None
    avatar_url: str | None


@dataclass(frozen=True)
class GitHubRepository:
    full_name: str
    default_branch: str
    private: bool
    html_url: str
    clone_url: str
    description: str | None


class GitHubAPIError(RuntimeError):
    """Raised when the GitHub API cannot complete an operation."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _git_remote_to_api(url: str) -> str:
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {"github.com", "www.github.com"}:
        raise ValueError("Only github.com repository URLs are supported")
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("GitHub repository URL must be https://github.com/owner/repo")
    return f"https://api.github.com/repos/{parts[0]}/{parts[1]}"


def _repository_to_api(repository: str) -> str:
    value = repository.strip()
    if value.startswith(("http://", "https://")):
        return _git_remote_to_api(value)
    parts = value.strip("/").split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("Repository must be owner/repo or a GitHub repository URL")
    return f"https://api.github.com/repos/{parts[0]}/{parts[1]}"


def _read_gh_token() -> str | None:
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.getenv(key)
        if token:
            return token.strip()
    try:
        completed = subprocess.run(
            ["gh", "auth", "token"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return None
    token = completed.stdout.strip()
    return token or None


class GitHubClient:
    """Authenticated GitHub REST client for AIO-CLi.

    Authentication is resolved from GITHUB_TOKEN/GH_TOKEN first and then from
    the local GitHub CLI (`gh auth token`). AIO-CLi never persists the token.
    """

    api_base = "https://api.github.com"

    def __init__(self, token: str | None = None, timeout: float = 15.0) -> None:
        self._token = token.strip() if token else _read_gh_token()
        self.timeout = timeout

    @property
    def authenticated(self) -> bool:
        return bool(self._token)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AIO-CLi/1.0",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        headers = dict(kwargs.pop("headers", {}))
        headers.update(self._headers())
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise GitHubAPIError(f"GitHub network error: {exc}") from exc
        if response.status_code >= 400:
            try:
                detail = response.json().get("message", response.text)
            except (ValueError, json.JSONDecodeError):
                detail = response.text
            raise GitHubAPIError(f"GitHub API error: {detail}", response.status_code)
        if not response.content:
            return None
        return response.json()

    async def status(self) -> dict[str, Any]:
        if not self.authenticated:
            return {
                "connected": False,
                "authenticated": False,
                "provider": "GitHub",
                "source": None,
                "message": "Connect with GITHUB_TOKEN or `gh auth login`.",
            }
        data = await self._request("GET", f"{self.api_base}/user")
        return {
            "connected": True,
            "authenticated": True,
            "provider": "GitHub",
            "source": "token" if os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") else "gh",
            "user": {
                "login": data.get("login"),
                "name": data.get("name"),
                "avatar_url": data.get("avatar_url"),
            },
        }

    async def repository(self, repository: str) -> GitHubRepository:
        data = await self._request("GET", _repository_to_api(repository))
        return GitHubRepository(
            full_name=data["full_name"],
            default_branch=data.get("default_branch") or "main",
            private=bool(data.get("private")),
            html_url=data["html_url"],
            clone_url=data["clone_url"],
            description=data.get("description"),
        )

    async def pull_requests(self, repository: str, state: str = "open", limit: int = 20) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            _repository_to_api(repository) + "/pulls",
            params={"state": state, "per_page": max(1, min(limit, 100))},
        )
        return [
            {
                "number": item["number"],
                "title": item["title"],
                "state": item["state"],
                "draft": bool(item.get("draft")),
                "head": item["head"]["ref"],
                "base": item["base"]["ref"],
                "html_url": item["html_url"],
                "author": item.get("user", {}).get("login"),
            }
            for item in data
        ]

    async def issues(self, repository: str, state: str = "open", limit: int = 20) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            _repository_to_api(repository) + "/issues",
            params={"state": state, "per_page": max(1, min(limit, 100))},
        )
        return [
            {
                "number": item["number"],
                "title": item["title"],
                "state": item["state"],
                "html_url": item["html_url"],
                "author": item.get("user", {}).get("login"),
            }
            for item in data
            if "pull_request" not in item
        ]

    async def create_pull_request(
        self,
        repository: str,
        title: str,
        head: str,
        base: str,
        body: str = "",
        draft: bool = False,
    ) -> dict[str, Any]:
        if not self.authenticated:
            raise GitHubAPIError("Authentication is required to create a pull request", 401)
        data = await self._request(
            "POST",
            _repository_to_api(repository) + "/pulls",
            json={"title": title, "head": head, "base": base, "body": body, "draft": draft},
        )
        return {
            "number": data["number"],
            "title": data["title"],
            "html_url": data["html_url"],
            "state": data["state"],
        }


__all__ = ["GitHubAPIError", "GitHubClient", "GitHubRepository", "GitHubUser"]
