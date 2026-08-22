"""Tests for agent interface."""

import pytest
import asyncio

from ma_cli.agents.base import Agent, AgentInfo
from ma_cli.core.models import (
    Task,
    AgentStatus,
    HealthStatus,
    ExecutionResult,
    ReviewResult,
)


class MockAgent(Agent):
    """Mock agent for testing."""
    
    def __init__(self):
        self._status = AgentStatus.IDLE
        self._health = HealthStatus.HEALTHY
    
    @property
    def id(self) -> str:
        return "mock-agent"
    
    @property
    def name(self) -> str:
        return "Mock Agent"
    
    @property
    def provider(self) -> str:
        return "mock"
    
    @property
    def capabilities(self) -> list[str]:
        return ["coding", "testing"]
    
    @property
    def roles(self) -> list[str]:
        return ["developer", "tester"]
    
    @property
    def status(self) -> AgentStatus:
        return self._status
    
    @property
    def health(self) -> HealthStatus:
        return self._health
    
    async def execute(self, task: Task) -> ExecutionResult:
        return ExecutionResult(success=True, output="Mock executed")
    
    async def cancel(self) -> bool:
        self._status = AgentStatus.IDLE
        return True
    
    async def inspect(self) -> dict:
        return {"status": "ok"}
    
    async def review(self, code: str) -> ReviewResult:
        return ReviewResult(passed=True, score=1.0)
    
    async def report(self) -> dict:
        return {"tasks_completed": 0}


class TestAgentInterface:
    """Tests for Agent interface."""
    
    def test_agent_properties(self):
        """Test agent property access."""
        agent = MockAgent()
        
        assert agent.id == "mock-agent"
        assert agent.name == "Mock Agent"
        assert agent.provider == "mock"
        assert "coding" in agent.capabilities
        assert "developer" in agent.roles
    
    def test_agent_status(self):
        """Test agent status tracking."""
        agent = MockAgent()
        
        assert agent.status == AgentStatus.IDLE
        assert agent.health == HealthStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_agent_execute(self):
        """Test agent execution."""
        agent = MockAgent()
        task = Task(title="Test", description="Test task")
        
        result = await agent.execute(task)
        
        assert result.success is True
        assert result.output == "Mock executed"
    
    @pytest.mark.asyncio
    async def test_agent_cancel(self):
        """Test agent cancellation."""
        agent = MockAgent()
        agent._status = AgentStatus.BUSY
        
        result = await agent.cancel()
        
        assert result is True
        assert agent.status == AgentStatus.IDLE
    
    @pytest.mark.asyncio
    async def test_agent_inspect(self):
        """Test agent inspection."""
        agent = MockAgent()
        
        info = await agent.inspect()
        
        assert "status" in info
        assert info["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_agent_review(self):
        """Test code review."""
        agent = MockAgent()
        
        result = await agent.review("print('hello')")
        
        assert result.passed is True
        assert result.score == 1.0
    
    def test_agent_get_info(self):
        """Test getting agent info."""
        agent = MockAgent()
        
        info = agent.get_info()
        
        assert isinstance(info, AgentInfo)
        assert info.id == "mock-agent"
        assert info.name == "Mock Agent"
        assert info.provider == "mock"
    
    def test_supports_role(self):
        """Test role support checking."""
        agent = MockAgent()
        
        assert agent.supports_role("developer") is True
        assert agent.supports_role("planner") is False
    
    def test_has_capability(self):
        """Test capability checking."""
        agent = MockAgent()
        
        assert agent.has_capability("coding") is True
        assert agent.has_capability("design") is False
