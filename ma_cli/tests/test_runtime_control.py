from __future__ import annotations

from pathlib import Path

import pytest

from ma_cli.runtime.connectors import ConnectorControlError, ConnectorRegistry
from ma_cli.runtime.control import RuntimeController, RuntimeControlError


def test_runtime_environments(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    ids = {item["id"] for item in controller.environments()}
    assert {"local", "cloud", "ssh", "wsl"} <= ids


def test_cloud_rejects_non_http_endpoint(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    with pytest.raises(RuntimeControlError):
        controller.configure_cloud("file:///etc/passwd")


def test_ssh_requires_valid_identity(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    with pytest.raises(RuntimeControlError):
        controller.configure_ssh("", "user")


def test_remote_dispatch_requires_remote_target(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    with pytest.raises(RuntimeControlError):
        controller.dispatch_remote("local", "run tests")


def test_extension_install_and_remove(tmp_path: Path) -> None:
    controller = RuntimeController(tmp_path)
    installed = controller.install_extension("demo", "Demo", "plugin", "1.0.0", "builtin-marketplace")
    assert installed["status"] == "installed"
    assert (tmp_path / ".aio-cli" / "extensions" / "demo.json").exists()
    removed = controller.uninstall_extension("demo")
    assert removed["status"] == "removed"


def test_connector_url_validation() -> None:
    registry = ConnectorRegistry()
    with pytest.raises(ConnectorControlError):
        registry.configure("custom", "not-a-url")
