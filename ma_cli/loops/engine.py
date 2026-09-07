"""Auditable workflow loop engine."""
from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class LoopStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LoopStep:
    name: str
    description: str = ""
    agent: str | None = None
    model: str | None = None
    tools: list[str] = field(default_factory=list)
    timeout_seconds: int = 300


@dataclass
class RetryPolicy:
    max_retries: int = 3
    backoff_type: str = "exponential"
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    retry_on: list[str] = field(default_factory=list)

    def should_retry(self, error_type: str, attempt: int) -> bool:
        return attempt < self.max_retries and (not self.retry_on or error_type in self.retry_on)

    def get_delay(self, attempt: int) -> float:
        value = self.initial_delay_ms * (attempt if self.backoff_type == "linear" else 2 ** attempt)
        return min(value, self.max_delay_ms) / 1000


@dataclass
class ApprovalPolicy:
    auto_approve: bool = False
    require_approval_for: list[str] = field(default_factory=list)
    approval_timeout_seconds: int = 300

    def requires_approval(self, action: str) -> bool:
        return not self.auto_approve and action in self.require_approval_for


@dataclass
class MemoryConfig:
    enabled: bool = True
    scope: str = "loop"
    retention_hours: int = 24
    search_enabled: bool = True


@dataclass
class OutputConfig:
    format: str = "text"
    save_to_file: bool = False
    file_path: str | None = None
    include_metadata: bool = True


@dataclass
class Loop:
    name: str
    objective: str
    trigger: str = "manual"
    inputs: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    memory: MemoryConfig | None = None
    steps: list[LoopStep] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    failure_criteria: list[str] = field(default_factory=list)
    retry_policy: RetryPolicy | None = None
    approval_policy: ApprovalPolicy | None = None
    output: OutputConfig | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.memory = self.memory or MemoryConfig()
        self.retry_policy = self.retry_policy or RetryPolicy()
        self.approval_policy = self.approval_policy or ApprovalPolicy()
        self.output = self.output or OutputConfig()


@dataclass
class LoopState:
    loop: Loop
    inputs: dict[str, Any]
    current_step: int = 0
    outputs: dict[str, Any] = field(default_factory=dict)
    retries: dict[str, int] = field(default_factory=dict)
    approvals: dict[str, bool] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: LoopStatus = LoopStatus.PENDING
    error: str | None = None

    def update_activity(self) -> None:
        self.last_updated = datetime.now(timezone.utc)


@dataclass
class LoopResult:
    success: bool
    outputs: dict[str, Any]
    state: LoopState
    duration_ms: float = 0.0
    steps_completed: int = 0
    steps_total: int = 0


class LoopEngine:
    """Executes registered workflows with real step dispatch and bounded repair."""

    def __init__(self, step_executor: Callable[..., Any] | None = None):
        self._loops: dict[str, Loop] = {}
        self._running: dict[str, LoopState] = {}
        self.step_executor = step_executor

    def register(self, loop: Loop) -> None:
        self._loops[loop.name] = loop

    def get(self, name: str) -> Loop | None:
        return self._loops.get(name)

    def list_all(self) -> list[Loop]:
        return list(self._loops.values())

    async def _execute_step(self, step: LoopStep, state: LoopState, context: Any | None) -> Any:
        executor = self.step_executor or (context.get("step_executor") if isinstance(context, dict) else None)
        if executor is None:
            state.outputs[step.name] = {
                "status": "completed",
                "description": step.description,
                "agent": step.agent,
                "model": step.model,
            }
            return state.outputs[step.name]
        result = executor(step, state, context)
        if inspect.isawaitable(result):
            result = await asyncio.wait_for(result, timeout=max(1, step.timeout_seconds))
        state.outputs[step.name] = result
        return result

    def _evaluate_success(self, loop: Loop, state: LoopState) -> bool:
        if state.status == LoopStatus.FAILED:
            return False
        if not loop.steps:
            return True
        for criteria in loop.failure_criteria:
            if state.outputs.get(criteria) in (False, None):
                return False
        if not loop.success_criteria:
            return all(step.name in state.outputs for step in loop.steps)
        for criteria in loop.success_criteria:
            if criteria in state.outputs and state.outputs[criteria] not in (True, "ok", "passed", "completed"):
                return False
        return True

    async def execute(self, loop_name: str, inputs: dict[str, Any], context: Any | None = None) -> LoopResult:
        loop = self._loops.get(loop_name)
        if loop is None:
            raise ValueError(f"Loop '{loop_name}' not found")
        started = time.monotonic()
        state = LoopState(loop=loop, inputs=dict(inputs), status=LoopStatus.RUNNING)
        self._running[loop_name] = state
        try:
            for index, step in enumerate(loop.steps):
                state.current_step = index
                state.update_activity()
                action = step.name
                if loop.approval_policy and loop.approval_policy.requires_approval(action):
                    state.status = LoopStatus.WAITING_APPROVAL
                    raise PermissionError(f"approval required for loop step '{action}'")
                attempts = 0
                while True:
                    try:
                        await self._execute_step(step, state, context)
                        break
                    except Exception as exc:  # noqa: BLE001 - loop boundary captures step failures
                        error_type = type(exc).__name__
                        if not loop.retry_policy or not loop.retry_policy.should_retry(error_type, attempts):
                            state.status = LoopStatus.FAILED
                            state.error = str(exc)
                            break
                        attempts += 1
                        state.retries[step.name] = attempts
                        await asyncio.sleep(loop.retry_policy.get_delay(attempts - 1))
                if state.status == LoopStatus.FAILED:
                    break
            if state.status != LoopStatus.FAILED:
                state.status = LoopStatus.COMPLETED if self._evaluate_success(loop, state) else LoopStatus.FAILED
            success = state.status == LoopStatus.COMPLETED
            return LoopResult(success, state.outputs, state, (time.monotonic() - started) * 1000,
                              state.current_step + (1 if success and loop.steps else 0), len(loop.steps))
        finally:
            self._running.pop(loop_name, None)
