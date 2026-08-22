"""
OpenViking Agent - RAG and Memory Capabilities

Integrates OpenViking repository for advanced RAG, memory, and vector search capabilities.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..agents.base import BaseAgent


class OpenVikingAgent(BaseAgent):
    """Agent for RAG, memory, and vector search using OpenViking."""
    
    ROLE = "RAG and Memory Expert"
    
    SYSTEM_PROMPT = """You are an expert in Retrieval-Augmented Generation (RAG) and memory systems.
    
    Capabilities:
    - Vector database operations
    - Semantic search
    - Memory persistence
    - Context management
    - Knowledge retrieval
    - Document embedding
    """
    
    def __init__(self, workspace_path: Optional[str] = None):
        super().__init__()
        self.workspace_path = Path(workspace_path) if workspace_path else Path.cwd()
        self.openviking_path = self._find_openviking_path()
        self.capabilities_list = [
            "vector_search",
            "memory_management",
            "rag_pipeline",
            "semantic_search",
            "document_indexing",
        ]
    
    def _find_openviking_path(self) -> Optional[Path]:
        possible_paths = [
            Path("/workspace/external_agents/OpenViking"),
            self.workspace_path / "external_agents" / "OpenViking",
        ]
        for path in possible_paths:
            if path.exists() and (path / "openviking").exists():
                return path
        return None
    
    @property
    def is_available(self) -> bool:
        return self.openviking_path is not None
    
    def get_capabilities(self) -> List[str]:
        return self.capabilities_list.copy()
    
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "agent": self.ROLE,
            "task": task,
            "openviking_available": self.is_available,
            "metadata": {
                "openviking_path": str(self.openviking_path) if self.openviking_path else None,
            },
        }
