"""Native autonomous runtime for MA-CLI.

The runtime is provider-agnostic and does not require Claude Code, Codex, Qwen
CLI, or another external agent CLI. External CLIs remain optional adapters.
"""

from .engine import NativeAgent, RuntimeResult
from .planner import IntentAnalyzer, Planner, TaskGraph

__all__ = ["NativeAgent", "RuntimeResult", "IntentAnalyzer", "Planner", "TaskGraph"]
