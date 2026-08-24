"""Autonomous orchestration with native runtime as the primary execution path."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..agents.adapters import get_agent_registry
from ..core.models import ExecutionResult, Task
from ..runtime.native import NativeAgent


@dataclass
class OrchestrationResult:
    success: bool
    task_id: str
    output: str = ""
    error: str | None = None
    agent: str | None = None
    attempts: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    metadata: dict = field(default_factory=dict)


class Orchestrator:
    """Coordinates native autonomy and optional external agents.

    NativeAgent is always attempted first. External coding CLIs are fallback
    integrations, never a required dependency for MA-CLI autonomy.
    """

    def __init__(self, registry=None, workspace: Path | None = None, native_model=None):
        self.registry = registry or get_agent_registry()
        self.workspace = (workspace or Path.cwd()).resolve()
        self.native = NativeAgent(self.workspace, model=native_model)

    async def run(self, prompt: str, preferred_agent: str | None = None,
                  timeout: int = 900, retries: int = 1, allow_external_fallback: bool = True):
        task = Task(title=prompt[:120], description=prompt)
        started = datetime.now(timezone.utc)
        try:
            native = await asyncio.wait_for(self.native.run(prompt), timeout=timeout)
            if native.success:
                return OrchestrationResult(True, task.id, native.output, agent="native-agent",
                                           attempts=native.attempts, started_at=started,
                                           finished_at=datetime.now(timezone.utc),
                                           metadata={"evidence": native.evidence})
            native_error = native.error or "native runtime did not converge"
        except asyncio.TimeoutError:
            native_error = f"native runtime timed out after {timeout}s"
        except Exception as exc:
            native_error = f"native runtime error: {exc}"

        if not allow_external_fallback:
            return OrchestrationResult(False, task.id, error=native_error, agent="native-agent",
                                       started_at=started, finished_at=datetime.now(timezone.utc))

        agent = None
        if preferred_agent:
            agent = self.registry.get(preferred_agent) or self.registry.get_by_name(preferred_agent)
        if agent is None:
            for candidate in self.registry.list_all():
                try:
                    health = await candidate.health_check()
                    if getattr(health, "value", health) == "healthy":
                        agent = candidate
                        break
                except Exception:
                    continue
        if agent is None:
            return OrchestrationResult(False, task.id, error=native_error,
                                       agent="native-agent", started_at=started,
                                       finished_at=datetime.now(timezone.utc))
        last_error = native_error
        for attempt in range(1, retries + 2):
            try:
                result: ExecutionResult = await asyncio.wait_for(agent.execute(task), timeout=timeout)
                if result.success:
                    return OrchestrationResult(True, task.id, result.output, agent=agent.id,
                                               attempts=attempt, started_at=started,
                                               finished_at=datetime.now(timezone.utc),
                                               metadata={"fallback": True})
                last_error = result.error or "agent execution failed"
            except asyncio.TimeoutError:
                last_error = f"fallback agent timed out after {timeout}s"
            except Exception as exc:
                last_error = str(exc)
        return OrchestrationResult(False, task.id, error=last_error, agent=agent.id,
                                   attempts=retries + 1, started_at=started,
                                   finished_at=datetime.now(timezone.utc), metadata={"fallback": True})


_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
