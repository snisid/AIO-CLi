"""
SubAgents Integration for AIO-CLI

This module integrates the awesome-claude-code-subagents collection
providing 158+ specialized agents across 10 categories.

Categories:
1. Core Development (11 agents)
2. Language Specialists (22 agents)
3. Infrastructure & DevOps (14 agents)
4. Quality & Security (16 agents)
5. Data & AI (15 agents)
6. Developer Experience (19 agents)
7. Specialized Domains (17 agents)
8. Business & Productivity (16 agents)
9. Meta & Orchestration (14 agents)
10. Research & Analysis (14 agents)
"""

from pathlib import Path
from typing import Dict, List, Optional
import json

# Base path for subagents
SUBAGENTS_BASE = Path(__file__).parent / "categories"

# Category mapping
CATEGORIES = {
    "01-core-development": "Core Development",
    "02-language-specialists": "Language Specialists",
    "03-infrastructure": "Infrastructure & DevOps",
    "04-quality-security": "Quality & Security",
    "05-data-ai": "Data & AI",
    "06-developer-experience": "Developer Experience",
    "07-specialized-domains": "Specialized Domains",
    "08-business-product": "Business & Productivity",
    "09-meta-orchestration": "Meta & Orchestration",
    "10-research-analysis": "Research & Analysis",
}


class SubAgentRegistry:
    """Registry for managing and discovering subagents."""
    
    def __init__(self):
        self._agents: Dict[str, dict] = {}
        self._categories: Dict[str, List[str]] = {}
        self._load_agents()
    
    def _load_agents(self):
        """Load all available subagents from the categories directory."""
        for category_dir in SUBAGENTS_BASE.iterdir():
            if not category_dir.is_dir():
                continue
            
            category_id = category_dir.name
            category_name = CATEGORIES.get(category_id, category_id)
            self._categories[category_id] = []
            
            for agent_file in category_dir.glob("*.md"):
                if agent_file.name == "README.md":
                    continue
                
                agent_id = agent_file.stem
                agent_info = self._parse_agent_file(agent_file)
                
                if agent_info:
                    agent_key = f"{category_id}/{agent_id}"
                    self._agents[agent_key] = {
                        "id": agent_id,
                        "category": category_id,
                        "category_name": category_name,
                        "file": str(agent_file),
                        **agent_info
                    }
                    self._categories[category_id].append(agent_id)
    
    def _parse_agent_file(self, file_path: Path) -> Optional[dict]:
        """Parse agent markdown file to extract metadata."""
        try:
            content = file_path.read_text()
            
            # Extract frontmatter
            if not content.startswith("---"):
                return None
            
            end_frontmatter = content.find("---", 3)
            if end_frontmatter == -1:
                return None
            
            frontmatter = content[3:end_frontmatter].strip()
            metadata = {}
            
            for line in frontmatter.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip().strip('"\'')
                    metadata[key] = value
            
            return metadata
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None
    
    def list_categories(self) -> Dict[str, str]:
        """List all available categories."""
        return CATEGORIES.copy()
    
    def list_agents(self, category: Optional[str] = None) -> List[dict]:
        """
        List agents, optionally filtered by category.
        
        Args:
            category: Category ID to filter by (e.g., "01-core-development")
        
        Returns:
            List of agent information dictionaries
        """
        if category:
            return [
                agent for agent in self._agents.values()
                if agent["category"] == category
            ]
        return list(self._agents.values())
    
    def get_agent(self, agent_id: str) -> Optional[dict]:
        """
        Get agent information by ID.
        
        Args:
            agent_id: Full agent ID (e.g., "01-core-development/fullstack-developer")
                     or just agent name (will search all categories)
        
        Returns:
            Agent information dictionary or None if not found
        """
        # Try direct lookup
        if agent_id in self._agents:
            return self._agents[agent_id]
        
        # Search by name only
        for key, agent in self._agents.items():
            if agent["id"] == agent_id:
                return agent
        
        return None
    
    def search_agents(self, query: str) -> List[dict]:
        """
        Search agents by name or description.
        
        Args:
            query: Search query string
        
        Returns:
            List of matching agents
        """
        query_lower = query.lower()
        matches = []
        
        for agent in self._agents.values():
            name_match = query_lower in agent.get("name", "").lower()
            desc_match = query_lower in agent.get("description", "").lower()
            
            if name_match or desc_match:
                matches.append(agent)
        
        return matches
    
    def get_agent_content(self, agent_id: str) -> Optional[str]:
        """
        Get the full content of an agent file.
        
        Args:
            agent_id: Full agent ID
        
        Returns:
            Agent file content or None if not found
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return None
        
        try:
            return Path(agent["file"]).read_text()
        except Exception:
            return None
    
    def install_agent(self, agent_id: str, target_dir: Path) -> bool:
        """
        Install an agent to a target directory.
        
        Args:
            agent_id: Full agent ID
            target_dir: Target directory for installation
        
        Returns:
            True if successful, False otherwise
        """
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            source_file = Path(agent["file"])
            target_file = target_dir / f"{agent['id']}.md"
            
            target_file.write_text(source_file.read_text())
            return True
        except Exception as e:
            print(f"Error installing agent: {e}")
            return False


# Global registry instance
registry = SubAgentRegistry()


def get_subagent_registry() -> SubAgentRegistry:
    """Get the global subagent registry instance."""
    return registry


__all__ = [
    "SubAgentRegistry",
    "get_subagent_registry",
    "CATEGORIES",
    "SUBAGENTS_BASE",
]
