"""Native autonomous execution loop.

The runtime owns planning, execution, observation, testing, bounded repair,
and finalization. External coding CLIs are not required.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import time
from typing import Any

from ..core.models import ExecutionResult
from ..security.runtime_policy import RuntimeSecurity
from ..tools.registry import ToolRegistry
from .planner import Planner, TaskRole


@dataclass
class NativeRuntimeResult:
    success: bool
    prompt: str
    output: str = ""
    error: str | None = None
    attempts: int = 0
    task_count: int = 0
    evidence: list[dict[str, Any]] = field(default_factory=list)


class NativeAgent:
    """Provider-agnostic autonomous runtime with bounded repair."""

    def __init__(self, workspace: Path, model: Any | None = None, max_repair_attempts: int = 2):
        self.workspace = workspace.resolve()
        self.model = model
        self.max_repair_attempts = max(0, max_repair_attempts)
        self.security = RuntimeSecurity(self.workspace)
        self.tools = ToolRegistry(self.workspace)

    async def _test(self) -> dict[str, Any]:
        started = time.monotonic()
        commands = [("python -m pytest -q", 300), ("python -m compileall -q ma_cli", 120)]
        failures = []
        output = []
        for command, timeout in commands:
            decision = self.security.authorize_command(command, approved=True)
            if not decision.allowed:
                failures.append(decision.reason)
                continue
            try:
                proc = await asyncio.to_thread(
                    subprocess.run, command, cwd=self.workspace, shell=True,
                    capture_output=True, text=True, timeout=timeout, check=False,
                )
                output.append(proc.stdout + proc.stderr)
                if proc.returncode != 0:
                    failures.append(f"{command}: exit {proc.returncode}")
            except subprocess.TimeoutExpired:
                failures.append(f"{command}: timeout")
        return {"passed": not failures, "failures": failures, "output": "\n".join(output),
                "duration_ms": int((time.monotonic() - started) * 1000)}

    async def _model_step(self, prompt: str, role: TaskRole) -> str:
        if self.model is None:
            return f"{role.value} planned; no model provider attached"
        complete = getattr(self.model, "complete", None)
        if complete is None:
            raise TypeError("model must expose async complete(messages, ...) method")
        response = await complete([{"role": "user", "content": prompt}], strategy=role.value,
                                  capabilities=[])
        return getattr(response, "content", str(response))

    async def run(self, prompt: str, cancellation: asyncio.Event | None = None) -> NativeRuntimeResult:
        _, graph = Planner().plan(prompt)
        ordered = graph.topological()
        evidence: list[dict[str, Any]] = []
        attempts = 0
        last_error: str | None = None
        for task in ordered:
            if cancellation and cancellation.is_set():
                return NativeRuntimeResult(False, prompt, error="cancelled", attempts=attempts,
                                           task_count=len(ordered), evidence=evidence)
            if task.role == TaskRole.TESTER:
                report = await self._test()
                evidence.append({"stage": "test", **report})
                if not report["passed"]:
                    last_error = "test gate failed"
                    continue
            elif task.role == TaskRole.SECURITY:
                decision = self.security.authorize_command("python -m pytest -q", approved=True)
                evidence.append({"stage": "security", "allowed": decision.allowed,
                                 "risk": decision.risk, "reason": decision.reason})
                if not decision.allowed:
                    last_error = decision.reason
            elif task.role in (TaskRole.CODER, TaskRole.RESEARCH, TaskRole.REVIEWER):
                try:
                    output = await self._model_step(prompt, task.role)
                    evidence.append({"stage": task.role.value, "output": output})
                except Exception as exc:
                    last_error = str(exc)
            elif task.role == TaskRole.FINALIZER:
                report = await self._test()
                evidence.append({"stage": "final_validation", **report})
                if report["passed"] and last_error is None:
                    return NativeRuntimeResult(True, prompt, output=report["output"], attempts=attempts,
                                               task_count=len(ordered), evidence=evidence)
                last_error = last_error or "final validation failed"
            attempts += 1

        for repair in range(self.max_repair_attempts):
            if cancellation and cancellation.is_set():
                return NativeRuntimeResult(False, prompt, error="cancelled", attempts=attempts,
                                           task_count=len(ordered), evidence=evidence)
            attempts += 1
            await self._model_step(f"Repair failed task for: {prompt}. Failure: {last_error}", TaskRole.CODER)
            report = await self._test()
            evidence.append({"stage": "repair_validation", "attempt": repair + 1, **report})
            if report["passed"]:
                return NativeRuntimeResult(True, prompt, output=report["output"], attempts=attempts,
                                           task_count=len(ordered), evidence=evidence)
        return NativeRuntimeResult(False, prompt, error=last_error or "runtime did not converge",
                                   attempts=attempts, task_count=len(ordered), evidence=evidence)

    async def execute(self, task: Any) -> ExecutionResult:
        result = await self.run(task.description or task.title)
        return ExecutionResult(success=result.success, output=result.output, error=result.error,
                               metadata={"attempts": result.attempts, "evidence": result.evidence})
