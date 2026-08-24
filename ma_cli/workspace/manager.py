"""
Cross-platform workspace and file-lock management for MA-CLI.
"""
from __future__ import annotations

import os
import shutil
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import portalocker


@dataclass
class WorkspaceInfo:
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
    path: Path
    locked_by: str
    locked_at: datetime
    purpose: str = ""


class FileLockManager:
    """Cross-platform advisory file locks with timeout support."""

    def __init__(self, lock_dir: Path | None = None):
        self.lock_dir = lock_dir or (Path.home() / ".ma-cli" / "locks")
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._held_locks: dict[str, tuple[Any, Path]] = {}

    def _get_lock_path(self, path: Path) -> Path:
        # Stable across processes/machines; unlike Python's hash(), this does not
        # change between interpreter invocations.
        import hashlib
        digest = hashlib.sha256(str(path.absolute()).encode("utf-8")).hexdigest()[:32]
        return self.lock_dir / f"{digest}.lock"

    @contextmanager
    def acquire(self, path: Path, purpose: str = "", timeout: int = 30):
        lock_path = self._get_lock_path(path)
        lock_file = open(lock_path, "a+", encoding="utf-8")
        try:
            portalocker.lock(lock_file, portalocker.LOCK_EX, timeout=timeout)
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(f"ma-cli|{datetime.utcnow().isoformat()}|{purpose}")
            lock_file.flush()
            self._held_locks[str(path)] = (lock_file, lock_path)
            yield True
        finally:
            self._held_locks.pop(str(path), None)
            try:
                portalocker.unlock(lock_file)
            finally:
                lock_file.close()
                try:
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def is_locked(self, path: Path) -> bool:
        lock_path = self._get_lock_path(path)
        if not lock_path.exists():
            return False
        try:
            with open(lock_path, "a+", encoding="utf-8") as probe:
                portalocker.lock(probe, portalocker.LOCK_EX | portalocker.LOCK_NB)
                portalocker.unlock(probe)
            return False
        except portalocker.exceptions.LockException:
            return True

    def get_lock_info(self, path: Path) -> FileLock | None:
        lock_path = self._get_lock_path(path)
        if not lock_path.exists():
            return None
        try:
            content = lock_path.read_text(encoding="utf-8").strip()
            parts = content.split("|", 2)
            if len(parts) >= 2:
                return FileLock(path, parts[0], datetime.fromisoformat(parts[1]), parts[2] if len(parts) == 3 else "")
        except (OSError, ValueError):
            pass
        return None

    def release_all(self) -> None:
        for path, (lock_file, lock_path) in list(self._held_locks.items()):
            try:
                portalocker.unlock(lock_file)
                lock_file.close()
                lock_path.unlink(missing_ok=True)
            except OSError:
                pass
            self._held_locks.pop(path, None)


class WorkspaceManager:
    """Manage isolated task workspaces."""

    def __init__(self, base_path: Path | None = None):
        self.base_path = base_path or (Path.home() / ".ma-cli" / "workspaces")
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.lock_manager = FileLockManager()
        self._current_workspace: WorkspaceInfo | None = None
        self._workspaces: dict[str, WorkspaceInfo] = {}

    def create_workspace(self, name: str | None = None, task_id: str | None = None,
                         source_path: Path | None = None, isolated: bool = True) -> WorkspaceInfo:
        name = name or f"ws-{uuid.uuid4().hex[:8]}"
        ws_path = self.base_path / name
        ws_path.mkdir(parents=True, exist_ok=True)
        if source_path and isolated:
            for item in source_path.iterdir():
                if item.name.startswith("."):
                    continue
                target = ws_path / item.name
                if item.is_dir():
                    shutil.copytree(item, target, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, target)
        workspace = WorkspaceInfo(str(uuid.uuid4()), name, ws_path, task_id=task_id, is_isolated=isolated)
        self._workspaces[name] = workspace
        return workspace

    def get_workspace(self, name: str) -> WorkspaceInfo | None:
        return self._workspaces.get(name)

    def switch_workspace(self, name: str) -> bool:
        workspace = self.get_workspace(name)
        if not workspace:
            return False
        self._current_workspace = workspace
        return True

    @contextmanager
    def use_workspace(self, name: str):
        old = self._current_workspace
        if not self.switch_workspace(name):
            raise ValueError(f"Workspace '{name}' not found")
        try:
            yield self._current_workspace
        finally:
            self._current_workspace = old

    @property
    def current_workspace(self) -> WorkspaceInfo | None:
        return self._current_workspace

    @property
    def current_path(self) -> Path:
        return self._current_workspace.path if self._current_workspace else Path.cwd()

    def list_workspaces(self) -> list[WorkspaceInfo]:
        return list(self._workspaces.values())

    def delete_workspace(self, name: str) -> bool:
        workspace = self._workspaces.get(name)
        if not workspace:
            return False
        try:
            shutil.rmtree(workspace.path, ignore_errors=True)
            del self._workspaces[name]
            if self._current_workspace and self._current_workspace.name == name:
                self._current_workspace = None
            return True
        except OSError:
            return False

    def cleanup_old_workspaces(self, days: int = 7) -> int:
        cutoff = datetime.utcnow() - timedelta(days=days)
        cleaned = 0
        for name, ws in list(self._workspaces.items()):
            if ws.created_at < cutoff and ws.task_id is None and self.delete_workspace(name):
                cleaned += 1
        return cleaned

    @contextmanager
    def file_lock(self, path: Path, purpose: str = ""):
        with self.lock_manager.acquire(path, purpose):
            yield True

    def get_relative_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.current_path))
        except ValueError:
            return str(path)

    def resolve_path(self, path: str) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else self.current_path / candidate

    def ensure_directory(self, path: str) -> Path:
        full_path = self.resolve_path(path)
        full_path.mkdir(parents=True, exist_ok=True)
        return full_path


_workspace_manager: WorkspaceManager | None = None


def get_workspace_manager(base_path: Path | None = None) -> WorkspaceManager:
    global _workspace_manager
    if _workspace_manager is None or (base_path and _workspace_manager.base_path != base_path):
        _workspace_manager = WorkspaceManager(base_path)
    return _workspace_manager
