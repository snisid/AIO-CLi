"""Native autonomous execution loop with structured tool calls and gates."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
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
    """Provider-agnostic autonomous runtime with bounded repair and tool execution."""

    def __init__(self, workspace: Path, model: Any | None = None, max_repair_attempts: int = 2):
        self.workspace = workspace.resolve()
        self.model = model
        self.max_repair_attempts = max(0, max_repair_attempts)
        self.security = RuntimeSecurity(self.workspace)
        self.tools = ToolRegistry(self.workspace)

    async def _test(self) -> dict[str, Any]:
        started = time.monotonic()
        failures: list[str] = []
        output: list[str] = []
        for command, timeout in (("python -m pytest -q", 300), ("python -m compileall -q ma_cli", 120)):
            try:
                result = await self.tools.execute_async("run_command", command=command,
                                                       timeout=timeout, approved=True)
                text = result["stdout"] + result["stderr"]
                output.append(text)
                if result["returncode"] != 0:
                    failures.append(f"{command}: exit {result['returncode']}")
            except Exception as exc:
                failures.append(f"{command}: {exc}")
        return {"passed": not failures, "failures": failures, "output": "\n".join(output),
                "duration_ms": int((time.monotonic() - started) * 1000)}

    async def _model_step(self, prompt: str, role: TaskRole) -> tuple[str, list[dict[str, Any]]]:
        if self.model is None:
            return f"{role.value} planned; no model provider attached", []
        complete = getattr(self.model, "complete", None)
        if complete is None:
            raise TypeError("model must expose async complete(messages, ...) method")
        response = await complete([{
            "role": "user",
            "content": (
                f"Role: {role.value}. Work autonomously on this task: {prompt}\n"
                "Use only structured tool calls when changing or inspecting the workspace."
            ),
        }], strategy=role.value, capabilities=self.tools.schemas())
        tool_results: list[dict[str, Any]] = []
        for call in getattr(response, "tool_calls", []) or []:
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
                    output, tool_results = await self._model_step(prompt, task.role)
                    evidence.append({"stage": task.role.value, "output": output,
                                     "tool_calls": tool_results})
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
            try:
                output, tool_results = await self._model_step(
                    f"Repair failed task for: {prompt}. Failure: {last_error}", TaskRole.CODER)
                report = await self._test()
                evidence.append({"stage": "repair_validation", "attempt": repair + 1,
                                 "output": output, "tool_calls": tool_results, **report})
                if report["passed"]:
                    return NativeRuntimeResult(True, prompt, output=report["output"], attempts=attempts,
                                               task_count=len(ordered), evidence=evidence)
            except Exception as exc:
                last_error = str(exc)
        return NativeRuntimeResult(False, prompt, error=last_error or "runtime did not converge",
                                   attempts=attempts, task_count=len(ordered), evidence=evidence)

    async def execute(self, task: Any) -> ExecutionResult:
        result = await self.run(task.description or task.title)
        return ExecutionResult(success=result.success, output=result.output, error=result.error,
                               metadata={"attempts": result.attempts, "evidence": result.evidence})
