"""Native agentic capability framework for MA-CLI.

The capability layer is provider-agnostic: it describes what a task needs and
what an execution environment can safely provide.  Model/provider selection is
left to the existing routing layer.
"""

from .engine import CapabilityEngine
from .models import (
    Capability,
    CapabilityProfile,
    ExecutionMode,
    ReasoningLevel,
    RiskLevel,
    TaskCapabilityRequest,
    ToolPermission,
)

__all__ = [
    "Capability",
    "CapabilityEngine",
    "CapabilityProfile",
    "ExecutionMode",
    "ReasoningLevel",
    "RiskLevel",
    "TaskCapabilityRequest",
    "ToolPermission",
]
