"""
State Manager for MA-CLI.

This module handles persistent state management using SQLite.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.models import (
    AgentStatus,
    AutonomyLevel,
    Event,
    HealthStatus,
    State,
    Task,
    TaskStatus,
)


class StateManager:
    """
    Persistent state manager using SQLite.

    Provides storage and retrieval for MA-CLI runtime state,
    tasks, sessions, and execution history.
    """

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            # Default to ~/.ma-cli/state/ma_cli.db
            db_path = Path.home() / ".ma-cli" / "state" / "ma_cli.db"

        self.db_path = db_path
        self._ensure_db_exists()
        self._current_session_id: str | None = None

    def _ensure_db_exists(self) -> None:
        """Ensure database file and tables exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    autonomy_level INTEGER,
                    workspace_path TEXT,
                    started_at TEXT,
                    last_activity TEXT,
                    status TEXT
                )
            """)

            # Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    title TEXT,
                    description TEXT,
                    status TEXT,
                    priority INTEGER,
                    assigned_agent TEXT,
                    assigned_role TEXT,
                    created_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    result TEXT,
                    error TEXT,
                    outputs TEXT,
                    metadata TEXT,
                    dependencies TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            # Agent states table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_states (
                    session_id TEXT,
                    agent_id TEXT,
                    status TEXT,
                    health TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (session_id, agent_id),
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            # Events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    event_type TEXT,
                    payload TEXT,
                    timestamp TEXT,
                    source TEXT,
                    correlation_id TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            # Run history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    request TEXT,
                    plan TEXT,
                    status TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    result TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def start_session(self, workspace_path: str | None = None) -> str:
        """
        Start a new session.

        Args:
            workspace_path: Optional workspace path

        Returns:
            Session ID
        """
        import uuid

        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sessions (session_id, autonomy_level, workspace_path, started_at, last_activity, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id,
                    AutonomyLevel.SUPERVISED_AUTO.value,
                    workspace_path,
                    now,
                    now,
                    "active",
                ),
            )
            conn.commit()

        self._current_session_id = session_id
        return session_id

    def get_current_session_id(self) -> str | None:
        """Get current session ID."""
        return self._current_session_id

    def set_current_session_id(self, session_id: str) -> None:
        """Set current session ID."""
        self._current_session_id = session_id

    def load_state(self, session_id: str | None = None) -> State:
        """
        Load state for a session.

        Args:
            session_id: Session ID (uses current if None)

        Returns:
            State object
        """
        session_id = session_id or self._current_session_id

        if session_id is None:
            return State()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM sessions WHERE session_id = ?
            """,
                (session_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return State()

            # Load active tasks
            cursor.execute(
                """
                SELECT id FROM tasks
                WHERE session_id = ? AND status IN (?, ?)
            """,
                (session_id, TaskStatus.RUNNING.value, TaskStatus.QUEUED.value),
            )

            active_tasks = [r["id"] for r in cursor.fetchall()]
            queued_tasks = [r["id"] for r in cursor.fetchall()]

            # Load agent states
            cursor.execute(
                """
                SELECT agent_id, status, health FROM agent_states WHERE session_id = ?
            """,
                (session_id,),
            )

            agent_states = {}
            for row in cursor.fetchall():
                agent_states[row["agent_id"]] = AgentStatus(row["status"])

            # Parse autonomy level
            autonomy_level = AutonomyLevel(row["autonomy_level"])

            return State(
                session_id=session_id,
                autonomy_level=autonomy_level,
                active_task_ids=active_tasks,
                queued_task_ids=queued_tasks,
                agent_states=agent_states,
                workspace_path=row["workspace_path"],
                started_at=datetime.fromisoformat(row["started_at"]),
                last_activity=datetime.fromisoformat(row["last_activity"]),
            )

    def save_state(self, state: State) -> None:
        """
        Save state for current session.

        Args:
            state: State to save
        """
        session_id = state.session_id

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions
                SET autonomy_level = ?, workspace_path = ?, last_activity = ?
                WHERE session_id = ?
            """,
                (
                    state.autonomy_level.value,
                    state.workspace_path,
                    state.last_activity.isoformat(),
                    session_id,
                ),
            )

            # Save agent states
            for agent_id, status in state.agent_states.items():
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO agent_states (session_id, agent_id, status, health, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        session_id,
                        agent_id,
                        status.value,
                        HealthStatus.HEALTHY.value,
                        datetime.utcnow().isoformat(),
                    ),
                )

            conn.commit()

    def save_task(self, task: Task, session_id: str | None = None) -> None:
        """Save a task to the database."""
        session_id = session_id or self._current_session_id

        if session_id is None:
            raise ValueError("No session ID available")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO tasks
                (id, session_id, title, description, status, priority, assigned_agent,
                 assigned_role, created_at, started_at, completed_at, result, error,
                 outputs, metadata, dependencies)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task.id,
                    session_id,
                    task.title,
                    task.description,
                    task.status.value,
                    task.priority,
                    task.assigned_agent,
                    task.assigned_role,
                    task.created_at.isoformat() if task.created_at else None,
                    task.started_at.isoformat() if task.started_at else None,
                    task.completed_at.isoformat() if task.completed_at else None,
                    task.result,
                    task.error,
                    json.dumps(task.outputs),
                    json.dumps(task.metadata),
                    json.dumps(task.dependencies),
                ),
            )
            conn.commit()

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM tasks WHERE id = ?
            """,
                (task_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return Task(
                id=row["id"],
                title=row["title"],
                description=row["description"],
                status=TaskStatus(row["status"]),
                priority=row["priority"],
                assigned_agent=row["assigned_agent"],
                assigned_role=row["assigned_role"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
                started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                completed_at=datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None,
                result=row["result"],
                error=row["error"],
                outputs=json.loads(row["outputs"]) if row["outputs"] else {},
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                dependencies=json.loads(row["dependencies"]) if row["dependencies"] else [],
            )

    def get_tasks_by_status(self, status: TaskStatus, session_id: str | None = None) -> list[Task]:
        """Get all tasks with a specific status."""
        session_id = session_id or self._current_session_id

        if session_id is None:
            return []

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM tasks WHERE session_id = ? AND status = ?
            """,
                (session_id, status.value),
            )

            tasks = []
            for row in cursor.fetchall():
                tasks.append(
                    Task(
                        id=row["id"],
                        title=row["title"],
                        description=row["description"],
                        status=TaskStatus(row["status"]),
                        priority=row["priority"],
                        assigned_agent=row["assigned_agent"],
                        assigned_role=row["assigned_role"],
                        created_at=datetime.fromisoformat(row["created_at"])
                        if row["created_at"]
                        else None,
                        started_at=datetime.fromisoformat(row["started_at"])
                        if row["started_at"]
                        else None,
                        completed_at=datetime.fromisoformat(row["completed_at"])
                        if row["completed_at"]
                        else None,
                        result=row["result"],
                        error=row["error"],
                        outputs=json.loads(row["outputs"]) if row["outputs"] else {},
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                        dependencies=json.loads(row["dependencies"]) if row["dependencies"] else [],
                    )
                )

            return tasks

    def record_event(self, event: Event, session_id: str | None = None) -> None:
        """Record an event to the database."""
        session_id = session_id or self._current_session_id

        if session_id is None:
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO events (session_id, event_type, payload, timestamp, source, correlation_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id,
                    event.event_type.value,
                    json.dumps(event.payload),
                    event.timestamp.isoformat(),
                    event.source,
                    event.correlation_id,
                ),
            )
            conn.commit()

    def get_events(self, session_id: str | None = None, limit: int = 100) -> list[Event]:
        """Get recent events."""
        session_id = session_id or self._current_session_id

        if session_id is None:
            return []

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM events
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (session_id, limit),
            )

            events = []
            for row in cursor.fetchall():
                events.append(
                    Event(
                        event_type=EventType(row["event_type"]),
                        payload=json.loads(row["payload"]),
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        source=row["source"],
                        correlation_id=row["correlation_id"],
                    )
                )

            return events

    def end_session(self, session_id: str | None = None) -> None:
        """End a session."""
        session_id = session_id or self._current_session_id

        if session_id is None:
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions SET status = ? WHERE session_id = ?
            """,
                ("ended", session_id),
            )
            conn.commit()

        if self._current_session_id == session_id:
            self._current_session_id = None

    def get_recent_sessions(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent sessions."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM sessions ORDER BY last_activity DESC LIMIT ?
            """,
                (limit,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def resume_last_session(self) -> str | None:
        """Resume the last active session."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id FROM sessions
                WHERE status = 'active'
                ORDER BY last_activity DESC
                LIMIT 1
            """)
            row = cursor.fetchone()

            if row:
                self._current_session_id = row["session_id"]
                return row["session_id"]

        return None

    def cleanup_old_sessions(self, days: int = 7) -> int:
        """Clean up sessions older than specified days."""
        from datetime import timedelta

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Delete old events
            cursor.execute(
                """
                DELETE FROM events WHERE session_id IN (
                    SELECT session_id FROM sessions WHERE last_activity < ?
                )
            """,
                (cutoff,),
            )

            # Delete old tasks
            cursor.execute(
                """
                DELETE FROM tasks WHERE session_id IN (
                    SELECT session_id FROM sessions WHERE last_activity < ?
                )
            """,
                (cutoff,),
            )

            # Delete old agent states
            cursor.execute(
                """
                DELETE FROM agent_states WHERE session_id IN (
                    SELECT session_id FROM sessions WHERE last_activity < ?
                )
            """,
                (cutoff,),
            )

            # Count and delete old sessions
            cursor.execute(
                """
                SELECT COUNT(*) FROM sessions WHERE last_activity < ? AND status != 'active'
            """,
                (cutoff,),
            )
            count = cursor.fetchone()[0]

            cursor.execute(
                """
                DELETE FROM sessions WHERE last_activity < ? AND status != 'active'
            """,
                (cutoff,),
            )

            conn.commit()
            return count


# Import EventType here to avoid circular imports
from ..core.models import EventType

# Global state manager instance
_state_manager: StateManager | None = None


def get_state_manager(db_path: Path | None = None) -> StateManager:
    """Get global state manager instance."""
    global _state_manager
    if _state_manager is None or (db_path and _state_manager.db_path != db_path):
        _state_manager = StateManager(db_path)
    return _state_manager
