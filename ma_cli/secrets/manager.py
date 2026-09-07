"""Encrypted local secret store. Values never appear in logs; file mode is 0600."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import stat
from pathlib import Path

_REDACTED = "***"
_PBKDF2_ROUNDS = 200_000
_VERSION = 1


class SecretsError(RuntimeError):
    """Raised for secret-store failures."""


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def _default_master() -> bytes:
    env = os.environ.get("MA_CLI_MASTER_KEY")
    if env:
        return env.encode("utf-8")
    identity = f"{os.environ.get('USER', os.environ.get('USERNAME', 'ma-cli'))}:{Path.home()}"
    return hashlib.sha256(identity.encode("utf-8")).digest()


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        out.extend(hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest())
        counter += 1
    return bytes(out[:length])


class SecretStore:
    def __init__(self, path: Path | None = None, master_key: bytes | None = None):
        self.path = path or (Path.home() / ".ma-cli" / "secrets.json")
        self._master = master_key or _default_master()

    def set(self, name: str, value: str) -> None:
        name = self._validate_name(name)
        if not value:
            raise SecretsError("secret value cannot be empty")
        envelope, entries = self._load_envelope()
        entries[name] = value
        self._save_envelope(envelope, entries)

    def get(self, name: str) -> str:
        name = self._validate_name(name)
        _, entries = self._load_envelope()
        if name not in entries:
            raise SecretsError(f"secret not found: {name}")
        return entries[name]

    def delete(self, name: str) -> None:
        name = self._validate_name(name)
        envelope, entries = self._load_envelope()
        if name not in entries:
            raise SecretsError(f"secret not found: {name}")
        del entries[name]
        self._save_envelope(envelope, entries)

    def list_names(self) -> list[str]:
        _, entries = self._load_envelope()
        return sorted(entries)

    def redact(self, text: str) -> str:
        redacted = text
        _, entries = self._load_envelope()
        for value in entries.values():
            if value:
                redacted = redacted.replace(value, _REDACTED)
        return redacted

    def _validate_name(self, name: str) -> str:
        cleaned = name.strip().upper().replace("-", "_")
        if not cleaned or not cleaned.replace("_", "").isalnum():
            raise SecretsError("invalid secret name")
        return cleaned

    def _derive(self, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", self._master, salt, _PBKDF2_ROUNDS, dklen=32)

    def _encrypt(self, key: bytes, plaintext: str) -> dict[str, str]:
        raw = plaintext.encode("utf-8")
        nonce = os.urandom(16)
        cipher = bytes(a ^ b for a, b in zip(raw, _keystream(key, nonce, len(raw)), strict=True))
        mac = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
        return {"n": _b64e(nonce), "c": _b64e(cipher), "m": _b64e(mac)}

    def _decrypt(self, key: bytes, blob: dict[str, str]) -> str:
        try:
            nonce, cipher, mac = _b64d(blob["n"]), _b64d(blob["c"]), _b64d(blob["m"])
        except (KeyError, ValueError) as exc:
            raise SecretsError("corrupt secret entry") from exc
        expected = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, mac):
            raise SecretsError("secret integrity check failed")
        raw = bytes(a ^ b for a, b in zip(cipher, _keystream(key, nonce, len(cipher)), strict=True))
        return raw.decode("utf-8")

    def _load_envelope(self) -> tuple[dict[str, object], dict[str, str]]:
        if not self.path.exists():
            salt = os.urandom(16)
            return {"v": _VERSION, "kdf": "pbkdf2-sha256", "salt": _b64e(salt)}, {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SecretsError("secret store is not valid JSON") from exc
        if not isinstance(data, dict):
            raise SecretsError("secret store is corrupt")
        if data.get("v") == _VERSION and isinstance(data.get("entries"), dict):
            salt = _b64d(str(data["salt"]))
            key = self._derive(salt)
            entries = {name: self._decrypt(key, blob) for name, blob in data["entries"].items()}
            return data, entries
        # Legacy plaintext store: migrate on read, never keep raw values on disk.
        if all(isinstance(v, str) for v in data.values()):
            salt = os.urandom(16)
            envelope = {"v": _VERSION, "kdf": "pbkdf2-sha256", "salt": _b64e(salt)}
            self._save_envelope(envelope, {self._validate_name(k): v for k, v in data.items() if v})
            return self._load_envelope()
        raise SecretsError("unsupported secret store format")

    def _save_envelope(self, envelope: dict[str, object], entries: dict[str, str]) -> None:
        salt = _b64d(str(envelope["salt"]))
        key = self._derive(salt)
        payload = {
            "v": _VERSION,
            "kdf": "pbkdf2-sha256",
            "salt": envelope["salt"],
            "entries": {name: self._encrypt(key, value) for name, value in entries.items()},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        if os.name != "nt":
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)


def get_secret_store(path: Path | None = None) -> SecretStore:
    return SecretStore(path)
