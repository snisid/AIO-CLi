"""
Validation Engine for MA-CLI.

Enforces quality gates with hard blocks on skipped reviews.
No task can be finalized without passing all required checks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from ..core.models import (
    ReviewResult,
    ValidationReport,
    TaskStatus,
)
from ..events.bus import EventBus

logger = logging.getLogger(__name__)


@dataclass
class ValidationConfig:
    """Configuration for validation engine."""
    
    require_tests: bool = True
    require_code_review: bool = True
    require_security_review: bool = True
    require_build: bool = False  # Optional, depends on project type
    
    # Hard block settings
    block_on_skipped_review: bool = True  # CRITICAL: Never allow skipped reviews
    block_on_test_failure: bool = True
    max_retries: int = 3
    
    # Thresholds
    min_review_score: float = 0.7
    max_critical_issues: int = 0
    max_high_issues: int = 2


class ValidationEngine:
    """
    Validation engine enforcing quality gates.
    
    CRITICAL FEATURES:
    - Hard block on skipped reviews (no silent skips)
    - Aggregates test, review, security, and build results
    - Determines finalization eligibility
    - Provides detailed block reasons
    """
    
    def __init__(
        self,
        config: Optional[ValidationConfig] = None,
        event_bus: Optional[EventBus] = None
    ):
        self.config = config or ValidationConfig()
        self.event_bus = event_bus
        self._validation_history: dict[str, list[ValidationReport]] = {}
    
    async def validate_task(
        self,
        task_id: str,
        test_results: Optional[dict[str, Any]] = None,
        code_reviews: list[ReviewResult] = None,
        security_reviews: list[ReviewResult] = None,
        build_output: Optional[str] = None,
        build_success: bool = True
    ) -> ValidationReport:
        """
        Perform comprehensive validation for a task.
        
        Returns ValidationReport with can_finalize() method.
        """
        code_reviews = code_reviews or []
        security_reviews = security_reviews or []
        
        logger.info(f"Starting validation for task {task_id}")
        
        report = ValidationReport(
            task_id=task_id,
            test_results=test_results,
            code_review_results=code_reviews,
            security_review_results=security_reviews,
            build_output=build_output
        )
        
        # Evaluate tests
        report.tests_passed = self._evaluate_tests(test_results)
        
        # Evaluate code reviews
        report.code_review_passed = self._evaluate_code_reviews(code_reviews)
        
        # Track skipped reviews
        skipped_code_reviews = [r for r in code_reviews if r.skipped]
        if skipped_code_reviews:
            report.reviews_skipped = True
            report.skipped_reviews.append("code_review")
            logger.warning(
                f"Task {task_id}: {len(skipped_code_reviews)} code review(s) skipped"
            )
        
        # Evaluate security reviews
        report.security_review_passed = self._evaluate_security_reviews(security_reviews)
        
        skipped_security_reviews = [r for r in security_reviews if r.skipped]
        if skipped_security_reviews:
            report.reviews_skipped = True
            report.skipped_reviews.append("security_review")
            logger.warning(
                f"Task {task_id}: {len(skipped_security_reviews)} security review(s) skipped"
            )
        
        # Evaluate build
        report.build_passed = build_success if self.config.require_build else True
        
        # Determine overall status
        report.status = self._determine_status(report)
        
        # Store history
        if task_id not in self._validation_history:
            self._validation_history[task_id] = []
        self._validation_history[task_id].append(report)
        
        # Emit event
        if self.event_bus:
            await self.event_bus.emit(
                "validation_completed",
                {
                    "task_id": task_id,
                    "status": report.status,
                    "can_finalize": report.can_finalize(),
                    "block_reason": report.get_block_reason()
                }
            )
        
        # Log result
        if report.can_finalize():
            logger.info(f"Task {task_id} PASSED validation - ready for finalization")
        else:
            reason = report.get_block_reason()
            logger.error(f"Task {task_id} FAILED validation - {reason}")
        
        return report
    
    def _evaluate_tests(self, test_results: Optional[dict[str, Any]]) -> bool:
        """Evaluate test results."""
        if not self.config.require_tests:
            return True
        
        if test_results is None:
            logger.warning("No test results available")
            return False
        
        # Check if tests passed
        passed = test_results.get("passed", False)
        total = test_results.get("total", 0)
        failed = test_results.get("failed", 0)
        
        if not passed:
            return False
        
        # Check failure count
        if failed > 0:
            return False
        
        return True
    
    def _evaluate_code_reviews(self, reviews: list[ReviewResult]) -> bool:
        """Evaluate code review results."""
        if not self.config.require_code_review:
            return True
        
        if not reviews:
            logger.warning("No code reviews available")
            return False
        
        # Check for skipped reviews (handled separately in main validate)
        non_skipped = [r for r in reviews if not r.skipped]
        if not non_skipped:
            return False
        
        # Check scores
        for review in non_skipped:
            if review.score < self.config.min_review_score:
                logger.warning(f"Code review score {review.score} below threshold")
                return False
            
            if not review.passed:
                return False
        
        return True
    
    def _evaluate_security_reviews(self, reviews: list[ReviewResult]) -> bool:
        """Evaluate security review results."""
        if not self.config.require_security_review:
            return True
        
        if not reviews:
            logger.warning("No security reviews available")
            return False
        
        # Check for skipped reviews (handled separately in main validate)
        non_skipped = [r for r in reviews if not r.skipped]
        if not non_skipped:
            return False
        
        # Security reviews must pass
        for review in non_skipped:
            if not review.passed:
                logger.warning(f"Security review failed: {review.issues}")
                return False
        
        return True
    
    def _determine_status(self, report: ValidationReport) -> str:
        """Determine overall validation status."""
        if report.can_finalize():
            return "SUCCESS"
        
        if report.reviews_skipped:
            return "REQUIRES_HUMAN"
        
        if not report.tests_passed or not report.code_review_passed or not report.security_review_passed:
            return "FAILED"
        
        return "PENDING"
    
    def get_validation_history(self, task_id: str) -> list[ValidationReport]:
        """Get validation history for a task."""
        return self._validation_history.get(task_id, [])
    
    def should_retry(self, task_id: str) -> bool:
        """Check if task should be retried based on validation history."""
        history = self.get_validation_history(task_id)
        if not history:
            return True
        
        # Count consecutive failures
        consecutive_failures = 0
        for report in reversed(history):
            if not report.can_finalize():
                consecutive_failures += 1
            else:
                break
        
        return consecutive_failures < self.config.max_retries


class Finalizer:
    """
    Finalizer that enforces validation gates.
    
    CRITICAL: Will NOT finalize tasks with skipped reviews.
    This is a hard block - no configuration option to bypass.
    """
    
    def __init__(
        self,
        validation_engine: ValidationEngine,
        event_bus: Optional[EventBus] = None
    ):
        self.validation_engine = validation_engine
        self.event_bus = event_bus
        self._finalized_tasks: set[str] = set()
    
    async def finalize_task(
        self,
        task_id: str,
        validation_report: Optional[ValidationReport] = None
    ) -> tuple[bool, str]:
        """
        Attempt to finalize a task.
        
        Returns:
            Tuple of (success, message)
            
        CRITICAL: Returns (False, block_reason) if validation fails,
        especially if reviews were skipped.
        """
        # Get or run validation
        if validation_report is None:
            validation_report = await self.validation_engine.validate_task(task_id)
        
        # HARD BLOCK: Check if task can be finalized
        if not validation_report.can_finalize():
            reason = validation_report.get_block_reason()
            
            logger.critical(
                f"FINALIZATION BLOCKED for task {task_id}: {reason}"
            )
            
            # Emit blocking event
            if self.event_bus:
                await self.event_bus.emit(
                    "finalization_blocked",
                    {
                        "task_id": task_id,
                        "reason": reason,
                        "reviews_skipped": validation_report.reviews_skipped,
                        "skipped_reviews": validation_report.skipped_reviews
                    }
                )
            
            return False, reason
        
        # All gates passed - proceed with finalization
        logger.info(f"Finalizing task {task_id}")
        
        self._finalized_tasks.add(task_id)
        
        if self.event_bus:
            await self.event_bus.emit(
                "finalized",
                {
                    "task_id": task_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        return True, "Task finalized successfully"
    
    def is_finalized(self, task_id: str) -> bool:
        """Check if task has been finalized."""
        return task_id in self._finalized_tasks
    
    def get_finalized_tasks(self) -> set[str]:
        """Get all finalized task IDs."""
        return self._finalized_tasks.copy()
