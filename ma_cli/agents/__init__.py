"""Agents module initialization."""

from ..runtime.native import NativeAgent
from .adapters import (
    AgentConfig,
    AgentRegistry,
    AgentResult,
    ClaudeAgent,
    CLIInfo,
    CodexAgent,
    ExternalAgentBase,
    HermesAgent,
    OpenClawAgent,
    QwenAgent,
    ZcodeAgent,
    get_agent_registry,
)
from .base import Agent, AgentInfo
from .extended_agents import (
    EXTENDED_AGENTS_REGISTRY,
    ClaudeMEMAgent,
    CodeReviewAgent,
    ComposioAgent,
    FrontendDesignAgent,
    GStackAgent,
    SecurityReviewAgent,
    SuperPowersAgent,
    get_extended_agent,
)

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentInfo",
    "AgentRegistry",
    "AgentResult",
    "CLIInfo",
    "ClaudeAgent",
    "ClaudeMEMAgent",
    "CodeReviewAgent",
    "CodexAgent",
    "ComposioAgent",
    "EXTENDED_AGENTS_REGISTRY",
    "ExternalAgentBase",
    "FrontendDesignAgent",
    "GStackAgent",
    "HermesAgent",
    "NativeAgent",
    "OpenClawAgent",
    "QwenAgent",
    "SecurityReviewAgent",
    "SuperPowersAgent",
    "ZcodeAgent",
    "get_agent_registry",
    "get_extended_agent",
]
