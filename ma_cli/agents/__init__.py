"""Agents module initialization."""

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
    GStackAgent,
    ClaudeMEMAgent,
    SecurityReviewAgent,
    CodeReviewAgent,
    FrontendDesignAgent,
    SuperPowersAgent,
    ComposioAgent,
    get_extended_agent,
    EXTENDED_AGENTS_REGISTRY,
)

__all__ = [
    # Base
    "Agent",
    "AgentInfo",
    # Adapters
    "AgentConfig",
    "AgentRegistry",
    "AgentResult",
    "CLIInfo",
    "ClaudeAgent",
    "CodexAgent",
    "ExternalAgentBase",
    "HermesAgent",
    "OpenClawAgent",
    "QwenAgent",
    "ZcodeAgent",
    "get_agent_registry",
    # Extended Agents
    "GStackAgent",
    "ClaudeMEMAgent",
    "SecurityReviewAgent",
    "CodeReviewAgent",
    "FrontendDesignAgent",
    "SuperPowersAgent",
    "ComposioAgent",
    "get_extended_agent",
    "EXTENDED_AGENTS_REGISTRY",
]
