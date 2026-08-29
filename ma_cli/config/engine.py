"""
Configuration Engine for MA-CLI.

This module handles loading, validating, and managing MA-CLI configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..core.models import AutonomyLevel


@dataclass
class MCPAuthConfig:
    """MCP authentication configuration."""

    type: str = "none"  # none, bearer, api_key
    token_env: str | None = None
    api_key_env: str | None = None


@dataclass
class MCPServerConfig:
    """Configuration for a single MCP server."""

    transport: str = "stdio"  # stdio, streamable_http
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    auth: MCPAuthConfig | None = None
    enabled: bool = True
    timeout: int = 30
    max_retries: int = 3


@dataclass
class MCPConfig:
    """MCP subsystem configuration."""

    enabled: bool = True
    servers: dict[str, MCPServerConfig] = field(default_factory=dict)


@dataclass
class ProviderConfig:
    """Configuration for a single provider."""

    type: str = "openai-compatible"
    enabled: bool = True
    base_url: str = ""
    api_key: str | None = None
    timeout: int = 60
    retry_count: int = 3
    headers: dict[str, str] = field(default_factory=dict)
    mcp: MCPConfig | None = None


@dataclass
class ModelAlias:
    """Model alias configuration."""

    provider: str
    model_id: str | None = None  # None means auto-discover
    fallback: str | None = None


@dataclass
class RuntimeConfig:
    """Runtime configuration settings."""

    autonomy_level: AutonomyLevel = AutonomyLevel.SUPERVISED_AUTO
    default_agent: str = "native"
    default_provider: str = "omniroute"
    workspace_path: str | None = None
    sandbox_enabled: bool = True
    audit_logging: bool = True
    max_concurrent_tasks: int = 5


@dataclass
class Config:
    """Main configuration container."""

    version: int = 1
    runtime: RuntimeConfig = None
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    models: dict[str, ModelAlias] = field(default_factory=dict)

    def __post_init__(self):
        if self.runtime is None:
            self.runtime = RuntimeConfig()


class ConfigurationError(Exception):
    """Configuration-related error."""


class ConfigurationEngine:
    """
    Configuration management engine.

    Handles loading, saving, and validating MA-CLI configuration.
    """

    DEFAULT_CONFIG_PATH = Path.home() / ".ma-cli" / "config.yaml"

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config: Config | None = None

    def load(self) -> Config:
        """
        Load configuration from file.

        Returns:
            Config object with loaded settings

        Raises:
            ConfigurationError: If config file is invalid
        """
        if not self.config_path.exists():
            return self._create_default_config()

        try:
            with open(self.config_path) as f:
                data = yaml.safe_load(f)

            if data is None:
                return self._create_default_config()

            self._config = self._parse_config(data)
            return self._config

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in config file: {e}") from e
        except Exception as e:
            raise ConfigurationError(f"Failed to load config: {e}") from e

    def save(self, config: Config | None = None) -> None:
        """
        Save configuration to file.

        Args:
            config: Config to save (uses current config if None)
        """
        if config is None:
            config = self._config

        if config is None:
            config = self._create_default_config()

        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        data = self._serialize_config(config)

        with open(self.config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def get(self) -> Config:
        """Get current configuration, loading if necessary."""
        if self._config is None:
            return self.load()
        return self._config

    def get_provider(self, name: str) -> ProviderConfig | None:
        """Get provider configuration by name."""
        config = self.get()
        return config.providers.get(name)

    def get_model_alias(self, alias: str) -> ModelAlias | None:
        """Get model alias configuration."""
        config = self.get()
        return config.models.get(alias)

    def update_runtime(self, **kwargs) -> RuntimeConfig:
        """Update runtime configuration."""
        config = self.get()
        for key, value in kwargs.items():
            if hasattr(config.runtime, key):
                setattr(config.runtime, key, value)
        self.save()
        return config.runtime

    def add_provider(self, name: str, provider_config: ProviderConfig) -> None:
        """Add or update a provider configuration."""
        config = self.get()
        config.providers[name] = provider_config
        self.save()

    def remove_provider(self, name: str) -> bool:
        """Remove a provider configuration."""
        config = self.get()
        if name in config.providers:
            del config.providers[name]
            self.save()
            return True
        return False

    def add_model_alias(self, alias: str, model_alias: ModelAlias) -> None:
        """Add or update a model alias."""
        config = self.get()
        config.models[alias] = model_alias
        self.save()

    def validate(self) -> list[str]:
        """
        Validate current configuration.

        Returns:
            List of validation warnings/errors
        """
        warnings = []
        config = self.get()

        # Check runtime config
        if config.runtime.autonomy_level not in AutonomyLevel:
            warnings.append(f"Invalid autonomy level: {config.runtime.autonomy_level}")

        # Check providers
        for name, provider in config.providers.items():
            if provider.enabled and not provider.base_url and provider.type != "anthropic":
                warnings.append(f"Provider '{name}' is enabled but has no base_url")

        # Check model aliases
        for alias, model in config.models.items():
            if model.provider not in config.providers:
                warnings.append(
                    f"Model alias '{alias}' references unknown provider '{model.provider}'"
                )

        return warnings

    def _create_default_config(self) -> Config:
        """Create default configuration."""
        config = Config(
            version=1,
            runtime=RuntimeConfig(),
            providers={
                "ollama": ProviderConfig(
                    type="openai-compatible", enabled=True, base_url="http://localhost:11434/v1"
                ),
                "omniroute": ProviderConfig(
                    type="openai-compatible", enabled=True, base_url="http://localhost:20128/v1"
                ),
                "9router": ProviderConfig(
                    type="openai-compatible", enabled=True, base_url="http://localhost:9090/v1"
                ),
            },
            models={
                "claude-opus-5": ModelAlias(provider="omniroute"),
                "claude-fable-5": ModelAlias(provider="omniroute"),
                "gpt-5.5": ModelAlias(provider="omniroute"),
                "gpt-5.6": ModelAlias(provider="omniroute"),
                "glm-5": ModelAlias(provider="9router"),
                "glm-5.2": ModelAlias(provider="9router"),
                "deepseek-v4-pro": ModelAlias(provider="omniroute"),
                "qwen-3.7": ModelAlias(provider="ollama"),
                "qwen-3.8": ModelAlias(provider="ollama"),
            },
        )
        self._config = config
        return config

    def _parse_config(self, data: dict[str, Any]) -> Config:
        """Parse raw config data into Config object."""
        runtime_data = data.get("runtime", {})

        # Parse autonomy level
        autonomy_str = runtime_data.get("autonomy_level", "SUPERVISED_AUTO")
        try:
            if isinstance(autonomy_str, int):
                autonomy_level = AutonomyLevel(autonomy_str)
            else:
                autonomy_level = AutonomyLevel[autonomy_str.upper()]
        except (KeyError, ValueError):
            autonomy_level = AutonomyLevel.SUPERVISED_AUTO

        runtime = RuntimeConfig(
            autonomy_level=autonomy_level,
            default_agent=runtime_data.get("default_agent", "native"),
            default_provider=runtime_data.get("default_provider", "omniroute"),
            workspace_path=runtime_data.get("workspace_path"),
            sandbox_enabled=runtime_data.get("sandbox_enabled", True),
            audit_logging=runtime_data.get("audit_logging", True),
            max_concurrent_tasks=runtime_data.get("max_concurrent_tasks", 5),
        )

        # Parse providers
        providers = {}
        for name, prov_data in data.get("providers", {}).items():
            providers[name] = ProviderConfig(
                type=prov_data.get("type", "openai-compatible"),
                enabled=prov_data.get("enabled", True),
                base_url=prov_data.get("base_url", ""),
                api_key=prov_data.get("api_key"),
                timeout=prov_data.get("timeout", 60),
                retry_count=prov_data.get("retry_count", 3),
                headers=prov_data.get("headers", {}),
            )

        # Parse model aliases
        models = {}
        for alias, model_data in data.get("models", {}).get("aliases", {}).items():
            models[alias] = ModelAlias(
                provider=model_data.get("provider", ""),
                model_id=model_data.get("model_id"),
                fallback=model_data.get("fallback"),
            )

        # Parse MCP config if present
        mcp_data = data.get("mcp", {})
        if mcp_data:
            mcp_servers = {}
            for server_name, server_data in mcp_data.get("servers", {}).items():
                auth_data = server_data.get("auth", {})
                auth = MCPAuthConfig(
                    type=auth_data.get("type", "none"),
                    token_env=auth_data.get("token_env"),
                    api_key_env=auth_data.get("api_key_env"),
                ) if auth_data else None
                mcp_servers[server_name] = MCPServerConfig(
                    transport=server_data.get("transport", "stdio"),
                    command=server_data.get("command"),
                    args=server_data.get("args", []),
                    url=server_data.get("url"),
                    auth=auth,
                    enabled=server_data.get("enabled", True),
                    timeout=server_data.get("timeout", 30),
                    max_retries=server_data.get("max_retries", 3),
                )
            mcp_config = MCPConfig(
                enabled=mcp_data.get("enabled", True),
                servers=mcp_servers,
            )
            # Attach MCP config to first provider for now (will be refactored)
            if providers:
                first_provider = list(providers.values())[0]
                first_provider.mcp = mcp_config

        return Config(
            version=data.get("version", 1), runtime=runtime, providers=providers, models=models
        )

    def _serialize_config(self, config: Config) -> dict[str, Any]:
        """Serialize Config object to dictionary."""
        return {
            "version": config.version,
            "runtime": {
                "autonomy_level": config.runtime.autonomy_level.name.lower(),
                "default_agent": config.runtime.default_agent,
                "default_provider": config.runtime.default_provider,
                "workspace_path": config.runtime.workspace_path,
                "sandbox_enabled": config.runtime.sandbox_enabled,
                "audit_logging": config.runtime.audit_logging,
                "max_concurrent_tasks": config.runtime.max_concurrent_tasks,
            },
            "providers": {
                name: {
                    "type": p.type,
                    "enabled": p.enabled,
                    "base_url": p.base_url,
                    "timeout": p.timeout,
                    "retry_count": p.retry_count,
                }
                for name, p in config.providers.items()
            },
            "models": {
                "aliases": {
                    alias: {
                        "provider": m.provider,
                        "model_id": m.model_id,
                        "fallback": m.fallback,
                    }
                    for alias, m in config.models.items()
                }
            },
        }


# Global configuration instance
_config_engine: ConfigurationEngine | None = None


def get_config_engine() -> ConfigurationEngine:
    """Get global configuration engine instance."""
    global _config_engine
    if _config_engine is None:
        _config_engine = ConfigurationEngine()
    return _config_engine


def load_config() -> Config:
    """Load and return global configuration."""
    return get_config_engine().load()
