from pathlib import Path

import pytest

from ma_cli.tools.registry import ToolRegistry


def test_registry_blocks_path_escape(tmp_path: Path):
    with pytest.raises(PermissionError):
        ToolRegistry(tmp_path).read_file("../secret.txt")


def test_registry_roundtrip(tmp_path: Path):
    registry = ToolRegistry(tmp_path)
    registry.write_file("a/b.txt", "hello")
    assert registry.read_file("a/b.txt") == "hello"
    assert "b.txt" in registry.list_dir("a")


def test_registry_exposes_schemas(tmp_path: Path):
    registry = ToolRegistry(tmp_path)
    names = {schema["name"] for schema in registry.schemas()}
    assert {"read_file", "write_file", "list_dir", "run_command"} <= names


def test_registry_requires_approval_for_high_risk_command(tmp_path: Path):
    registry = ToolRegistry(tmp_path)
    with pytest.raises(PermissionError):
        registry.execute("run_command", command="echo blocked")


def test_registry_executes_approved_command_and_audits(tmp_path: Path):
    registry = ToolRegistry(tmp_path)
    result = registry.execute("run_command", command="echo ok", approved=True)
    assert result["returncode"] == 0
    assert "ok" in result["stdout"]
    audit = registry.audit_log()
    assert audit[-1]["tool"] == "run_command"
    assert audit[-1]["status"] == "success"


def test_registry_handles_command_timeout(tmp_path: Path):
    registry = ToolRegistry(tmp_path)
    command = "Start-Sleep -Seconds 2" if __import__("os").name == "nt" else "sleep 2"
    result = registry.execute("run_command", command=command, timeout=1, approved=True)
    assert result["returncode"] == -1
    assert "timed out" in result["stderr"]
