from pathlib import Path

import pytest

from ma_cli.runtime.native import NativeAgent
from ma_cli.runtime.planner import IntentAnalyzer, Planner, TaskRole
from ma_cli.security.runtime_policy import RuntimeSecurity
from ma_cli.tools.registry import ToolRegistry


def test_planner_creates_ordered_autonomous_graph():
    intent, graph = Planner().plan("Build and test a private Git authentication service")
    assert intent.private is True
    assert "git" in intent.capabilities
    ordered = graph.topological()
    assert ordered[0].role in {TaskRole.CODER, TaskRole.RESEARCH}
    assert ordered[-1].role == TaskRole.FINALIZER


def test_runtime_security_blocks_workspace_escape(tmp_path: Path):
    security = RuntimeSecurity(tmp_path)
    with pytest.raises(PermissionError):
        security.resolve_workspace_path("../outside.txt")


def test_runtime_security_blocks_destructive_command(tmp_path: Path):
    decision = RuntimeSecurity(tmp_path).authorize_command("Remove-Item -Recurse .")
    assert decision.allowed is False
    assert decision.risk == "critical"


def test_registry_requires_approval_for_high_risk(tmp_path: Path):
    registry = ToolRegistry(tmp_path)
    with pytest.raises(PermissionError):
        registry.execute("run_command", command="python --version")


def test_registry_records_audit_for_approved_command(tmp_path: Path):
    registry = ToolRegistry(tmp_path)
    result = registry.execute("run_command", command="python --version", approved=True)
    assert result["returncode"] == 0
    assert registry.audit_log()[-1]["status"] == "success"


def test_native_runtime_has_bounded_repair(tmp_path: Path):
    agent = NativeAgent(tmp_path, max_repair_attempts=2)
    assert agent.max_repair_attempts == 2
