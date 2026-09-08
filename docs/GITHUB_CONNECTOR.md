# AIO-CLi GitHub Connector

AIO-CLi now exposes a native GitHub connector for the desktop-style workspace.

## Authentication

For local desktop use, authenticate once with the GitHub CLI:

```powershell
gh auth login
gh auth status
```

AIO-CLi resolves credentials in this order:

1. `GITHUB_TOKEN`
2. `GH_TOKEN`
3. `gh auth token`

Tokens are not written to AIO-CLi local storage.

## Workspace features

The dashboard GitHub dialog provides:

- connection status and authenticated account
- repository inspection
- `Add from GitHub` local clone
- open Pull Requests
- open Issues

The runtime exposes these endpoints:

- `GET /api/github/status`
- `GET /api/github/repository?repository=owner/repo`
- `GET /api/github/pulls?repository=owner/repo`
- `GET /api/github/issues?repository=owner/repo`
- `POST /api/github/import`
- `POST /api/github/pulls`

Local repository import is restricted to the configured `AIO_CLI_WORKSPACE_ROOT` and only accepts `github.com` repository URLs.

## Desktop model

GitHub is treated as a first-class connector alongside the existing Prompt / Code / Hub workspace. This supports the same general agentic workflow described in the product specification: project context, repository access, isolated workspaces, PR review/creation, and CI/CD visibility.
