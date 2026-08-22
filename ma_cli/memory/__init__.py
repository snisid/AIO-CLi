"""
MA-CLI Memory Engine.

Multi-layer persistent memory system for MA-CLI.
"""

from .engine import (
    # Enums
    MemoryType,
    MemoryScope,
    
    # Data classes
    MemoryEntry,
    ConversationMessage,
    MemorySummary,
    SessionState,
    
    # Backend
    MemoryBackend,
    SQLiteMemoryBackend,
    
    # Engine
    MemoryEngine,
    
    # Session management
    SessionManager,
    
    # Factory functions
    create_memory_engine,
    create_session_manager,
    
    # CLI helpers
    format_memory_summary,
    format_session_list,
)

__all__ = [
    # Enums
    "MemoryType",
    "MemoryScope",
    
    # Data classes
    "MemoryEntry",
    "ConversationMessage",
    "MemorySummary",
    "SessionState",
    
    # Backend
    "MemoryBackend",
    "SQLiteMemoryBackend",
    
    # Engine
    "MemoryEngine",
    
    # Session management
    "SessionManager",
    
    # Factory functions
    "create_memory_engine",
    "create_session_manager",
    
    # CLI helpers
    "format_memory_summary",
    "format_session_list",
]
