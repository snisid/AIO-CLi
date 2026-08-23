"""
MA-CLI Memory Engine.

This module implements a multi-layer persistent memory system for MA-CLI,
providing conversation, project, task, run, agent, and long-term memory.

Inspired by architectural patterns from:
- claude-mem: https://github.com/thedotmack/claude-mem.git
- OpenViking: https://github.com/volcengine/OpenViking.git

Memory Layers:
1. Conversation Memory - Chat/dialogue history
2. Project Memory - Project-specific context
3. Task Memory - Individual task context
4. Run Memory - Execution run history
5. Agent Memory - Agent-specific state
6. Long-Term Memory - Compressed/summarized knowledge
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


def _now_utc() -> datetime:
    """Get current UTC time in a timezone-aware manner."""
    return datetime.now(UTC)


# ============================================================================
# Memory Types and Enums
# ============================================================================


class MemoryType(Enum):
    """Types of memory layers."""

    CONVERSATION = "conversation"
    PROJECT = "project"
    TASK = "task"
    RUN = "run"
    AGENT = "agent"
    LONG_TERM = "long_term"


class MemoryScope(Enum):
    """Scope of memory visibility."""

    GLOBAL = "global"  # Across all projects
    PROJECT = "project"  # Within a project
    SESSION = "session"  # Within a session
    TASK = "task"  # Within a task
    RUN = "run"  # Within a run


@dataclass
class MemoryEntry:
    """A single memory entry."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    memory_type: MemoryType = MemoryType.LONG_TERM
    scope: MemoryScope = MemoryScope.GLOBAL

    # Content
    key: str = ""
    value: Any = None
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # Context
    project_id: str | None = "default-project"
    session_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    agent_id: str | None = None

    # Timestamps
    created_at: datetime = field(default_factory=_now_utc)
    updated_at: datetime = field(default_factory=_now_utc)
    expires_at: datetime | None = None

    # Access control
    privacy_level: str = "normal"  # normal, sensitive, private

    # Usage tracking
    access_count: int = 0
    last_accessed: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "memory_type": self.memory_type.value,
            "scope": self.scope.value,
            "key": self.key,
            "value": self.value,
            "content": self.content,
            "metadata": self.metadata,
            "project_id": self.project_id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "privacy_level": self.privacy_level,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            memory_type=MemoryType(data["memory_type"]),
            scope=MemoryScope(data["scope"]),
            key=data["key"],
            value=data.get("value"),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            project_id=data.get("project_id"),
            session_id=data.get("session_id"),
            task_id=data.get("task_id"),
            run_id=data.get("run_id"),
            agent_id=data.get("agent_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"])
            if data.get("expires_at")
            else None,
            privacy_level=data.get("privacy_level", "normal"),
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"])
            if data.get("last_accessed")
            else None,
        )


@dataclass
class ConversationMessage:
    """A message in conversation memory."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: str = "user"  # user, assistant, system
    content: str = ""
    timestamp: datetime = field(default_factory=_now_utc)
    session_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "metadata": self.metadata,
        }


@dataclass
class MemorySummary:
    """Summary of memory contents."""

    total_entries: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    by_scope: dict[str, int] = field(default_factory=dict)
    storage_size_bytes: int = 0
    oldest_entry: datetime | None = None
    newest_entry: datetime | None = None


# ============================================================================
# Memory Backend Interface
# ============================================================================


class MemoryBackend(ABC):
    """Abstract base class for memory backends."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the backend."""

    @abstractmethod
    def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry. Returns entry ID."""

    @abstractmethod
    def retrieve(self, entry_id: str) -> MemoryEntry | None:
        """Retrieve a memory entry by ID."""

    @abstractmethod
    def search(self, query: str, filters: dict[str, Any] | None = None) -> list[MemoryEntry]:
        """Search for memory entries."""

    @abstractmethod
    def update(self, entry: MemoryEntry) -> None:
        """Update a memory entry."""

    @abstractmethod
    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""

    @abstractmethod
    def get_summary(self, filters: dict[str, Any] | None = None) -> MemorySummary:
        """Get memory summary."""

    @abstractmethod
    def cleanup(self, older_than: datetime | None = None) -> int:
        """Clean up old entries. Returns count deleted."""


# ============================================================================
# SQLite Memory Backend
# ============================================================================


class SQLiteMemoryBackend(MemoryBackend):
    """SQLite-based memory backend."""

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = Path.home() / ".ma-cli" / "memory" / "ma_cli_memory.db"

        self.db_path = db_path
        self._initialized = False

    def _ensure_db_exists(self) -> None:
        """Ensure database and tables exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Memory entries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT,
                    scope TEXT,
                    key TEXT,
                    value TEXT,
                    content TEXT,
                    metadata TEXT,
                    project_id TEXT,
                    session_id TEXT,
                    task_id TEXT,
                    run_id TEXT,
                    agent_id TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    expires_at TEXT,
                    privacy_level TEXT,
                    access_count INTEGER,
                    last_accessed TEXT
                )
            """)

            # Conversation messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id TEXT PRIMARY KEY,
                    role TEXT,
                    content TEXT,
                    timestamp TEXT,
                    session_id TEXT,
                    metadata TEXT
                )
            """)

            # Create indexes for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_type
                ON memory_entries(memory_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scope
                ON memory_entries(scope)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_project_id
                ON memory_entries(project_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id
                ON memory_entries(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_key
                ON memory_entries(key)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON memory_entries(created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at
                ON memory_entries(expires_at)
            """)
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                USING fts5(content, key, metadata)
            """)

            conn.commit()
            self._initialized = True

    @contextmanager
    def _get_connection(self):
        """Get database connection context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        """Initialize the backend."""
        self._ensure_db_exists()

    def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry."""
        if not self._initialized:
            self.initialize()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO memory_entries
                (id, memory_type, scope, key, value, content, metadata,
                 project_id, session_id, task_id, run_id, agent_id,
                 created_at, updated_at, expires_at, privacy_level,
                 access_count, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    entry.id,
                    entry.memory_type.value,
                    entry.scope.value,
                    entry.key,
                    json.dumps(entry.value) if entry.value is not None else None,
                    entry.content,
                    json.dumps(entry.metadata),
                    entry.project_id,
                    entry.session_id,
                    entry.task_id,
                    entry.run_id,
                    entry.agent_id,
                    entry.created_at.isoformat(),
                    entry.updated_at.isoformat(),
                    entry.expires_at.isoformat() if entry.expires_at else None,
                    entry.privacy_level,
                    int(entry.access_count),
                    entry.last_accessed.isoformat() if entry.last_accessed else None,
                ),
            )

            # Update FTS index - handle metadata carefully for FTS5
            try:
                metadata_str = json.dumps(entry.metadata) if entry.metadata else ""
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO memory_fts(rowid, content, key, metadata)
                    VALUES (?, ?, ?, ?)
                """,
                    (entry.id, entry.content or "", entry.key or "", metadata_str),
                )
            except sqlite3.IntegrityError:
                # FTS insertion is not critical, skip if it fails
                pass

            conn.commit()

        return entry.id

    def retrieve(self, entry_id: str) -> MemoryEntry | None:
        """Retrieve a memory entry by ID."""
        if not self._initialized:
            self.initialize()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM memory_entries WHERE id = ?
            """,
                (entry_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            # Update access count
            cursor.execute(
                """
                UPDATE memory_entries
                SET access_count = access_count + 1, last_accessed = ?
                WHERE id = ?
            """,
                (_now_utc().isoformat(), entry_id),
            )
            conn.commit()

            return self._row_to_entry(row)

    def search(self, query: str, filters: dict[str, Any] | None = None) -> list[MemoryEntry]:
        """Search for memory entries."""
        if not self._initialized:
            self.initialize()

        conditions = []
        params = []

        # Build WHERE clause from filters
        if filters:
            if "memory_type" in filters:
                conditions.append("memory_type = ?")
                params.append(
                    filters["memory_type"].value
                    if isinstance(filters["memory_type"], MemoryType)
                    else filters["memory_type"]
                )

            if "scope" in filters:
                conditions.append("scope = ?")
                params.append(
                    filters["scope"].value
                    if isinstance(filters["scope"], MemoryScope)
                    else filters["scope"]
                )

            if "project_id" in filters:
                conditions.append("project_id = ?")
                params.append(filters["project_id"])

            if "session_id" in filters:
                conditions.append("session_id = ?")
                params.append(filters["session_id"])

            if "task_id" in filters:
                conditions.append("task_id = ?")
                params.append(filters["task_id"])

            if "run_id" in filters:
                conditions.append("run_id = ?")
                params.append(filters["run_id"])

            if "agent_id" in filters:
                conditions.append("agent_id = ?")
                params.append(filters["agent_id"])

            if "privacy_level" in filters:
                conditions.append("privacy_level = ?")
                params.append(filters["privacy_level"])

            if "expires_before" in filters:
                conditions.append("expires_at < ?")
                params.append(filters["expires_before"].isoformat())

            if "created_after" in filters:
                conditions.append("created_at > ?")
                params.append(filters["created_after"].isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Use FTS for content search if query is provided
            if query:
                cursor.execute(
                    f"""
                    SELECT m.* FROM memory_entries m
                    JOIN memory_fts fts ON m.id = fts.rowid
                    WHERE memory_fts MATCH ? AND {where_clause}
                    ORDER BY created_at DESC
                """,
                    (query, *params),
                )
            else:
                sql = f"SELECT * FROM memory_entries WHERE {where_clause} ORDER BY created_at DESC"
                cursor.execute(sql, params)

            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def update(self, entry: MemoryEntry) -> None:
        """Update a memory entry."""
        entry.updated_at = _now_utc()
        self.store(entry)

    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        if not self._initialized:
            self.initialize()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM memory_entries WHERE id = ?
            """,
                (entry_id,),
            )

            # Remove from FTS
            cursor.execute(
                """
                DELETE FROM memory_fts WHERE rowid = ?
            """,
                (entry_id,),
            )

            conn.commit()
            return cursor.rowcount > 0

    def get_summary(self, filters: dict[str, Any] | None = None) -> MemorySummary:
        """Get memory summary."""
        if not self._initialized:
            self.initialize()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Base query
            where_clause = "WHERE 1=1"
            params = []

            if filters:
                if "project_id" in filters:
                    where_clause += " AND project_id = ?"
                    params.append(filters["project_id"])
                if "session_id" in filters:
                    where_clause += " AND session_id = ?"
                    params.append(filters["session_id"])

            # Total count
            cursor.execute(f"SELECT COUNT(*) FROM memory_entries {where_clause}", params)
            total = cursor.fetchone()[0]

            # Count by type
            cursor.execute(
                f"""
                SELECT memory_type, COUNT(*) as count
                FROM memory_entries {where_clause}
                GROUP BY memory_type
            """,
                params,
            )
            by_type = {row["memory_type"]: row["count"] for row in cursor.fetchall()}

            # Count by scope
            cursor.execute(
                f"""
                SELECT scope, COUNT(*) as count
                FROM memory_entries {where_clause}
                GROUP BY scope
            """,
                params,
            )
            by_scope = {row["scope"]: row["count"] for row in cursor.fetchall()}

            # Storage size
            cursor.execute(
                f"SELECT SUM(length(content)) FROM memory_entries {where_clause}", params
            )
            storage_size = cursor.fetchone()[0] or 0

            # Oldest and newest
            cursor.execute(
                f"SELECT MIN(created_at), MAX(created_at) FROM memory_entries {where_clause}",
                params,
            )
            row = cursor.fetchone()
            oldest = datetime.fromisoformat(row[0]) if row[0] else None
            newest = datetime.fromisoformat(row[1]) if row[1] else None

            return MemorySummary(
                total_entries=total,
                by_type=by_type,
                by_scope=by_scope,
                storage_size_bytes=storage_size,
                oldest_entry=oldest,
                newest_entry=newest,
            )

    def cleanup(self, older_than: datetime | None = None) -> int:
        """Clean up old entries."""
        if not self._initialized:
            self.initialize()

        if older_than is None:
            # Default: clean up entries older than 90 days that are expired
            older_than = _now_utc() - timedelta(days=90)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Delete expired entries
            cursor.execute(
                """
                DELETE FROM memory_entries
                WHERE expires_at IS NOT NULL AND expires_at < ?
            """,
                (older_than.isoformat(),),
            )
            deleted = cursor.rowcount

            # Clean up FTS
            cursor.execute("""
                DELETE FROM memory_fts
                WHERE rowid NOT IN (SELECT id FROM memory_entries)
            """)

            conn.commit()
            return deleted

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """Convert a database row to MemoryEntry."""
        return MemoryEntry(
            id=row["id"],
            memory_type=MemoryType(row["memory_type"]),
            scope=MemoryScope(row["scope"]),
            key=row["key"],
            value=json.loads(row["value"]) if row["value"] else None,
            content=row["content"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            project_id=row["project_id"],
            session_id=row["session_id"],
            task_id=row["task_id"],
            run_id=row["run_id"],
            agent_id=row["agent_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            privacy_level=row["privacy_level"],
            access_count=row["access_count"],
            last_accessed=datetime.fromisoformat(row["last_accessed"])
            if row["last_accessed"]
            else None,
        )

    # Conversation-specific methods
    def add_message(self, message: ConversationMessage) -> str:
        """Add a conversation message."""
        if not self._initialized:
            self.initialize()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO conversation_messages (id, role, content, timestamp, session_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    message.id,
                    message.role,
                    message.content,
                    message.timestamp.isoformat(),
                    message.session_id,
                    json.dumps(message.metadata),
                ),
            )
            conn.commit()

        return message.id

    def get_conversation(self, session_id: str, limit: int = 50) -> list[ConversationMessage]:
        """Get conversation messages for a session."""
        if not self._initialized:
            self.initialize()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM conversation_messages
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (session_id, limit),
            )

            messages = []
            for row in cursor.fetchall():
                messages.append(
                    ConversationMessage(
                        id=row["id"],
                        role=row["role"],
                        content=row["content"],
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        session_id=row["session_id"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    )
                )

            return list(reversed(messages))  # Return in chronological order

    def clear_conversation(self, session_id: str) -> int:
        """Clear conversation messages for a session."""
        if not self._initialized:
            self.initialize()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM conversation_messages WHERE session_id = ?
            """,
                (session_id,),
            )
            conn.commit()
            return cursor.rowcount


# ============================================================================
# Memory Engine (High-level API)
# ============================================================================


class MemoryEngine:
    """
    High-level memory engine providing multi-layer memory operations.

    This is the main interface for MA-CLI components to interact with memory.
    """

    def __init__(self, backend: MemoryBackend | None = None):
        self.backend = backend or SQLiteMemoryBackend()
        self.backend.initialize()
        self._current_session_id: str | None = None
        self._current_project_id: str | None = "default-project"

    def set_context(
        self, session_id: str | None = None, project_id: str | None = "default-project"
    ) -> None:
        """Set the current context for memory operations."""
        self._current_session_id = session_id
        self._current_project_id = project_id

    # -------------------------------------------------------------------------
    # Conversation Memory
    # -------------------------------------------------------------------------

    def add_conversation_message(
        self,
        role: str,
        content: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a conversation message."""
        session_id = session_id or self._current_session_id
        message = ConversationMessage(
            role=role, content=content, session_id=session_id, metadata=metadata or {}
        )

        if isinstance(self.backend, SQLiteMemoryBackend):
            return self.backend.add_message(message)

        # Fallback: store as memory entry
        entry = MemoryEntry(
            memory_type=MemoryType.CONVERSATION,
            scope=MemoryScope.SESSION,
            key=f"msg_{len(self.get_conversation(session_id))}",
            content=content,
            metadata={"role": role, **metadata} if metadata else {"role": role},
            session_id=session_id,
        )
        return self.backend.store(entry)

    def get_conversation(
        self, session_id: str | None = None, limit: int = 50
    ) -> list[ConversationMessage]:
        """Get recent conversation messages."""
        session_id = session_id or self._current_session_id

        if isinstance(self.backend, SQLiteMemoryBackend):
            return self.backend.get_conversation(session_id, limit)

        # Fallback
        entries = self.backend.search(
            "", {"memory_type": MemoryType.CONVERSATION, "session_id": session_id}
        )
        return [
            ConversationMessage(
                content=e.content, role=e.metadata.get("role", "assistant"), session_id=e.session_id
            )
            for e in entries[-limit:]
        ]

    def clear_conversation(self, session_id: str | None = None) -> int:
        """Clear conversation for a session."""
        session_id = session_id or self._current_session_id

        if isinstance(self.backend, SQLiteMemoryBackend):
            return self.backend.clear_conversation(session_id)

        entries = self.backend.search(
            "", {"memory_type": MemoryType.CONVERSATION, "session_id": session_id}
        )
        count = 0
        for entry in entries:
            if self.backend.delete(entry.id):
                count += 1
        return count

    # -------------------------------------------------------------------------
    # Project Memory
    # -------------------------------------------------------------------------

    def store_project_context(
        self,
        key: str,
        value: Any,
        project_id: str | None = "default-project",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store project-specific context."""
        project_id = project_id or self._current_project_id

        entry = MemoryEntry(
            memory_type=MemoryType.PROJECT,
            scope=MemoryScope.PROJECT,
            key=key,
            value=value,
            content=str(value) if not isinstance(value, str) else value,
            metadata=metadata or {},
            project_id=project_id,
        )
        return self.backend.store(entry)

    def get_project_context(
        self, key: str, project_id: str | None = "default-project"
    ) -> Any | None:
        """Retrieve project-specific context."""
        project_id = project_id or self._current_project_id

        entries = self.backend.search(
            "", {"memory_type": MemoryType.PROJECT, "project_id": project_id}
        )

        for entry in entries:
            if entry.key == key:
                return entry.value

        return None

    def get_all_project_context(self, project_id: str | None = "default-project") -> dict[str, Any]:
        """Get all project context."""
        project_id = project_id or self._current_project_id

        entries = self.backend.search(
            "", {"memory_type": MemoryType.PROJECT, "project_id": project_id}
        )

        return {entry.key: entry.value for entry in entries}

    # -------------------------------------------------------------------------
    # Task Memory
    # -------------------------------------------------------------------------

    def store_task_context(
        self, task_id: str, key: str, value: Any, metadata: dict[str, Any] | None = None
    ) -> str:
        """Store task-specific context."""
        entry = MemoryEntry(
            memory_type=MemoryType.TASK,
            scope=MemoryScope.TASK,
            key=key,
            value=value,
            content=str(value) if not isinstance(value, str) else value,
            metadata=metadata or {},
            task_id=task_id,
        )
        return self.backend.store(entry)

    def get_task_context(self, task_id: str, key: str | None = None) -> Any | None:
        """Retrieve task-specific context."""
        filters = {"memory_type": MemoryType.TASK, "task_id": task_id}
        entries = self.backend.search("", filters)

        if key is None:
            return {e.key: e.value for e in entries}

        for entry in entries:
            if entry.key == key:
                return entry.value

        return None

    # -------------------------------------------------------------------------
    # Run Memory
    # -------------------------------------------------------------------------

    def store_run_context(
        self,
        run_id: str,
        request: str,
        plan: str | None = None,
        result: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store run context."""
        entry = MemoryEntry(
            memory_type=MemoryType.RUN,
            scope=MemoryScope.RUN,
            key=f"run_{run_id}",
            content=request,
            value={"request": request, "plan": plan, "result": result, **(metadata or {})},
            metadata=metadata or {},
            run_id=run_id,
        )
        return self.backend.store(entry)

    def get_run_context(self, run_id: str) -> dict[str, Any] | None:
        """Retrieve run context."""
        # Search for the entry by run_id
        entries = self.backend.search("", {"memory_type": MemoryType.RUN, "run_id": run_id})

        if not entries:
            return None

        return entries[0].value

    def get_run_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent run history."""
        entries = self.backend.search("", {"memory_type": MemoryType.RUN})
        return [e.value for e in entries[:limit]]

    # -------------------------------------------------------------------------
    # Agent Memory
    # -------------------------------------------------------------------------

    def store_agent_state(
        self, agent_id: str, state: dict[str, Any], metadata: dict[str, Any] | None = None
    ) -> str:
        """Store agent state."""
        entry = MemoryEntry(
            memory_type=MemoryType.AGENT,
            scope=MemoryScope.GLOBAL,
            key=f"agent_{agent_id}_state",
            value=state,
            metadata=metadata or {},
            agent_id=agent_id,
        )
        return self.backend.store(entry)

    def get_agent_state(self, agent_id: str) -> dict[str, Any] | None:
        """Retrieve agent state."""
        entries = self.backend.search("", {"memory_type": MemoryType.AGENT, "agent_id": agent_id})

        if not entries:
            return None

        return entries[0].value

    # -------------------------------------------------------------------------
    # Long-Term Memory
    # -------------------------------------------------------------------------

    def store_long_term(
        self,
        key: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        privacy_level: str = "normal",
    ) -> str:
        """Store long-term memory."""
        entry = MemoryEntry(
            memory_type=MemoryType.LONG_TERM,
            scope=MemoryScope.GLOBAL,
            key=key,
            content=content,
            metadata=metadata or {},
            privacy_level=privacy_level,
        )
        return self.backend.store(entry)

    def search_long_term(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search long-term memory."""
        return self.backend.search(query, {"memory_type": MemoryType.LONG_TERM})[:limit]

    def summarize_knowledge(self, topic: str, max_entries: int = 20) -> str:
        """Summarize knowledge about a topic."""
        entries = self.search_long_term(topic, max_entries)

        if not entries:
            return f"No knowledge found about: {topic}"

        # Simple summarization (can be enhanced with AI)
        summaries = []
        for entry in entries:
            summaries.append(f"- {entry.content[:200]}...")

        return f"Knowledge summary for '{topic}':\n\n" + "\n".join(summaries)

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def get_summary(self, filters: dict[str, Any] | None = None) -> MemorySummary:
        """Get memory summary."""
        return self.backend.get_summary(filters)

    def cleanup_old_memory(self, days: int = 90) -> int:
        """Clean up old memory entries."""
        cutoff = _now_utc() - timedelta(days=days)
        return self.backend.cleanup(cutoff)

    def export_memory(self, output_path: Path, filters: dict[str, Any] | None = None) -> int:
        """Export memory to JSON file."""
        entries = self.backend.search("", filters or {})

        data = {
            "exported_at": _now_utc().isoformat(),
            "total_entries": len(entries),
            "entries": [e.to_dict() for e in entries],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        return len(entries)

    def import_memory(self, input_path: Path) -> int:
        """Import memory from JSON file."""
        with open(input_path) as f:
            data = json.load(f)

        count = 0
        for entry_data in data.get("entries", []):
            entry = MemoryEntry.from_dict(entry_data)
            self.backend.store(entry)
            count += 1

        return count


# ============================================================================
# Session Manager with Memory Integration
# ============================================================================


@dataclass
class SessionState:
    """State of a MA-CLI session."""

    session_id: str
    started_at: datetime
    last_activity: datetime
    workspace_path: str | None
    project_id: str | None
    status: str = "active"  # active, paused, completed, failed
    request: str | None = None
    plan: str | None = None
    tasks: list[str] = field(default_factory=list)
    completed_tasks: list[str] = field(default_factory=list)
    pending_tasks: list[str] = field(default_factory=list)
    agent_states: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """
    Manages MA-CLI sessions with memory persistence.

    Supports session creation, suspension, resumption, and listing.
    """

    def __init__(self, memory_engine: MemoryEngine | None = None):
        self.memory = memory_engine or MemoryEngine()
        self._current_session: SessionState | None = None

    def create_session(
        self,
        workspace_path: str | None = None,
        project_id: str | None = "default-project",
        request: str | None = None,
    ) -> SessionState:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        now = _now_utc()

        state = SessionState(
            session_id=session_id,
            started_at=now,
            last_activity=now,
            workspace_path=workspace_path,
            project_id=project_id,
            request=request,
        )

        # Store in memory
        self.memory.store_run_context(
            run_id=session_id,
            request=request or "",
            metadata={
                "workspace_path": workspace_path,
                "project_id": project_id,
                "status": "active",
            },
        )

        self._current_session = state
        self.memory.set_context(session_id=session_id, project_id=project_id)

        return state

    def save_session(self, state: SessionState | None = None) -> None:
        """Save session state."""
        state = state or self._current_session
        if state is None:
            return

        state.last_activity = _now_utc()

        self.memory.store_run_context(
            run_id=state.session_id,
            request=state.request or "",
            plan=state.plan,
            result=json.dumps(
                {
                    "completed_tasks": state.completed_tasks,
                    "pending_tasks": state.pending_tasks,
                    "outputs": state.outputs,
                    "errors": state.errors,
                    "agent_states": state.agent_states,
                }
            ),
            metadata={
                "status": state.status,
                "workspace_path": state.workspace_path,
                "project_id": state.project_id,
                "tasks": state.tasks,
                "last_activity": state.last_activity.isoformat(),
            },
        )

    def load_session(self, session_id: str) -> SessionState | None:
        """Load a session by ID."""
        run_data = self.memory.get_run_context(session_id)

        if run_data is None:
            return None

        # Find the memory entry for this run
        entries = self.memory.backend.search(
            "", {"memory_type": MemoryType.RUN, "run_id": session_id}
        )

        if not entries:
            return None

        entry = entries[0]
        metadata = entry.metadata

        # Reconstruct session state
        result_data = json.loads(run_data.get("result", "{}")) if run_data.get("result") else {}

        state = SessionState(
            session_id=session_id,
            started_at=entry.created_at,
            last_activity=datetime.fromisoformat(
                metadata.get("last_activity", entry.updated_at.isoformat())
            ),
            workspace_path=metadata.get("workspace_path"),
            project_id=metadata.get("project_id"),
            status=metadata.get("status", "active"),
            request=run_data.get("request"),
            plan=run_data.get("plan"),
            tasks=metadata.get("tasks", []),
            completed_tasks=result_data.get("completed_tasks", []),
            pending_tasks=result_data.get("pending_tasks", []),
            agent_states=result_data.get("agent_states", {}),
            outputs=result_data.get("outputs", {}),
            errors=result_data.get("errors", []),
        )

        self._current_session = state
        self.memory.set_context(session_id=session_id, project_id=state.project_id)

        return state

    def get_active_sessions(self) -> list[SessionState]:
        """Get all active sessions."""
        entries = self.memory.backend.search("", {"memory_type": MemoryType.RUN})

        active_sessions = []
        for entry in entries:
            metadata = entry.metadata
            if metadata.get("status") == "active":
                state = self.load_session(entry.run_id)
                if state:
                    active_sessions.append(state)

        return active_sessions

    def get_recent_sessions(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent sessions."""
        entries = self.memory.backend.search("", {"memory_type": MemoryType.RUN})[:limit]

        return [
            {
                "session_id": e.run_id,
                "started_at": e.created_at.isoformat(),
                "last_activity": e.updated_at.isoformat(),
                "status": e.metadata.get("status", "unknown"),
                "request": e.content[:100] + "..." if len(e.content) > 100 else e.content,
                "workspace_path": e.metadata.get("workspace_path"),
            }
            for e in entries
        ]

    def resume_session(self, session_id: str) -> SessionState | None:
        """Resume a session."""
        state = self.load_session(session_id)
        if state:
            state.status = "active"
            self.save_session(state)
        return state

    def end_session(self, session_id: str | None = None, status: str = "completed") -> None:
        """End a session."""
        session_id = session_id or (
            self._current_session.session_id if self._current_session else None
        )
        if session_id is None:
            return

        state = self.load_session(session_id)
        if state:
            state.status = status
            self.save_session(state)

        if self._current_session and self._current_session.session_id == session_id:
            self._current_session = None

    def get_current_session(self) -> SessionState | None:
        """Get current session."""
        return self._current_session


# ============================================================================
# Factory Functions
# ============================================================================


def create_memory_engine(db_path: Path | None = None) -> MemoryEngine:
    """Create a memory engine instance."""
    backend = SQLiteMemoryBackend(db_path)
    return MemoryEngine(backend)


def create_session_manager(memory_engine: MemoryEngine | None = None) -> SessionManager:
    """Create a session manager instance."""
    return SessionManager(memory_engine)


# ============================================================================
# CLI Helper Functions
# ============================================================================


def format_memory_summary(summary: MemorySummary) -> str:
    """Format memory summary for display."""
    lines = [
        f"Total Entries: {summary.total_entries}",
        f"Storage Size: {summary.storage_size_bytes:,} bytes",
        "",
        "By Type:",
    ]

    for mem_type, count in sorted(summary.by_type.items()):
        lines.append(f"  {mem_type}: {count}")

    lines.append("")
    lines.append("By Scope:")

    for scope, count in sorted(summary.by_scope.items()):
        lines.append(f"  {scope}: {count}")

    if summary.oldest_entry:
        lines.append(f"\nOldest Entry: {summary.oldest_entry.isoformat()}")
    if summary.newest_entry:
        lines.append(f"Newest Entry: {summary.newest_entry.isoformat()}")

    return "\n".join(lines)


def format_session_list(sessions: list[dict[str, Any]]) -> str:
    """Format session list for display."""
    if not sessions:
        return "No sessions found."

    lines = ["Sessions:", ""]

    for i, session in enumerate(sessions, 1):
        status_icon = "●" if session.get("status") == "active" else "○"
        lines.append(f"{i}. {status_icon} {session.get('session_id', 'N/A')[:8]}...")
        lines.append(f"   Status: {session.get('status', 'unknown')}")
        lines.append(f"   Request: {session.get('request', 'N/A')[:50]}...")
        lines.append(f"   Last Activity: {session.get('last_activity', 'N/A')}")
        lines.append("")

    return "\n".join(lines)
