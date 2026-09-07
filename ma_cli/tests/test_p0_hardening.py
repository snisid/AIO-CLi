from __future__ import annotations

from pathlib import Path

import pytest

from ma_cli.context.engine import ContextEngine
from ma_cli.observability.engine import ObservabilityEngine
from ma_cli.orchestrator.engine import Orchestrator
from ma_cli.plugins.engine import PluginEngine, PluginError, PluginSpec
from ma_cli.report.engine import ReportEngine
from ma_cli.review.engine import ReviewEngine
from ma_cli.runtime.model_adapter import ProviderModel, attach_default_model
from ma_cli.tools.registry import RUNTIME_GRANT, ToolRegistry


def test_attach_default_model_never_uses_auto():
    model = attach_default_model()
    if model is not None:
        assert model.model_id != "auto"
        assert model.model_id


def test_provider_model_rejects_auto_id():
    class Dummy:
        enabled = True

        async def chat(self, *args, **kwargs):
            raise AssertionError("should not chat")

    with pytest.raises(ValueError, match="concrete"):
        ProviderModel(Dummy(), model_id="auto")


def test_plugin_rejects_non_literal_and_does_not_exec(tmp_path: Path):
    module = tmp_path / "bad.py"
    module.write_text("PLUGIN = dict(name='nope')\n", encoding="utf-8")
    engine = PluginEngine(tmp_path, allow_unsigned=True)
    with pytest.raises(PluginError, match="literal"):
        engine.load(PluginSpec(name="bad", path=module, enabled=True))


@pytest.mark.asyncio
async def test_orchestrator_blocks_on_review_failure(tmp_path: Path):
    (tmp_path / "mod.py").write_text("def f():\n    exec('x')\n", encoding="utf-8")
    result = await Orchestrator(workspace=tmp_path, native_model=None).run(
        "hello", allow_external_fallback=False, timeout=30,
    )
    assert result.success is False
    assert result.error


@pytest.mark.asyncio
async def test_orchestrator_validates_clean_workspace(tmp_path: Path):
    (tmp_path / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    result = await Orchestrator(workspace=tmp_path, native_model=None).run(
        "hello", allow_external_fallback=False, timeout=30,
    )
    assert result.success is True
    assert result.metadata["validation"]["can_finalize"] is True


def test_review_report_context_observability(tmp_path: Path):
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    review = ReviewEngine(tmp_path).review_workspace()
    assert review.passed is True
    assert review.skipped is False
    bundle = ContextEngine(tmp_path, max_tokens=500).collect()
    assert bundle.files
    obs = ObservabilityEngine(tmp_path)
    span = obs.start_span("t")
    obs.end_span(span)
    snap = obs.snapshot()
    assert snap["spans"]
    report = ReportEngine(tmp_path)
    path = report.write(type("R", (), {"success": True, "task_id": "t", "output": "ok", "metadata": {}})())
    assert path.exists()
    assert "PRODUCTION VERIFIED PASS" not in path.read_text(encoding="utf-8") or "not a PRODUCTION" in path.read_text(encoding="utf-8")


def test_release_gate_blocks_pending_live():
    import runpy
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "scripts" / "release_gate.py"
    ns = runpy.run_path(str(path))
    assert ns["main"]() == 1


def test_run_command_is_not_a_shell(tmp_path: Path):
    registry = ToolRegistry(tmp_path)
    with pytest.raises(PermissionError, match="metacharacters"):
        registry.execute("run_command", command="echo hi | cat", grant=RUNTIME_GRANT)
