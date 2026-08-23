"""
Workspace Manager for MA-CLI.

This module handles workspace isolation, file locks, and task workspaces.
"""

from __future__ import annotations

import fcntl
import os
import shutil
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class WorkspaceInfo:
    """Information about a workspace."""

    id: str
    name: str
    path: Path
    created_at: datetime = field(default_factory=datetime.utcnow)
    task_id: str | None = None
    branch: str | None = None
    is_isolated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FileLock:
    """Represents a file lock."""

    path: Path
    locked_by: str
    locked_at: datetime
    purpose: str = ""


class FileLockManager:
    """
    Manages file locks to prevent concurrent modification conflicts.
    """

    def __init__(self, lock_dir: Path | None = None):
        if lock_dir is None:
            lock_dir = Path.home() / ".ma-cli" / "locks"

        self.lock_dir = lock_dir
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._held_locks: dict[str, tuple[fcntl.flock, Path]] = {}

    def _get_lock_path(self, path: Path) -> Path:
        """Get the lock file path for a given file."""
        # Create a unique lock file name based on the path
        path_hash = hash(str(path.absolute()))
        return self.lock_dir / f"{path_hash}.lock"

    @contextmanager
    def acquire(self, path: Path, purpose: str = "", timeout: int = 30):
        """
        Acquire a file lock with context manager.

        Args:
            path: Path to lock
            purpose: Reason for locking
            timeout: Timeout in seconds

        Yields:
            True if lock acquired

        Raises:
            TimeoutError: If lock cannot be acquired within timeout
        """
        lock_path = self._get_lock_path(path)
        lock_file = open(lock_path, "w")

        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError(f"Could not acquire lock for {path} within {timeout}s")

        # Set timeout
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)

        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            self._held_locks[str(path)] = (lock_file, lock_path)
            yield True
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

            # Release lock
            if str(path) in self._held_locks:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
                del self._held_locks[str(path)]
                try:
                    lock_path.unlink(missing_ok=True)
                except Exception:
                    pass

    def is_locked(self, path: Path) -> bool:
        """Check if a path is currently locked."""
        lock_path = self._get_lock_path(path)
        if not lock_path.exists():
            return False

        try:
            test_file = open(lock_path)
            fcntl.flock(test_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(test_file.fileno(), fcntl.LOCK_UN)
            test_file.close()
            return False
        except OSError:
            return True

    def get_lock_info(self, path: Path) -> FileLock | None:
        """Get information about a lock."""
        lock_path = self._get_lock_path(path)
        if not lock_path.exists():
            return None

        try:
            with open(lock_path) as f:
                content = f.read().strip()
                if content:
                    parts = content.split("|")
                    if len(parts) >= 2:
                        return FileLock(
                            path=path,
                            locked_by=parts[0],
                            locked_at=datetime.fromisoformat(parts[1]),
                            purpose=parts[2] if len(parts) > 2 else "",
                        )
        except Exception:
            pass

        return None

    def release_all(self) -> None:
        """Release all held locks."""
        for _path_str, (lock_file, lock_path) in list(self._held_locks.items()):
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
                lock_path.unlink(missing_ok=True)
            except Exception:
                pass

        self._held_locks.clear()


class WorkspaceManager:
    """
    Manages workspaces for task isolation.

    Provides workspace creation, switching, and cleanup functionality.
    """

    def __init__(self, base_path: Path | None = None):
        if base_path is None:
            base_path = Path.home() / ".ma-cli" / "workspaces"

        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.lock_manager = FileLockManager()
        self._current_workspace: WorkspaceInfo | None = None
        self._workspaces: dict[str, WorkspaceInfo] = {}

    def create_workspace(
        self,
        name: str | None = None,
        task_id: str | None = None,
        source_path: Path | None = None,
        isolated: bool = True,
    ) -> WorkspaceInfo:
        """
        Create a new workspace.

        Args:
            name: Workspace name (auto-generated if None)
            task_id: Associated task ID
            source_path: Optional source to copy from
            isolated: Whether to create isolated copy

        Returns:
            WorkspaceInfo for the created workspace
        """
        import uuid

        if name is None:
            name = f"ws-{uuid.uuid4().hex[:8]}"

        ws_path = self.base_path / name
        ws_path.mkdir(parents=True, exist_ok=True)

        # Copy source if provided
        if source_path and isolated:
            for item in source_path.iterdir():
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    shutil.copytree(item, ws_path / item.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, ws_path / item.name)

        workspace = WorkspaceInfo(
            id=str(uuid.uuid4()), name=name, path=ws_path, task_id=task_id, is_isolated=isolated
        )

        self._workspaces[name] = workspace
        return workspace

    def get_workspace(self, name: str) -> WorkspaceInfo | None:
        """Get workspace by name."""
        return self._workspaces.get(name)

    def switch_workspace(self, name: str) -> bool:
        """
        Switch to a different workspace.

        Args:
            name: Workspace name

        Returns:
            True if successful
        """
        workspace = self.get_workspace(name)
        if not workspace:
            return False

        self._current_workspace = workspace
        return True

    @contextmanager
    def use_workspace(self, name: str):
        """
        Context manager for temporary workspace switching.

        Args:
            name: Workspace name to use

        Yields:
            WorkspaceInfo
        """
        old_workspace = self._current_workspace

        if not self.switch_workspace(name):
            raise ValueError(f"Workspace '{name}' not found")

        try:
            yield self._current_workspace
        finally:
            self._current_workspace = old_workspace

    @property
    def current_workspace(self) -> WorkspaceInfo | None:
        """Get current workspace."""
        return self._current_workspace

    @property
    def current_path(self) -> Path:
        """Get current workspace path."""
        if self._current_workspace:
            return self._current_workspace.path
        return Path.cwd()

    def list_workspaces(self) -> list[WorkspaceInfo]:
        """List all workspaces."""
        return list(self._workspaces.values())

    def delete_workspace(self, name: str) -> bool:
        """
        Delete a workspace.

        Args:
            name: Workspace name

        Returns:
            True if deleted successfully
        """
        workspace = self.get_workspace(name)
        if not workspace:
            return False

        try:
            if workspace.path.exists():
                shutil.rmtree(workspace.path)

            del self._workspaces[name]

            if self._current_workspace and self._current_workspace.name == name:
                self._current_workspace = None

            return True
        except Exception:
            return False

    def cleanup_old_workspaces(self, days: int = 7) -> int:
        """Clean up workspaces older than specified days."""
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)
        cleaned = 0

        for name, ws in list(self._workspaces.items()):
            if ws.created_at < cutoff and ws.task_id is None:
                if self.delete_workspace(name):
                    cleaned += 1

        return cleaned

    @contextmanager
    def file_lock(self, path: Path, purpose: str = ""):
        """
        Acquire a file lock within workspace context.

        Args:
            path: Path to lock
            purpose: Lock purpose

        Yields:
            True if lock acquired
        """
        with self.lock_manager.acquire(path, purpose):
            yield True

    def get_relative_path(self, path: Path) -> str:
        """Get path relative to current workspace."""
        try:
            return str(path.relative_to(self.current_path))
        except ValueError:
            return str(path)

    def resolve_path(self, path: str) -> Path:
        """Resolve a path within current workspace."""
        if os.path.isabs(path):
            return Path(path)
        return self.current_path / path

    def ensure_directory(self, path: str) -> Path:
        """Ensure a directory exists within workspace."""
        full_path = self.resolve_path(path)
        full_path.mkdir(parents=True, exist_ok=True)
        return full_path


# Global workspace manager instance
_workspace_manager: WorkspaceManager | None = None


def get_workspace_manager(base_path: Path | None = None) -> WorkspaceManager:
    """Get global workspace manager instance."""
    global _workspace_manager
    if _workspace_manager is None or (base_path and _workspace_manager.base_path != base_path):
        _workspace_manager = WorkspaceManager(base_path)
    return _workspace_manager
