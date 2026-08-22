"""Tests for external agent adapters."""

import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

from ma_cli.agents.adapters import (
    AgentConfig,
    CLIInfo,
    AgentResult,
    ExternalAgentBase,
    ClaudeAgent,
    CodexAgent,
    QwenAgent,
    ZcodeAgent,
    OpenClawAgent,
    HermesAgent,
    AgentRegistry,
    get_agent_registry,
)
from ma_cli.core.models import (
    Task,
    AgentStatus,
    HealthStatus,
    ExecutionResult,
    ReviewResult,
)


class TestAgentConfig:
    """Tests for AgentConfig dataclass."""
    
    def test_agent_config_creation(self):
        """Test creating an AgentConfig."""
        config = AgentConfig(
            name="TestAgent",
            cli_command="test-cli",
            version_args=["--version"],
            default_timeout=120,
            required_env_vars=["TEST_API_KEY"],
            capabilities=["coding"],
            roles=["developer"]
        )
        
        assert config.name == "TestAgent"
        assert config.cli_command == "test-cli"
        assert config.version_args == ["--version"]
        assert config.default_timeout == 120
        assert config.required_env_vars == ["TEST_API_KEY"]
        assert config.capabilities == ["coding"]
        assert config.roles == ["developer"]
    
    def test_agent_config_defaults(self):
        """Test AgentConfig default values."""
        config = AgentConfig(
            name="MinimalAgent",
            cli_command="minimal"
        )
        
        assert config.version_args == []
        assert config.health_check_args == []
        assert config.execute_args == []
        assert config.default_timeout == 300
        assert config.required_env_vars == []
        assert config.capabilities == []
        assert config.roles == []
    
    def test_get_full_command(self):
        """Test building full command from config."""
        config = AgentConfig(
            name="TestAgent",
            cli_command="test",
            execute_args=["--run", "--verbose"]
        )
        
        cmd = config.get_full_command("Do something")
        
        assert cmd == ["test", "--run", "--verbose", "Do something"]
    
    def test_get_full_command_no_args(self):
        """Test building command without extra args."""
        config = AgentConfig(
            name="SimpleAgent",
            cli_command="simple"
        )
        
        cmd = config.get_full_command("Task prompt")
        
        assert cmd == ["simple", "Task prompt"]


class TestCLIInfo:
    """Tests for CLIInfo dataclass."""
    
    def test_cli_info_exists(self):
        """Test CLIInfo when CLI exists."""
        info = CLIInfo(
            exists=True,
            path="/usr/bin/test-cli",
            version="1.0.0"
        )
        
        assert info.exists is True
        assert info.path == "/usr/bin/test-cli"
        assert info.version == "1.0.0"
        assert info.error is None
    
    def test_cli_info_not_exists(self):
        """Test CLIInfo when CLI doesn't exist."""
        info = CLIInfo(
            exists=False,
            error="Command not found"
        )
        
        assert info.exists is False
        assert info.path is None
        assert info.version is None
        assert info.error == "Command not found"


class TestAgentResult:
    """Tests for AgentResult dataclass."""
    
    def test_agent_result_success(self):
        """Test successful agent result."""
        result = AgentResult(
            success=True,
            stdout="Output here",
            exit_code=0,
            duration_ms=1500
        )
        
        assert result.success is True
        assert result.stdout == "Output here"
        assert result.exit_code == 0
        assert result.duration_ms == 1500
        assert result.cancelled is False
        assert result.timed_out is False
    
    def test_agent_result_failure(self):
        """Test failed agent result."""
        result = AgentResult(
            success=False,
            stderr="Error occurred",
            exit_code=1,
            duration_ms=500
        )
        
        assert result.success is False
        assert result.stderr == "Error occurred"
        assert result.exit_code == 1
    
    def test_agent_result_timeout(self):
        """Test timed out agent result."""
        result = AgentResult(
            success=False,
            timed_out=True,
            duration_ms=300000
        )
        
        assert result.timed_out is True
        assert result.success is False
    
    def test_to_execution_result_success(self):
        """Test converting successful result to ExecutionResult."""
        agent_result = AgentResult(
            success=True,
            stdout="Success output",
            duration_ms=2000,
            metadata={"key": "value"}
        )
        
        exec_result = agent_result.to_execution_result()
        
        assert isinstance(exec_result, ExecutionResult)
        assert exec_result.success is True
        assert exec_result.output == "Success output"
        assert exec_result.error is None
        assert exec_result.duration_ms == 2000
        assert exec_result.metadata == {"key": "value"}
    
    def test_to_execution_result_failure(self):
        """Test converting failed result to ExecutionResult."""
        agent_result = AgentResult(
            success=False,
            stderr="Something went wrong",
            exit_code=1,
            duration_ms=1000
        )
        
        exec_result = agent_result.to_execution_result()
        
        assert isinstance(exec_result, ExecutionResult)
        assert exec_result.success is False
        assert exec_result.error == "Something went wrong"


class TestExternalAgentBase:
    """Tests for ExternalAgentBase class."""
    
    @pytest.fixture
    def test_config(self):
        """Create a test agent config."""
        return AgentConfig(
            name="TestAgent",
            cli_command="test-cli",
            version_args=["--version"],
            health_check_args=["--health"],
            execute_args=["--run"],
            default_timeout=60,
            required_env_vars=["TEST_API_KEY"],
            capabilities=["coding", "testing"],
            roles=["developer", "tester"]
        )
    
    @pytest.fixture
    def test_agent(self, test_config):
        """Create a test agent instance."""
        return ExternalAgentBase(config=test_config)
    
    def test_agent_properties(self, test_agent):
        """Test agent property access."""
        assert test_agent.id == "test_agent"
        assert test_agent.name == "TestAgent"
        assert test_agent.provider == "testagent"
        assert test_agent.capabilities == ["coding", "testing"]
        assert test_agent.roles == ["developer", "tester"]
    
    def test_agent_initial_status(self, test_agent):
        """Test initial agent status."""
        assert test_agent.status == AgentStatus.OFFLINE
        assert test_agent.health == HealthStatus.UNKNOWN
    
    @pytest.mark.asyncio
    async def test_detect_cli_not_found(self, test_agent):
        """Test CLI detection when not found."""
        with patch('shutil.which', return_value=None):
            cli_info = await test_agent.detect_cli()
            
            assert cli_info.exists is False
            assert "not found in PATH" in cli_info.error
    
    @pytest.mark.asyncio
    async def test_detect_cli_found(self, test_agent):
        """Test CLI detection when found."""
        with patch('shutil.which', return_value="/usr/bin/test-cli"):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="test-cli version 1.0.0",
                    stderr=""
                )
                
                cli_info = await test_agent.detect_cli()
                
                assert cli_info.exists is True
                assert cli_info.path == "/usr/bin/test-cli"
                assert "1.0.0" in cli_info.version
    
    @pytest.mark.asyncio
    async def test_health_check_cli_missing(self, test_agent):
        """Test health check when CLI is missing."""
        with patch('shutil.which', return_value=None):
            health = await test_agent.health_check()
            
            assert health == HealthStatus.UNHEALTHY
            assert test_agent.status == AgentStatus.OFFLINE
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, test_agent):
        """Test successful health check."""
        # Mock CLI exists
        with patch('shutil.which', return_value="/usr/bin/test-cli"):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="1.0.0",
                    stderr=""
                )
                
                # Mock async health check
                mock_process = AsyncMock()
                mock_process.communicate = AsyncMock(return_value=(b"", b""))
                mock_process.returncode = 0
                
                with patch('asyncio.create_subprocess_exec', return_value=mock_process):
                    health = await test_agent.health_check()
                    
                    assert health == HealthStatus.HEALTHY
                    assert test_agent.status == AgentStatus.IDLE
    
    @pytest.mark.asyncio
    async def test_execute_cli_missing(self, test_agent):
        """Test execution when CLI is missing."""
        task = Task(title="Test Task", description="Test description")
        
        with patch('shutil.which', return_value=None):
            result = await test_agent.execute(task)
            
            assert result.success is False
            assert "CLI not found" in result.error
    
    @pytest.mark.asyncio
    async def test_execute_missing_env_vars(self, test_agent):
        """Test execution when required env vars are missing."""
        task = Task(title="Test Task", description="Test description")
        
        with patch('shutil.which', return_value="/usr/bin/test-cli"):
            with patch.dict('os.environ', {}, clear=True):
                result = await test_agent.execute(task)
                
                assert result.success is False
                assert "Missing required environment variables" in result.error
                assert "TEST_API_KEY" in result.error
    
    @pytest.mark.asyncio
    async def test_cancel_no_process(self, test_agent):
        """Test cancellation when no process is running."""
        result = await test_agent.cancel()
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_inspect(self, test_agent):
        """Test agent inspection."""
        with patch('shutil.which', return_value=None):
            info = await test_agent.inspect()
            
            assert info["agent_id"] == "test_agent"
            assert info["agent_name"] == "TestAgent"
            assert info["cli_exists"] is False
            assert info["capabilities"] == ["coding", "testing"]
            assert info["roles"] == ["developer", "tester"]
    
    @pytest.mark.asyncio
    async def test_review_success(self, test_agent):
        """Test code review with successful execution."""
        code = "def hello():\n    print('Hello')"
        
        # Mock successful execution
        with patch.object(test_agent, 'execute') as mock_execute:
            mock_execute.return_value = ExecutionResult(
                success=True,
                output="Code looks good!"
            )
            
            result = await test_agent.review(code)
            
            assert isinstance(result, ReviewResult)
            assert result.passed is True
            assert result.score == 0.8
    
    @pytest.mark.asyncio
    async def test_report(self, test_agent):
        """Test agent report generation."""
        report = await test_agent.report()
        
        assert report["agent_id"] == "test_agent"
        assert report["agent_name"] == "TestAgent"
        assert "status" in report
        assert "health" in report


class TestSpecificAgents:
    """Tests for specific agent implementations."""
    
    def test_claude_agent_config(self):
        """Test ClaudeAgent configuration."""
        agent = ClaudeAgent()
        
        assert agent.id == "claude_agent"
        assert agent.name == "ClaudeAgent"
        assert agent.config.cli_command == "claude"
        assert "ANTHROPIC_API_KEY" in agent.config.required_env_vars
        assert "coding" in agent.capabilities
        assert "developer" in agent.roles
    
    def test_codex_agent_config(self):
        """Test CodexAgent configuration."""
        agent = CodexAgent()
        
        assert agent.id == "codex_agent"
        assert agent.name == "CodexAgent"
        assert agent.config.cli_command == "codex"
        assert "OPENAI_API_KEY" in agent.config.required_env_vars
    
    def test_qwen_agent_config(self):
        """Test QwenAgent configuration."""
        agent = QwenAgent()
        
        assert agent.id == "qwen_agent"
        assert agent.name == "QwenAgent"
        assert agent.config.cli_command == "qwen"
        assert "DASHSCOPE_API_KEY" in agent.config.required_env_vars
        assert "--run" in agent.config.execute_args
    
    def test_zcode_agent_config(self):
        """Test ZcodeAgent configuration."""
        agent = ZcodeAgent()
        
        assert agent.id == "zcode_agent"
        assert agent.name == "ZcodeAgent"
        assert agent.config.cli_command == "zcode"
        assert "ZHIPU_API_KEY" in agent.config.required_env_vars
        assert "--execute" in agent.config.execute_args
    
    def test_openclaw_agent_stub(self):
        """Test OpenClawAgent stub implementation."""
        agent = OpenClawAgent()
        
        assert agent.id == "open_claw_agent"
        assert agent.name == "OpenClawAgent"
        # Placeholder CLI command
        assert agent.config.cli_command == "openclaw"
    
    def test_hermes_agent_stub(self):
        """Test HermesAgent stub implementation."""
        agent = HermesAgent()
        
        assert agent.id == "hermes_agent"
        assert agent.name == "HermesAgent"
        # Placeholder CLI command
        assert agent.config.cli_command == "hermes"


class TestAgentRegistry:
    """Tests for AgentRegistry."""
    
    @pytest.fixture
    def fresh_registry(self):
        """Create a fresh registry instance."""
        # Reset singleton
        AgentRegistry._instance = None
        return get_agent_registry()
    
    def test_registry_singleton(self, fresh_registry):
        """Test registry is a singleton."""
        registry1 = get_agent_registry()
        registry2 = get_agent_registry()
        
        assert registry1 is registry2
    
    def test_registry_contains_agents(self, fresh_registry):
        """Test registry contains expected agents."""
        all_agents = fresh_registry.list_all()
        
        assert len(all_agents) >= 6  # Claude, Codex, Qwen, Zcode, OpenClaw, Hermes
        
        agent_names = [a.name for a in all_agents]
        assert "ClaudeAgent" in agent_names
        assert "CodexAgent" in agent_names
        assert "QwenAgent" in agent_names
        assert "ZcodeAgent" in agent_names
    
    def test_get_agent_by_id(self, fresh_registry):
        """Test getting agent by ID."""
        agent = fresh_registry.get("claude_agent")
        
        assert agent is not None
        assert agent.name == "ClaudeAgent"
    
    def test_get_agent_by_name(self, fresh_registry):
        """Test getting agent by name."""
        agent = fresh_registry.get_by_name("ClaudeAgent")
        
        assert agent is not None
        assert agent.id == "claude_agent"
    
    def test_get_nonexistent_agent(self, fresh_registry):
        """Test getting nonexistent agent."""
        agent = fresh_registry.get("nonexistent_agent")
        
        assert agent is None
    
    def test_register_custom_agent(self, fresh_registry):
        """Test registering a custom agent."""
        custom_agent = ClaudeAgent()
        custom_agent._config.name = "CustomAgent"
        
        fresh_registry.register(custom_agent)
        
        retrieved = fresh_registry.get("custom_agent")
        assert retrieved is not None
        assert retrieved.name == "CustomAgent"
    
    def test_unregister_agent(self, fresh_registry):
        """Test unregistering an agent."""
        # First register one
        custom_agent = ClaudeAgent()
        custom_agent._config.name = "TempAgent"
        fresh_registry.register(custom_agent)
        
        # Then unregister
        result = fresh_registry.unregister("temp_agent")
        
        assert result is True
        assert fresh_registry.get("temp_agent") is None
    
    def test_capabilities_summary(self, fresh_registry):
        """Test getting capabilities summary."""
        summary = fresh_registry.get_capabilities_summary()
        
        assert isinstance(summary, dict)
        # All agents should have coding capability
        assert "coding" in summary
        assert len(summary["coding"]) > 0


@pytest.mark.asyncio
async def test_agent_health_check_all():
    """Test health checking all agents."""
    registry = get_agent_registry()
    
    results = await registry.health_check_all()
    
    assert isinstance(results, dict)
    assert len(results) >= 6  # At least 6 agents
    
    # All results should be HealthStatus values
    for agent_id, health in results.items():
        assert isinstance(health, HealthStatus)


class TestAgentExecutionIntegration:
    """Integration tests for agent execution."""
    
    @pytest.mark.asyncio
    async def test_claude_agent_execution_mock(self):
        """Test ClaudeAgent execution with mocked subprocess."""
        agent = ClaudeAgent()
        task = Task(title="Test", description="Test task")
        
        # Mock CLI not found
        with patch('shutil.which', return_value=None):
            result = await agent.execute(task)
            
            assert result.success is False
            assert "CLI not found" in result.error
    
    @pytest.mark.asyncio
    async def test_agent_with_env_vars_mock(self):
        """Test agent execution with mocked env vars."""
        agent = ClaudeAgent()
        task = Task(title="Test", description="Test task")
        
        # Mock CLI exists but env var missing
        with patch('shutil.which', return_value="/usr/bin/claude"):
            with patch.dict('os.environ', {}, clear=True):
                result = await agent.execute(task)
                
                assert result.success is False
                assert "ANTHROPIC_API_KEY" in result.error
    
    @pytest.mark.asyncio
    async def test_successful_execution_mock(self):
        """Test successful execution with full mocking."""
        agent = ClaudeAgent()
        task = Task(title="Test", description="Test task")
        
        # Mock CLI exists and env var present
        with patch('shutil.which', return_value="/usr/bin/claude"):
            with patch.dict('os.environ', {"ANTHROPIC_API_KEY": "test-key"}):
                # Mock subprocess
                mock_process = AsyncMock()
                mock_process.communicate = AsyncMock(
                    return_value=(b"Success output", b"")
                )
                mock_process.returncode = 0
                
                with patch('asyncio.create_subprocess_exec', return_value=mock_process):
                    result = await agent.execute(task)
                    
                    assert result.success is True
                    assert result.output == "Success output"
