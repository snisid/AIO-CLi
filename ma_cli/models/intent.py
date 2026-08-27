"""
Intent models for MA-CLI.

This module defines intent types and complexity levels for task analysis.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class IntentType(Enum):
    """Types of user intents."""
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    READ = "read"
    TEST = "test"
    EXPLAIN = "explain"
    COMPLEX = "complex"


class TaskComplexity(Enum):
    """Task complexity levels."""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class Intent:
    """Represents a parsed user intent."""
    type: IntentType
    description: str
    complexity: TaskComplexity = TaskComplexity.MEDIUM
    entities: list[dict[str, str]] = field(default_factory=list)
    requires_planning: bool = False
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["Intent", "IntentType", "TaskComplexity"]
