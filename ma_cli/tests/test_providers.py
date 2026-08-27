"""
Provider Integration Tests for MA-CLI.

Tests for all provider implementations:
- Ollama
- OpenAI
- Anthropic
- OmniRoute
- 9router

Test categories:
- Unit tests (mocked HTTP)
- Integration tests (real provider behavior with mocks)
- Live tests (opt-in, require real API keys - NEVER run in CI)
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ma_cli.core.models import HealthStatus
from ma_cli.providers.base import ChatMessage, ChatResponse, ModelInfo, ProviderConfig
from ma_cli.providers.circuit_breaker import (
    CircuitBreaker,
    CircuitConfig,
    CircuitOpenError,
    CircuitState,
)
from ma_cli.providers.implementations import (
    AnthropicProvider,
    GenericOpenAICompatibleProvider,
    NineRouterProvider,
    OllamaProvider,
    OmniRouteProvider,
    OpenAIProvider,
    ProviderRegistry,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def ollama_config():
    """Ollama provider configuration."""
    return ProviderConfig(
        name="ollama",
        type="openai-compatible",
        enabled=True,
        base_url="http://localhost:11434",
        timeout=30,
    )


@pytest.fixture
def openai_config():
    """OpenAI provider configuration."""
    return ProviderConfig(
        name="openai",
        type="openai-compatible",
        enabled=True,
        base_url="https://api.openai.com/v1",
        api_key="sk-test-key-for-testing-only",
        timeout=60,
    )


@pytest.fixture
def anthropic_config():
    """Anthropic provider configuration."""
    return ProviderConfig(
        name="anthropic",
        type="anthropic",
        enabled=True,
        base_url="https://api.anthropic.com",
        api_key="sk-ant-test-key-for-testing-only",
        timeout=60,
    )


@pytest.fixture
def omniroute_config():
    """OmniRoute provider configuration."""
    return ProviderConfig(
        name="omniroute",
        type="openai-compatible",
        enabled=True,
        base_url="http://localhost:20128/v1",
        api_key="test-key",
        timeout=30,
    )


@pytest.fixture
def ninerouter_config():
    """9router provider configuration."""
    return ProviderConfig(
        name="9router",
        type="openai-compatible",
        enabled=True,
        base_url="http://localhost:9000/v1",
        timeout=30,
    )


@pytest.fixture
def sample_messages():
    """Sample chat messages for testing."""
    return [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="Hello, how are you?"),
    ]


@pytest.fixture
def mock_http_response():
    """Create a mock HTTP response."""

    def _create_response(status_code=200, json_data=None):
        response = MagicMock(spec=httpx.Response)
        response.status_code = status_code
        response.json.return_value = json_data or {}
        response.raise_for_status = MagicMock()
        if status_code >= 400:
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                f"HTTP {status_code}", request=MagicMock(), response=response
            )
        return response

    return _create_response


# ============================================================================
# Unit Tests - Ollama Provider
# ============================================================================


class TestOllamaProvider:
    """Unit tests for OllamaProvider."""

    def test_provider_initialization(self, ollama_config):
        """Test OllamaProvider initialization."""
        provider = OllamaProvider(ollama_config)
        assert provider.name == "ollama"
        assert provider.type == "openai-compatible"
        assert provider.base_url == "http://localhost:11434"
        assert provider.enabled is True

    def test_provider_disabled(self):
        """Test OllamaProvider when disabled."""
        config = ProviderConfig(name="ollama", type="openai-compatible", enabled=False)
        provider = OllamaProvider(config)
        assert provider.enabled is False

    @pytest.mark.asyncio
    async def test_discover_models_success(self, ollama_config, mock_http_response):
        """Test model discovery from Ollama."""
        provider = OllamaProvider(ollama_config)

        mock_data = {
            "models": [
                {
                    "name": "llama3.2",
                    "details": {"family": "llama", "context_length": 8192},
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_http_response(200, mock_data))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            models = await provider.discover_models()

            assert len(models) == 1
            assert models[0].model_id == "llama3.2"
            assert models[0].provider == "ollama"
            assert "chat" in models[0].capabilities

    @pytest.mark.asyncio
    async def test_discover_models_connection_error(self, ollama_config):
        """Test model discovery when Ollama is unreachable."""
        provider = OllamaProvider(ollama_config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            models = await provider.discover_models()
            assert models == []

    @pytest.mark.asyncio
    async def test_chat_completion(self, ollama_config, sample_messages, mock_http_response):
        """Test chat completion with Ollama."""
        provider = OllamaProvider(ollama_config)

        mock_data = {
            "choices": [{"message": {"content": "Hello! How can I help you?"}, "finish_reason": "stop"}],
            "model": "llama3.2",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, mock_data))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            response = await provider.chat(sample_messages, "llama3.2")

            assert isinstance(response, ChatResponse)
            assert response.content == "Hello! How can I help you?"
            assert response.model == "llama3.2"
            assert response.usage == {"prompt_tokens": 10, "completion_tokens": 20}

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, ollama_config, mock_http_response):
        """Test health check when Ollama is healthy."""
        provider = OllamaProvider(ollama_config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_http_response(200, {"models": []}))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            status = await provider.health_check()
            assert status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, ollama_config):
        """Test health check when Ollama is unreachable."""
        provider = OllamaProvider(ollama_config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            status = await provider.health_check()
            assert status == HealthStatus.UNHEALTHY


# ============================================================================
# Unit Tests - OpenAI Provider
# ============================================================================


class TestOpenAIProvider:
    """Unit tests for OpenAIProvider."""

    def test_provider_initialization(self, openai_config):
        """Test OpenAIProvider initialization."""
        provider = OpenAIProvider(openai_config)
        assert provider.name == "openai"
        assert provider.type == "openai-compatible"
        assert provider.base_url == "https://api.openai.com/v1"
        assert provider.enabled is True

    def test_provider_no_api_key(self):
        """Test OpenAIProvider without API key."""
        config = ProviderConfig(name="openai", type="openai-compatible", enabled=True, api_key=None)
        provider = OpenAIProvider(config)
        assert provider.enabled is False

    @pytest.mark.asyncio
    async def test_discover_models_success(self, openai_config, mock_http_response):
        """Test model discovery from OpenAI."""
        provider = OpenAIProvider(openai_config)

        mock_data = {
            "data": [
                {"id": "gpt-4o", "object": "model"},
                {"id": "gpt-4o-mini", "object": "model"},
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_http_response(200, mock_data))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            models = await provider.discover_models()

            assert len(models) >= 2
            model_ids = [m.model_id for m in models]
            assert "gpt-4o" in model_ids
            assert "gpt-4o-mini" in model_ids

    @pytest.mark.asyncio
    async def test_chat_completion(self, openai_config, sample_messages, mock_http_response):
        """Test chat completion with OpenAI."""
        provider = OpenAIProvider(openai_config)

        mock_data = {
            "choices": [{"message": {"content": "I'm doing well, thank you!"}, "finish_reason": "stop"}],
            "model": "gpt-4o",
            "usage": {"prompt_tokens": 15, "completion_tokens": 25},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, mock_data))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            response = await provider.chat(sample_messages, "gpt-4o")

            assert isinstance(response, ChatResponse)
            assert response.content == "I'm doing well, thank you!"
            assert response.model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_health_check_no_api_key(self, openai_config):
        """Test health check without API key."""
        config = ProviderConfig(name="openai", type="openai-compatible", enabled=True, api_key=None)
        provider = OpenAIProvider(config)
        status = await provider.health_check()
        assert status == HealthStatus.UNHEALTHY


# ============================================================================
# Unit Tests - Anthropic Provider
# ============================================================================


class TestAnthropicProvider:
    """Unit tests for AnthropicProvider."""

    def test_provider_initialization(self, anthropic_config):
        """Test AnthropicProvider initialization."""
        provider = AnthropicProvider(anthropic_config)
        assert provider.name == "anthropic"
        assert provider.type == "anthropic"
        assert provider.base_url == "https://api.anthropic.com"
        assert provider.enabled is True

    def test_provider_no_api_key(self):
        """Test AnthropicProvider without API key."""
        config = ProviderConfig(name="anthropic", type="anthropic", enabled=True, api_key=None)
        provider = AnthropicProvider(config)
        assert provider.enabled is False

    @pytest.mark.asyncio
    async def test_discover_models_returns_known_models(self, anthropic_config):
        """Test that Anthropic provider returns known Claude models."""
        provider = AnthropicProvider(anthropic_config)
        models = await provider.discover_models()

        assert len(models) >= 4
        model_ids = [m.model_id for m in models]
        assert any("claude-sonnet" in mid for mid in model_ids)
        assert any("claude-opus" in mid for mid in model_ids)
        assert any("claude-3-5-sonnet" in mid for mid in model_ids)

    @pytest.mark.asyncio
    async def test_chat_completion(self, anthropic_config, sample_messages, mock_http_response):
        """Test chat completion with Anthropic."""
        provider = AnthropicProvider(anthropic_config)

        mock_data = {
            "content": [{"type": "text", "text": "Hello! I'm Claude."}],
            "model": "claude-3-5-sonnet-20241022",
            "usage": {"input_tokens": 12, "output_tokens": 18},
            "stop_reason": "end_turn",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, mock_data))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            response = await provider.chat(sample_messages, "claude-3-5-sonnet-20241022")

            assert isinstance(response, ChatResponse)
            assert response.content == "Hello! I'm Claude."
            assert response.model == "claude-3-5-sonnet-20241022"
            assert response.finish_reason == "end_turn"

    @pytest.mark.asyncio
    async def test_chat_handles_system_message(self, anthropic_config, mock_http_response):
        """Test that system messages are handled correctly."""
        provider = AnthropicProvider(anthropic_config)
        messages = [
            ChatMessage(role="system", content="You are a coding assistant."),
            ChatMessage(role="user", content="Write a function."),
        ]

        mock_data = {
            "content": [{"type": "text", "text": "def hello(): pass"}],
            "model": "claude-3-5-sonnet-20241022",
            "stop_reason": "end_turn",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def check_payload(*args, **kwargs):
                # Verify system message was extracted
                payload = kwargs.get("json", {})
                assert "system" in payload
                assert payload["system"] == "You are a coding assistant."
                return mock_http_response(200, mock_data)

            mock_client.post = AsyncMock(side_effect=check_payload)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            response = await provider.chat(messages, "claude-3-5-sonnet-20241022")
            assert response.content == "def hello(): pass"


# ============================================================================
# Unit Tests - OmniRoute Provider
# ============================================================================


class TestOmniRouteProvider:
    """Unit tests for OmniRouteProvider."""

    def test_provider_initialization(self, omniroute_config):
        """Test OmniRouteProvider initialization."""
        provider = OmniRouteProvider(omniroute_config)
        assert provider.name == "omniroute"
        assert provider.type == "openai-compatible"
        assert provider.base_url == "http://localhost:20128/v1"
        assert provider.enabled is True

    @pytest.mark.asyncio
    async def test_discover_models_with_routing_info(self, omniroute_config, mock_http_response):
        """Test model discovery with routing information."""
        provider = OmniRouteProvider(omniroute_config)

        mock_data = {
            "models": [
                {
                    "id": "gpt-4o-via-omniroute",
                    "name": "GPT-4o",
                    "capabilities": ["chat", "code"],
                    "cost_per_token": 0.000005,
                    "available": True,
                }
            ],
            "routing": {"strategy": "cost_optimized"},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_http_response(200, mock_data))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            models = await provider.discover_models()

            assert len(models) == 1
            assert models[0].model_id == "gpt-4o-via-omniroute"
            assert models[0].cost_per_token == 0.000005
            assert provider._routing_info == {"strategy": "cost_optimized"}

    @pytest.mark.asyncio
    async def test_chat_with_routing_hints(self, omniroute_config, sample_messages, mock_http_response):
        """Test chat completion with routing hints."""
        provider = OmniRouteProvider(omniroute_config)

        mock_data = {
            "choices": [{"message": {"content": "Response via OmniRoute"}, "finish_reason": "stop"}],
            "model": "gpt-4o-via-omniroute",
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def check_payload(*args, **kwargs):
                payload = kwargs.get("json", {})
                assert "routing_strategy" in payload
                assert payload["routing_strategy"] == "performance"
                assert "max_cost" in payload
                assert payload["max_cost"] == 0.0001
                return mock_http_response(200, mock_data)

            mock_client.post = AsyncMock(side_effect=check_payload)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            response = await provider.chat(
                sample_messages,
                "gpt-4o-via-omniroute",
                routing_strategy="performance",
                max_cost=0.0001,
            )

            assert response.content == "Response via OmniRoute"


# ============================================================================
# Unit Tests - 9router Provider
# ============================================================================


class TestNineRouterProvider:
    """Unit tests for NineRouterProvider."""

    def test_provider_initialization(self, ninerouter_config):
        """Test NineRouterProvider initialization."""
        provider = NineRouterProvider(ninerouter_config)
        assert provider.name == "9router"
        assert provider.type == "openai-compatible"
        assert provider.base_url == "http://localhost:9000/v1"
        assert provider.enabled is True

    @pytest.mark.asyncio
    async def test_discover_models_cost_optimized(self, ninerouter_config, mock_http_response):
        """Test model discovery from 9router with cost info."""
        provider = NineRouterProvider(ninerouter_config)

        mock_data = {
            "models": [
                {
                    "id": "claude-sonnet-4",
                    "name": "Claude Sonnet 4",
                    "cost_per_token": 0.000003,
                    "available": True,
                },
                {
                    "id": "gpt-4o-mini",
                    "name": "GPT-4o Mini",
                    "cost_per_token": 0.000001,
                    "available": True,
                },
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_http_response(200, mock_data))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            models = await provider.discover_models()

            assert len(models) == 2
            # Models should have cost information
            costs = {m.model_id: m.cost_per_token for m in models}
            assert costs["claude-sonnet-4"] == 0.000003
            assert costs["gpt-4o-mini"] == 0.000001


# ============================================================================
# Unit Tests - Generic OpenAI-Compatible Provider
# ============================================================================


class TestGenericOpenAICompatibleProvider:
    """Unit tests for GenericOpenAICompatibleProvider."""

    def test_provider_custom_name(self):
        """Test generic provider with custom configuration."""
        config = ProviderConfig(
            name="custom-provider",
            type="openai-compatible",
            enabled=True,
            base_url="http://custom.local/v1",
            api_key="custom-key",
        )
        provider = GenericOpenAICompatibleProvider(config)
        assert provider.name == "custom-provider"
        assert provider.type == "openai-compatible"
        assert provider.base_url == "http://custom.local/v1"

    @pytest.mark.asyncio
    async def test_chat_with_custom_headers(self, mock_http_response):
        """Test chat completion with custom headers."""
        config = ProviderConfig(
            name="custom",
            type="openai-compatible",
            enabled=True,
            base_url="http://custom.local/v1",
            api_key="test-key",
            headers={"X-Custom-Header": "custom-value"},
        )
        provider = GenericOpenAICompatibleProvider(config)

        mock_data = {"choices": [{"message": {"content": "Custom response"}}]}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def check_headers(*args, **kwargs):
                headers = kwargs.get("headers", {})
                assert "Authorization" in headers
                assert headers["Authorization"] == "Bearer test-key"
                assert headers["X-Custom-Header"] == "custom-value"
                return mock_http_response(200, mock_data)

            mock_client.post = AsyncMock(side_effect=check_headers)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            messages = [ChatMessage(role="user", content="Test")]
            response = await provider.chat(messages, "custom-model")
            assert response.content == "Custom response"


# ============================================================================
# Circuit Breaker Integration Tests
# ============================================================================


class TestProviderCircuitBreakerIntegration:
    """Test circuit breaker integration with providers."""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self, ollama_config):
        """Test that circuit opens after consecutive failures."""
        provider = OllamaProvider(ollama_config)

        # Configure circuit breaker for faster testing
        provider.circuit_breaker.config.failure_threshold = 3

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Cause failures
            messages = [ChatMessage(role="user", content="Test")]
            for _ in range(3):
                try:
                    await provider.safe_chat(messages, "llama3.2")
                except Exception:
                    pass

            # Circuit should be open now
            assert provider.circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_rejects_when_open(self, ollama_config):
        """Test that requests are rejected when circuit is open."""
        provider = OllamaProvider(ollama_config)
        provider.circuit_breaker._state = CircuitState.OPEN
        provider.circuit_breaker._opened_at = None  # Prevent auto-reset

        messages = [ChatMessage(role="user", content="Test")]

        with pytest.raises(CircuitOpenError):
            await provider.safe_chat(messages, "llama3.2")

    @pytest.mark.asyncio
    async def test_circuit_recovers_after_successes(self, ollama_config, mock_http_response):
        """Test that circuit closes after successful requests."""
        provider = OllamaProvider(ollama_config)
        provider.circuit_breaker.config.success_threshold = 2
        provider.circuit_breaker._state = CircuitState.HALF_OPEN

        mock_data = {"choices": [{"message": {"content": "OK"}}]}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_http_response(200, mock_data))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            messages = [ChatMessage(role="user", content="Test")]

            # Successful requests
            for _ in range(2):
                await provider.safe_chat(messages, "llama3.2")

            # Circuit should be closed now
            assert provider.circuit_breaker.state == CircuitState.CLOSED


# ============================================================================
# Provider Registry Tests
# ============================================================================


class TestProviderRegistry:
    """Tests for ProviderRegistry."""

    def teardown_method(self):
        """Reset registry between tests."""
        ProviderRegistry._instance = None

    def test_registry_singleton(self):
        """Test that registry is a singleton."""
        registry1 = ProviderRegistry()
        registry2 = ProviderRegistry()
        assert registry1 is registry2

    def test_registry_initialization(self):
        """Test registry initialization with config."""
        from unittest.mock import Mock

        mock_config = Mock()
        mock_config.providers = {
            "ollama": ProviderConfig(name="ollama", type="openai-compatible", enabled=True),
            "openai": ProviderConfig(
                name="openai", type="openai-compatible", enabled=True, api_key="test"
            ),
        }

        registry = ProviderRegistry()
        registry.initialize(mock_config)

        assert registry.get("ollama") is not None
        assert registry.get("openai") is not None
        assert registry.get("nonexistent") is None

    def test_list_all_providers(self):
        """Test listing all registered providers."""
        from unittest.mock import Mock

        mock_config = Mock()
        mock_config.providers = {
            "ollama": ProviderConfig(name="ollama", type="openai-compatible", enabled=True),
        }

        registry = ProviderRegistry()
        registry.initialize(mock_config)

        all_providers = registry.list_all()
        assert len(all_providers) == 1
        assert all_providers[0].name == "ollama"

    def test_get_enabled_providers(self):
        """Test getting only enabled providers."""
        from unittest.mock import Mock

        mock_config = Mock()
        mock_config.providers = {
            "ollama": ProviderConfig(name="ollama", type="openai-compatible", enabled=True),
            "openai": ProviderConfig(
                name="openai", type="openai-compatible", enabled=False, api_key="test"
            ),
        }

        registry = ProviderRegistry()
        registry.initialize(mock_config)

        enabled = registry.get_enabled()
        assert len(enabled) == 1
        assert enabled[0].name == "ollama"


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestProviderErrorHandling:
    """Test error handling across providers."""

    @pytest.mark.asyncio
    async def test_timeout_handling(self, ollama_config):
        """Test that timeouts are handled correctly."""
        provider = OllamaProvider(ollama_config)
        provider._config.timeout = 1

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timed out"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            messages = [ChatMessage(role="user", content="Test")]

            with pytest.raises(httpx.TimeoutException):
                await provider.chat(messages, "llama3.2")

    @pytest.mark.asyncio
    async def test_http_error_handling(self, ollama_config):
        """Test HTTP error handling."""
        provider = OllamaProvider(ollama_config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Internal Server Error", request=MagicMock(), response=mock_response
            )

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            messages = [ChatMessage(role="user", content="Test")]

            with pytest.raises(httpx.HTTPStatusError):
                await provider.chat(messages, "llama3.2")

    @pytest.mark.asyncio
    async def test_malformed_response_handling(self, ollama_config):
        """Test handling of malformed JSON responses."""
        provider = OllamaProvider(ollama_config)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            messages = [ChatMessage(role="user", content="Test")]

            with pytest.raises(ValueError):
                await provider.chat(messages, "llama3.2")


# ============================================================================
# Live Provider Tests (OPT-IN ONLY - NEVER RUN IN CI)
# ============================================================================


@pytest.mark.skipif(
    not os.environ.get("MA_CLI_LIVE_PROVIDER_TESTS"),
    reason="Live provider tests require MA_CLI_LIVE_PROVIDER_TESTS=1",
)
class TestLiveProviders:
    """
    Live provider tests.

    These tests make real API calls and require valid credentials.
    NEVER run these in CI/CD pipelines.
    Only run locally with proper environment variables set.

    Required environment variables:
    - MA_CLI_LIVE_PROVIDER_TESTS=1 (to enable)
    - OPENAI_API_KEY (for OpenAI tests)
    - ANTHROPIC_API_KEY (for Anthropic tests)
    """

    @pytest.mark.asyncio
    async def test_live_openai_chat(self):
        """Test live OpenAI API call."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set")

        config = ProviderConfig(
            name="openai",
            type="openai-compatible",
            enabled=True,
            base_url="https://api.openai.com/v1",
            api_key=api_key,
            timeout=30,
        )
        provider = OpenAIProvider(config)

        messages = [ChatMessage(role="user", content="Say 'hello' in one word.")]
        response = await provider.chat(messages, "gpt-4o-mini")

        assert response.content
        assert len(response.content.strip()) > 0

    @pytest.mark.asyncio
    async def test_live_anthropic_chat(self):
        """Test live Anthropic API call."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY not set")

        config = ProviderConfig(
            name="anthropic",
            type="anthropic",
            enabled=True,
            base_url="https://api.anthropic.com",
            api_key=api_key,
            timeout=30,
        )
        provider = AnthropicProvider(config)

        messages = [ChatMessage(role="user", content="Say 'hello' in one word.")]
        response = await provider.chat(messages, "claude-3-5-haiku-20241022")

        assert response.content
        assert len(response.content.strip()) > 0

    @pytest.mark.asyncio
    async def test_live_ollama_chat(self):
        """Test live Ollama API call (local)."""
        config = ProviderConfig(
            name="ollama",
            type="openai-compatible",
            enabled=True,
            base_url="http://localhost:11434",
            timeout=30,
        )
        provider = OllamaProvider(config)

        # Check if Ollama is running
        health = await provider.health_check()
        if health != HealthStatus.HEALTHY:
            pytest.skip("Ollama not running locally")

        messages = [ChatMessage(role="user", content="Say 'hello' in one word.")]
        response = await provider.chat(messages, "llama3.2")

        assert response.content
        assert len(response.content.strip()) > 0
