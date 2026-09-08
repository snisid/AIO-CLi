from __future__ import annotations

import pytest

from ma_cli.github.client import GitHubAPIError, GitHubClient, _repository_to_api, _git_remote_to_api
from ma_cli.github.workspace import GitHubWorkspaceError, validate_github_repository_url


def test_repository_url_is_normalized() -> None:
    assert _git_remote_to_api("https://github.com/snisid/AIO-CLi.git") == "https://api.github.com/repos/snisid/AIO-CLi"
    assert _repository_to_api("snisid/AIO-CLi") == "https://api.github.com/repos/snisid/AIO-CLi"


def test_repository_url_rejects_non_github_hosts() -> None:
    with pytest.raises(ValueError):
        _git_remote_to_api("https://example.com/owner/repo")


def test_import_url_is_strict() -> None:
    assert validate_github_repository_url("https://github.com/snisid/AIO-CLi") == "https://github.com/snisid/AIO-CLi.git"
    with pytest.raises(GitHubWorkspaceError):
        validate_github_repository_url("https://example.com/owner/repo")


@pytest.mark.asyncio
async def test_status_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr("ma_cli.github.client._read_gh_token", lambda: None)
    result = await GitHubClient().status()
    assert result["connected"] is False
    assert result["authenticated"] is False


@pytest.mark.asyncio
async def test_status_with_mocked_api() -> None:
    client = GitHubClient(token="test-token")

    async def fake_request(method: str, url: str, **kwargs: object) -> dict[str, str]:
        assert method == "GET"
        assert url.endswith("/user")
        return {"login": "aio-test", "name": "AIO Test", "avatar_url": "https://example.test/a.png"}

    client._request = fake_request  # type: ignore[method-assign]
    result = await client.status()
    assert result["connected"] is True
    assert result["user"]["login"] == "aio-test"


def test_github_api_error_keeps_http_status() -> None:
    error = GitHubAPIError("rate limited", 429)
    assert error.status_code == 429
