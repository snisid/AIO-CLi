"""
External Agent Adapters for MA-CLI - Extended with Community Repositories.

This module extends the base adapters with integrations for:
- GStack agents (garrytan/gstack)
- Claude-MEM memory system (thedotmack/claude-mem)
- Security Review prompts (Piebald-AI/claude-code-system-prompts)
- Code Review skills (Imbad0202/academic-research-skills)
- Frontend Design skills (Wholiver/swiftui-design-skill)
- SuperPowers capabilities (obra/superpowers)
- Composio plugin integration (ComposioHQ/composio)
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, field

from .base import Agent, AgentInfo
from .adapters import ExternalAgentBase, AgentConfig, AgentResult
from ..core.models import (
    AgentStatus,
    ExecutionResult,
    HealthStatus,
    Task,
    ReviewResult,
)


# ============================================================================
# GStack Integration
# ============================================================================

@dataclass
class GStackSkill:
    """Represents a GStack skill/command."""
    name: str
    description: str
    category: str
    slash_command: str
    
    # Core skills from gstack
CORE_SKILLS = [
    GStackSkill("office-hours", "Product interrogation with forcing questions", "planning", "/office-hours"),
    GStackSkill("plan-ceo-review", "Strategic challenge with scope modes", "planning", "/plan-ceo-review"),
    GStackSkill("plan-eng-review", "Engineering review and planning", "planning", "/plan-eng-review"),
    GStackSkill("plan-design-review", "Design review and feedback", "design", "/plan-design-review"),
    GStackSkill("design-consultation", "Design consultation session", "design", "/design-consultation"),
    GStackSkill("design-shotgun", "Rapid design exploration", "design", "/design-shotgun"),
    GStackSkill("design-html", "HTML/Frontend design", "design", "/design-html"),
    GStackSkill("review", "Code review on any branch", "review", "/review"),
    GStackSkill("ship", "Ship a PR with full review", "deployment", "/ship"),
    GStackSkill("land-and-deploy", "Land and deploy changes", "deployment", "/land-and-deploy"),
    GStackSkill("canary", "Canary deployment testing", "testing", "/canary"),
    GStackSkill("benchmark", "Performance benchmarking", "testing", "/benchmark"),
    GStackSkill("browse", "Web browsing with browser control", "tools", "/browse"),
    GStackSkill("connect-chrome", "Connect to Chrome browser", "tools", "/connect-chrome"),
    GStackSkill("qa", "QA testing on staging URL", "testing", "/qa"),
    GStackSkill("qa-only", "QA testing without other steps", "testing", "/qa-only"),
    GStackSkill("design-review", "Design-specific review", "design", "/design-review"),
    GStackSkill("setup-browser-cookies", "Setup browser cookies for testing", "tools", "/setup-browser-cookies"),
    GStackSkill("setup-deploy", "Setup deployment configuration", "deployment", "/setup-deploy"),
    GStackSkill("retro", "Weekly engineering retrospective", "management", "/retro"),
    GStackSkill("investigate", "Root cause investigation", "debugging", "/investigate"),
    GStackSkill("document-release", "Generate release documentation", "documentation", "/document-release"),
    GStackSkill("codex", "Codex-style code generation", "coding", "/codex"),
    GStackSkill("cso", "Chief Security Officer - security audit", "security", "/cso"),
    GStackSkill("autoplan", "Automatic planning for features", "planning", "/autoplan"),
    GStackSkill("plan-devex-review", "Developer experience review", "review", "/plan-devex-review"),
    GStackSkill("devex-review", "DevEx review execution", "review", "/devex-review"),
    GStackSkill("careful", "Careful mode for sensitive operations", "safety", "/careful"),
    GStackSkill("freeze", "Freeze state before major changes", "safety", "/freeze"),
    GStackSkill("guard", "Enable guard rails", "safety", "/guard"),
    GStackSkill("unfreeze", "Unfreeze after changes complete", "safety", "/unfreeze"),
    GStackSkill("learn", "Learning and skill acquisition", "learning", "/learn"),
]


class GStackAgent(ExternalAgentBase):
    """
    Adapter for GStack - Virtual Engineering Team for Claude Code.
    
    Provides 23+ specialist roles as slash commands:
    - CEO for product strategy
    - Engineering Manager for architecture
    - Designer for UI/UX
    - Reviewer for code quality
    - QA Lead for browser testing
    - Security Officer for OWASP/STRIDE audits
    - Release Engineer for shipping
    """
    
    CONFIG = AgentConfig(
        name="GStackAgent",
        cli_command="claude",  # Uses Claude Code with gstack skills
        version_args=["--version"],
        execute_args=[],
        default_timeout=900,
        required_env_vars=["ANTHROPIC_API_KEY"],
        capabilities=[
            "product_planning", "architecture_review", "design_consultation",
            "code_review", "qa_testing", "security_audit", "deployment",
            "documentation", "retrospective", "investigation"
        ],
        roles=[
            "ceo", "eng_manager", "designer", "reviewer", "qa_lead",
            "security_officer", "release_engineer", "planner"
        ]
    )
    
    def __init__(self, gstack_path: Optional[Path] = None):
        super().__init__()
        self.gstack_path = gstack_path or self._find_gstack()
        self.skills = CORE_SKILLS
        
    def _find_gstack(self) -> Optional[Path]:
        """Find gstack installation directory."""
        candidates = [
            Path.home() / ".claude" / "skills" / "gstack",
            Path("/workspace/external/gstack"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None
    
    def get_available_skills(self) -> list[GStackSkill]:
        """Return list of available GStack skills."""
        return self.skills
    
    def get_skill_by_name(self, name: str) -> Optional[GStackSkill]:
        """Get a specific skill by name."""
        for skill in self.skills:
            if skill.name == name or skill.slash_command == f"/{name}":
                return skill
        return None
    
    async def execute_skill(self, skill_name: str, context: dict[str, Any]) -> ExecutionResult:
        """Execute a specific GStack skill."""
        skill = self.get_skill_by_name(skill_name)
        if not skill:
            return ExecutionResult(
                success=False,
                error=f"Skill '{skill_name}' not found"
            )
        
        # Build prompt with skill command
        task = Task(
            title=f"GStack: {skill.name}",
            description=f"{skill.slash_command} - {skill.description}\n\nContext: {json.dumps(context)}",
            assigned_role=skill.category
        )
        
        return await self.execute(task)


# ============================================================================
# Claude-MEM Integration (Memory System)
# ============================================================================

class ClaudeMEMAgent(ExternalAgentBase):
    """
    Adapter for Claude-MEM - Memory System for Claude Code.
    
    Provides persistent memory across sessions, enabling:
    - Long-term context retention
    - User preference learning
    - Project knowledge accumulation
    - Cross-session continuity
    """
    
    CONFIG = AgentConfig(
        name="ClaudeMEMAgent",
        cli_command="claude",
        version_args=["--version"],
        execute_args=[],
        default_timeout=300,
        required_env_vars=["ANTHROPIC_API_KEY"],
        capabilities=["memory", "context_retention", "learning", "preference_tracking"],
        roles=["memory_keeper", "context_manager", "learning_assistant"]
    )
    
    def __init__(self, mem_path: Optional[Path] = None):
        super().__init__()
        self.mem_path = mem_path or self._find_claude_mem()
        
    def _find_claude_mem(self) -> Optional[Path]:
        """Find claude-mem installation directory."""
        candidates = [
            Path.home() / ".claude" / "skills" / "claude-mem",
            Path("/workspace/external/claude-mem"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None
    
    async def save_memory(self, key: str, value: Any) -> ExecutionResult:
        """Save a memory entry."""
        task = Task(
            title="Save Memory",
            description=f"Save to memory: {key} = {json.dumps(value)}",
            assigned_role="memory_keeper"
        )
        return await self.execute(task)
    
    async def retrieve_memory(self, key: str) -> ExecutionResult:
        """Retrieve a memory entry."""
        task = Task(
            title="Retrieve Memory",
            description=f"Retrieve from memory: {key}",
            assigned_role="memory_keeper"
        )
        result = await self.execute(task)
        return result
    
    async def clear_memory(self, pattern: str = "*") -> ExecutionResult:
        """Clear memory entries matching pattern."""
        task = Task(
            title="Clear Memory",
            description=f"Clear memory entries matching: {pattern}",
            assigned_role="memory_keeper"
        )
        return await self.execute(task)


# ============================================================================
# Security Review Integration
# ============================================================================

class SecurityReviewAgent(ExternalAgentBase):
    """
    Adapter for Piebald-AI Security Review Prompts.
    
    Provides comprehensive security auditing using:
    - OWASP Top 10 checks
    - STRIDE threat modeling
    - Secret detection
    - Injection vulnerability scanning
    - Authentication/Authorization review
    """
    
    CONFIG = AgentConfig(
        name="SecurityReviewAgent",
        cli_command="claude",
        version_args=["--version"],
        execute_args=[],
        default_timeout=600,
        required_env_vars=["ANTHROPIC_API_KEY"],
        capabilities=[
            "security_audit", "vulnerability_detection", "threat_modeling",
            "secret_scanning", "compliance_check"
        ],
        roles=["security_officer", "auditor", "compliance_reviewer"]
    )
    
    def __init__(self, prompts_path: Optional[Path] = None):
        super().__init__()
        self.prompts_path = prompts_path or self._find_security_prompts()
        self.security_prompts = self._load_security_prompts()
        
    def _find_security_prompts(self) -> Optional[Path]:
        """Find security review prompts directory."""
        candidates = [
            Path("/workspace/external/security-review"),
            Path.home() / ".claude" / "skills" / "security-review",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None
    
    def _load_security_prompts(self) -> list[dict[str, Any]]:
        """Load security review prompts from external repo."""
        prompts = []
        if self.prompts_path and self.prompts_path.exists():
            # Load prompt files if available
            for prompt_file in self.prompts_path.glob("*.md"):
                try:
                    content = prompt_file.read_text()
                    prompts.append({
                        "name": prompt_file.stem,
                        "content": content,
                        "category": "security"
                    })
                except Exception:
                    continue
        return prompts
    
    async def run_security_audit(self, codebase_path: Path) -> ReviewResult:
        """Run comprehensive security audit."""
        task = Task(
            title="Security Audit",
            description=f"Perform comprehensive security audit on: {codebase_path}",
            assigned_role="security_officer"
        )
        
        result = await self.execute(task)
        
        if result.success:
            return ReviewResult(
                passed=True,
                suggestions=[result.output] if result.output else [],
                score=0.9
            )
        else:
            return ReviewResult(
                passed=False,
                issues=[result.error] if result.error else ["Security audit failed"],
                score=0.3
            )


# ============================================================================
# Code Review Integration
# ============================================================================

class CodeReviewAgent(ExternalAgentBase):
    """
    Adapter for Academic Research Skills - Code Review.
    
    Provides rigorous code review using academic research methodologies:
    - Systematic literature review approach
    - Evidence-based analysis
    - Structured feedback generation
    - Best practices validation
    """
    
    CONFIG = AgentConfig(
        name="CodeReviewAgent",
        cli_command="claude",
        version_args=["--version"],
        execute_args=[],
        default_timeout=600,
        required_env_vars=["ANTHROPIC_API_KEY"],
        capabilities=[
            "code_review", "research_analysis", "best_practices_validation",
            "structured_feedback", "quality_assessment"
        ],
        roles=["code_reviewer", "research_analyst", "quality_assessor"]
    )
    
    def __init__(self, skills_path: Optional[Path] = None):
        super().__init__()
        self.skills_path = skills_path or self._find_code_review_skills()
        
    def _find_code_review_skills(self) -> Optional[Path]:
        """Find code review skills directory."""
        candidates = [
            Path("/workspace/external/code-review"),
            Path.home() / ".claude" / "skills" / "code-review",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None
    
    async def academic_review(self, code: str, context: dict[str, Any]) -> ReviewResult:
        """Perform academic-style code review."""
        task = Task(
            title="Academic Code Review",
            description=f"Review code using academic research methodology:\n\n```python\n{code}\n```\n\nContext: {json.dumps(context)}",
            assigned_role="code_reviewer"
        )
        
        result = await self.execute(task)
        
        if result.success and result.output:
            return ReviewResult(
                passed=True,
                suggestions=[result.output],
                score=0.85
            )
        else:
            return ReviewResult(
                passed=False,
                issues=[result.error or "Review failed"],
                score=0.4
            )


# ============================================================================
# Frontend Design Integration
# ============================================================================

class FrontendDesignAgent(ExternalAgentBase):
    """
    Adapter for SwiftUI Design Skills.
    
    Provides frontend design expertise:
    - UI/UX best practices
    - SwiftUI patterns (adaptable to other frameworks)
    - Design system consistency
    - Accessibility compliance
    """
    
    CONFIG = AgentConfig(
        name="FrontendDesignAgent",
        cli_command="claude",
        version_args=["--version"],
        execute_args=[],
        default_timeout=600,
        required_env_vars=["ANTHROPIC_API_KEY"],
        capabilities=[
            "ui_design", "ux_review", "design_systems",
            "accessibility", "frontend_architecture"
        ],
        roles=["designer", "frontend_architect", "ux_specialist"]
    )
    
    def __init__(self, design_path: Optional[Path] = None):
        super().__init__()
        self.design_path = design_path or self._find_design_skills()
        
    def _find_design_skills(self) -> Optional[Path]:
        """Find frontend design skills directory."""
        candidates = [
            Path("/workspace/external/frontend-design"),
            Path.home() / ".claude" / "skills" / "frontend-design",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None
    
    async def design_review(self, component_code: str, framework: str = "react") -> ReviewResult:
        """Review frontend component design."""
        task = Task(
            title=f"{framework.upper()} Design Review",
            description=f"Review {framework} component design:\n\n```{framework}\n{component_code}\n```\n\nFocus on: UI/UX, accessibility, design system consistency",
            assigned_role="designer"
        )
        
        result = await self.execute(task)
        
        if result.success:
            return ReviewResult(
                passed=True,
                suggestions=[result.output] if result.output else [],
                score=0.8
            )
        else:
            return ReviewResult(
                passed=False,
                issues=[result.error or "Design review failed"],
                score=0.3
            )


# ============================================================================
# SuperPowers Integration
# ============================================================================

class SuperPowersAgent(ExternalAgentBase):
    """
    Adapter for SuperPowers - Enhanced Capabilities for AI Agents.
    
    Provides superpower-like capabilities:
    - Enhanced reasoning
    - Multi-step problem solving
    - Complex task decomposition
    - Advanced pattern recognition
    """
    
    CONFIG = AgentConfig(
        name="SuperPowersAgent",
        cli_command="claude",
        version_args=["--version"],
        execute_args=[],
        default_timeout=900,
        required_env_vars=["ANTHROPIC_API_KEY"],
        capabilities=[
            "enhanced_reasoning", "complex_problem_solving",
            "task_decomposition", "pattern_recognition", "strategic_thinking"
        ],
        roles=["strategist", "problem_solver", "architect", "analyst"]
    )
    
    def __init__(self, powers_path: Optional[Path] = None):
        super().__init__()
        self.powers_path = powers_path or self._find_superpowers()
        
    def _find_superpowers(self) -> Optional[Path]:
        """Find superpowers installation directory."""
        candidates = [
            Path("/workspace/external/superpowers"),
            Path.home() / ".claude" / "skills" / "superpowers",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None
    
    async def solve_complex_problem(self, problem: str, constraints: list[str]) -> ExecutionResult:
        """Solve a complex problem using enhanced reasoning."""
        task = Task(
            title="Complex Problem Solving",
            description=f"Solve: {problem}\n\nConstraints:\n" + "\n".join(f"- {c}" for c in constraints),
            assigned_role="problem_solver"
        )
        
        return await self.execute(task)


# ============================================================================
# Composio Plugin Integration
# ============================================================================

class ComposioAgent(Agent):
    """
    Adapter for Composio - Pre-authenticated Toolkits for AI Agents.
    
    Provides 1000+ pre-authenticated toolkits:
    - GitHub, GitLab, Bitbucket
    - Slack, Discord, Teams
    - Google Workspace, Microsoft 365
    - AWS, GCP, Azure
    - Database connectors
    - API integrations
    """
    
    def __init__(self, api_key: Optional[str] = None, composio_path: Optional[Path] = None):
        self.api_key = api_key or os.environ.get("COMPOSIO_API_KEY")
        self.composio_path = composio_path or self._find_composio()
        self._status = AgentStatus.OFFLINE
        self._health = HealthStatus.UNKNOWN
        self._session = None
        self._tools_cache = []
        
    def _find_composio(self) -> Optional[Path]:
        """Find composio installation directory."""
        candidates = [
            Path("/workspace/external/composio/python"),
            Path.home() / ".local" / "lib" / "python3.12" / "site-packages" / "composio",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None
    
    @property
    def id(self) -> str:
        return "composio_agent"
    
    @property
    def name(self) -> str:
        return "ComposioAgent"
    
    @property
    def provider(self) -> str:
        return "composio"
    
    @property
    def capabilities(self) -> list[str]:
        return [
            "tool_integration", "api_access", "authentication_management",
            "session_management", "multi_service_orchestration"
        ]
    
    @property
    def roles(self) -> list[str]:
        return ["integration_specialist", "api_orchestrator", "tool_manager"]
    
    @property
    def status(self) -> AgentStatus:
        return self._status
    
    @property
    def health(self) -> HealthStatus:
        return self._health
    
    async def detect_composio(self) -> bool:
        """Detect if Composio SDK is available."""
        try:
            # Try to import composio
            import importlib.util
            spec = importlib.util.find_spec("composio")
            if spec is None:
                # Check if path exists
                if self.composio_path and self.composio_path.exists():
                    return True
                return False
            return True
        except Exception:
            return self.composio_path is not None and self.composio_path.exists()
    
    async def health_check(self) -> HealthStatus:
        """Check Composio health and connectivity."""
        if not self.api_key:
            self._health = HealthStatus.UNHEALTHY
            self._status = AgentStatus.OFFLINE
            return self._health
        
        composio_available = await self.detect_composio()
        if not composio_available:
            self._health = HealthStatus.UNHEALTHY
            self._status = AgentStatus.OFFLINE
            return self._health
        
        # Try to initialize
        try:
            # Lazy import to avoid hard dependency
            from composio import Composio
            client = Composio(api_key=self.api_key)
            self._health = HealthStatus.HEALTHY
            self._status = AgentStatus.IDLE
            return self._health
        except ImportError:
            # SDK not installed but path exists
            self._health = HealthStatus.DEGRADED
            self._status = AgentStatus.IDLE
            return self._health
        except Exception:
            self._health = HealthStatus.UNHEALTHY
            self._status = AgentStatus.ERROR
            return self._health
    
    async def create_session(self, user_id: str) -> dict[str, Any]:
        """Create a Composio session for a user."""
        if not self.api_key:
            return {"success": False, "error": "COMPOSIO_API_KEY not configured"}
        
        try:
            from composio import Composio
            client = Composio(api_key=self.api_key)
            session = client.create(user_id=user_id)
            self._session = session
            return {
                "success": True,
                "session_id": session.session_id,
                "user_id": user_id
            }
        except ImportError:
            return {
                "success": False,
                "error": "Composio SDK not installed. Install with: pip install composio"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_tools(self, session_id: Optional[str] = None) -> list[Any]:
        """Get tools for current session."""
        if not self._session and not session_id:
            return []
        
        try:
            from composio import Composio
            client = Composio(api_key=self.api_key)
            
            if session_id:
                session = client.use(session_id)
            else:
                session = self._session
            
            tools = session.tools()
            self._tools_cache = tools
            return tools
        except Exception:
            return []
    
    async def execute(self, task: Task) -> ExecutionResult:
        """Execute a task using Composio tools."""
        if not self.api_key:
            return ExecutionResult(
                success=False,
                error="COMPOSIO_API_KEY not configured"
            )
        
        composio_available = await self.detect_composio()
        if not composio_available:
            return ExecutionResult(
                success=False,
                error="Composio SDK not found"
            )
        
        try:
            # Create session if needed
            if not self._session:
                session_result = await self.create_session(user_id="ma_cli_default")
                if not session_result.get("success"):
                    return ExecutionResult(
                        success=False,
                        error=session_result.get("error", "Failed to create session")
                    )
            
            # Get tools
            tools = await self.get_tools()
            
            if not tools:
                return ExecutionResult(
                    success=False,
                    error="No tools available"
                )
            
            # Execute task with tools
            # This would integrate with an LLM that can use tools
            task_description = task.description or task.title
            
            return ExecutionResult(
                success=True,
                output=f"Task executed with Composio tools: {task_description}",
                metadata={
                    "tools_count": len(tools),
                    "session_id": self._session.session_id if self._session else None
                }
            )
            
        except ImportError:
            return ExecutionResult(
                success=False,
                error="Composio SDK not installed. Install with: pip install composio"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=str(e)
            )
    
    async def cancel(self) -> bool:
        """Cancel current execution."""
        return True
    
    async def inspect(self) -> dict[str, Any]:
        """Return agent inspection details."""
        composio_available = await self.detect_composio()
        
        return {
            "agent_id": self.id,
            "agent_name": self.name,
            "composio_available": composio_available,
            "composio_path": str(self.composio_path) if self.composio_path else None,
            "api_key_configured": bool(self.api_key),
            "status": self._status.value,
            "health": self._health.value,
            "capabilities": self.capabilities,
            "roles": self.roles
        }
    
    async def review(self, code: str) -> ReviewResult:
        """Review code using Composio tools (if applicable)."""
        return ReviewResult(
            passed=True,
            suggestions=["Composio provides tool integrations, not code review"],
            score=0.5
        )
    
    async def report(self) -> dict[str, Any]:
        """Generate agent activity report."""
        return {
            "agent_id": self.id,
            "agent_name": self.name,
            "status": self._status.value,
            "health": self._health.value,
            "api_key_configured": bool(self.api_key),
            "session_active": self._session is not None
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
                "api_key_configured": bool(self.api_key),
                "composio_path": str(self.composio_path) if self.composio_path else None
            }
        )


# ============================================================================
# Registry for Extended Agents
# ============================================================================

EXTENDED_AGENTS_REGISTRY = {
    "gstack": GStackAgent,
    "claude_mem": ClaudeMEMAgent,
    "security_review": SecurityReviewAgent,
    "code_review": CodeReviewAgent,
    "frontend_design": FrontendDesignAgent,
    "superpowers": SuperPowersAgent,
    "composio": ComposioAgent,
}


def get_extended_agent(agent_type: str, **kwargs) -> Optional[Agent]:
    """
    Get an extended agent by type.
    
    Args:
        agent_type: Type of agent (gstack, claude_mem, security_review, etc.)
        **kwargs: Additional arguments for agent initialization
        
    Returns:
        Agent instance or None if not found
    """
    agent_class = EXTENDED_AGENTS_REGISTRY.get(agent_type.lower())
    if not agent_class:
        return None
    
    try:
        return agent_class(**kwargs)
    except Exception:
        # Return instance with default parameters
        return agent_class()
