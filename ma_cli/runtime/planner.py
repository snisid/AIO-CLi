"""Deterministic intent analysis and executable task-graph planning."""
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
    text: str
    capabilities: frozenset[str] = frozenset()
    roles: tuple[TaskRole, ...] = (TaskRole.CODER, TaskRole.TESTER, TaskRole.FINALIZER)
    private: bool = False


@dataclass
class PlanTask:
    title: str
    role: TaskRole = TaskRole.CODER
    dependencies: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    success_criteria: list[str] = field(default_factory=list)


class IntentAnalyzer:
    def analyze(self, text: str) -> Intent:
        normalized = text.lower()
        capabilities = set()
        for keyword in ("git", "docker", "browser", "mcp", "python", "node", "database", "api", "auth", "security", "test"):
            if keyword in normalized:
                capabilities.add(keyword)
        roles = [TaskRole.CODER, TaskRole.TESTER]
        if any(k in normalized for k in ("research", "investigate", "compare", "find")):
            roles.insert(0, TaskRole.RESEARCH)
        if any(k in normalized for k in ("security", "secure", "vulnerability", "audit")):
            roles.insert(-1, TaskRole.SECURITY)
        roles.extend([TaskRole.REVIEWER, TaskRole.FINALIZER])
        return Intent(text=text, capabilities=frozenset(capabilities), roles=tuple(dict.fromkeys(roles)),
                      private=bool(re.search(r"\b(private|local|offline|proprietary)\b", normalized)))


class TaskGraph:
    def __init__(self, tasks: list[PlanTask]):
        self.tasks = tasks
        self._by_id = {task.id: task for task in tasks}
        self.validate()

    def validate(self) -> None:
        if len(self._by_id) != len(self.tasks):
            raise ValueError("duplicate task id")
        for task in self.tasks:
            missing = set(task.dependencies) - self._by_id.keys()
            if missing:
                raise ValueError(f"unknown dependencies: {sorted(missing)}")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("task graph contains a cycle")
            if node in visited:
                return
            visiting.add(node)
            for dep in self._by_id[node].dependencies:
                visit(dep)
            visiting.remove(node)
            visited.add(node)

        for task in self.tasks:
            visit(task.id)

    def topological(self) -> list[PlanTask]:
        self.validate()
        result: list[PlanTask] = []
        remaining = {task.id: task for task in self.tasks}
        while remaining:
            ready = [t for t in remaining.values() if all(d not in remaining for d in t.dependencies)]
            if not ready:
                raise ValueError("task graph cannot be topologically ordered")
            ready.sort(key=lambda t: t.id)
            for task in ready:
                result.append(task)
                remaining.pop(task.id)
        return result


class Planner:
    def __init__(self, analyzer: IntentAnalyzer | None = None):
        self.analyzer = analyzer or IntentAnalyzer()

    def plan(self, prompt: str) -> tuple[Intent, TaskGraph]:
        intent = self.analyzer.analyze(prompt)
        tasks: list[PlanTask] = []
        previous: str | None = None
        for role in intent.roles:
            task = PlanTask(title=f"{role.value}: {prompt[:80]}", role=role,
                            dependencies=[previous] if previous else [],
                            success_criteria=[f"{role.value} completed with evidence"])
            tasks.append(task)
            previous = task.id
        return intent, TaskGraph(tasks)
