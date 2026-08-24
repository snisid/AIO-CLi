"""
MA-CLI Memory Engine.

Multi-layer persistent memory system for MA-CLI.
"""

from .engine import (
    ConversationMessage,
    # Backend
    MemoryBackend,
    # Engine
    MemoryEngine,
    # Data classes
    MemoryEntry,
    MemoryScope,
    MemorySummary,
    # Enums
    MemoryType,
    # Session management
    SessionManager,
    SessionState,
    SQLiteMemoryBackend,
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
