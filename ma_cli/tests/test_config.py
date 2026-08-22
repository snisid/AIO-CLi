"""Tests for configuration engine."""

import tempfile
from pathlib import Path

import pytest

from ma_cli.config.engine import (
    Config,
    ConfigurationEngine,
    ConfigurationError,
    ModelAlias,
    ProviderConfig,
    RuntimeConfig,
)
from ma_cli.core.models import AutonomyLevel


class TestConfigurationEngine:
    """Tests for ConfigurationEngine."""
    
    def test_create_default_config(self):
        """Test creating default configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            engine = ConfigurationEngine(config_path)
            
            config = engine.load()
            
            assert config.version == 1
            assert config.runtime.autonomy_level == AutonomyLevel.SUPERVISED_AUTO
            assert len(config.providers) > 0
            assert "ollama" in config.providers
            assert "omniroute" in config.providers
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            engine = ConfigurationEngine(config_path)
            
            # Create custom config
            config = Config(
                version=1,
                runtime=RuntimeConfig(
                    autonomy_level=AutonomyLevel.ASSIST,
                    default_agent="custom",
                    max_concurrent_tasks=10
                ),
                providers={
                    "test": ProviderConfig(
                        type="openai-compatible",
                        base_url="http://test.local/v1"
                    )
                }
            )
            
            engine.save(config)
            
            # Load it back
            loaded = engine.load()
            
            assert loaded.runtime.default_agent == "custom"
            assert loaded.runtime.max_concurrent_tasks == 10
            assert "test" in loaded.providers
            assert loaded.providers["test"].base_url == "http://test.local/v1"
    
    def test_get_provider(self):
        """Test getting provider configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            engine = ConfigurationEngine(config_path)
            
            config = engine.load()
            
            ollama = engine.get_provider("ollama")
            assert ollama is not None
            assert ollama.type == "openai-compatible"
            
            nonexistent = engine.get_provider("nonexistent")
            assert nonexistent is None
    
    def test_add_provider(self):
        """Test adding a provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            engine = ConfigurationEngine(config_path)
            
            new_provider = ProviderConfig(
                type="anthropic",
                enabled=True,
                api_key="test-key"
            )
            
            engine.add_provider("anthropic", new_provider)
            
            config = engine.get()
            assert "anthropic" in config.providers
            assert config.providers["anthropic"].type == "anthropic"
    
    def test_remove_provider(self):
        """Test removing a provider."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            engine = ConfigurationEngine(config_path)
            
            # Add then remove
            provider = ProviderConfig(type="test")
            engine.add_provider("temp", provider)
            
            result = engine.remove_provider("temp")
            assert result is True
            
            config = engine.get()
            assert "temp" not in config.providers
            
            # Remove non-existent
            result = engine.remove_provider("nonexistent")
            assert result is False
    
    def test_validate_config(self):
        """Test configuration validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            engine = ConfigurationEngine(config_path)
            
            config = engine.load()
            warnings = engine.validate()
            
            # Should have some warnings about unconfigured providers
            assert isinstance(warnings, list)
    
    def test_model_aliases(self):
        """Test model alias management."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            engine = ConfigurationEngine(config_path)
            
            alias = ModelAlias(provider="ollama", model_id="qwen-3.8")
            engine.add_model_alias("my-model", alias)
            
            loaded = engine.get_model_alias("my-model")
            assert loaded is not None
            assert loaded.provider == "ollama"
            assert loaded.model_id == "qwen-3.8"
    
    def test_update_runtime(self):
        """Test updating runtime configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            engine = ConfigurationEngine(config_path)
            
            engine.update_runtime(
                sandbox_enabled=False,
                audit_logging=False
            )
            
            config = engine.get()
            assert config.runtime.sandbox_enabled is False
            assert config.runtime.audit_logging is False
    
    def test_invalid_yaml_raises_error(self):
        """Test that invalid YAML raises ConfigurationError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            
            # Write invalid YAML
            config_path.write_text("invalid: yaml: content: [")
            
            engine = ConfigurationEngine(config_path)
            
            with pytest.raises(ConfigurationError):
                engine.load()
