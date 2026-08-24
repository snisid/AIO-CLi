"""Planning primitives for the native MA-CLI runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
import uuid


class TaskRole(str, Enum):
    CODER = "coder"
    TESTER = "tester"
    RESEARCH = "research"
    REVIEWER = "reviewer"
    SECURITY = "security"
    FINALIZER = "finalizer"


@dataclass(frozen=True)
class Intent:
    goal: str
    roles: tuple[TaskRole, ...]
    capabilities: tuple[str, ...]
    risk: str
    private: bool = False


@dataclass
class PlanTask:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    role: TaskRole = TaskRole.CODER
    dependencies: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class IntentAnalyzer:
    """Deterministic first-pass intent analysis; models may refine, never bypass it."""

    def analyze(self, prompt: str) -> Intent:
        text = prompt.strip()
        if not text:
            raise ValueError("prompt cannot be empty")
        lower = text.lower()
        roles: list[TaskRole] = [TaskRole.CODER]
        capabilities = {"files", "search", "shell"}
        risk = "standard"
        private = any(x in lower for x in ("private", "confidential", "secret", "local only"))
        if any(x in lower for x in ("test", "bug", "failure", "verify")):
            roles.append(TaskRole.TESTER); capabilities.add("testing")
        if any(x in lower for x in ("research", "investigate", "compare", "documentation")):
            roles.append(TaskRole.RESEARCH); capabilities.add("research")
        if any(x in lower for x in ("security", "credential", "permission", "sandbox")):
            roles.append(TaskRole.SECURITY); risk = "high"
        if any(x in lower for x in ("delete", "deploy", "production", "format", "reset")):
            risk = "critical"
        if re.search(r"\b(git|commit|branch|merge|rebase)\b", lower):
            capabilities.add("git")
        if re.search(r"\b(browser|playwright|web page|website)\b", lower):
            capabilities.add("browser")
        return Intent(text, tuple(dict.fromkeys(roles)), tuple(sorted(capabilities)), risk, private)


class TaskGraph:
    """Validated DAG. Cycles and unknown dependencies are rejected."""

    def __init__(self, tasks: list[PlanTask] | None = None):
        self.tasks: dict[str, PlanTask] = {}
        for task in tasks or []:
            self.add(task)

    def add(self, task: PlanTask) -> None:
        if task.id in self.tasks:
            raise ValueError(f"duplicate task id: {task.id}")
        self.tasks[task.id] = task
        self.validate()

    def validate(self) -> None:
        for task in self.tasks.values():
            missing = [dep for dep in task.dependencies if dep not in self.tasks]
            if missing:
                raise ValueError(f"unknown dependencies for {task.id}: {missing}")
        visiting, visited = set(), set()
        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("task graph contains a cycle")
            if node in visited:
                return
            visiting.add(node)
            for dep in self.tasks[node].dependencies:
                visit(dep)
            visiting.remove(node); visited.add(node)
        for node in self.tasks:
            visit(node)

    def ready(self, completed: set[str]) -> list[PlanTask]:
        return [t for t in self.tasks.values() if t.id not in completed and all(d in completed for d in t.dependencies)]

    def topological(self) -> list[PlanTask]:
        completed: set[str] = set(); result: list[PlanTask] = []
        while len(result) < len(self.tasks):
            ready = self.ready(completed)
            if not ready:
                raise ValueError("task graph cannot be topologically ordered")
            result.extend(ready); completed.update(t.id for t in ready)
        return result


class Planner:
    """Builds a minimal but executable graph; later model planning can refine it."""

    def __init__(self, analyzer: IntentAnalyzer | None = None):
        self.analyzer = analyzer or IntentAnalyzer()

    def plan(self, prompt: str) -> tuple[Intent, TaskGraph]:
        intent = self.analyzer.analyze(prompt)
        tasks: list[PlanTask] = []
        research = PlanTask(title="Research", description=f"Collect facts and inspect the workspace for: {intent.goal}", role=TaskRole.RESEARCH, capabilities=list(intent.capabilities))
        tasks.append(research)
        coder = PlanTask(title="Implement", description=intent.goal, role=TaskRole.CODER, dependencies=[research.id], capabilities=list(intent.capabilities))
        tasks.append(coder)
        tester = PlanTask(title="Test", description=f"Validate implementation for: {intent.goal}", role=TaskRole.TESTER, dependencies=[coder.id], capabilities=["testing", "shell", "files"])
        tasks.append(tester)
        security = PlanTask(title="Security review", description=f"Check security controls for: {intent.goal}", role=TaskRole.SECURITY, dependencies=[tester.id], capabilities=["security", "files", "shell"], metadata={"risk": intent.risk})
        tasks.append(security)
        finalizer = PlanTask(title="Finalize", description="Validate all gates and produce the final result", role=TaskRole.FINALIZER, dependencies=[security.id], capabilities=["validation"])
        tasks.append(finalizer)
        return intent, TaskGraph(tasks)
