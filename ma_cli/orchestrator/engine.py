"""Native orchestration facade.

External agent adapters remain available as optional integrations, but the core
orchestrator is now independent of Claude/Codex/Qwen CLI installations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..core.models import Task
from ..runtime.engine import NativeAgent, RuntimeResult


@dataclass
class OrchestrationResult:
    success: bool
    task_id: str
    output: str = ""
    error: str | None = None
    agent: str | None = "native_agent"
    attempts: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


class Orchestrator:
    """Compatibility facade that delegates execution to NativeAgent."""

    def __init__(self, runtime: NativeAgent | None = None):
        self.runtime = runtime or NativeAgent()

    async def choose_agent(self, task: Task, preferred: str | None = None):
        """Return the native agent unless an explicit external adapter is requested."""
        if preferred and preferred != "native_agent":
            # Deliberately do not make external CLIs a runtime dependency.
            return None
        return self.runtime

    async def run(self, prompt: str, preferred_agent: str | None = None, timeout: int = 900, retries: int = 1) -> OrchestrationResult:
        started = datetime.now(timezone.utc)
        if preferred_agent and preferred_agent != "native_agent":
            return OrchestrationResult(False, "", error="External agent selection is not part of the native runtime; use native_agent or an explicit adapter integration.", started_at=started, finished_at=datetime.now(timezone.utc))
        try:
            result: RuntimeResult = await self.runtime.run(prompt)
            task_id = next(iter(result.task_results), "")
            return OrchestrationResult(
                success=result.success,
                task_id=task_id,
                output=result.output,
                error=result.blocked_reason,
                attempts=result.attempts,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                evidence={k: v.evidence for k, v in result.task_results.items()},
            )
        except Exception as exc:
            return OrchestrationResult(False, "", error=str(exc), started_at=started, finished_at=datetime.now(timezone.utc))


_orchestrator: Orchestrator | None = None

def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
