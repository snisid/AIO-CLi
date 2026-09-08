from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Any
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class ExternalConnector:
    id: str
    name: str
    kind: str
    base_url: str
    auth_env: str | None
    configured: bool


class ConnectorControlError(RuntimeError):
    pass


CATALOG = {
    "gitlab": ("GitLab", "git", "GITLAB_TOKEN", "https://gitlab.com/api/v4"),
    "slack": ("Slack", "communication", "SLACK_BOT_TOKEN", "https://slack.com/api"),
    "notion": ("Notion", "productivity", "NOTION_TOKEN", "https://api.notion.com/v1"),
    "linear": ("Linear", "project", "LINEAR_API_KEY", "https://api.linear.app"),
    "jira": ("Jira", "project", "JIRA_API_TOKEN", os.getenv("JIRA_BASE_URL", "")),
    "figma": ("Figma", "design", "FIGMA_TOKEN", "https://api.figma.com/v1"),
    "custom": ("Custom API", "custom", "AIO_CLI_CUSTOM_CONNECTOR_TOKEN", ""),
}


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, ExternalConnector] = {}
        for connector_id, (name, kind, env, default_url) in CATALOG.items():
            base_url = os.getenv(f"AIO_CLI_{connector_id.upper()}_BASE_URL", default_url).strip().rstrip("/")
            self._connectors[connector_id] = ExternalConnector(
                id=connector_id,
                name=name,
                kind=kind,
                base_url=base_url,
                auth_env=env,
                configured=bool(base_url and os.getenv(env)),
            )

    def list(self) -> list[dict[str, Any]]:
        return [asdict(item) | {"configured": self.is_configured(item.id)} for item in self._connectors.values()]

    def is_configured(self, connector_id: str) -> bool:
        connector = self._connectors.get(connector_id)
        return bool(connector and connector.base_url and connector.auth_env and os.getenv(connector.auth_env))

    def configure(self, connector_id: str, base_url: str | None = None) -> dict[str, Any]:
        connector = self._connectors.get(connector_id)
        if connector is None:
            raise ConnectorControlError("Unknown connector")
        if base_url:
            parsed = urlparse(base_url.strip())
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ConnectorControlError("Connector base URL must be an absolute http(s) URL")
            os.environ[f"AIO_CLI_{connector_id.upper()}_BASE_URL"] = base_url.strip().rstrip("/")
            self._connectors[connector_id] = ExternalConnector(connector.id, connector.name, connector.kind, base_url.strip().rstrip("/"), connector.auth_env, False)
        return asdict(self._connectors[connector_id]) | {"configured": self.is_configured(connector_id)}

    async def check(self, connector_id: str) -> dict[str, Any]:
        connector = self._connectors.get(connector_id)
        if connector is None:
            raise ConnectorControlError("Unknown connector")
        if not self.is_configured(connector_id):
            return {"id": connector_id, "configured": False, "reachable": False, "message": "Base URL or credential environment variable is missing"}
        headers = {"User-Agent": "AIO-CLi/1.0"}
        token = os.getenv(connector.auth_env or "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                response = await client.get(connector.base_url, headers=headers)
            return {"id": connector_id, "configured": True, "reachable": response.status_code < 500, "status_code": response.status_code}
        except httpx.HTTPError as exc:
            return {"id": connector_id, "configured": True, "reachable": False, "message": str(exc)}

    async def request(self, connector_id: str, path: str = "", method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        connector = self._connectors.get(connector_id)
        if connector is None:
            raise ConnectorControlError("Unknown connector")
        if not path.startswith("/"):
            path = f"/{path}" if path else ""
        if ".." in path.split("/"):
            raise ConnectorControlError("Invalid connector path")
        if not self.is_configured(connector_id):
            raise ConnectorControlError("Connector is not configured")
        token = os.getenv(connector.auth_env or "")
        headers = {"User-Agent": "AIO-CLi/1.0", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        url = f"{connector.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.request(method.upper(), url, headers=headers, json=payload if method.upper() != "GET" else None)
        except httpx.HTTPError as exc:
            raise ConnectorControlError(str(exc)) from exc
        content_type = response.headers.get("content-type", "")
        data: Any
        if "application/json" in content_type:
            try:
                data = response.json()
            except ValueError:
                data = response.text
        else:
            data = response.text
        return {"id": connector_id, "status_code": response.status_code, "ok": response.is_success, "data": data}
