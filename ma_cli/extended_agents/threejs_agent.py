"""Img2ThreeJS Agent - 3D Model Generation"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..agents.base import BaseAgent


class Img2ThreeJSAgent(BaseAgent):
    """Agent for image to 3D model conversion using img2threejs."""
    
    ROLE = "3D Model Generation Expert"
    SYSTEM_PROMPT = "You convert images to 3D models using Three.js."
    
    def __init__(self, workspace_path: Optional[str] = None):
        super().__init__()
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.threejs_path = self._find_threejs_path()
        self.capabilities_list = ["image_to_3d", "threejs_generation", "model_optimization"]
    
    def _find_threejs_path(self) -> Optional[Path]:
        possible_paths = [
            Path("/workspace/external_agents/img2threejs"),
            self.workspace_path / "external_agents" / "img2threejs",
        ]
        for path in possible_paths:
            if path.exists():
                return path
        return None
    
    @property
    def is_available(self) -> bool:
        return self.threejs_path is not None
    
    def get_capabilities(self) -> List[str]:
        return self.capabilities_list.copy()
    
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "agent": self.ROLE,
            "task": task,
            "threejs_available": self.is_available,
        }
