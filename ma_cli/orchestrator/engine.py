"""Autonomous task orchestration using the existing agent registry."""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from ..agents.adapters import get_agent_registry
from ..core.models import Task, ExecutionResult

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

class Orchestrator:
    def __init__(self, registry=None):
        self.registry = registry or get_agent_registry()

    async def choose_agent(self, task: Task, preferred: str | None = None):
        if preferred:
            agent = self.registry.get(preferred) or self.registry.get_by_name(preferred)
            if agent: return agent
        for agent in self.registry.list_all():
            try:
                health = await agent.health_check()
                if getattr(health, "value", health) == "healthy":
                    if not task.required_capabilities or set(task.required_capabilities).issubset(agent.capabilities):
                        return agent
            except Exception:
                continue
        return None

    async def run(self, prompt: str, preferred_agent: str | None = None, timeout: int = 900, retries: int = 1):
        task = Task(title=prompt[:120], description=prompt)
        started = datetime.now(timezone.utc)
        agent = await self.choose_agent(task, preferred_agent)
        if not agent:
            return OrchestrationResult(False, task.id, error="No healthy coding agent is available.",
                                       started_at=started, finished_at=datetime.now(timezone.utc))
        last_error = None
        for attempt in range(1, retries + 2):
            try:
                result: ExecutionResult = await asyncio.wait_for(agent.execute(task), timeout=timeout)
                if result.success:
                    return OrchestrationResult(True, task.id, result.output, agent=agent.id,
                                               attempts=attempt, started_at=started,
                                               finished_at=datetime.now(timezone.utc))
                last_error = result.error or "agent execution failed"
            except asyncio.TimeoutError:
                last_error = f"orchestration timed out after {timeout}s"
            except Exception as exc:
                last_error = str(exc)
        return OrchestrationResult(False, task.id, error=last_error, agent=agent.id,
                                   attempts=retries + 1, started_at=started,
                                   finished_at=datetime.now(timezone.utc))

_orchestrator = None
def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None: _orchestrator = Orchestrator()
    return _orchestrator
