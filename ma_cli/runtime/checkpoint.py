"""Small durable checkpoint store for resumable autonomous runs."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RunCheckpoint:
    run_id: str
    prompt: str
    state: str = "PENDING"
    completed_tasks: list[str] = field(default_factory=list)
    current_task: str | None = None
    attempts: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)


class CheckpointStore:
    """Atomic JSON checkpoint store; secrets are caller responsibility and should not be persisted."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.directory = self.root / ".aio-cli" / "checkpoints"
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, run_id: str) -> Path:
        safe = "".join(c for c in run_id if c.isalnum() or c in "-_")
        if not safe or safe != run_id:
            raise ValueError("invalid run_id")
        return self.directory / f"{safe}.json"

    def save(self, checkpoint: RunCheckpoint) -> None:
        checkpoint.updated_at = time.time()
        target = self._path(checkpoint.run_id)
        payload = json.dumps(asdict(checkpoint), ensure_ascii=False, indent=2)
        with self._lock:
            fd, tmp = tempfile.mkstemp(prefix="checkpoint-", suffix=".tmp", dir=self.directory)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp, target)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)

    def load(self, run_id: str) -> RunCheckpoint | None:
        target = self._path(run_id)
        if not target.exists():
            return None
        try:
            return RunCheckpoint(**json.loads(target.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"corrupt checkpoint: {run_id}") from exc

    def delete(self, run_id: str) -> None:
        self._path(run_id).unlink(missing_ok=True)
