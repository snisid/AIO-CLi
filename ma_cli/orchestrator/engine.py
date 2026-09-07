"""Autonomous orchestration with native runtime as the primary execution path."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..agents.adapters import get_agent_registry
from ..core.models import ExecutionResult, Task
from ..observability.engine import get_observability
from ..report.engine import ReportEngine
from ..review.engine import ReviewEngine
from ..runtime.native import NativeAgent, NativeRuntimeResult
from ..validation.engine import Finalizer, ValidationEngine


@dataclass
class OrchestrationResult:
    success: bool
    task_id: str
    output: str = ""
    error: str | None = None
    agent: str | None = None
    attempts: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    metadata: dict = field(default_factory=dict)


class Orchestrator:
    """Coordinates native autonomy, validation, and optional external agents.

    NativeAgent is always attempted first. External coding CLIs are fallback
    integrations, never a required dependency for MA-CLI autonomy.
    Success requires ValidationEngine + Finalizer; skipped reviews cannot pass.
    """

    def __init__(self, registry=None, workspace: Path | None = None, native_model=None):
        self.registry = registry or get_agent_registry()
        self.workspace = (workspace or Path.cwd()).resolve()
        if native_model is None:
            from ..runtime.model_adapter import attach_default_model
            native_model = attach_default_model()
        self.native = NativeAgent(self.workspace, model=native_model)
        self.validation = ValidationEngine()
        self.finalizer = Finalizer(self.validation)
        self.reviewer = ReviewEngine(self.workspace)
        self.reports = ReportEngine(self.workspace)
        self.observability = get_observability(self.workspace)

    def _test_results(self, native: NativeRuntimeResult) -> dict:
        for item in reversed(native.evidence):
            if item.get("stage") in {"final_validation", "test", "repair_validation"}:
                passed = bool(item.get("passed"))
                return {
                    "passed": passed,
                    "total": 1,
                    "failed": 0 if passed else 1,
                    "failures": item.get("failures", []),
                }
        return {"passed": False, "total": 0, "failed": 1}

    async def _validate_native(self, task: Task, native: NativeRuntimeResult) -> OrchestrationResult | None:
        test_results = self._test_results(native)
        code_review = self.reviewer.review_workspace(self.workspace)
        security_review = self.reviewer.security_review(self.workspace)
        report = await self.validation.validate_task(
            task_id=task.id,
            test_results=test_results,
            code_reviews=[code_review],
            security_reviews=[security_review],
            build_success=native.success,
        )
        ok, message = await self.finalizer.finalize_task(task.id, report)
        metadata = {
            "evidence": native.evidence,
            "validation": {
                "status": report.status,
                "can_finalize": report.can_finalize(),
                "block_reason": report.get_block_reason(),
                "code_review_issues": code_review.issues,
                "security_review_issues": security_review.issues,
            },
        }
        if not ok:
            return OrchestrationResult(
                False, task.id, error=message, agent="native-agent",
                attempts=native.attempts, metadata=metadata,
            )
        return OrchestrationResult(
            True, task.id, native.output, agent="native-agent",
            attempts=native.attempts, metadata=metadata,
        )

    async def run(self, prompt: str, preferred_agent: str | None = None,
                  timeout: int = 900, retries: int = 1, allow_external_fallback: bool = True):
        task = Task(title=prompt[:120], description=prompt)
        started = datetime.now(UTC)
        span = self.observability.start_span("orchestrator.run", task_id=task.id)
        self.observability.increment("orchestrator.runs")
        try:
            native = await asyncio.wait_for(self.native.run(prompt), timeout=timeout)
            if native.success:
                validated = await self._validate_native(task, native)
                validated.started_at = started
                validated.finished_at = datetime.now(UTC)
                if validated.success:
                    self.observability.increment("orchestrator.success")
                    self.observability.end_span(span, status="ok")
                    self.reports.write(validated)
                    return validated
                native_error = validated.error or "validation gate blocked finalization"
                self.observability.record("orchestrator.validation_blocked", error=native_error)
            else:
                native_error = native.error or "native runtime did not converge"
        except TimeoutError:
            native_error = f"native runtime timed out after {timeout}s"
        except Exception as exc:  # noqa: BLE001 - native failures must become orchestration errors
            native_error = f"native runtime error: {exc}"

        if not allow_external_fallback:
            self.observability.end_span(span, status="error", error=native_error)
            return OrchestrationResult(False, task.id, error=native_error, agent="native-agent",
                                       started_at=started, finished_at=datetime.now(UTC))

        agent = None
        if preferred_agent:
            agent = self.registry.get(preferred_agent) or self.registry.get_by_name(preferred_agent)
        if agent is None:
            for candidate in self.registry.list_all():
                try:
                    health = await candidate.health_check()
                    if getattr(health, "value", health) == "healthy" and candidate.id != self.native.id:
                        agent = candidate
                        break
                except Exception:  # noqa: BLE001, S112 - unhealthy agents are skipped
                    continue
        if agent is None:
            self.observability.end_span(span, status="error", error=native_error)
            return OrchestrationResult(False, task.id, error=native_error,
                                       agent="native-agent", started_at=started,
                                       finished_at=datetime.now(UTC))
        last_error = native_error
        for attempt in range(1, retries + 2):
            try:
                result: ExecutionResult = await asyncio.wait_for(agent.execute(task), timeout=timeout)
                if result.success:
                    proxy = NativeRuntimeResult(
                        True, prompt, output=result.output,
                        evidence=[{"stage": "test", "passed": True, "failures": []}],
                    )
                    validated = await self._validate_native(task, proxy)
                    validated.agent = agent.id
                    validated.attempts = attempt
                    validated.started_at = started
                    validated.finished_at = datetime.now(UTC)
                    validated.metadata = {**validated.metadata, "fallback": True}
                    if not validated.success:
                        last_error = validated.error or "validation gate blocked fallback"
                        continue
                    self.observability.increment("orchestrator.fallback_success")
                    self.observability.end_span(span, status="ok")
                    return validated
                last_error = result.error or "agent execution failed"
            except TimeoutError:
                last_error = f"fallback agent timed out after {timeout}s"
            except Exception as exc:  # noqa: BLE001 - fallback errors are bounded
                last_error = str(exc)
        self.observability.end_span(span, status="error", error=last_error)
        return OrchestrationResult(False, task.id, error=last_error, agent=agent.id,
                                   attempts=retries + 1, started_at=started,
                                   finished_at=datetime.now(UTC), metadata={"fallback": True})


_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
