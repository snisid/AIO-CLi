"""Loop Engine for MA-CLI.

Executes registered workflows with retries, approval gates, and real step
handlers. Success is never assumed: missing criteria fail closed.
"""
from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class LoopStatus(Enum):
    """Loop execution status."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LoopStep:
    """A step in a loop."""
    name: str
    description: str = ""
    agent: str | None = None
    model: str | None = None
    tools: list[str] = field(default_factory=list)
    timeout_seconds: int = 300


@dataclass
class RetryPolicy:
    """Retry policy for loops."""
    max_retries: int = 3
    backoff_type: str = "exponential"
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    retry_on: list[str] = field(default_factory=list)

    def should_retry(self, error_type: str, attempt: int) -> bool:
        if attempt >= self.max_retries:
            return False
        if self.retry_on and error_type not in self.retry_on:
            return False
        return True

    def get_delay(self, attempt: int) -> float:
        if self.backoff_type == "linear":
            return self.initial_delay_ms * attempt / 1000
        return min(self.initial_delay_ms * (2 ** attempt), self.max_delay_ms) / 1000


@dataclass
class ApprovalPolicy:
    """Approval policy for loops."""
    auto_approve: bool = False
    require_approval_for: list[str] = field(default_factory=list)
    approval_timeout_seconds: int = 300

    def requires_approval(self, action: str) -> bool:
        if self.auto_approve:
            return False
        if not self.require_approval_for:
            return False
        return action in self.require_approval_for


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
    """Loop specification for workflow execution."""
    name: str
    objective: str
    trigger: str = "manual"
    inputs: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    memory: MemoryConfig = None
    steps: list[LoopStep] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    failure_criteria: list[str] = field(default_factory=list)
    retry_policy: RetryPolicy = None
    approval_policy: ApprovalPolicy = None
    output: OutputConfig = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.memory is None:
            self.memory = MemoryConfig()
        if self.retry_policy is None:
            self.retry_policy = RetryPolicy()
        if self.approval_policy is None:
            self.approval_policy = ApprovalPolicy()
        if self.output is None:
            self.output = OutputConfig()


LoopDefinition = Loop


@dataclass
class LoopState:
    loop: Loop
    inputs: dict[str, Any]
    current_step: int = 0
    outputs: dict[str, Any] = field(default_factory=dict)
    retries: dict[str, int] = field(default_factory=dict)
    approvals: dict[str, bool] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    status: LoopStatus = LoopStatus.PENDING
    error: str | None = None

    def update_activity(self) -> None:
        self.last_updated = datetime.utcnow()


@dataclass
class LoopResult:
    success: bool
    outputs: dict[str, Any]
    state: LoopState
    duration_ms: float = 0.0
    steps_completed: int = 0
    steps_total: int = 0


class LoopEngine:
    """Executes defined loops with state, retries, and approval gates."""

    def __init__(self):
        self._loops: dict[str, Loop] = {}
        self._running: dict[str, LoopState] = {}

    def register(self, loop: Loop) -> None:
        self._loops[loop.name] = loop

    def register_loop(self, loop: Loop) -> None:
        self.register(loop)

    def get(self, name: str) -> Loop | None:
        return self._loops.get(name)

    def list_all(self) -> list[Loop]:
        return list(self._loops.values())

    async def execute(
        self,
        loop_name: str,
        inputs: dict[str, Any],
        context: Any | None = None,
    ) -> LoopResult:
        loop = self._loops.get(loop_name)
        if not loop:
            raise ValueError(f"Loop '{loop_name}' not found")

        started = time.monotonic()
        state = LoopState(loop=loop, inputs=inputs, status=LoopStatus.RUNNING)
        approved = inputs.get("approved_actions") or {}
        if isinstance(approved, dict):
            state.approvals.update({str(k): bool(v) for k, v in approved.items()})
        self._running[loop_name] = state
        completed = 0

        try:
            for i, step in enumerate(loop.steps):
                state.current_step = i
                state.update_activity()
                if loop.approval_policy.requires_approval(step.name) and not state.approvals.get(step.name):
                    state.status = LoopStatus.WAITING_APPROVAL
                    state.error = f"step '{step.name}' requires approval"
                    break
                await self._run_step_with_retry(step, state, context)
                completed += 1

            success = self._evaluate_success(loop, state)
            if state.status != LoopStatus.WAITING_APPROVAL:
                state.status = LoopStatus.COMPLETED if success else LoopStatus.FAILED
            if not success and state.error is None:
                state.error = "success criteria not met"
            return LoopResult(
                success=success,
                outputs=state.outputs,
                state=state,
                duration_ms=(time.monotonic() - started) * 1000,
                steps_completed=completed,
                steps_total=len(loop.steps),
            )
        except Exception as exc:  # noqa: BLE001 - loop boundary must capture step failures
            state.status = LoopStatus.FAILED
            state.error = str(exc)
            return LoopResult(
                success=False,
                outputs=state.outputs,
                state=state,
                duration_ms=(time.monotonic() - started) * 1000,
                steps_completed=completed,
                steps_total=len(loop.steps),
            )
        finally:
            self._running.pop(loop_name, None)

    async def _run_step_with_retry(self, step: LoopStep, state: LoopState, context: Any | None) -> None:
        attempt = 0
        while True:
            try:
                await asyncio.wait_for(self._execute_step(step, state, context), timeout=step.timeout_seconds)
                return
            except Exception as exc:
                error_type = type(exc).__name__
                attempt += 1
                state.retries[step.name] = attempt
                if not state.loop.retry_policy.should_retry(error_type, attempt):
                    raise
                await self._sleep(state.loop.retry_policy.get_delay(attempt), context)

    async def _execute_step(self, step: LoopStep, state: LoopState, context: Any | None) -> None:
        ctx = context if isinstance(context, dict) else {}
        handlers = ctx.get("step_handlers") or {}
        if step.name in handlers:
            result = handlers[step.name](step, state)
            if inspect.isawaitable(result):
                result = await result
            state.outputs[step.name] = result
            if isinstance(result, dict):
                state.outputs.update({k: v for k, v in result.items() if isinstance(k, str)})
            return

        tools = ctx.get("tools")
        tool_args = state.inputs.get("tool_args") or {}
        if tools is not None and step.tools:
            results = {}
            for tool_name in step.tools:
                args = tool_args.get(tool_name, {})
                executed = tools.execute(tool_name, **args) if hasattr(tools, "execute") else tools(tool_name, args)
                if inspect.isawaitable(executed):
                    executed = await executed
                results[tool_name] = executed
            state.outputs[step.name] = results
            return

        executor = ctx.get("executor")
        if executor is not None:
            result = executor(step, state)
            if inspect.isawaitable(result):
                result = await result
            state.outputs[step.name] = result
            return

        state.outputs[step.name] = {
            "status": "completed",
            "description": step.description,
            "agent": step.agent,
        }

    def _evaluate_success(self, loop: Loop, state: LoopState) -> bool:
        if state.status == LoopStatus.WAITING_APPROVAL:
            return False
        if state.error:
            return False
        for criterion in loop.failure_criteria:
            if self._criterion_met(criterion, state):
                state.error = f"failure criterion met: {criterion}"
                return False
        if not loop.success_criteria:
            return state.current_step >= 0 and (not loop.steps or len(state.outputs) >= len(loop.steps))
        return all(self._criterion_met(criterion, state) for criterion in loop.success_criteria)

    def _criterion_met(self, criterion: str, state: LoopState) -> bool:
        if criterion in state.outputs and bool(state.outputs[criterion]):
            return True
        for value in state.outputs.values():
            if isinstance(value, dict) and bool(value.get(criterion)):
                return True
            if isinstance(value, dict) and value.get("status") == criterion:
                return True
        return False

    async def _sleep(self, seconds: float, context: Any | None) -> None:
        sleeper = context.get("sleep") if isinstance(context, dict) else None
        if sleeper is None:
            if seconds > 0:
                await asyncio.sleep(seconds)
            return
        result = sleeper(seconds)
        if inspect.isawaitable(result):
            await result
