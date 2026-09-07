from ma_cli.providers.base import ProviderConfig
from ma_cli.providers.openrouter import OpenRouterProvider


def test_openrouter_defaults_to_official_api_endpoint(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    provider = OpenRouterProvider(ProviderConfig(name="openrouter", type="openai-compatible"))
    assert provider.base_url == "https://openrouter.ai/api/v1"
    assert provider.enabled is True
    assert provider.name == "openrouter"


def test_openrouter_custom_endpoint_is_preserved(monkeypatch):
    provider = OpenRouterProvider(
        ProviderConfig(
            name="openrouter",
            type="openai-compatible",
            base_url="http://gateway.test/v1",
            api_key="test-key",
        )
    )
    assert provider.base_url == "http://gateway.test/v1"
    assert provider.enabled is True
