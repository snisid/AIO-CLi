from pathlib import Path
import asyncio

import pytest

from ma_cli.tools.registry import ToolRegistry


def test_tool_registry_has_required_pipeline(tmp_path: Path):
    registry = ToolRegistry(tmp_path)
    names = {tool.name for tool in registry.list()}
    assert {"read_file", "write_file", "list_dir", "run_command"} <= names
    schemas = {item["name"] for item in registry.schemas()}
    assert names == schemas


def test_path_traversal_and_symlink_escape_are_blocked(tmp_path: Path):
    registry = ToolRegistry(tmp_path)
    with pytest.raises(PermissionError):
        registry.execute("read_file", path="../outside.txt")
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "escape"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(PermissionError):
        registry.execute("read_file", path="escape")


def test_command_danger_gate_and_audit(tmp_path: Path):
    registry = ToolRegistry(tmp_path)
    with pytest.raises(PermissionError):
        registry.execute("run_command", command="rm -rf /")
    assert registry.audit_log()[-1]["status"] == "failed"


def test_real_write_read_and_command(tmp_path: Path):
    registry = ToolRegistry(tmp_path)
    registry.execute("write_file", path="hello.txt", content="hello")
    assert registry.execute("read_file", path="hello.txt") == "hello"
    result = registry.execute("run_command", command="python -c \"print(2+2)\"")
    assert result["returncode"] == 0
    assert "4" in result["stdout"]
