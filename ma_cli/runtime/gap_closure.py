"""Production gap-closure primitives for the native autonomous runtime.

This module provides bounded task execution, observation, diagnosis and repair
contracts without pretending that external environments are live-verified.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    REPAIRED = "repaired"
    CANCELLED = "cancelled"


@dataclass
class Task:
    id: str
    action: Callable[[], T]
    dependencies: tuple[str, ...] = ()
    state: TaskState = TaskState.PENDING
    result: T | None = None
    error: str | None = None
    attempts: int = 0


@dataclass
class ExecutionReport(Generic[T]):
    tasks: dict[str, Task] = field(default_factory=dict)
    success: bool = False


class TaskGraph:
    def __init__(self, tasks: list[Task]) -> None:
        self.tasks = {task.id: task for task in tasks}
        self._validate()

    def _validate(self) -> None:
        for task in self.tasks.values():
            missing = [dep for dep in task.dependencies if dep not in self.tasks]
            if missing:
                raise ValueError(f"Unknown task dependencies: {missing}")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("Task graph contains a cycle")
            if node in visited:
                return
            visiting.add(node)
            for dep in self.tasks[node].dependencies:
                visit(dep)
            visiting.remove(node)
            visited.add(node)

        for node in self.tasks:
            visit(node)

    def ready(self) -> list[Task]:
        return [
            task for task in self.tasks.values()
            if task.state == TaskState.PENDING
            and all(self.tasks[d].state in {TaskState.PASSED, TaskState.REPAIRED} for d in task.dependencies)
        ]


class ExecutionEngine:
    def __init__(self, max_attempts: int = 2) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.max_attempts = max_attempts

    def run(self, graph: TaskGraph, repair: Callable[[Task, Exception], bool] | None = None) -> ExecutionReport:
        report = ExecutionReport(tasks=graph.tasks)
        while True:
            ready = graph.ready()
            if not ready:
                break
            for task in ready:
                task.state = TaskState.RUNNING
                task.attempts += 1
                try:
                    task.result = task.action()
                    task.state = TaskState.PASSED
                except Exception as exc:  # noqa: BLE001 - task boundary must capture failures
                    task.error = str(exc)
                    if repair and task.attempts < self.max_attempts and repair(task, exc):
                        task.state = TaskState.REPAIRED
                    else:
                        task.state = TaskState.FAILED
        report.success = bool(graph.tasks) and all(
            task.state in {TaskState.PASSED, TaskState.REPAIRED} for task in graph.tasks.values()
        )
        return report
