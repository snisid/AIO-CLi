"""Native autonomous runtime.

The runtime owns the lifecycle: plan -> execute -> observe -> diagnose -> repair
-> validate -> finalize. External agent CLIs are optional and never required.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..models.router import ModelRouter, RoutingStrategy
from ..providers import ChatMessage, get_provider_registry
from ..tools.registry import ToolRegistry, get_tool_registry
from .planner import PlanTask, Planner, TaskRole


class ModelExecutor(Protocol):
    async def complete(self, messages: list[ChatMessage], *, strategy: RoutingStrategy, capabilities: list[str], tools: list[dict[str, Any]] | None = None) -> Any: ...


class RoutedModelExecutor:
    """Uses the native provider abstraction; no external coding CLI is required."""

    def __init__(self, router: ModelRouter | None = None):
        self.router = router or ModelRouter()
        self.router.initialize()

    async def complete(self, messages: list[ChatMessage], *, strategy: RoutingStrategy = RoutingStrategy.BALANCED, capabilities: list[str] | None = None, tools: list[dict[str, Any]] | None = None):
        capabilities = capabilities or ["chat", "code"]
        aliases = ["coding", "default", "local", "qwen", "ollama", "omniroute", "9router", "openai", "anthropic"]
        last_error = None
        for alias in aliases:
            try:
                selected = await self.router.resolve_alias(alias, strategy, capabilities)
                if not selected.success or not selected.selected_model or not selected.provider_used:
                    continue
                provider = get_provider_registry().get(selected.provider_used)
                if provider is None:
                    continue
                kwargs = {"tools": tools} if tools else {}
                return await provider.safe_chat(messages, selected.selected_model.model_id, **kwargs)
            except Exception as exc:
                last_error = str(exc)
        raise RuntimeError(last_error or "no native model provider is available")


@dataclass
class Observation:
    task_id: str
    success: bool
    output: str = ""
    failures: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeResult:
    success: bool
    goal: str
    output: str = ""
    task_results: dict[str, Observation] = field(default_factory=dict)
    attempts: int = 0
    elapsed_ms: int = 0
    blocked_reason: str | None = None


class Observer:
    """Collects objective evidence after model/tool execution."""

    def __init__(self, tools: ToolRegistry):
        self.tools = tools

    async def test_workspace(self, task: PlanTask) -> Observation:
        command = "python -m pytest -q"
        try:
            result = await self.tools.execute_async("run_command", command=command, timeout=300)
            ok = result["returncode"] == 0
            return Observation(task.id, ok, result.get("stdout", ""), [] if ok else [result.get("stderr", "test command failed")], {"command": command, "returncode": result["returncode"]})
        except Exception as exc:
            return Observation(task.id, False, "", [str(exc)], {"command": command})

    async def security_check(self, task: PlanTask) -> Observation:
        audit = self.tools.audit_log()
        failures = [a["error"] for a in audit if a.get("status") == "failed" and a.get("error")]
        return Observation(task.id, not failures, "security evidence collected", failures, {"tool_audit_entries": len(audit)})


class NativeAgent:
    """Autonomous development agent with bounded retries and explicit gates."""

    def __init__(self, workspace=None, model: ModelExecutor | None = None, planner: Planner | None = None, max_repair_attempts: int = 3, max_tool_rounds: int = 8):
        self.tools = get_tool_registry(workspace)
        self.model = model or RoutedModelExecutor()
        self.planner = planner or Planner()
        self.observer = Observer(self.tools)
        self.max_repair_attempts = max(1, min(max_repair_attempts, 10))
        self.max_tool_rounds = max(1, min(max_tool_rounds, 32))
        self.cancel_event = asyncio.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    @staticmethod
    def _tool_call(call: Any) -> tuple[str, dict[str, Any]]:
        if not isinstance(call, dict):
            raise ValueError("provider returned invalid tool call")
        name = call.get("name") or call.get("function", {}).get("name")
        arguments = call.get("arguments", call.get("function", {}).get("arguments", {}))
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        if not isinstance(name, str) or not isinstance(arguments, dict):
            raise ValueError("tool call must contain a name and object arguments")
        return name, arguments

    async def _model(self, prompt: str, role: TaskRole, capabilities: list[str]) -> str:
        strategy = RoutingStrategy.PRIVACY if "private" in prompt.lower() else RoutingStrategy.BALANCED
        system = (
            "You are a native MA-CLI agent. Use structured tool calls only for actions. "
            "Never turn natural-language text into a shell command. Never claim success without evidence."
        )
        messages = [ChatMessage("system", system), ChatMessage("user", f"Role: {role.value}\nTask: {prompt}")]
        schemas = self.tools.schemas()
        for _ in range(self.max_tool_rounds):
            if self.cancel_event.is_set():
                raise asyncio.CancelledError()
            response = await self.model.complete(messages, strategy=strategy, capabilities=capabilities, tools=schemas)
            calls = list(getattr(response, "tool_calls", None) or [])
            if not calls:
                return response.content
            messages.append(ChatMessage("assistant", response.content or "", tool_calls=calls))
            for raw_call in calls:
                name, arguments = self._tool_call(raw_call)
                result = await self.tools.execute_async(name, **arguments)
                messages.append(ChatMessage("tool", json.dumps(result, default=str), tool_call_id=str(raw_call.get("id", name))))
        raise RuntimeError("tool execution round limit exceeded")

    async def _execute_task(self, task: PlanTask) -> Observation:
        if self.cancel_event.is_set():
            return Observation(task.id, False, failures=["cancelled"])
        if task.role in (TaskRole.RESEARCH, TaskRole.CODER):
            output = await self._model(task.description, task.role, task.capabilities)
            return Observation(task.id, True, output, evidence={"role": task.role.value})
        if task.role == TaskRole.TESTER:
            return await self.observer.test_workspace(task)
        if task.role == TaskRole.SECURITY:
            return await self.observer.security_check(task)
        if task.role == TaskRole.FINALIZER:
            return Observation(task.id, True, "all required observations passed", evidence={"tool_audit": self.tools.audit_log()})
        return Observation(task.id, False, failures=[f"unsupported task role: {task.role.value}"])

    async def _repair(self, task: PlanTask, failure: Observation) -> Observation:
        prompt = f"Diagnose and repair task {task.title}. Failures: {failure.failures}. Evidence: {failure.evidence}"
        output = await self._model(prompt, TaskRole.CODER, task.capabilities)
        return Observation(task.id, True, output, evidence={"repair": True, "diagnosis": failure.failures})

    async def run(self, goal: str) -> RuntimeResult:
        started = time.monotonic()
        intent, graph = self.planner.plan(goal)
        results: dict[str, Observation] = {}
        attempts = 0
        for task in graph.topological():
            if self.cancel_event.is_set():
                return RuntimeResult(False, goal, task_results=results, attempts=attempts, elapsed_ms=int((time.monotonic()-started)*1000), blocked_reason="cancelled")
            observation = await self._execute_task(task)
            attempts += 1
            for _ in range(self.max_repair_attempts if not observation.success else 0):
                if observation.success:
                    break
                await self._repair(task, observation)
                attempts += 1
                observation = await self._execute_task(task)
                attempts += 1
            results[task.id] = observation
            if not observation.success:
                return RuntimeResult(False, goal, task_results=results, attempts=attempts, elapsed_ms=int((time.monotonic()-started)*1000), blocked_reason=f"task failed: {task.title}: {observation.failures}")
        final = results[next(reversed(results))] if results else None
        return RuntimeResult(bool(final and final.success), intent.goal, final.output if final else "", results, attempts, int((time.monotonic()-started)*1000))
