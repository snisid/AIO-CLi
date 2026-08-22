"""
Extended Agents Integration for MA-CLI

This module provides integration with external agent repositories:
- ui-ux-pro-max-skill: UI/UX Design expertise
- ECC (Everything Claude Code): Multi-domain engineering agents
- OpenViking: RAG and memory capabilities
- impeccable: Code quality assurance
- awesome-design-md: Design resources
- img2threejs: 3D model generation
- taste-skill: Design taste evaluation
"""

from .ui_ux_agent import UIUXProMaxAgent
from .ecc_agent import ECCAgent
from .openviking_agent import OpenVikingAgent
from .impeccable_agent import ImpeccableAgent
from .design_agent import AwesomeDesignMDAgent
from .threejs_agent import Img2ThreeJSAgent
from .taste_agent import TasteSkillAgent

__all__ = [
    "UIUXProMaxAgent",
    "ECCAgent",
    "OpenVikingAgent",
    "ImpeccableAgent",
    "AwesomeDesignMDAgent",
    "Img2ThreeJSAgent",
    "TasteSkillAgent",
]

__version__ = "1.0.0"
