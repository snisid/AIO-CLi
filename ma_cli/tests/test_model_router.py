"""Tests for the Model Router."""

import pytest
from datetime import datetime, timezone

from ma_cli.models.router import (
    ModelRouter,
    RoutingStrategy,
    TaskType,
    ModelSpec,
    AgentContext,
    ModelSelectionResult,
)
from ma_cli.providers.base import ModelInfo
from ma_cli.core.models import HealthStatus


class TestModelSpec:
    """Tests for ModelSpec dataclass."""
    
    def test_model_spec_creation(self):
        """Test creating a ModelSpec with all fields."""
        spec = ModelSpec(
            model_id="claude-sonnet-4",
            name="Claude Sonnet 4",
            provider="anthropic",
            capabilities=["code", "reasoning", "chat"],
            context_window=200000,
            max_output=64000,
            speed=150.0,
            cost=3.0,
            quality=0.95,
            reasoning_level="advanced",
            coding_score=0.92,
            availability=1.0,
            health=HealthStatus.HEALTHY,
            latency_ms=50.0,
        )
        
        assert spec.model_id == "claude-sonnet-4"
        assert spec.provider == "anthropic"
        assert len(spec.capabilities) == 3
        assert spec.context_window == 200000
        assert spec.quality == 0.95
        assert spec.coding_score == 0.92
    
    def test_model_spec_from_model_info(self):
        """Test creating ModelSpec from ModelInfo."""
        info = ModelInfo(
            model_id="gpt-4o",
            name="GPT-4o",
            provider="openai",
            capabilities=["code", "chat", "vision"],
            max_context_tokens=128000,
            cost_per_token=2.5,
            available=True
        )
        
        spec = ModelSpec.from_model_info(info)
        
        assert spec.model_id == "gpt-4o"
        assert spec.provider == "openai"
        assert spec.context_window == 128000
        assert spec.cost == 2.5
        assert spec.availability == 1.0
    
    def test_model_spec_to_model_info(self):
        """Test converting ModelSpec to ModelInfo."""
        spec = ModelSpec(
            model_id="llama-3",
            name="Llama 3",
            provider="ollama",
            capabilities=["chat"],
            context_window=8000,
            cost=0.0,
            availability=1.0
        )
        
        info = spec.to_model_info()
        
        assert info.model_id == "llama-3"
        assert info.provider == "ollama"
        assert info.max_context_tokens == 8000
        assert info.available is True
    
    def test_model_spec_has_capabilities(self):
        """Test capability checking."""
        spec = ModelSpec(
            model_id="test",
            name="Test",
            provider="test",
            capabilities=["code", "reasoning", "chat"]
        )
        
        assert spec.has_capabilities(["code"]) is True
        assert spec.has_capabilities(["code", "chat"]) is True
        assert spec.has_capabilities(["code", "reasoning", "chat"]) is True
        assert spec.has_capabilities(["code", "reasoning", "chat", "vision"]) is False


class TestAgentContext:
    """Tests for AgentContext dataclass."""
    
    def test_agent_context_creation(self):
        """Test creating an AgentContext."""
        ctx = AgentContext(
            agent_type="Coder",
            task_type=TaskType.CODING,
            required_tools=["read_file", "write_file"],
            required_context=50000,
            quality_requirement=0.8,
            latency_requirement=2.0,
            cost_limit=5.0,
            privacy_required=False
        )
        
        assert ctx.agent_type == "Coder"
        assert ctx.task_type == TaskType.CODING
        assert len(ctx.required_tools) == 2
        assert ctx.required_context == 50000
        assert ctx.quality_requirement == 0.8
    
    def test_agent_context_defaults(self):
        """Test AgentContext default values."""
        ctx = AgentContext(
            agent_type="Tester",
            task_type=TaskType.TESTING
        )
        
        assert ctx.required_tools == []
        assert ctx.required_context == 0
        assert ctx.quality_requirement == 0.5
        assert ctx.latency_requirement == 1.0
        assert ctx.cost_limit == 0.0
        assert ctx.privacy_required is False


class TestTaskType:
    """Tests for TaskType enum."""
    
    def test_task_types_exist(self):
        """Test that all required task types are defined."""
        assert TaskType.CODING.value == "coding"
        assert TaskType.DEBUGGING.value == "debugging"
        assert TaskType.ARCHITECTURE.value == "architecture"
        assert TaskType.REFACTORING.value == "refactoring"
        assert TaskType.RESEARCH.value == "research"
        assert TaskType.TESTING.value == "testing"
        assert TaskType.SECURITY.value == "security"
        assert TaskType.DOCUMENTATION.value == "documentation"
        assert TaskType.FAST_TASK.value == "fast_task"
        assert TaskType.LONG_CONTEXT.value == "long_context"
        assert TaskType.REASONING.value == "reasoning"
        assert TaskType.GENERAL.value == "general"


class TestRoutingScore:
    """Tests for routing score calculation."""
    
    @pytest.fixture
    def sample_spec(self):
        """Create a sample ModelSpec for testing."""
        return ModelSpec(
            model_id="test-model",
            name="Test Model",
            provider="anthropic",
            capabilities=["code", "reasoning", "chat"],
            context_window=200000,
            quality=0.95,
            coding_score=0.92,
            availability=1.0,
            health=HealthStatus.HEALTHY,
            latency_ms=100.0,
            cost=3.0
        )
    
    def test_calculate_routing_score_balanced(self, sample_spec):
        """Test score calculation with BALANCED strategy."""
        router = ModelRouter()
        
        score = router._calculate_routing_score(
            spec=sample_spec,
            task_type=TaskType.CODING,
            required_capabilities=["code", "chat"],
            agent_context=None,
            strategy=RoutingStrategy.BALANCED
        )
        
        assert score > 0.5
    
    def test_calculate_routing_score_cost_optimized(self, sample_spec):
        """Test score calculation with COST_OPTIMIZED strategy."""
        router = ModelRouter()
        
        score = router._calculate_routing_score(
            spec=sample_spec,
            task_type=TaskType.CODING,
            required_capabilities=["code", "chat"],
            agent_context=None,
            strategy=RoutingStrategy.COST_OPTIMIZED
        )
        
        assert score > 0
    
    def test_calculate_routing_score_performance(self, sample_spec):
        """Test score calculation with PERFORMANCE strategy."""
        router = ModelRouter()
        
        score = router._calculate_routing_score(
            spec=sample_spec,
            task_type=TaskType.CODING,
            required_capabilities=["code", "chat"],
            agent_context=None,
            strategy=RoutingStrategy.PERFORMANCE
        )
        
        assert score > 0.7
    
    def test_calculate_routing_score_missing_capabilities(self, sample_spec):
        """Test score is zero when capabilities missing."""
        router = ModelRouter()
        
        score = router._calculate_routing_score(
            spec=sample_spec,
            task_type=TaskType.SECURITY,
            required_capabilities=["security", "code", "reasoning", "chat"],
            agent_context=None,
            strategy=RoutingStrategy.BALANCED
        )
        
        assert score == 0.0
    
    def test_calculate_routing_score_with_agent_context(self, sample_spec):
        """Test score adjustment with agent context."""
        router = ModelRouter()
        
        ctx = AgentContext(
            agent_type="Coder",
            task_type=TaskType.CODING,
            quality_requirement=0.9,
            latency_requirement=0.5
        )
        
        score = router._calculate_routing_score(
            spec=sample_spec,
            task_type=TaskType.CODING,
            required_capabilities=["code", "chat"],
            agent_context=ctx,
            strategy=RoutingStrategy.BALANCED
        )
        
        assert score > 0
    
    def test_calculate_routing_score_quality_penalty(self, sample_spec):
        """Test score penalty when quality requirement not met."""
        router = ModelRouter()
        
        ctx = AgentContext(
            agent_type="Architect",
            task_type=TaskType.ARCHITECTURE,
            quality_requirement=0.99
        )
        
        score_with_penalty = router._calculate_routing_score(
            spec=sample_spec,
            task_type=TaskType.ARCHITECTURE,
            required_capabilities=["reasoning", "chat"],
            agent_context=ctx,
            strategy=RoutingStrategy.BALANCED
        )
        
        score_without_penalty = router._calculate_routing_score(
            spec=sample_spec,
            task_type=TaskType.ARCHITECTURE,
            required_capabilities=["reasoning", "chat"],
            agent_context=None,
            strategy=RoutingStrategy.BALANCED
        )
        
        assert score_with_penalty < score_without_penalty


class TestGetCapabilitiesForTask:
    """Tests for capability mapping."""
    
    def test_coding_capabilities(self):
        """Test capabilities required for CODING task."""
        router = ModelRouter()
        caps = router._get_capabilities_for_task(TaskType.CODING)
        
        assert "code" in caps
        assert "chat" in caps
    
    def test_debugging_capabilities(self):
        """Test capabilities required for DEBUGGING task."""
        router = ModelRouter()
        caps = router._get_capabilities_for_task(TaskType.DEBUGGING)
        
        assert "code" in caps
        assert "reasoning" in caps
        assert "chat" in caps
    
    def test_security_capabilities(self):
        """Test capabilities required for SECURITY task."""
        router = ModelRouter()
        caps = router._get_capabilities_for_task(TaskType.SECURITY)
        
        assert "security" in caps
        assert "code" in caps
        assert "reasoning" in caps
        assert "chat" in caps
    
    def test_general_capabilities(self):
        """Test capabilities required for GENERAL task."""
        router = ModelRouter()
        caps = router._get_capabilities_for_task(TaskType.GENERAL)
        
        assert caps == ["chat"]


class TestEnrichModelSpec:
    """Tests for model spec enrichment."""
    
    def test_enrich_anthropic_spec(self):
        """Test enrichment for Anthropic provider."""
        router = ModelRouter()
        spec = ModelSpec(
            model_id="claude-test",
            name="Claude Test",
            provider="anthropic",
            capabilities=["code", "chat"]
        )
        
        enriched = router._enrich_model_spec(spec, "anthropic", TaskType.CODING)
        
        assert enriched.quality == 0.95
        assert enriched.reasoning_level == "advanced"
        assert enriched.coding_score >= 0.92
    
    def test_enrich_ollama_spec(self):
        """Test enrichment for Ollama provider."""
        router = ModelRouter()
        spec = ModelSpec(
            model_id="llama-test",
            name="Llama Test",
            provider="ollama",
            capabilities=["chat"]
        )
        
        enriched = router._enrich_model_spec(spec, "ollama", TaskType.GENERAL)
        
        assert enriched.quality == 0.70
        assert enriched.reasoning_level == "basic"
        assert enriched.coding_score == 0.65
    
    def test_enrich_coding_boost(self):
        """Test coding score boost for coding tasks."""
        router = ModelRouter()
        spec = ModelSpec(
            model_id="test",
            name="Test",
            provider="anthropic",
            capabilities=["code", "chat"],
            coding_score=0.92
        )
        
        enriched = router._enrich_model_spec(spec, "anthropic", TaskType.CODING)
        
        assert enriched.coding_score == min(1.0, 0.92 + 0.1)


class TestModelRouterIntegration:
    """Integration tests for ModelRouter."""
    
    def test_router_singleton(self):
        """Test that ModelRouter is a singleton."""
        router1 = ModelRouter()
        router2 = ModelRouter()
        
        assert router1 is router2
    
    def test_router_initialization(self):
        """Test router initialization."""
        router = ModelRouter()
        router.initialize()
    
    @pytest.mark.asyncio
    async def test_select_for_task_no_models(self):
        """Test select_for_task when no models are available."""
        router = ModelRouter()
        router._discovered_models = {}
        
        result = await router.select_for_task(
            task_type=TaskType.CODING
        )
        
        assert result.success is False
        assert "No models available" in result.error
    
    @pytest.mark.asyncio
    async def test_select_for_task_with_mock_models(self):
        """Test select_for_task with mock discovered models."""
        router = ModelRouter()
        
        router._discovered_models = {
            "anthropic": [
                ModelInfo(
                    model_id="claude-sonnet",
                    name="Claude Sonnet",
                    provider="anthropic",
                    capabilities=["code", "reasoning", "chat"],
                    max_context_tokens=200000,
                    cost_per_token=3.0,
                    available=True
                )
            ],
            "ollama": [
                ModelInfo(
                    model_id="llama-3",
                    name="Llama 3",
                    provider="ollama",
                    capabilities=["chat"],
                    max_context_tokens=8000,
                    cost_per_token=0.0,
                    available=True
                )
            ]
        }
        
        result = await router.select_for_task(
            task_type=TaskType.CODING,
            strategy=RoutingStrategy.PERFORMANCE
        )
        
        assert result.success is True
        assert result.selected_model is not None
        assert result.provider_used in ["anthropic", "ollama"]
    
    @pytest.mark.asyncio
    async def test_select_for_task_privacy_requirement(self):
        """Test select_for_task with privacy requirement."""
        router = ModelRouter()
        
        router._discovered_models = {
            "anthropic": [
                ModelInfo(
                    model_id="claude-sonnet",
                    name="Claude Sonnet",
                    provider="anthropic",
                    capabilities=["code", "chat"],
                    max_context_tokens=200000,
                    cost_per_token=3.0,
                    available=True
                )
            ],
            "ollama": [
                ModelInfo(
                    model_id="llama-3",
                    name="Llama 3",
                    provider="ollama",
                    capabilities=["chat", "code"],
                    max_context_tokens=8000,
                    cost_per_token=0.0,
                    available=True
                )
            ]
        }
        
        ctx = AgentContext(
            agent_type="Coder",
            task_type=TaskType.CODING,
            privacy_required=True
        )
        
        result = await router.select_for_task(
            task_type=TaskType.CODING,
            agent_context=ctx
        )
        
        assert result.success is True
        assert result.selected_model is not None
        assert result.provider_used == "ollama"
