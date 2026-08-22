"""
ECC (Everything Claude Code) Agent

Integrates ECC repository for multi-domain engineering capabilities.
Provides access to 80+ specialized agents for various programming languages and tasks.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..agents.base import BaseAgent


class ECCAgent(BaseAgent):
    """
    Agent leveraging ECC (Everything Claude Code) for multi-domain engineering tasks.
    
    Capabilities:
    - Multi-language code review (Python, Rust, Go, Java, TypeScript, etc.)
    - Build error resolution
    - Architecture design
    - Security review
    - Performance optimization
    - Test generation and analysis
    - Documentation updates
    """
    
    ROLE = "Multi-Domain Engineering Expert"
    
    SYSTEM_PROMPT = """You are an expert software engineer with access to the ECC (Everything Claude Code) repository.

Your responsibilities:
1. Provide expert-level code review across multiple programming languages
2. Resolve build errors and dependency issues
3. Design scalable and maintainable architectures
4. Ensure security best practices
5. Optimize performance
6. Generate comprehensive tests
7. Maintain up-to-date documentation

Available specializations:
- Backend: Python, Rust, Go, Java, Node.js, PHP, Ruby
- Frontend: React, Vue, TypeScript, Swift, Kotlin
- DevOps: Docker, Kubernetes, CI/CD
- Database: SQL, NoSQL, ORM optimization
- Security: Vulnerability assessment, secure coding
- Testing: Unit, integration, E2E testing
"""
    
    def __init__(self, workspace_path: Optional[str] = None):
        super().__init__()
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.ecc_path = self._find_ecc_path()
        self.agents_registry = self._load_agents_registry()
        self.commands_registry = self._load_commands_registry()
        
        self.capabilities_list = [
            "code_review",
            "build_fix",
            "architecture_design",
            "security_audit",
            "performance_optimization",
            "test_generation",
            "documentation",
            "multi_language_support",
        ]
    
    def _find_ecc_path(self) -> Optional[Path]:
        """Find the ECC repository path."""
        possible_paths = [
            Path("/workspace/external_agents/ECC"),
            self.workspace_path / "external_agents" / "ECC",
            Path.home() / "external_agents" / "ECC",
        ]
        
        for path in possible_paths:
            if path.exists() and (path / "agent.yaml").exists():
                return path
        
        return None
    
    @property
    def is_available(self) -> bool:
        """Check if the ECC repository is available."""
        return self.ecc_path is not None
    
    def get_capabilities(self) -> List[str]:
        """Return list of capabilities."""
        return self.capabilities_list.copy()
    
    def get_available_agents(self) -> List[Dict[str, str]]:
        """Get list of available specialized agents from ECC."""
        if not self.is_available:
            return []
        
        agents = []
        agents_dir = self.ecc_path / "agents"
        
        if agents_dir.exists():
            for agent_file in agents_dir.glob("*.md"):
                agent_name = agent_file.stem
                agents.append({
                    "name": agent_name,
                    "description": self._parse_agent_description(agent_file),
                })
        
        return agents
    
    def get_available_commands(self) -> List[Dict[str, str]]:
        """Get list of available commands from ECC."""
        if not self.is_available:
            return []
        
        commands = []
        commands_dir = self.ecc_path / "commands"
        
        if commands_dir.exists():
            for cmd_file in commands_dir.glob("*.md"):
                cmd_name = cmd_file.stem
                commands.append({
                    "name": cmd_name,
                    "description": self._parse_command_description(cmd_file),
                })
        
        return commands
    
    def execute_code_review(
        self,
        code: str,
        language: str = "python",
        review_type: str = "general",
    ) -> Dict[str, Any]:
        """
        Execute code review using ECC agents.
        
        Args:
            code: Source code to review
            language: Programming language
            review_type: Type of review (general, security, performance, etc.)
            
        Returns:
            Dictionary containing review results
        """
        if not self.is_available:
            return {
                "status": "unavailable",
                "message": "ECC repository not found",
                "fallback_review": self._perform_basic_review(code, language),
            }
        
        # Select appropriate reviewer agent
        reviewer_agent = f"{language}-reviewer"
        
        review_result = {
            "status": "completed",
            "language": language,
            "review_type": review_type,
            "issues": [],
            "suggestions": [],
            "positive_aspects": [],
        }
        
        # Basic review logic (would integrate with ECC agents in production)
        lines = code.split("\n")
        
        # Check for common issues
        if len(lines) > 100:
            review_result["suggestions"].append({
                "type": "maintainability",
                "message": "Consider breaking down this large file into smaller modules",
                "severity": "medium",
            })
        
        if "TODO" in code or "FIXME" in code:
            review_result["suggestions"].append({
                "type": "code_quality",
                "message": "Address TODO/FIXME comments before production",
                "severity": "low",
            })
        
        if language == "python":
            if "import *" in code:
                review_result["issues"].append({
                    "type": "best_practice",
                    "message": "Avoid wildcard imports",
                    "severity": "medium",
                    "line": next(
                        i
                        for i, line in enumerate(lines)
                        if "import *" in line
                    ),
                })
        
        return review_result
    
    def resolve_build_error(
        self,
        error_message: str,
        language: str,
        build_system: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolve build errors using ECC expertise.
        
        Args:
            error_message: Build error message
            language: Programming language
            build_system: Build system (pip, cargo, gradle, maven, etc.)
            
        Returns:
            Dictionary containing resolution steps
        """
        if not self.is_available:
            return {
                "status": "unavailable",
                "message": "ECC repository not found",
            }
        
        resolution = {
            "status": "analyzed",
            "error_type": self._classify_error(error_message),
            "likely_causes": [],
            "resolution_steps": [],
            "prevention_tips": [],
        }
        
        # Analyze error patterns
        error_lower = error_message.lower()
        
        if "module not found" in error_lower or "cannot find module" in error_lower:
            resolution["likely_causes"].append("Missing dependency")
            resolution["resolution_steps"].append(
                f"Install missing package using your package manager"
            )
            resolution["prevention_tips"].append(
                "Use a requirements file to track all dependencies"
            )
        
        if "syntax error" in error_lower:
            resolution["likely_causes"].append("Syntax error in code")
            resolution["resolution_steps"].append(
                "Check the indicated line for syntax issues"
            )
        
        if "type error" in error_lower or "typeerror" in error_lower:
            resolution["likely_causes"].append("Type mismatch")
            resolution["resolution_steps"].append(
                "Verify variable types and function signatures"
            )
        
        return resolution
    
    def generate_architecture(
        self,
        requirements: str,
        scale: str = "medium",
        constraints: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate software architecture based on requirements.
        
        Args:
            requirements: Functional and non-functional requirements
            scale: Project scale (small, medium, large, enterprise)
            constraints: Technical or business constraints
            
        Returns:
            Dictionary containing architecture proposal
        """
        architecture = {
            "status": "proposed",
            "scale": scale,
            "pattern": self._select_architecture_pattern(requirements, scale),
            "components": [],
            "technologies": [],
            "diagram_description": "",
        }
        
        # Select pattern based on requirements
        req_lower = requirements.lower()
        
        if "microservice" in req_lower or scale in ["large", "enterprise"]:
            architecture["pattern"] = "microservices"
            architecture["components"] = [
                "API Gateway",
                "Service Discovery",
                "Message Queue",
                "Database per Service",
                "Load Balancer",
            ]
        elif "real-time" in req_lower or "websocket" in req_lower:
            architecture["pattern"] = "event_driven"
            architecture["components"] = [
                "Event Bus",
                "WebSocket Server",
                "Message Broker",
                "Cache Layer",
            ]
        else:
            architecture["pattern"] = "layered"
            architecture["components"] = [
                "Presentation Layer",
                "Business Logic Layer",
                "Data Access Layer",
                "Database",
            ]
        
        return architecture
    
    def _load_agents_registry(self) -> Dict[str, Any]:
        """Load ECC agents registry if available."""
        if self.is_available:
            agent_yaml = self.ecc_path / "agent.yaml"
            if agent_yaml.exists():
                try:
                    import yaml
                    
                    with open(agent_yaml, "r", encoding="utf-8") as f:
                        return yaml.safe_load(f)
                except (ImportError, yaml.YAMLError, IOError):
                    pass
        return {}
    
    def _load_commands_registry(self) -> Dict[str, Any]:
        """Load ECC commands registry if available."""
        if self.is_available:
            commands_json = self.ecc_path / "docs" / "COMMAND_REGISTRY.json"
            if commands_json.exists():
                try:
                    with open(commands_json, "r", encoding="utf-8") as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass
        return {}
    
    def _parse_agent_description(self, agent_file: Path) -> str:
        """Parse agent description from markdown file."""
        try:
            content = agent_file.read_text(encoding="utf-8")
            # Extract first paragraph after headers
            lines = content.split("\n")
            for line in lines:
                if line.strip() and not line.startswith("#"):
                    return line[:200]
        except IOError:
            pass
        return "Specialized agent for this domain"
    
    def _parse_command_description(self, cmd_file: Path) -> str:
        """Parse command description from markdown file."""
        try:
            content = cmd_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            for line in lines:
                if line.strip() and not line.startswith("#"):
                    return line[:200]
        except IOError:
            pass
        return "Command for specific task"
    
    def _perform_basic_review(self, code: str, language: str) -> Dict[str, Any]:
        """Perform basic code review without ECC."""
        return {
            "status": "basic_review",
            "message": "ECC not available, performing basic review",
            "lines_of_code": len(code.split("\n")),
            "language": language,
        }
    
    def _classify_error(self, error_message: str) -> str:
        """Classify error type based on message."""
        error_lower = error_message.lower()
        
        if "module" in error_lower or "import" in error_lower:
            return "dependency_error"
        if "syntax" in error_lower:
            return "syntax_error"
        if "type" in error_lower:
            return "type_error"
        if "permission" in error_lower or "access" in error_lower:
            return "permission_error"
        if "network" in error_lower or "connection" in error_lower:
            return "network_error"
        if "memory" in error_lower:
            return "memory_error"
        
        return "unknown_error"
    
    def _select_architecture_pattern(
        self, requirements: str, scale: str
    ) -> str:
        """Select appropriate architecture pattern."""
        req_lower = requirements.lower()
        
        if scale == "enterprise":
            return "microservices"
        
        if "real-time" in req_lower:
            return "event_driven"
        
        if "crud" in req_lower or "simple" in req_lower:
            return "layered"
        
        if scale == "small":
            return "monolithic"
        
        return "layered"
    
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute an engineering task using ECC capabilities.
        
        Args:
            task: Task description
            context: Additional context information
            
        Returns:
            Execution result dictionary
        """
        context = context or {}
        
        return {
            "agent": self.ROLE,
            "task": task,
            "ecc_available": self.is_available,
            "available_agents_count": len(self.get_available_agents()),
            "available_commands_count": len(self.get_available_commands()),
            "metadata": {
                "ecc_path": str(self.ecc_path) if self.ecc_path else None,
            },
        }
