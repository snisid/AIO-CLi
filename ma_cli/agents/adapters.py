"""
External Agent Adapters for MA-CLI.

This module provides adapters for external agent CLIs:
- ClaudeAgent (Anthropic Claude Code)
- CodexAgent (OpenAI Codex CLI)
- QwenAgent (Alibaba Qwen CLI)
- ZcodeAgent (Zhipu GLM/Zcode CLI)
- OpenClawAgent (stub/interface ready)
- HermesAgent (stub/interface ready)

Each adapter detects the CLI, reports health, and executes tasks
through structured command execution with timeout and cancellation support.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..core.models import (
    AgentStatus,
    ExecutionResult,
    HealthStatus,
    ReviewResult,
    Task,
)
from .base import Agent, AgentInfo


@dataclass
class AgentConfig:
    """Configuration for an external agent CLI."""
    name: str
    cli_command: str
    version_args: list[str] = field(default_factory=list)
    health_check_args: list[str] = field(default_factory=list)
    execute_args: list[str] = field(default_factory=list)
    default_timeout: int = 300  # 5 minutes
    required_env_vars: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    
    def get_full_command(self, task_prompt: str) -> list[str]:
        """Get full command to execute a task."""
        cmd = [self.cli_command]
        cmd.extend(self.execute_args)
        cmd.append(task_prompt)
        return cmd


@dataclass 
class CLIInfo:
    """Information about a detected CLI."""
    exists: bool
    path: str | None = None
    version: str | None = None
    error: str | None = None


@dataclass
class AgentResult:
    """Structured result from agent execution."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration_ms: int = 0
    cancelled: bool = False
    timed_out: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_execution_result(self) -> ExecutionResult:
        """Convert to ExecutionResult."""
        if self.success:
            return ExecutionResult(
                success=True,
                output=self.stdout,
                duration_ms=self.duration_ms,
                metadata=self.metadata
            )
        else:
            return ExecutionResult(
                success=False,
                output=self.stdout,
                error=self.stderr or f"Exit code: {self.exit_code}",
                duration_ms=self.duration_ms,
                metadata=self.metadata
            )


class ExternalAgentBase(Agent):
    """
    Base class for external agent CLI adapters.
    
    Provides common functionality for detecting, health-checking,
    and executing external agent CLIs.
    """
    
    CONFIG: AgentConfig
    
    def __init__(self, config: AgentConfig | None = None):
        self._config = config or self.CONFIG
        self._status = AgentStatus.OFFLINE
        self._health = HealthStatus.UNKNOWN
        self._cli_info: CLIInfo | None = None
        self._current_process: asyncio.subprocess.Process | None = None
        self._last_check: datetime | None = None
        
    @property
    def id(self) -> str:
        # Convert name to snake_case for ID
        name = self._config.name
        # Insert underscore before uppercase letters, then lowercase everything
        import re
        snake_case = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        return snake_case
    
    @property
    def name(self) -> str:
        return self._config.name
    
    @property
    def provider(self) -> str:
        return self._config.name.lower()
    
    @property
    def capabilities(self) -> list[str]:
        return self._config.capabilities
    
    @property
    def roles(self) -> list[str]:
        return self._config.roles
    
    @property
    def status(self) -> AgentStatus:
        return self._status
    
    @property
    def health(self) -> HealthStatus:
        return self._health
    
    @property
    def config(self) -> AgentConfig:
        return self._config
    
    async def detect_cli(self) -> CLIInfo:
        """Detect if the CLI exists and get its version."""
        cmd = self._config.cli_command
        
        # Check if command exists in PATH
        cli_path = shutil.which(cmd)
        
        if not cli_path:
            self._cli_info = CLIInfo(
                exists=False,
                error=f"Command '{cmd}' not found in PATH"
            )
            return self._cli_info
        
        # Try to get version
        version = None
        if self._config.version_args:
            try:
                result = subprocess.run(
                    [cli_path] + self._config.version_args,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    version = result.stdout.strip() or result.stderr.strip()
            except Exception as e:
                version = f"Version check failed: {e}"
        
        self._cli_info = CLIInfo(
            exists=True,
            path=cli_path,
            version=version
        )
        return self._cli_info
    
    async def health_check(self) -> HealthStatus:
        """Check agent health and connectivity."""
        try:
            # First detect CLI
            cli_info = await self.detect_cli()
            
            if not cli_info.exists:
                self._health = HealthStatus.UNHEALTHY
                self._status = AgentStatus.OFFLINE
                return self._health
            
            # Run health check command if configured
            if self._config.health_check_args:
                try:
                    result = await asyncio.create_subprocess_exec(
                        cli_info.path,
                        *self._config.health_check_args,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await asyncio.wait_for(
                        result.communicate(),
                        timeout=30
                    )
                    
                    if result.returncode == 0:
                        self._health = HealthStatus.HEALTHY
                        self._status = AgentStatus.IDLE
                    else:
                        self._health = HealthStatus.DEGRADED
                        self._status = AgentStatus.ERROR
                except asyncio.TimeoutError:
                    self._health = HealthStatus.DEGRADED
                    self._status = AgentStatus.ERROR
                except Exception:
                    self._health = HealthStatus.UNHEALTHY
                    self._status = AgentStatus.OFFLINE
            else:
                # No health check args, assume healthy if CLI exists
                self._health = HealthStatus.HEALTHY
                self._status = AgentStatus.IDLE
            
            self._last_check = datetime.now(timezone.utc)
            return self._health
            
        except Exception:
            self._health = HealthStatus.UNHEALTHY
            self._status = AgentStatus.OFFLINE
            return self._health
    
    async def execute(self, task: Task) -> ExecutionResult:
        """Execute a task using the external CLI."""
        start_time = datetime.now(timezone.utc)
        
        # Detect CLI first
        cli_info = await self.detect_cli()
        
        if not cli_info.exists:
            return ExecutionResult(
                success=False,
                error=f"CLI not found: {self._config.cli_command}"
            )
        
        # Build command
        prompt = task.description or task.title
        cmd = [cli_info.path] + self._config.get_full_command(prompt)
        
        # Check required environment variables
        import os
        missing_env = []
        for env_var in self._config.required_env_vars:
            if env_var not in os.environ:
                missing_env.append(env_var)
        
        if missing_env:
            return ExecutionResult(
                success=False,
                error=f"Missing required environment variables: {', '.join(missing_env)}"
            )
        
        try:
            # Update status
            self._status = AgentStatus.BUSY
            
            # Create process
            self._current_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ}  # Copy current environment
            )
            
            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    self._current_process.communicate(),
                    timeout=self._config.default_timeout
                )
                
                end_time = datetime.now(timezone.utc)
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                
                result = AgentResult(
                    success=self._current_process.returncode == 0,
                    stdout=stdout.decode('utf-8', errors='replace') if stdout else "",
                    stderr=stderr.decode('utf-8', errors='replace') if stderr else "",
                    exit_code=self._current_process.returncode or 0,
                    duration_ms=duration_ms
                )
                
                self._status = AgentStatus.IDLE if result.success else AgentStatus.ERROR
                return result.to_execution_result()
                
            except asyncio.TimeoutError:
                # Kill process on timeout
                await self.cancel()
                end_time = datetime.now(timezone.utc)
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                
                return ExecutionResult(
                    success=False,
                    error=f"Task timed out after {self._config.default_timeout}s",
                    duration_ms=duration_ms,
                    metadata={"timed_out": True}
                )
                
        except Exception as e:
            self._status = AgentStatus.ERROR
            return ExecutionResult(
                success=False,
                error=str(e)
            )
        finally:
            self._current_process = None
    
    async def cancel(self) -> bool:
        """Cancel current execution."""
        if self._current_process:
            try:
                self._current_process.terminate()
                await asyncio.wait_for(self._current_process.wait(), timeout=5)
                self._status = AgentStatus.IDLE
                return True
            except Exception:
                try:
                    self._current_process.kill()
                    self._status = AgentStatus.IDLE
                    return True
                except Exception:
                    return False
        return True
    
    async def inspect(self) -> dict[str, Any]:
        """Return agent inspection details."""
        cli_info = await self.detect_cli()
        
        return {
            "agent_id": self.id,
            "agent_name": self.name,
            "cli_exists": cli_info.exists,
            "cli_path": cli_info.path,
            "cli_version": cli_info.version,
            "status": self._status.value,
            "health": self._health.value,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "capabilities": self.capabilities,
            "roles": self.roles,
            "required_env": self._config.required_env_vars
        }
    
    async def review(self, code: str) -> ReviewResult:
        """Review generated code using the agent."""
        # Default implementation: create a review task
        review_task = Task(
            title="Code Review",
            description=f"Review the following code and provide feedback:\n\n{code}",
            assigned_role="code_reviewer"
        )
        
        result = await self.execute(review_task)
        
        if result.success:
            return ReviewResult(
                passed=True,
                suggestions=[result.output] if result.output else [],
                score=0.8
            )
        else:
            return ReviewResult(
                passed=False,
                issues=[result.error] if result.error else ["Review failed"],
                score=0.3
            )
    
    async def report(self) -> dict[str, Any]:
        """Generate agent activity report."""
        return {
            "agent_id": self.id,
            "agent_name": self.name,
            "status": self._status.value,
            "health": self._health.value,
            "cli_info": {
                "exists": self._cli_info.exists if self._cli_info else False,
                "path": self._cli_info.path if self._cli_info else None,
                "version": self._cli_info.version if self._cli_info else None
            },
            "last_check": self._last_check.isoformat() if self._last_check else None
        }
    
    def get_info(self) -> AgentInfo:
        """Get comprehensive agent information."""
        return AgentInfo(
            id=self.id,
            name=self.name,
            provider=self.provider,
            capabilities=self.capabilities,
            roles=self.roles,
            status=self._status,
            health=self._health,
            metadata={
                "cli_command": self._config.cli_command,
                "required_env": self._config.required_env_vars
            }
        )


# ============================================================================
# ClaudeAgent
# ============================================================================

class ClaudeAgent(ExternalAgentBase):
    """
    Adapter for Anthropic Claude Code CLI.
    
    Detects and interfaces with the Claude Code CLI tool.
    """
    
    CONFIG = AgentConfig(
        name="ClaudeAgent",
        cli_command="claude",
        version_args=["--version"],
        execute_args=[],  # claude <prompt>
        default_timeout=600,
        required_env_vars=["ANTHROPIC_API_KEY"],
        capabilities=["coding", "reasoning", "tool_use", "file_editing", "shell"],
        roles=["developer", "architect", "reviewer", "planner"]
    )


# ============================================================================
# CodexAgent
# ============================================================================

class CodexAgent(ExternalAgentBase):
    """
    Adapter for OpenAI Codex CLI.
    
    Detects and interfaces with the Codex CLI tool.
    """
    
    CONFIG = AgentConfig(
        name="CodexAgent",
        cli_command="codex",
        version_args=["--version"],
        execute_args=[],  # codex <prompt>
        default_timeout=600,
        required_env_vars=["OPENAI_API_KEY"],
        capabilities=["coding", "reasoning", "tool_use", "file_editing"],
        roles=["developer", "backend_engineer", "tester"]
    )


# ============================================================================
# QwenAgent
# ============================================================================

class QwenAgent(ExternalAgentBase):
    """
    Adapter for Alibaba Qwen CLI.
    
    Detects and interfaces with the Qwen CLI tool.
    """
    
    CONFIG = AgentConfig(
        name="QwenAgent",
        cli_command="qwen",
        version_args=["--version"],
        execute_args=["--run"],
        default_timeout=600,
        required_env_vars=["DASHSCOPE_API_KEY"],
        capabilities=["coding", "reasoning", "multilingual", "analysis"],
        roles=["developer", "researcher", "data_analyst"]
    )


# ============================================================================
# ZcodeAgent
# ============================================================================

class ZcodeAgent(ExternalAgentBase):
    """
    Adapter for Zhipu GLM/Zcode CLI.
    
    Detects and interfaces with the Zcode CLI tool.
    """
    
    CONFIG = AgentConfig(
        name="ZcodeAgent",
        cli_command="zcode",
        version_args=["--version"],
        execute_args=["--execute"],
        default_timeout=600,
        required_env_vars=["ZHIPU_API_KEY"],
        capabilities=["coding", "reasoning", "glm_models"],
        roles=["developer", "backend_engineer"]
    )


# ============================================================================
# OpenClawAgent (Stub/Interface Ready)
# ============================================================================

class OpenClawAgent(ExternalAgentBase):
    """
    Adapter for OpenClaw (Open-source alternative).
    
    This is a stub/interface ready implementation.
    Actual CLI command may vary based on OpenClaw installation.
    """
    
    CONFIG = AgentConfig(
        name="OpenClawAgent",
        cli_command="openclaw",  # Placeholder - update when OpenClaw CLI is available
        version_args=["--version"],
        execute_args=[],
        default_timeout=600,
        required_env_vars=[],  # May need OPENCLAW_API_KEY or similar
        capabilities=["coding", "reasoning"],
        roles=["developer"]
    )
    
    async def detect_cli(self) -> CLIInfo:
        """Override to handle placeholder status."""
        # Check if this is still a placeholder
        if self._config.cli_command == "openclaw":
            # Try to detect anyway
            return await super().detect_cli()
        return await super().detect_cli()


# ============================================================================
# HermesAgent (Stub/Interface Ready)
# ============================================================================

class HermesAgent(ExternalAgentBase):
    """
    Adapter for Hermes Agent Framework.
    
    This is a stub/interface ready implementation.
    Actual CLI command may vary based on Hermes installation.
    """
    
    CONFIG = AgentConfig(
        name="HermesAgent",
        cli_command="hermes",  # Placeholder - update when Hermes CLI is available
        version_args=["--version"],
        execute_args=["--run"],
        default_timeout=600,
        required_env_vars=[],  # May need HERMES_API_KEY or similar
        capabilities=["coding", "orchestration", "multi_agent"],
        roles=["developer", "orchestrator"]
    )
    
    async def detect_cli(self) -> CLIInfo:
        """Override to handle placeholder status."""
        if self._config.cli_command == "hermes":
            return await super().detect_cli()
        return await super().detect_cli()


# ============================================================================
# Agent Registry
# ============================================================================

class AgentRegistry:
    """
    Registry for managing and discovering agents.
    
    Provides centralized access to all available agents.
    """
    
    _instance: AgentRegistry | None = None
    
    def __new__(cls) -> AgentRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents = {}
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._agents: dict[str, Agent] = {}
        self._register_default_agents()
        self._initialized = True
    
    def _register_default_agents(self) -> None:
        """Register all default agents."""
        agents = [
            ClaudeAgent(),
            CodexAgent(),
            QwenAgent(),
            ZcodeAgent(),
            OpenClawAgent(),
            HermesAgent(),
        ]
        
        for agent in agents:
            self._agents[agent.id] = agent
    
    def get(self, agent_id: str) -> Agent | None:
        """Get an agent by ID."""
        return self._agents.get(agent_id)
    
    def get_by_name(self, name: str) -> Agent | None:
        """Get an agent by name."""
        for agent in self._agents.values():
            if agent.name.lower() == name.lower():
                return agent
        return None
    
    def list_all(self) -> list[Agent]:
        """List all registered agents."""
        return list(self._agents.values())
    
    def list_available(self) -> list[Agent]:
        """List agents that are currently available (CLI detected)."""
        available = []
        for agent in self._agents.values():
            if agent.health == HealthStatus.HEALTHY:
                available.append(agent)
        return available
    
    def register(self, agent: Agent) -> None:
        """Register a custom agent."""
        self._agents[agent.id] = agent
    
    def unregister(self, agent_id: str) -> bool:
        """Unregister an agent."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            return True
        return False
    
    async def health_check_all(self) -> dict[str, HealthStatus]:
        """Run health checks on all agents."""
        results = {}
        for agent_id, agent in self._agents.items():
            health = await agent.health_check()
            results[agent_id] = health
        return results
    
    def get_capabilities_summary(self) -> dict[str, list[str]]:
        """Get summary of capabilities across all agents."""
        capabilities = {}
        for agent in self._agents.values():
            for cap in agent.capabilities:
                if cap not in capabilities:
                    capabilities[cap] = []
                capabilities[cap].append(agent.name)
        return capabilities


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry."""
    return AgentRegistry()
