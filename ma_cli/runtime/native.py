"""Native autonomous execution loop with capability gates and resumable checkpoints."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
import time
import uuid
from typing import Any

from ..capabilities import CapabilityEngine
from ..capabilities.integration import CapabilityNegotiator
from ..core.models import ExecutionResult
from ..security.runtime_policy import RuntimeSecurity
from ..tools.registry import ToolRegistry
from .checkpoint import CheckpointStore, RunCheckpoint
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
    run_id: str | None = None


class NativeAgent:
    """Provider-agnostic autonomous runtime with bounded repair and tool execution."""

    def __init__(self, workspace: Path, model: Any | None = None, max_repair_attempts: int = 2):
        self.workspace = workspace.resolve()
        self.model = model
        self.max_repair_attempts = max(0, max_repair_attempts)
        self.security = RuntimeSecurity(self.workspace)
        self.tools = ToolRegistry(self.workspace)
        self.capabilities = CapabilityEngine()
        self.negotiator = CapabilityNegotiator(self.capabilities)
        self.checkpoints = CheckpointStore(self.workspace)

    async def _test(self) -> dict[str, Any]:
        started = time.monotonic()
        failures: list[str] = []
        output: list[str] = []
        for command, timeout in (("python -m pytest -q", 300), ("python -m compileall -q ma_cli", 120)):
            try:
                result = await self.tools.execute_async("run_command", command=command, timeout=timeout, approved=True)
                text = result["stdout"] + result["stderr"]
                output.append(text)
                if result["returncode"] != 0:
                    failures.append(f"{command}: exit {result['returncode']}")
            except Exception as exc:
                failures.append(f"{command}: {exc}")
        return {"passed": not failures, "failures": failures, "output": "\n".join(output),
                "duration_ms": int((time.monotonic() - started) * 1000)}

    async def _model_step(self, prompt: str, role: TaskRole) -> tuple[str, list[dict[str, Any]]]:
        complexity = 5 if role == TaskRole.CODER else 4 if role in (TaskRole.RESEARCH, TaskRole.REVIEWER) else 3
        request = self.negotiator.request_for(role.value, complexity=complexity)
        if self.model is None:
            return f"{role.value} planned; no model provider attached", []
        profile = getattr(self.model, "capability_profile", None)
        if profile is not None:
            negotiation = self.negotiator.negotiate(profile, request)
            if not negotiation.accepted:
                raise RuntimeError(f"model capability gate rejected task: {negotiation.reason}")
        complete = getattr(self.model, "complete", None)
        if complete is None:
            raise TypeError("model must expose async complete(messages, ...) method")
        task_type = {
            TaskRole.CODER: "coding",
            TaskRole.RESEARCH: "research",
            TaskRole.REVIEWER: "architecture",
            TaskRole.TESTER: "testing",
            TaskRole.SECURITY: "security",
            TaskRole.FINALIZER: "testing",
        }.get(role, "coding")
        response = await complete(
            [{"role": "user", "content": (
                f"Role: {role.value}. Work autonomously on this task: {prompt}\n"
                "Use only structured tool calls when changing or inspecting the workspace."
            )}],
            task_type=task_type,
            complexity=complexity,
            risk=2 if role == TaskRole.SECURITY else 1,
            tools=self.tools.schemas(),
        )
        tool_results: list[dict[str, Any]] = []
        calls = getattr(response, "tool_calls", []) or []
        for call in calls:
            name = call.get("name") or call.get("function", {}).get("name")
            arguments = call.get("arguments") or call.get("function", {}).get("arguments", {})
            if isinstance(arguments, str):
                import json
                arguments = json.loads(arguments)
            if not name or not isinstance(arguments, dict):
                raise ValueError("invalid structured tool call")
            result = await self.tools.execute_async(name, **arguments)
            tool_results.append({"tool": name, "result": result})
        return getattr(response, "content", str(response)), tool_results

    async def run(self, prompt: str, cancellation: asyncio.Event | None = None,
                  run_id: str | None = None, resume: bool = False) -> NativeRuntimeResult:
        run_id = run_id or str(uuid.uuid4())
        checkpoint = self.checkpoints.load(run_id) if resume else None
        _, graph = Planner().plan(prompt)
        ordered = graph.topological()
        completed = set(checkpoint.completed_tasks if checkpoint else [])
        evidence: list[dict[str, Any]] = []
        attempts = checkpoint.attempts if checkpoint else 0
        last_error: str | None = None
        self.checkpoints.save(RunCheckpoint(run_id, prompt, "RUNNING", list(completed), attempts=attempts))
        for task in ordered:
            if task.title in completed:
                continue
            if cancellation and cancellation.is_set():
                self.checkpoints.save(RunCheckpoint(run_id, prompt, "PAUSED", list(completed), task.title, attempts))
                return NativeRuntimeResult(False, prompt, error="cancelled", attempts=attempts,
                                           task_count=len(ordered), evidence=evidence, run_id=run_id)
            self.checkpoints.save(RunCheckpoint(run_id, prompt, "RUNNING", list(completed), task.title, attempts))
            if task.role == TaskRole.TESTER:
                report = await self._test()
                evidence.append({"stage": "test", **report})
                if not report["passed"]:
                    last_error = "test gate failed"
            elif task.role == TaskRole.SECURITY:
                decision = self.security.authorize_command("python -m pytest -q", approved=True)
                evidence.append({"stage": "security", "allowed": decision.allowed,
                                 "risk": decision.risk, "reason": decision.reason})
                if not decision.allowed:
                    last_error = decision.reason
            elif task.role in (TaskRole.CODER, TaskRole.RESEARCH, TaskRole.REVIEWER):
                try:
                    output, tool_results = await self._model_step(prompt, task.role)
                    evidence.append({"stage": task.role.value, "output": output, "tool_calls": tool_results})
                except Exception as exc:
                    last_error = str(exc)
            elif task.role == TaskRole.FINALIZER:
                report = await self._test()
                evidence.append({"stage": "final_validation", **report})
                if report["passed"] and last_error is None:
                    self.checkpoints.save(RunCheckpoint(run_id, prompt, "SUCCESS", list(completed), attempts=attempts))
                    return NativeRuntimeResult(True, prompt, output=report["output"], attempts=attempts,
                                               task_count=len(ordered), evidence=evidence, run_id=run_id)
                last_error = last_error or "final validation failed"
            completed.add(task.title)
            attempts += 1
            self.checkpoints.save(RunCheckpoint(run_id, prompt, "RUNNING", list(completed), attempts=attempts))

        for repair in range(self.max_repair_attempts):
            if cancellation and cancellation.is_set():
                self.checkpoints.save(RunCheckpoint(run_id, prompt, "PAUSED", list(completed), attempts=attempts))
                return NativeRuntimeResult(False, prompt, error="cancelled", attempts=attempts,
                                           task_count=len(ordered), evidence=evidence, run_id=run_id)
            attempts += 1
            try:
                output, tool_results = await self._model_step(
                    f"Repair failed task for: {prompt}. Failure: {last_error}", TaskRole.CODER)
                report = await self._test()
                evidence.append({"stage": "repair_validation", "attempt": repair + 1,
                                 "output": output, "tool_calls": tool_results, **report})
                if report["passed"]:
                    self.checkpoints.save(RunCheckpoint(run_id, prompt, "SUCCESS", list(completed), attempts=attempts))
                    return NativeRuntimeResult(True, prompt, output=report["output"], attempts=attempts,
                                               task_count=len(ordered), evidence=evidence, run_id=run_id)
            except Exception as exc:
                last_error = str(exc)
        self.checkpoints.save(RunCheckpoint(run_id, prompt, "FAILED", list(completed), attempts=attempts,
                                             metadata={"error": last_error or "runtime did not converge"}))
        return NativeRuntimeResult(False, prompt, error=last_error or "runtime did not converge",
                                   attempts=attempts, task_count=len(ordered), evidence=evidence, run_id=run_id)

    async def execute(self, task: Any) -> ExecutionResult:
        result = await self.run(task.description or task.title)
        return ExecutionResult(success=result.success, output=result.output, error=result.error,
                               metadata={"attempts": result.attempts, "evidence": result.evidence, "run_id": result.run_id})
