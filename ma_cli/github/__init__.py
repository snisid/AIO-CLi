"""GitHub connector for the AIO-CLi desktop/runtime experience."""

from .client import GitHubAPIError, GitHubClient, GitHubRepository, GitHubUser

__all__ = ["GitHubAPIError", "GitHubClient", "GitHubRepository", "GitHubUser"]
