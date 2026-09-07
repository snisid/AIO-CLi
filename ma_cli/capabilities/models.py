"""Typed capability contracts used by the autonomous runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet


class Capability(str, Enum):
    CODING = "coding"
    REASONING = "reasoning"
    RESEARCH = "research"
    FILE_SEARCH = "file_search"
    DATA_ANALYSIS = "data_analysis"
    TERMINAL = "terminal"
    BROWSER = "browser"
    COMPUTER_USE = "computer_use"
    MCP = "mcp"
    PATCH = "patch"
    STRUCTURED_OUTPUT = "structured_output"
    STREAMING = "streaming"
    ASYNC_TOOLS = "async_tools"
    STEERING = "steering"
    CHECKPOINTS = "checkpoints"
    LONG_RUNNING = "long_running"


class ReasoningLevel(str, Enum):
    FAST = "fast"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"


class ExecutionMode(str, Enum):
    INTERACTIVE = "interactive"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"
    READ_ONLY = "read_only"


class RiskLevel(str, Enum):
    SAFE = "safe"
    REVIEW = "review"
    HIGH_RISK = "high_risk"
    BLOCKED = "blocked"


class ToolPermission(str, Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    NETWORK = "network"
    EXTERNAL = "external"


@dataclass(frozen=True)
class CapabilityProfile:
    """Capabilities exposed by a model/provider/runtime endpoint."""
    capabilities: FrozenSet[Capability] = frozenset()
    max_context_tokens: int = 0
    max_output_tokens: int = 0
    supports_reasoning_levels: FrozenSet[ReasoningLevel] = frozenset()
    supports_streaming: bool = False
    supports_async_tools: bool = False

    def supports(self, required: set[Capability] | frozenset[Capability]) -> bool:
        return set(required).issubset(self.capabilities)


@dataclass(frozen=True)
class TaskCapabilityRequest:
    """Normalized requirements extracted from an agent task."""
    required: FrozenSet[Capability] = frozenset()
    reasoning: ReasoningLevel = ReasoningLevel.MEDIUM
    execution_mode: ExecutionMode = ExecutionMode.SUPERVISED
    risk_level: RiskLevel = RiskLevel.SAFE
    required_permissions: FrozenSet[ToolPermission] = frozenset()
    context_tokens: int = 0
    max_latency_ms: int | None = None
    max_cost_per_token: float | None = None
    metadata: dict[str, str] = field(default_factory=dict)
