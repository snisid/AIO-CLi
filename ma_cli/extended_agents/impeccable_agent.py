"""Impeccable Agent - Code Quality Assurance"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..agents.base import BaseAgent


class ImpeccableAgent(BaseAgent):
    """Agent for code quality using impeccable repository."""
    
    ROLE = "Code Quality Expert"
    SYSTEM_PROMPT = "You ensure code quality follows impeccable standards."
    
    def __init__(self, workspace_path: Optional[str] = None):
        super().__init__()
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.impeccable_path = self._find_impeccable_path()
        self.capabilities_list = ["code_quality", "standards_check", "best_practices"]
    
    def _find_impeccable_path(self) -> Optional[Path]:
        possible_paths = [
            Path("/workspace/external_agents/impeccable"),
            self.workspace_path / "external_agents" / "impeccable",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return None
    
    @property
    def is_available(self) -> bool:
        return self.impeccable_path is not None
    
    def get_capabilities(self) -> List[str]:
        return self.capabilities_list.copy()
    
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "agent": self.ROLE,
            "task": task,
            "impeccable_available": self.is_available,
        }
