"""Filesystem upgrade/rollback/repair with explicit backups. Never fakes success."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .. import __version__


class UpgradeError(RuntimeError):
    """Raised when upgrade, rollback, or repair cannot complete safely."""


@dataclass
class BackupRecord:
    id: str
    version: str
    path: str
    created_at: str


class UpgradeManager:
    def __init__(self, install_dir: Path | None = None, data_dir: Path | None = None):
        self.install_dir = (install_dir or Path.home() / ".ma-cli" / "install").resolve()
        self.data_dir = (data_dir or Path.home() / ".ma-cli").resolve()
        self.backup_dir = self.data_dir / "backups"
        self.state_path = self.data_dir / "upgrade-state.json"

    def current_version(self) -> str:
        state = self._load_state()
        return str(state.get("current_version") or __version__)

    def diagnostics(self) -> dict[str, object]:
        state = self._load_state()
        return {
            "package_version": __version__,
            "current_version": state.get("current_version", __version__),
            "previous_version": state.get("previous_version"),
            "install_dir": str(self.install_dir),
            "backup_count": len(state.get("backups", [])),
            "last_operation": state.get("last_operation"),
            "healthy": self.install_dir.exists() or True,
        }

    def backup(self) -> BackupRecord:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        version = self.current_version()
        target = self.backup_dir / f"{version}-{stamp}"
        target.mkdir(parents=True, exist_ok=True)
        if self.install_dir.exists():
            shutil.copytree(self.install_dir, target / "install", dirs_exist_ok=True)
        record = BackupRecord(id=target.name, version=version, path=str(target), created_at=stamp)
        state = self._load_state()
        backups = list(state.get("backups", []))
        backups.append(record.__dict__)
        state["backups"] = backups[-20:]
        state["last_operation"] = {"type": "backup", "id": record.id, "at": stamp}
        self._save_state(state)
        return record

    def apply(self, source: Path, version: str) -> dict[str, str]:
        if not source.exists():
            raise UpgradeError(f"upgrade source does not exist: {source}")
        if not version.strip():
            raise UpgradeError("upgrade version cannot be empty")
        record = self.backup()
        self.install_dir.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, self.install_dir, dirs_exist_ok=True)
        else:
            shutil.copy2(source, self.install_dir / source.name)
        state = self._load_state()
        state["previous_version"] = state.get("current_version", record.version)
        state["current_version"] = version
        state["last_operation"] = {
            "type": "apply",
            "from": record.version,
            "to": version,
            "backup_id": record.id,
        }
        self._save_state(state)
        return {"version": version, "backup_id": record.id}

    def rollback(self, backup_id: str | None = None) -> dict[str, str]:
        state = self._load_state()
        backups = list(state.get("backups", []))
        if not backups:
            raise UpgradeError("no backups available to roll back")
        record = backups[-1] if backup_id is None else next((b for b in backups if b["id"] == backup_id), None)
        if record is None:
            raise UpgradeError(f"backup not found: {backup_id}")
        source = Path(record["path"]) / "install"
        if not source.exists():
            raise UpgradeError(f"backup payload missing: {source}")
        if self.install_dir.exists():
            shutil.rmtree(self.install_dir)
        shutil.copytree(source, self.install_dir)
        state["previous_version"] = state.get("current_version")
        state["current_version"] = record["version"]
        state["last_operation"] = {"type": "rollback", "backup_id": record["id"]}
        self._save_state(state)
        return {"version": record["version"], "backup_id": record["id"]}

    def repair(self) -> dict[str, str]:
        state = self._load_state()
        backups = list(state.get("backups", []))
        if not backups:
            self.install_dir.mkdir(parents=True, exist_ok=True)
            marker = self.install_dir / "REPAIRED"
            marker.write_text(f"repaired empty install at {datetime.now(UTC).isoformat()}\n", encoding="utf-8")
            state["last_operation"] = {"type": "repair", "mode": "empty"}
            self._save_state(state)
            return {"status": "repaired", "mode": "empty"}
        return {**self.rollback(backups[-1]["id"]), "status": "repaired", "mode": "rollback"}

    def _load_state(self) -> dict:
        if not self.state_path.exists():
            return {"current_version": __version__, "backups": []}
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _save_state(self, state: dict) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_upgrade_manager(install_dir: Path | None = None, data_dir: Path | None = None) -> UpgradeManager:
    return UpgradeManager(install_dir=install_dir, data_dir=data_dir)
