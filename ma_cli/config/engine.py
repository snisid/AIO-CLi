"""Configuration Engine for AIO-CLi."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..core.models import AutonomyLevel


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


@dataclass
class ModelAlias:
    """Model alias configuration."""
    provider: str
    model_id: str | None = None
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
    """Load, validate and persist AIO-CLi configuration."""

    DEFAULT_CONFIG_PATH = Path.home() / ".ma-cli" / "config.yaml"

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config: Config | None = None

    def load(self) -> Config:
        if not self.config_path.exists():
            return self._create_default_config()
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
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
        if config is None:
            config = self._config or self._create_default_config()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self._serialize_config(config), f, default_flow_style=False, sort_keys=False)

    def get(self) -> Config:
        if self._config is None:
            return self.load()
        return self._config

    def get_provider(self, name: str) -> ProviderConfig | None:
        return self.get().providers.get(name)

    def get_model_alias(self, alias: str) -> ModelAlias | None:
        return self.get().models.get(alias)

    def update_runtime(self, **kwargs) -> RuntimeConfig:
        config = self.get()
        for key, value in kwargs.items():
            if hasattr(config.runtime, key):
                setattr(config.runtime, key, value)
        self.save()
        return config.runtime

    def add_provider(self, name: str, provider_config: ProviderConfig) -> None:
        config = self.get()
        config.providers[name] = provider_config
        self.save()

    def remove_provider(self, name: str) -> bool:
        config = self.get()
        if name not in config.providers:
            return False
        del config.providers[name]
        self.save()
        return True

    def add_model_alias(self, alias: str, model_alias: ModelAlias) -> None:
        config = self.get()
        config.models[alias] = model_alias
        self.save()

    def validate(self) -> list[str]:
        warnings: list[str] = []
        config = self.get()
        if config.runtime.autonomy_level not in AutonomyLevel:
            warnings.append(f"Invalid autonomy level: {config.runtime.autonomy_level}")
        for name, provider in config.providers.items():
            if provider.enabled and not provider.base_url and provider.type != "anthropic":
                warnings.append(f"Provider '{name}' is enabled but has no base_url")
        for alias, model in config.models.items():
            if model.provider not in config.providers:
                warnings.append(f"Model alias '{alias}' references unknown provider '{model.provider}'")
        return warnings

    def _create_default_config(self) -> Config:
        config = Config(
            version=1,
            runtime=RuntimeConfig(),
            providers={
                "ollama": ProviderConfig(
                    type="openai-compatible", enabled=True,
                    base_url="http://localhost:11434/v1",
                ),
                "omniroute": ProviderConfig(
                    type="openai-compatible", enabled=True,
                    base_url="http://localhost:20128/v1",
                ),
                "9router": ProviderConfig(
                    type="openai-compatible", enabled=True,
                    base_url="http://localhost:9090/v1",
                ),
                "openrouter": ProviderConfig(
                    type="openai-compatible", enabled=bool(os.getenv("OPENROUTER_API_KEY")),
                    base_url="https://openrouter.ai/api/v1",
                    api_key=os.getenv("OPENROUTER_API_KEY"),
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
        runtime_data = data.get("runtime", {})
        autonomy_str = runtime_data.get("autonomy_level", "SUPERVISED_AUTO")
        try:
            autonomy_level = AutonomyLevel(autonomy_str) if isinstance(autonomy_str, int) else AutonomyLevel[str(autonomy_str).upper()]
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
        providers: dict[str, ProviderConfig] = {}
        for name, prov_data in data.get("providers", {}).items():
            providers[name] = ProviderConfig(
                type=prov_data.get("type", "openai-compatible"),
                enabled=prov_data.get("enabled", True),
                base_url=prov_data.get("base_url", ""),
                api_key=prov_data.get("api_key") or (os.getenv("OPENROUTER_API_KEY") if name == "openrouter" else None),
                timeout=prov_data.get("timeout", 60),
                retry_count=prov_data.get("retry_count", 3),
                headers=prov_data.get("headers", {}),
            )
        if "openrouter" not in providers and os.getenv("OPENROUTER_API_KEY"):
            providers["openrouter"] = ProviderConfig(
                type="openai-compatible", enabled=True,
                base_url="https://openrouter.ai/api/v1",
                api_key=os.getenv("OPENROUTER_API_KEY"),
            )

        models: dict[str, ModelAlias] = {}
        for alias, model_data in data.get("models", {}).get("aliases", {}).items():
            models[alias] = ModelAlias(
                provider=model_data.get("provider", ""),
                model_id=model_data.get("model_id"),
                fallback=model_data.get("fallback"),
            )
        config = Config(version=data.get("version", 1), runtime=runtime, providers=providers, models=models)
        self._config = config
        return config

    def _serialize_config(self, config: Config) -> dict[str, Any]:
        # API keys deliberately never persist to disk; environment variables are preferred.
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
                    "headers": p.headers,
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


_config_engine: ConfigurationEngine | None = None


def get_config_engine() -> ConfigurationEngine:
    global _config_engine
    if _config_engine is None:
        _config_engine = ConfigurationEngine()
    return _config_engine


def load_config() -> Config:
    return get_config_engine().load()
