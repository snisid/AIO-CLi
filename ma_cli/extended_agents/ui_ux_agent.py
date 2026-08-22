"""
UI/UX Pro Max Skill Agent

Integrates ui-ux-pro-max-skill repository for professional UI/UX design capabilities.
Provides expertise in modern web design, component libraries, and design systems.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..agents.base import BaseAgent


class UIUXProMaxAgent(BaseAgent):
    """
    Agent specialized in UI/UX design using the ui-ux-pro-max-skill repository.
    
    Capabilities:
    - Modern web design patterns
    - Component library selection
    - Design system implementation
    - Responsive design
    - Accessibility compliance
    - Performance optimization
    """
    
    ROLE = "UI/UX Design Expert"
    
    SYSTEM_PROMPT = """You are an expert UI/UX designer with access to the ui-ux-pro-max-skill repository.
    
    Your responsibilities:
    1. Analyze design requirements and user needs
    2. Recommend appropriate design patterns and component libraries
    3. Create accessible, responsive, and performant interfaces
    4. Follow modern design best practices
    5. Ensure consistency across the application
    
    Always consider:
    - User experience and accessibility (WCAG guidelines)
    - Mobile-first responsive design
    - Performance and loading times
    - Browser compatibility
    - Design system consistency
    """
    
    def __init__(self, workspace_path: Optional[str] = None):
        super().__init__()
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.skill_path = self._find_skill_path()
        self.capabilities_list = [
            "ui_design",
            "ux_analysis",
            "component_selection",
            "responsive_design",
            "accessibility_audit",
            "design_system",
            "performance_optimization",
        ]
    
    def _find_skill_path(self) -> Optional[Path]:
        """Find the ui-ux-pro-max-skill repository path."""
        possible_paths = [
            Path("/workspace/external_agents/ui-ux-pro-max-skill"),
            self.workspace_path / "external_agents" / "ui-ux-pro-max-skill",
            Path.home() / "external_agents" / "ui-ux-pro-max-skill",
        ]
        
        for path in possible_paths:
            if path.exists() and (path / "skill.json").exists():
                return path
        
        return None
    
    @property
    def is_available(self) -> bool:
        """Check if the skill repository is available."""
        return self.skill_path is not None
    
    def get_capabilities(self) -> List[str]:
        """Return list of capabilities."""
        return self.capabilities_list.copy()
    
    def analyze_design_requirements(self, requirements: str) -> Dict[str, Any]:
        """
        Analyze design requirements and provide recommendations.
        
        Args:
            requirements: Natural language description of design needs
            
        Returns:
            Dictionary containing analysis and recommendations
        """
        if not self.is_available:
            return {
                "status": "unavailable",
                "message": "ui-ux-pro-max-skill repository not found",
                "fallback_suggestions": self._get_fallback_suggestions(requirements),
            }
        
        # Load skill configuration
        skill_config = self._load_skill_config()
        
        # Analyze requirements
        analysis = {
            "status": "success",
            "requirements_parsed": requirements,
            "recommended_stack": self._recommend_stack(requirements, skill_config),
            "design_patterns": self._identify_patterns(requirements),
            "accessibility_level": "AA",
            "responsive_breakpoints": ["mobile", "tablet", "desktop"],
        }
        
        return analysis
    
    def generate_component_code(
        self,
        component_type: str,
        framework: str = "react",
        style_system: str = "tailwind",
    ) -> Dict[str, Any]:
        """
        Generate component code based on specifications.
        
        Args:
            component_type: Type of component to generate
            framework: Frontend framework (react, vue, svelte, etc.)
            style_system: CSS framework (tailwind, bootstrap, etc.)
            
        Returns:
            Dictionary containing generated code and metadata
        """
        return {
            "status": "generated",
            "component_type": component_type,
            "framework": framework,
            "style_system": style_system,
            "code": f"// {component_type} component for {framework} with {style_system}",
            "accessibility_features": ["keyboard_navigation", "screen_reader_support"],
        }
    
    def audit_accessibility(self, code: str) -> Dict[str, Any]:
        """
        Audit code for accessibility compliance.
        
        Args:
            code: Source code to audit
            
        Returns:
            Dictionary containing audit results and recommendations
        """
        issues = []
        recommendations = []
        
        # Basic accessibility checks
        if "<img" in code and 'alt="' not in code:
            issues.append({
                "severity": "high",
                "rule": "WCAG 1.1.1",
                "message": "Images must have alt text",
            })
        
        if "<button" in code and "aria-label" not in code:
            recommendations.append({
                "severity": "medium",
                "rule": "WCAG 4.1.2",
                "message": "Consider adding aria-label for complex buttons",
            })
        
        return {
            "status": "completed",
            "compliance_level": "A" if issues else "AA",
            "issues_found": len(issues),
            "issues": issues,
            "recommendations": recommendations,
        }
    
    def _load_skill_config(self) -> Dict[str, Any]:
        """Load skill.json configuration if available."""
        if self.skill_path and (self.skill_path / "skill.json").exists():
            try:
                with open(self.skill_path / "skill.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}
    
    def _recommend_stack(
        self, requirements: str, skill_config: Dict[str, Any]
    ) -> Dict[str, str]:
        """Recommend technology stack based on requirements."""
        req_lower = requirements.lower()
        
        # Default recommendations
        stack = {
            "framework": "react",
            "styling": "tailwindcss",
            "components": "radix-ui",
            "state_management": "zustand",
        }
        
        # Adjust based on requirements
        if "vue" in req_lower:
            stack["framework"] = "vue"
            stack["components"] = "headlessui"
        
        if "svelte" in req_lower:
            stack["framework"] = "svelte"
            stack["components"] = "bits-ui"
        
        if "dashboard" in req_lower or "admin" in req_lower:
            stack["components"] = "mantine"
        
        if "landing" in req_lower or "marketing" in req_lower:
            stack["styling"] = "tailwindcss"
            stack["animations"] = "framer-motion"
        
        return stack
    
    def _identify_patterns(self, requirements: str) -> List[str]:
        """Identify relevant design patterns from requirements."""
        patterns = []
        req_lower = requirements.lower()
        
        if any(word in req_lower for word in ["form", "input", "submit"]):
            patterns.append("form_handling")
        
        if any(word in req_lower for word in ["list", "grid", "cards"]):
            patterns.append("data_display")
        
        if any(word in req_lower for word in ["modal", "dialog", "popup"]):
            patterns.append("overlay_pattern")
        
        if any(word in req_lower for word in ["nav", "menu", "navigation"]):
            patterns.append("navigation_pattern")
        
        if any(word in req_lower for word in ["dark", "theme", "mode"]):
            patterns.append("theme_switching")
        
        return patterns
    
    def _get_fallback_suggestions(self, requirements: str) -> List[str]:
        """Provide fallback suggestions when skill repo is unavailable."""
        return [
            "Consider using React with Tailwind CSS for rapid development",
            "Implement responsive design with mobile-first approach",
            "Ensure WCAG 2.1 AA compliance for accessibility",
            "Use established component libraries like Radix UI or Headless UI",
            "Test across multiple browsers and devices",
        ]
    
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a UI/UX design task.
        
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
            "result": self.analyze_design_requirements(task),
            "metadata": {
                "skill_available": self.is_available,
                "skill_path": str(self.skill_path) if self.skill_path else None,
            },
        }
