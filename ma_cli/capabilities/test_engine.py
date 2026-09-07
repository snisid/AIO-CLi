from .engine import CapabilityEngine
from .models import Capability, CapabilityProfile, ReasoningLevel


def test_infer_debugging_requires_terminal_and_patch():
    request = CapabilityEngine().infer("debugging", complexity=7, risk=1)
    assert Capability.TERMINAL in request.required
    assert Capability.PATCH in request.required
    assert request.reasoning == ReasoningLevel.HIGH


def test_profile_rejects_missing_capability():
    engine = CapabilityEngine()
    request = engine.infer("computer")
    profile = CapabilityProfile(capabilities=frozenset({Capability.REASONING}))
    assert not engine.can_satisfy(profile, request)


def test_context_limit_is_enforced():
    engine = CapabilityEngine()
    request = engine.infer("research")
    request = request.__class__(
        required=request.required,
        reasoning=request.reasoning,
        context_tokens=1000,
    )
    profile = CapabilityProfile(
        capabilities=request.required,
        max_context_tokens=999,
        supports_reasoning_levels=frozenset({ReasoningLevel.MAX}),
    )
    assert not engine.can_satisfy(profile, request)
