from pathlib import Path
import asyncio

import pytest

from ma_cli.runtime.planner import IntentAnalyzer, PlanTask, Planner, TaskGraph, TaskRole
from ma_cli.runtime.engine import NativeAgent


def test_intent_analyzer_is_deterministic():
    intent = IntentAnalyzer().analyze("Build and test a private Git authentication service")
    assert intent.private is True
    assert "git" in intent.capabilities
    assert TaskRole.CODER in intent.roles
    assert TaskRole.TESTER in intent.roles


def test_task_graph_rejects_cycles():
    a = PlanTask(title="a")
    b = PlanTask(title="b", dependencies=[a.id])
    graph = TaskGraph([a, b])
    a.dependencies.append(b.id)
    with pytest.raises(ValueError):
        graph.validate()


def test_planner_produces_executable_dag():
    _, graph = Planner().plan("Implement authentication")
    ordered = graph.topological()
    assert len(ordered) == 5
    assert ordered[-1].role == TaskRole.FINALIZER


class FakeModel:
    async def complete(self, messages, *, strategy, capabilities, tools=None):
        class Response:
            content = "model response"
            tool_calls = []
        assert tools is not None
        return Response()


def test_native_agent_uses_real_test_gate(tmp_path: Path):
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    agent = NativeAgent(workspace=tmp_path, model=FakeModel())
    result = asyncio.run(agent.run("Implement a tiny testable change"))
    assert result.success is True
    assert result.attempts >= 5
