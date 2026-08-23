"""
Agent Interface for MA-CLI.

This module defines the universal agent abstraction that all agents must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..core.models import (
    AgentStatus,
    ExecutionResult,
    HealthStatus,
    ReviewResult,
    Task,
)


@dataclass
class AgentInfo:
    """Information about an agent."""

    id: str
    name: str
    provider: str
    capabilities: list[str]
    roles: list[str]
    status: AgentStatus = AgentStatus.OFFLINE
    health: HealthStatus = HealthStatus.UNKNOWN
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class Agent(ABC):
    """
    Universal Agent Interface.

    All agents (NativeAgent, ClaudeAgent, CodexAgent, etc.) must implement
    this interface to be used by MA-CLI.
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique agent identifier."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Provider this agent uses (e.g., 'anthropic', 'openai', 'ollama')."""

    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        """List of agent capabilities (e.g., 'coding', 'reasoning', 'tool_use')."""

    @property
    @abstractmethod
    def roles(self) -> list[str]:
        """Roles this agent can perform (e.g., 'developer', 'reviewer', 'planner')."""

    @property
    @abstractmethod
    def status(self) -> AgentStatus:
        """Current agent status."""

    @property
    @abstractmethod
    def health(self) -> HealthStatus:
        """Agent health status."""

    @abstractmethod
    async def execute(self, task: Task) -> ExecutionResult:
        """
        Execute a task.

        Args:
            task: The task to execute

        Returns:
            ExecutionResult with success status and output
        """

    @abstractmethod
    async def cancel(self) -> bool:
        """
        Cancel current execution.

        Returns:
            True if cancellation was successful
        """

    @abstractmethod
    async def inspect(self) -> dict[str, Any]:
        """
        Return agent inspection details.

        Returns:
            Dictionary with agent state and diagnostic information
        """

    @abstractmethod
    async def review(self, code: str) -> ReviewResult:
        """
        Review generated code.

        Args:
            code: Code to review

        Returns:
            ReviewResult with issues and suggestions
        """

    @abstractmethod
    async def report(self) -> dict[str, Any]:
        """
        Generate agent activity report.

        Returns:
            Dictionary with activity metrics and status
        """

    async def health_check(self) -> HealthStatus:
        """
        Check agent health and connectivity.

        Returns:
            Current health status
        """
        try:
            # Default implementation: try a simple operation
            await self.inspect()
            return HealthStatus.HEALTHY
        except Exception:
            return HealthStatus.UNHEALTHY

    def get_info(self) -> AgentInfo:
        """Get comprehensive agent information."""
        return AgentInfo(
            id=self.id,
            name=self.name,
            provider=self.provider,
            capabilities=self.capabilities,
            roles=self.roles,
            status=self.status,
            health=self.health,
        )

    def supports_role(self, role: str) -> bool:
        """Check if agent supports a specific role."""
        return role in self.roles

    def has_capability(self, capability: str) -> bool:
        """Check if agent has a specific capability."""
        return capability in self.capabilities
