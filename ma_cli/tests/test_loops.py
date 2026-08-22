"""Tests for loop engine."""


import pytest

from ma_cli.loops.engine import (
    ApprovalPolicy,
    Loop,
    LoopEngine,
    LoopStep,
    RetryPolicy,
)


class TestLoopEngine:
    """Tests for LoopEngine."""
    
    def test_loop_engine_creation(self):
        """Test creating loop engine."""
        engine = LoopEngine()
        
        assert engine._loops == {}
        assert engine._running == {}
    
    def test_register_loop(self):
        """Test registering a loop."""
        engine = LoopEngine()
        loop = Loop(name="test_loop", objective="Test objective")
        
        engine.register(loop)
        
        assert "test_loop" in engine._loops
        assert engine.get("test_loop") == loop
    
    def test_get_unknown_loop(self):
        """Test getting non-existent loop."""
        engine = LoopEngine()
        
        result = engine.get("unknown")
        
        assert result is None
    
    def test_list_all_loops(self):
        """Test listing all loops."""
        engine = LoopEngine()
        engine.register(Loop(name="loop1", objective="Objective 1"))
        engine.register(Loop(name="loop2", objective="Objective 2"))
        
        loops = engine.list_all()
        
        assert len(loops) == 2
        names = [l.name for l in loops]
        assert "loop1" in names
        assert "loop2" in names


class TestRetryPolicy:
    """Tests for RetryPolicy."""
    
    def test_should_retry_within_limit(self):
        """Test retry within limit."""
        policy = RetryPolicy(max_retries=3)
        
        assert policy.should_retry("error", 0) is True
        assert policy.should_retry("error", 1) is True
        assert policy.should_retry("error", 2) is True
        assert policy.should_retry("error", 3) is False
    
    def test_should_retry_with_error_filter(self):
        """Test retry with error type filtering."""
        policy = RetryPolicy(max_retries=3, retry_on=["TimeoutError"])
        
        assert policy.should_retry("TimeoutError", 0) is True
        assert policy.should_retry("ValueError", 0) is False
    
    def test_get_delay_linear(self):
        """Test linear backoff delay."""
        policy = RetryPolicy(backoff_type="linear", initial_delay_ms=1000)
        
        assert policy.get_delay(0) == 0.0
        assert policy.get_delay(1) == 1.0
        assert policy.get_delay(2) == 2.0
    
    def test_get_delay_exponential(self):
        """Test exponential backoff delay."""
        policy = RetryPolicy(backoff_type="exponential", initial_delay_ms=1000)
        
        assert policy.get_delay(0) == 1.0
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 4.0
    
    def test_get_delay_max(self):
        """Test max delay cap."""
        policy = RetryPolicy(
            backoff_type="exponential",
            initial_delay_ms=1000,
            max_delay_ms=5000
        )
        
        # Should be capped at max_delay_ms
        assert policy.get_delay(10) <= 5.0


class TestApprovalPolicy:
    """Tests for ApprovalPolicy."""
    
    def test_auto_approve(self):
        """Test auto-approve mode."""
        policy = ApprovalPolicy(auto_approve=True)
        
        assert policy.requires_approval("any_action") is False
    
    def test_requires_approval_for_listed(self):
        """Test approval for listed actions."""
        policy = ApprovalPolicy(
            auto_approve=False,
            require_approval_for=["delete", "deploy"]
        )
        
        assert policy.requires_approval("delete") is True
        assert policy.requires_approval("deploy") is True
        assert policy.requires_approval("read") is False
    
    def test_no_approval_when_empty_list(self):
        """Test no approval when list is empty."""
        policy = ApprovalPolicy(
            auto_approve=False,
            require_approval_for=[]
        )
        
        assert policy.requires_approval("any_action") is False


class TestLoopExecution:
    """Tests for loop execution."""
    
    @pytest.mark.asyncio
    async def test_execute_simple_loop(self):
        """Test executing a simple loop."""
        engine = LoopEngine()
        loop = Loop(
            name="simple_loop",
            objective="Simple test",
            steps=[
                LoopStep(name="step1", description="First step"),
                LoopStep(name="step2", description="Second step"),
            ]
        )
        engine.register(loop)
        
        result = await engine.execute("simple_loop", {"input": "value"})
        
        assert result.success is True
        assert result.steps_total == 2
        assert result.steps_completed == 2
    
    @pytest.mark.asyncio
    async def test_execute_unknown_loop(self):
        """Test executing non-existent loop."""
        engine = LoopEngine()
        
        with pytest.raises(ValueError) as exc_info:
            await engine.execute("unknown_loop", {})
        
        assert "not found" in str(exc_info.value)
