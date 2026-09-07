"""Native autonomous runtime for MA-CLI."""

from .gap_closure import ExecutionEngine, ExecutionReport, Task, TaskGraph, TaskState
from .native import NativeAgent, NativeRuntimeResult
from .planner import IntentAnalyzer, Planner
from .planner import TaskGraph as PlanTaskGraph

__all__ = [
    "ExecutionEngine",
    "ExecutionReport",
    "IntentAnalyzer",
    "NativeAgent",
    "NativeRuntimeResult",
    "PlanTaskGraph",
    "Planner",
    "Task",
    "TaskGraph",
    "TaskState",
]
