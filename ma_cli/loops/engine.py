"""
Loop Engine for MA-CLI.

This module defines the loop abstraction for workflow execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class LoopStatus(Enum):
    """Loop execution status."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LoopStep:
    """A step in a loop."""
    name: str
    description: str = ""
    agent: Optional[str] = None
    model: Optional[str] = None
    tools: list[str] = field(default_factory=list)
    timeout_seconds: int = 300


@dataclass
class RetryPolicy:
    """Retry policy for loops."""
    max_retries: int = 3
    backoff_type: str = "exponential"  # 'linear' or 'exponential'
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    retry_on: list[str] = field(default_factory=list)  # Error types to retry
    
    def should_retry(self, error_type: str, attempt: int) -> bool:
        """Check if retry should be attempted."""
        if attempt >= self.max_retries:
            return False
        if self.retry_on and error_type not in self.retry_on:
            return False
        return True
    
    def get_delay(self, attempt: int) -> float:
        """Get delay in seconds for retry attempt."""
        if self.backoff_type == "linear":
            return self.initial_delay_ms * attempt / 1000
        else:  # exponential
            return min(
                self.initial_delay_ms * (2 ** attempt),
                self.max_delay_ms
            ) / 1000


@dataclass
class ApprovalPolicy:
    """Approval policy for loops."""
    auto_approve: bool = False
    require_approval_for: list[str] = field(default_factory=list)
    approval_timeout_seconds: int = 300
    
    def requires_approval(self, action: str) -> bool:
        """Check if action requires approval."""
        if self.auto_approve:
            return False
        if not self.require_approval_for:
            return False
        return action in self.require_approval_for


@dataclass
class MemoryConfig:
    """Memory configuration for loops."""
    enabled: bool = True
    scope: str = "loop"  # 'loop', 'task', 'session'
    retention_hours: int = 24
    search_enabled: bool = True


@dataclass
class OutputConfig:
    """Output configuration for loops."""
    format: str = "text"  # 'text', 'json', 'markdown'
    save_to_file: bool = False
    file_path: Optional[str] = None
    include_metadata: bool = True


@dataclass
class Loop:
    """
    Loop specification for workflow execution.
    
    Loops are the primary workflow abstraction in MA-CLI, replacing
    'Skills' with explicit, auditable workflows.
    """
    name: str
    objective: str
    trigger: str = "manual"
    inputs: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    memory: MemoryConfig = None
    steps: list[LoopStep] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    failure_criteria: list[str] = field(default_factory=list)
    retry_policy: RetryPolicy = None
    approval_policy: ApprovalPolicy = None
    output: OutputConfig = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.memory is None:
            self.memory = MemoryConfig()
        if self.retry_policy is None:
            self.retry_policy = RetryPolicy()
        if self.approval_policy is None:
            self.approval_policy = ApprovalPolicy()
        if self.output is None:
            self.output = OutputConfig()


@dataclass
class LoopState:
    """State of a running loop."""
    loop: Loop
    inputs: dict[str, Any]
    current_step: int = 0
    outputs: dict[str, Any] = field(default_factory=dict)
    retries: dict[str, int] = field(default_factory=dict)
    approvals: dict[str, bool] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    status: LoopStatus = LoopStatus.PENDING
    error: Optional[str] = None
    
    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_updated = datetime.utcnow()


@dataclass
class LoopResult:
    """Result of loop execution."""
    success: bool
    outputs: dict[str, Any]
    state: LoopState
    duration_ms: float = 0.0
    steps_completed: int = 0
    steps_total: int = 0


class LoopEngine:
    """
    Loop execution engine.
    
    Executes defined loops with proper state management,
    retry handling, and approval gates.
    """
    
    def __init__(self):
        self._loops: dict[str, Loop] = {}
        self._running: dict[str, LoopState] = {}
    
    def register(self, loop: Loop) -> None:
        """Register a loop definition."""
        self._loops[loop.name] = loop
    
    def get(self, name: str) -> Optional[Loop]:
        """Get a loop by name."""
        return self._loops.get(name)
    
    def list_all(self) -> list[Loop]:
        """List all registered loops."""
        return list(self._loops.values())
    
    async def execute(
        self,
        loop_name: str,
        inputs: dict[str, Any],
        context: Optional[Any] = None
    ) -> LoopResult:
        """
        Execute a loop with given inputs.
        
        Args:
            loop_name: Name of loop to execute
            inputs: Input values for the loop
            context: Optional execution context
            
        Returns:
            LoopResult with execution outcome
        """
        loop = self._loops.get(loop_name)
        if not loop:
            raise ValueError(f"Loop '{loop_name}' not found")
        
        # Initialize state
        state = LoopState(
            loop=loop,
            inputs=inputs,
            status=LoopStatus.RUNNING
        )
        self._running[loop_name] = state
        
        try:
            # Execute steps
            for i, step in enumerate(loop.steps):
                state.current_step = i
                state.update_activity()
                
                # Execute step (placeholder - actual implementation in Phase 13)
                # result = await self._execute_step(step, state, context)
                
            # Evaluate success
            success = self._evaluate_success(loop, state)
            
            return LoopResult(
                success=success,
                outputs=state.outputs,
                state=state,
                steps_completed=len(loop.steps) if success else state.current_step,
                steps_total=len(loop.steps)
            )
            
        finally:
            if loop_name in self._running:
                del self._running[loop_name]
    
    def _evaluate_success(self, loop: Loop, state: LoopState) -> bool:
        """Evaluate if loop succeeded based on criteria."""
        # Placeholder - actual implementation in Phase 13
        return True
