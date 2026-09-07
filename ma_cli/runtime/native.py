"""Native autonomous execution loop with structured tool calls and gates."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..agents.base import Agent
from ..core.models import AgentStatus, ExecutionResult, HealthStatus, ReviewResult
from ..security.runtime_policy import RuntimeSecurity
from ..tools.registry import RUNTIME_GRANT, ToolRegistry
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


class NativeAgent(Agent):
    """Provider-agnostic autonomous runtime with bounded repair and tool execution."""

    def __init__(self, workspace: Path | None = None, model: Any | None = None, max_repair_attempts: int = 2):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.model = model
        self.max_repair_attempts = max(0, max_repair_attempts)
        self.security = RuntimeSecurity(self.workspace)
        self.tools = ToolRegistry(self.workspace)
        self._status = AgentStatus.IDLE
        self._health = HealthStatus.HEALTHY
        self._cancel = asyncio.Event()

    @property
    def id(self) -> str:
        return "native-agent"

    @property
    def name(self) -> str:
        return "NativeAgent"

    @property
    def provider(self) -> str:
        return "native"

    @property
    def capabilities(self) -> list[str]:
        return ["coding", "testing", "tool_use", "file_editing", "shell", "planning"]

    @property
    def roles(self) -> list[str]:
        return ["developer", "tester", "reviewer", "planner", "finalizer"]

    @property
    def status(self) -> AgentStatus:
        return self._status

    @property
    def health(self) -> HealthStatus:
        return self._health

    def _workspace_test_commands(self) -> list[tuple[str, int]]:
        """Test the current workspace only. Never compileall the MA-CLI package as a proxy."""
        commands: list[tuple[str, int]] = []
        has_tests = any(
            (self.workspace / name).exists()
            for name in ("tests", "test", "pytest.ini", "pyproject.toml")
        ) or any(self.workspace.glob("test_*.py")) or any(self.workspace.glob("*_test.py"))
        if (self.workspace / "tests").exists() or any(self.workspace.glob("test_*.py")):
            commands.append(("python -m pytest -q", 300))
        elif has_tests and (self.workspace / "pyproject.toml").exists():
            # pyproject without a tests/ directory is not treated as a pytest suite.
            pass
        if any(path.suffix == ".py" for path in self.workspace.rglob("*.py") if ".venv" not in path.parts):
            commands.append(("python -m compileall -q .", 120))
        return commands

    async def _test(self) -> dict[str, Any]:
        started = time.monotonic()
        failures: list[str] = []
        output: list[str] = []
        commands = self._workspace_test_commands()
        if not commands:
            return {"passed": True, "failures": [], "output": "no workspace tests",
                    "duration_ms": int((time.monotonic() - started) * 1000)}
        for command, timeout in commands:
            try:
                result = await self.tools.execute_async(
                    "run_command", command=command, timeout=timeout, grant=RUNTIME_GRANT,
                )
                text = result["stdout"] + result["stderr"]
                output.append(text)
                if result["returncode"] != 0:
                    failures.append(f"{command}: exit {result['returncode']}")
            except Exception as exc:  # noqa: BLE001 - test gate must continue
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
            sanitized = {key: value for key, value in arguments.items() if key not in {"approved", "grant"}}
            result = await self.tools.execute_async(name, **sanitized)
            tool_results.append({"tool": name, "result": result})
        return getattr(response, "content", str(response)), tool_results

    async def run(self, prompt: str, cancellation: asyncio.Event | None = None) -> NativeRuntimeResult:
        injection = self.security.inspect_prompt(prompt)
        if not injection.allowed:
            return NativeRuntimeResult(False, prompt, error=injection.reason)
        cancel = cancellation or self._cancel
        _, graph = Planner().plan(prompt)
        ordered = graph.topological()
        evidence: list[dict[str, Any]] = []
        attempts = 0
        last_error: str | None = None
        self._status = AgentStatus.BUSY
        try:
            for task in ordered:
                if cancel.is_set():
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
                    except Exception as exc:  # noqa: BLE001 - role step must not abort the graph
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
                if cancel.is_set():
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
                except Exception as exc:  # noqa: BLE001 - repair attempts are bounded
                    last_error = str(exc)
            return NativeRuntimeResult(False, prompt, error=last_error or "runtime did not converge",
                                       attempts=attempts, task_count=len(ordered), evidence=evidence)
        finally:
            self._status = AgentStatus.IDLE

    async def execute(self, task: Any) -> ExecutionResult:
        prompt = str(getattr(task, "description", None) or getattr(task, "title", None) or task)
        result = await self.run(prompt)
        return ExecutionResult(success=result.success, output=result.output, error=result.error,
                               metadata={"attempts": result.attempts, "evidence": result.evidence})

    async def cancel(self) -> bool:
        self._cancel.set()
        self._status = AgentStatus.IDLE
        return True

    async def inspect(self) -> dict[str, Any]:
        return {
            "agent_id": self.id,
            "agent_name": self.name,
            "workspace": str(self.workspace),
            "model_attached": self.model is not None,
            "model_id": getattr(self.model, "model_id", None),
            "status": self._status.value,
            "health": self._health.value,
            "tools": [spec.name for spec in self.tools.list()],
        }

    async def review(self, code: str) -> ReviewResult:
        from ..review.engine import ReviewEngine
        return ReviewEngine(self.workspace).review_code(code)

    async def report(self) -> dict[str, Any]:
        return await self.inspect()

    async def health_check(self) -> HealthStatus:
        self._health = HealthStatus.HEALTHY if self.workspace.exists() else HealthStatus.UNHEALTHY
        return self._health
