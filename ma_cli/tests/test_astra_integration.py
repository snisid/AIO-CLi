from ma_cli.capabilities import CapabilityEngine, CapabilityProfile
from ma_cli.capabilities.integration import CapabilityNegotiator
from ma_cli.runtime.checkpoint import CheckpointStore, RunCheckpoint


def test_capability_negotiation_accepts_coding_profile():
    engine = CapabilityEngine()
    request = engine.infer("coding", complexity=5)
    profile = CapabilityProfile(capabilities=set(request.required), max_context_tokens=10000)
    assert CapabilityNegotiator(engine).negotiate(profile, request).accepted


def test_capability_negotiation_rejects_context_overflow():
    engine = CapabilityEngine()
    request = engine.infer("coding")
    request.context_tokens = 20000
    profile = CapabilityProfile(capabilities=set(request.required), max_context_tokens=1000)
    result = CapabilityNegotiator(engine).negotiate(profile, request)
    assert not result.accepted
    assert "context" in result.reason


def test_checkpoint_round_trip(tmp_path):
    store = CheckpointStore(tmp_path)
    store.save(RunCheckpoint("run-1", "build project", state="RUNNING", completed_tasks=["a"]))
    restored = store.load("run-1")
    assert restored is not None
    assert restored.completed_tasks == ["a"]
