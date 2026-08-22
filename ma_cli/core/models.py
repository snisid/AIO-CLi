"""
Core data models for MA-CLI.

This module defines the fundamental data structures used throughout MA-CLI,
including tasks, events, state, and permissions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid


# ============================================================================
# Enums
# ============================================================================

class TaskStatus(Enum):
    """Task lifecycle status."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"


class AgentStatus(Enum):
    """Agent operational status."""
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    OFFLINE = "offline"


class HealthStatus(Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AutonomyLevel(Enum):
    """Autonomy levels for MA-CLI operation."""
    OBSERVE_ONLY = 0       # Read-only, no modifications
    ASSIST = 1             # Suggestions, requires approval
    AUTONOMOUS_DEV = 2     # Self-directed with guardrails
    SUPERVISED_AUTO = 3    # Full autonomy with oversight (default)


class PermissionLevel(Enum):
    """Permission levels for operations."""
    READ_ONLY = "read_only"
    STANDARD = "standard"
    ELEVATED = "elevated"
    DANGEROUS = "dangerous"
    CRITICAL = "critical"


class EventType(Enum):
    """Event types for the event bus."""
    # Task events
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    
    # Agent events
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"
    AGENT_FAILED = "agent_failed"
    
    # Tool events
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    
    # Test events
    TEST_STARTED = "test_started"
    TEST_PASSED = "test_passed"
    TEST_FAILED = "test_failed"
    
    # Review events
    REVIEW_STARTED = "review_started"
    REVIEW_PASSED = "review_passed"
    REVIEW_FAILED = "review_failed"
    
    # Build events
    BUILD_STARTED = "build_started"
    BUILD_PASSED = "build_passed"
    BUILD_FAILED = "build_failed"
    
    # Approval events
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    
    # Finalization
    FINALIZED = "finalized"


# ============================================================================
# Core Models
# ============================================================================

@dataclass
class Task:
    """Represents a task to be executed by an agent."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5  # 1-10, higher is more urgent
    
    # Task assignment
    assigned_agent: Optional[str] = None
    assigned_role: Optional[str] = None
    required_capabilities: list[str] = field(default_factory=list)
    
    # Model requirements
    preferred_model: Optional[str] = None
    model_constraints: dict[str, Any] = field(default_factory=dict)
    
    # Execution tracking
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Dependencies
    dependencies: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    
    # Results
    result: Optional[str] = None
    error: Optional[str] = None
    outputs: dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def is_blocked(self, completed_tasks: set[str]) -> bool:
        """Check if task is blocked by incomplete dependencies."""
        return not all(dep in completed_tasks for dep in self.dependencies)


@dataclass
class Event:
    """Represents an event in the system."""
    
    event_type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = ""  # Component that emitted the event
    correlation_id: Optional[str] = None  # For tracing related events
    
    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_type": self.event_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "correlation_id": self.correlation_id
        }


@dataclass
class State:
    """Represents the current state of MA-CLI."""
    
    # Runtime state
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    autonomy_level: AutonomyLevel = AutonomyLevel.SUPERVISED_AUTO
    
    # Current work
    active_task_ids: list[str] = field(default_factory=list)
    queued_task_ids: list[str] = field(default_factory=list)
    
    # Agent states
    agent_states: dict[str, AgentStatus] = field(default_factory=dict)
    
    # Provider states
    provider_health: dict[str, HealthStatus] = field(default_factory=dict)
    
    # Workspace
    current_workspace: Optional[str] = None
    workspace_path: Optional[str] = None
    
    # Timing
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    
    # Persistence
    version: int = 1
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()


@dataclass
class Permission:
    """Represents a permission for an operation."""
    
    action: str
    level: PermissionLevel
    requires_approval: bool = False
    allowed_paths: list[str] = field(default_factory=list)
    denied_commands: list[str] = field(default_factory=list)
    max_resource_usage: dict[str, Any] = field(default_factory=dict)
    
    def check_path(self, path: str) -> bool:
        """Check if path is allowed by this permission."""
        if not self.allowed_paths:
            return True
        return any(path.startswith(allowed) for allowed in self.allowed_paths)
    
    def check_command(self, command: str) -> bool:
        """Check if command is allowed by this permission."""
        return command not in self.denied_commands


@dataclass
class PermissionPolicy:
    """Policy defining permission rules."""
    
    name: str
    default_level: PermissionLevel = PermissionLevel.STANDARD
    permissions: list[Permission] = field(default_factory=list)
    approval_required_actions: list[str] = field(default_factory=list)
    
    def get_permission(self, action: str) -> Optional[Permission]:
        """Get permission for an action."""
        for perm in self.permissions:
            if perm.action == action:
                return perm
        return None
    
    def requires_approval(self, action: str) -> bool:
        """Check if action requires approval."""
        return action in self.approval_required_actions or any(
            p.requires_approval for p in self.permissions if p.action == action
        )


# ============================================================================
# Result Models
# ============================================================================

@dataclass
class ExecutionResult:
    """Result of executing a task or tool."""
    
    success: bool
    output: str = ""
    error: Optional[str] = None
    duration_ms: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewResult:
    """Result of a code or security review."""
    
    passed: bool
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    score: float = 0.0  # 0.0 to 1.0
    severity: str = "info"  # info, warning, error, critical
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheck:
    """Result of a health check."""
    
    component: str
    healthy: bool
    status: HealthStatus = HealthStatus.UNKNOWN
    message: Optional[str] = None
    latency_ms: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    details: dict[str, Any] = field(default_factory=dict)
