"""
Tests for critical security and reliability features.

Tests cover:
- Sandbox hard-fail policy
- Circuit breaker pattern
- Validation engine with hard blocks on skipped reviews
- Finalizer enforcement
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from ma_cli.core.models import ReviewResult, ValidationReport
from ma_cli.providers.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitConfig,
    CircuitOpenError,
    CircuitState,
)
from ma_cli.sandbox.manager import (
    PolicyViolationError,
    SandboxConfig,
    SandboxManager,
    SandboxPolicy,
    SandboxUnavailableError,
)
from ma_cli.validation.engine import (
    Finalizer,
    ValidationConfig,
    ValidationEngine,
)

# ============================================================================
# Sandbox Tests - Hard Fail Policy
# ============================================================================

class TestSandboxHardFail:
    """Test sandbox hard-fail policy."""
    
    def test_sandbox_unavailable_raises_error(self):
        """Test that unavailable sandbox raises SandboxUnavailableError."""
        config = SandboxConfig(policy=SandboxPolicy.STRICT)
        manager = SandboxManager(config=config)
        
        # Mock is_available to return False
        with patch.object(manager, 'is_available', return_value=False):
            with pytest.raises(SandboxUnavailableError) as exc_info:
                asyncio.run(manager.execute("task-123", "echo hello"))
            
            assert "Docker sandbox required but unavailable" in str(exc_info.value)
            assert "Task aborted for security" in str(exc_info.value)
    
    def test_sandbox_never_fallback_to_host(self):
        """Verify sandbox never falls back to host execution."""
        config = SandboxConfig(policy=SandboxPolicy.STRICT)
        manager = SandboxManager(config=config)
        
        # The execute method should raise error if Docker unavailable
        # NOT fall back to subprocess on host
        with patch.object(manager, 'is_available', return_value=False):
            with pytest.raises(SandboxUnavailableError):
                asyncio.run(manager.execute("task-456", "rm -rf /"))
    
    def test_policy_violation_detected(self):
        """Test that denied commands are blocked."""
        config = SandboxConfig(
            denied_commands=["rm -rf", "sudo", "curl http"]
        )
        
        # Mock docker.from_env to avoid Docker requirement
        with patch("docker.from_env") as mock_docker_from_env:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_docker_from_env.return_value = mock_client
            
            manager = SandboxManager(config=config)

            # Mock is_available and _build_docker_run_args
            with patch.object(manager, "is_available", return_value=True):
                with patch.object(manager, "_build_docker_run_args", return_value={}):
                    result = asyncio.run(
                        manager.execute("task-789", "rm -rf /tmp")
                    )

                    assert result.policy_violation is True
                    assert "denied pattern" in result.violation_details

    def test_network_policy_summary(self):
        """Test network policy reporting."""
        config = SandboxConfig(
            network_enabled=False,
            allowed_network_hosts=["api.example.com"]
        )
        manager = SandboxManager(config=config)
        
        summary = manager.get_network_policy_summary()
        
        assert summary["network_enabled"] is False
        assert summary["default_policy"] == "DENY_ALL"
    
    def test_filesystem_policy_summary(self):
        """Test filesystem policy reporting."""
        config = SandboxConfig(
            read_only_paths=["/etc"],
            writable_paths=["/workspace"]
        )
        manager = SandboxManager(config=config)
        
        summary = manager.get_filesystem_policy_summary()
        
        assert summary["workspace_isolated"] is True
        assert summary["read_only_root"] is True
        assert "/etc" in summary["read_only_paths"]


# ============================================================================
# Circuit Breaker Tests - Provider Resilience
# ============================================================================

class TestCircuitBreaker:
    """Test circuit breaker pattern for providers."""
    
    def test_circuit_starts_closed(self):
        """Test circuit breaker starts in closed state."""
        cb = CircuitBreaker("test-provider")
        assert cb.state == CircuitState.CLOSED
    
    def test_circuit_opens_after_failures(self):
        """Test circuit opens after threshold failures."""
        config = CircuitConfig(failure_threshold=3)
        cb = CircuitBreaker("test-provider", config=config)
        
        def failing_func():
            raise Exception("Provider error")
        
        # Trigger failures
        for _ in range(3):
            with pytest.raises(Exception):
                cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
    
    def test_circuit_rejects_when_open(self):
        """Test open circuit rejects requests."""
        config = CircuitConfig(failure_threshold=2, timeout_seconds=300)
        cb = CircuitBreaker("test-provider", config=config)
        
        def failing_func():
            raise Exception("Provider error")
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Should reject without calling function
        def success_func():
            return "success"
        
        with pytest.raises(CircuitOpenError) as exc_info:
            cb.call(success_func)
        
        assert "OPEN" in str(exc_info.value)
    
    def test_circuit_half_open_after_timeout(self):
        """Test circuit transitions to half-open after timeout."""
        config = CircuitConfig(
            failure_threshold=2,
            timeout_seconds=1,  # Short timeout for testing
            success_threshold=2
        )
        cb = CircuitBreaker("test-provider", config=config)
        
        def failing_func():
            raise Exception("Provider error")
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(failing_func)
        
        assert cb.state == CircuitState.OPEN
        
        # Wait for timeout
        import time
        time.sleep(1.1)
        
        # Should transition to half-open on next access
        assert cb.state == CircuitState.HALF_OPEN
    
    def test_circuit_closes_after_successes(self):
        """Test circuit closes after successful calls in half-open."""
        config = CircuitConfig(
            failure_threshold=2,
            timeout_seconds=0,  # Immediate half-open
            success_threshold=2
        )
        cb = CircuitBreaker("test-provider", config=config)
        
        call_count = [0]
        
        def failing_then_success():
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception("Initial failure")
            return "success"
        
        # Open the circuit
        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(failing_then_success)
        
        # Now succeed
        for _ in range(2):
            cb.call(failing_then_success)
        
        assert cb.state == CircuitState.CLOSED
    
    def test_circuit_stats_tracking(self):
        """Test circuit breaker statistics."""
        cb = CircuitBreaker("test-provider")
        
        def success_func():
            return "ok"
        
        def fail_func():
            raise Exception("error")
        
        # Record some results
        cb.call(success_func)
        cb.call(success_func)
        
        with pytest.raises(Exception):
            cb.call(fail_func)
        
        stats = cb.stats
        assert stats.total_calls == 3
        assert stats.successful_calls == 2
        assert stats.failed_calls == 1
        assert stats.consecutive_failures == 1
    
    def test_circuit_registry_singleton(self):
        """Test circuit breaker registry is singleton."""
        registry1 = CircuitBreakerRegistry()
        registry2 = CircuitBreakerRegistry()
        
        assert registry1 is registry2
    
    def test_circuit_registry_manages_multiple(self):
        """Test registry manages multiple circuits."""
        registry = CircuitBreakerRegistry()
        
        cb1 = registry.get_or_create("provider-a")
        cb2 = registry.get_or_create("provider-b")
        
        assert cb1.name == "provider-a"
        assert cb2.name == "provider-b"
        assert cb1 is not cb2
        
        all_names = registry.list_all()
        assert "provider-a" in all_names
        assert "provider-b" in all_names


# ============================================================================
# Validation Engine Tests - Hard Block on Skipped Reviews
# ============================================================================

class TestValidationEngine:
    """Test validation engine with hard blocks."""
    
    @pytest.mark.asyncio
    async def test_validation_passes_all_gates(self):
        """Test validation passes when all gates pass."""
        engine = ValidationEngine()
        
        code_review = ReviewResult(passed=True, score=0.9)
        security_review = ReviewResult(passed=True, score=0.95)
        
        report = await engine.validate_task(
            task_id="task-123",
            test_results={"passed": True, "total": 10, "failed": 0},
            code_reviews=[code_review],
            security_reviews=[security_review],
            build_success=True
        )
        
        assert report.can_finalize() is True
        assert report.status == "SUCCESS"
    
    @pytest.mark.asyncio
    async def test_validation_blocks_skipped_code_review(self):
        """Test validation blocks when code review is skipped."""
        engine = ValidationEngine()
        
        # Skipped review
        code_review = ReviewResult(passed=False, score=0.0, skipped=True)
        security_review = ReviewResult(passed=True, score=0.95)
        
        report = await engine.validate_task(
            task_id="task-456",
            test_results={"passed": True, "total": 10, "failed": 0},
            code_reviews=[code_review],
            security_reviews=[security_review],
            build_success=True
        )
        
        assert report.can_finalize() is False
        assert report.reviews_skipped is True
        assert "code_review" in report.skipped_reviews
        
        block_reason = report.get_block_reason()
        assert "Reviews were skipped" in block_reason
    
    @pytest.mark.asyncio
    async def test_validation_blocks_skipped_security_review(self):
        """Test validation blocks when security review is skipped."""
        engine = ValidationEngine()
        
        code_review = ReviewResult(passed=True, score=0.9)
        security_review = ReviewResult(passed=False, score=0.0, skipped=True)
        
        report = await engine.validate_task(
            task_id="task-789",
            test_results={"passed": True},
            code_reviews=[code_review],
            security_reviews=[security_review]
        )
        
        assert report.can_finalize() is False
        assert report.reviews_skipped is True
        assert "security_review" in report.skipped_reviews
    
    @pytest.mark.asyncio
    async def test_validation_blocks_test_failure(self):
        """Test validation blocks on test failure."""
        engine = ValidationEngine()
        
        code_review = ReviewResult(passed=True, score=0.9)
        security_review = ReviewResult(passed=True, score=0.95)
        
        report = await engine.validate_task(
            task_id="task-abc",
            test_results={"passed": False, "total": 10, "failed": 3},
            code_reviews=[code_review],
            security_reviews=[security_review]
        )
        
        assert report.can_finalize() is False
        assert report.tests_passed is False
    
    @pytest.mark.asyncio
    async def test_finalizer_enforces_hard_block(self):
        """Test finalizer refuses to finalize with skipped reviews."""
        engine = ValidationEngine()
        finalizer = Finalizer(engine)
        
        # Create report with skipped review
        code_review = ReviewResult(passed=False, score=0.0, skipped=True)
        
        report = await engine.validate_task(
            task_id="task-def",
            test_results={"passed": True},
            code_reviews=[code_review],
            security_reviews=[]
        )
        
        success, message = await finalizer.finalize_task("task-def", report)
        
        assert success is False
        assert "Reviews were skipped" in message
        assert finalizer.is_finalized("task-def") is False
    
    @pytest.mark.asyncio
    async def test_finalizer_allows_valid_task(self):
        """Test finalizer allows task with all gates passed."""
        engine = ValidationEngine()
        finalizer = Finalizer(engine)
        
        code_review = ReviewResult(passed=True, score=0.9)
        security_review = ReviewResult(passed=True, score=0.95)
        
        report = await engine.validate_task(
            task_id="task-ghi",
            test_results={"passed": True},
            code_reviews=[code_review],
            security_reviews=[security_review]
        )
        
        success, message = await finalizer.finalize_task("task-ghi", report)
        
        assert success is True
        assert "finalized successfully" in message.lower()
        assert finalizer.is_finalized("task-ghi") is True
    
    @pytest.mark.asyncio
    async def test_validation_report_block_reason(self):
        """Test validation report provides clear block reasons."""
        report = ValidationReport(
            task_id="test",
            tests_passed=True,
            code_review_passed=False,
            security_review_passed=True,
            reviews_skipped=False
        )
        
        assert report.can_finalize() is False
        reason = report.get_block_reason()
        assert "Code review" in reason
        
        # Now test skipped review reason
        report.reviews_skipped = True
        report.skipped_reviews = ["code_review", "security_review"]
        
        assert report.can_finalize() is False
        reason = report.get_block_reason()
        assert "Reviews were skipped" in reason
        assert "code_review" in reason
        assert "security_review" in reason


# ============================================================================
# Integration Tests
# ============================================================================

class TestSecurityIntegration:
    """Integration tests for security features."""
    
    def test_sandbox_config_denies_dangerous_commands(self):
        """Test sandbox configuration blocks dangerous patterns."""
        config = SandboxConfig(
            denied_commands=[
                "rm -rf",
                "sudo",
                "chmod 777",
                "curl | bash",
                "wget | sh",
                "> /etc/",
                "dd if=/dev/zero",
            ]
        )
        
        manager = SandboxManager(config=config)
        
        dangerous = ["rm -rf /", "sudo su", "chmod 777 /tmp"]
        safe = ["ls -la", "cat file.txt", "python test.py"]
        
        for cmd in dangerous:
            with pytest.raises(PolicyViolationError):
                manager._check_command_policy(cmd)
        
        for cmd in safe:
            manager._check_command_policy(cmd)  # Should not raise
    
    def test_circuit_breaker_prevents_cascading_failures(self):
        """Test circuit breaker prevents cascade across providers."""
        registry = CircuitBreakerRegistry()
        
        # Simulate provider A failing
        cb_a = registry.get_or_create("provider-a")
        cb_a._transition_to_open()
        
        # Provider B should still be healthy
        cb_b = registry.get_or_create("provider-b")
        assert cb_b.state == CircuitState.CLOSED
        
        # Get healthy providers
        healthy = registry.get_healthy_providers()
        assert "provider-b" in healthy
        assert "provider-a" not in healthy
    
    def test_validation_history_tracking(self):
        """Test validation history is tracked for retries."""
        engine = ValidationEngine(
            config=ValidationConfig(max_retries=3)
        )
        
        # Run multiple validations
        for i in range(3):
            asyncio.run(engine.validate_task(
                task_id="retry-test",
                test_results={"passed": False},
                code_reviews=[],
                security_reviews=[]
            ))
        
        history = engine.get_validation_history("retry-test")
        assert len(history) == 3
        
        # Check retry eligibility
        assert engine.should_retry("retry-test") is False  # Max retries exceeded
