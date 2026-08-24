from pathlib import Path
import pytest
from ma_cli.tools.registry import ToolRegistry

def test_registry_blocks_path_escape(tmp_path: Path):
    with pytest.raises(PermissionError):
        ToolRegistry(tmp_path).read_file("../secret.txt")

def test_registry_roundtrip(tmp_path: Path):
    r = ToolRegistry(tmp_path)
    r.write_file("a/b.txt", "hello")
    assert r.read_file("a/b.txt") == "hello"
    assert "b.txt" in r.list_dir("a")
