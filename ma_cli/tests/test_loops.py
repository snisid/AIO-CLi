"""Tests for loop engine."""

import pytest

from ma_cli.loops.engine import ApprovalPolicy, Loop, LoopEngine, LoopStep, RetryPolicy


class TestLoopEngine:
    def test_loop_engine_creation(self):
        engine = LoopEngine()
        assert engine._loops == {}
        assert engine._running == {}

    def test_register_loop(self):
        engine = LoopEngine()
        loop = Loop(name="test_loop", objective="Test objective")
        engine.register(loop)
        assert "test_loop" in engine._loops
        assert engine.get("test_loop") == loop

    def test_register_loop_alias(self):
        engine = LoopEngine()
        loop = Loop(name="alias_loop", objective="Alias objective")
        engine.register_loop(loop)
        assert engine.get("alias_loop") == loop

    def test_get_unknown_loop(self):
        assert LoopEngine().get("unknown") is None

    def test_list_all_loops(self):
        engine = LoopEngine()
        engine.register(Loop(name="loop1", objective="Objective 1"))
        engine.register(Loop(name="loop2", objective="Objective 2"))
        names = [loop.name for loop in engine.list_all()]
        assert names == ["loop1", "loop2"]


class TestRetryPolicy:
    def test_should_retry_within_limit(self):
        policy = RetryPolicy(max_retries=3)
        assert [policy.should_retry("error", i) for i in range(4)] == [True, True, True, False]

    def test_should_retry_with_error_filter(self):
        policy = RetryPolicy(max_retries=3, retry_on=["TimeoutError"])
        assert policy.should_retry("TimeoutError", 0) is True
        assert policy.should_retry("ValueError", 0) is False

    def test_get_delay_linear(self):
        policy = RetryPolicy(backoff_type="linear", initial_delay_ms=1000)
        assert policy.get_delay(0) == 0.0
        assert policy.get_delay(1) == 1.0
        assert policy.get_delay(2) == 2.0

    def test_get_delay_exponential(self):
        policy = RetryPolicy(backoff_type="exponential", initial_delay_ms=1000)
        assert policy.get_delay(0) == 1.0
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 4.0

    def test_get_delay_max(self):
        policy = RetryPolicy(initial_delay_ms=1000, max_delay_ms=5000)
        assert policy.get_delay(10) <= 5.0


class TestApprovalPolicy:
    def test_auto_approve(self):
        assert ApprovalPolicy(auto_approve=True).requires_approval("any_action") is False

    def test_requires_approval_for_listed(self):
        policy = ApprovalPolicy(require_approval_for=["delete", "deploy"])
        assert policy.requires_approval("delete") is True
        assert policy.requires_approval("deploy") is True
        assert policy.requires_approval("read") is False

    def test_no_approval_when_empty_list(self):
        assert ApprovalPolicy().requires_approval("any_action") is False


class TestLoopExecution:
    @pytest.mark.asyncio
    async def test_execute_simple_loop_with_real_executor(self):
        calls = []

        async def executor(step, state, context):
            calls.append(step.name)
            return {"success": True, "step": step.name, "inputs": state.inputs}

        engine = LoopEngine(step_executor=executor)
        engine.register(Loop(
            name="simple_loop",
            objective="Simple test",
            steps=[LoopStep(name="step1"), LoopStep(name="step2")],
        ))
        result = await engine.execute("simple_loop", {"input": "value"})
        assert result.success is True
        assert result.steps_total == 2
        assert result.steps_completed == 2
        assert calls == ["step1", "step2"]

    @pytest.mark.asyncio
    async def test_execute_without_executor_fails_closed(self):
        engine = LoopEngine()
        engine.register(Loop(name="no_executor", objective="Must not fake", steps=[LoopStep(name="step")]))
        result = await engine.execute("no_executor", {})
        assert result.success is False
        assert "no executor" in (result.state.error or "")

    @pytest.mark.asyncio
    async def test_execute_unknown_loop(self):
        with pytest.raises(ValueError) as exc_info:
            await LoopEngine().execute("unknown", {})
        assert "not found" in str(exc_info.value)
