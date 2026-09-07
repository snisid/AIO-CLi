from pathlib import Path

from ma_cli.capabilities import Capability, CapabilityProfile, CapabilityEngine
from ma_cli.capabilities.integration import CapabilityNegotiator
from ma_cli.runtime.checkpoint import CheckpointStore, RunCheckpoint


def test_negotiation_accepts_required_capabilities():
    engine = CapabilityEngine()
    request = engine.infer("coding", complexity=5)
    profile = CapabilityProfile(capabilities=set(request.required), max_context_tokens=10000)
    result = CapabilityNegotiator(engine).negotiate(profile, request)
    assert result.accepted


def test_negotiation_rejects_context_overflow():
    engine = CapabilityEngine()
    request = engine.infer("coding")
    request.context_tokens = 20000
    profile = CapabilityProfile(capabilities=set(request.required), max_context_tokens=1000)
    result = CapabilityNegotiator(engine).negotiate(profile, request)
    assert not result.accepted
    assert "context" in result.reason


def test_checkpoint_round_trip(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    checkpoint = RunCheckpoint("run-1", "build project", state="RUNNING", completed_tasks=["a"])
    store.save(checkpoint)
    restored = store.load("run-1")
    assert restored is not None
    assert restored.completed_tasks == ["a"]
    assert restored.state == "RUNNING"
