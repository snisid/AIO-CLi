"""Taste Skill Agent - Design Taste Evaluation"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..agents.base import BaseAgent


class TasteSkillAgent(BaseAgent):
    """Agent for design taste evaluation using taste-skill."""
    
    ROLE = "Design Taste Expert"
    SYSTEM_PROMPT = "You evaluate and improve design taste and aesthetics."
    
    def __init__(self, workspace_path: Optional[str] = None):
        super().__init__()
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.taste_path = self._find_taste_path()
        self.capabilities_list = ["taste_evaluation", "aesthetic_analysis", "design_improvement"]
    
    def _find_taste_path(self) -> Optional[Path]:
        possible_paths = [
            Path("/workspace/external_agents/taste-skill"),
            self.workspace_path / "external_agents" / "taste-skill",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return None
    
    @property
    def is_available(self) -> bool:
        return self.taste_path is not None
    
    def get_capabilities(self) -> List[str]:
        return self.capabilities_list.copy()
    
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "agent": self.ROLE,
            "task": task,
            "taste_skill_available": self.is_available,
        }
