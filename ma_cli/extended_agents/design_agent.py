"""Awesome Design MD Agent - Design Resources"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..agents.base import BaseAgent


class AwesomeDesignMDAgent(BaseAgent):
    """Agent providing design resources from awesome-design-md."""
    
    ROLE = "Design Resources Expert"
    SYSTEM_PROMPT = "You provide curated design resources and references."
    
    def __init__(self, workspace_path: Optional[str] = None):
        super().__init__()
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.design_path = self._find_design_path()
        self.capabilities_list = ["design_resources", "ui_references", "design_systems"]
    
    def _find_design_path(self) -> Optional[Path]:
        possible_paths = [
            Path("/workspace/external_agents/awesome-design-md"),
            self.workspace_path / "external_agents" / "awesome-design-md",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return None
    
    @property
    def is_available(self) -> bool:
        return self.design_path is not None
    
    def get_capabilities(self) -> List[str]:
        return self.capabilities_list.copy()
    
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "agent": self.ROLE,
            "task": task,
            "design_resources_available": self.is_available,
        }
