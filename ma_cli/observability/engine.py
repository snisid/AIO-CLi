"""Structured observability: events, counters, and JSONL traces."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class Span:
    name: str
    started_at: float
    attributes: dict[str, Any] = field(default_factory=dict)
    finished_at: float | None = None
    status: str = "ok"
    error: str | None = None

    def duration_ms(self) -> int:
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return int((end - self.started_at) * 1000)


class ObservabilityEngine:
    def __init__(self, workspace: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.log_path = self.workspace / ".ma-cli" / "logs" / "observability.jsonl"
        self._lock = threading.Lock()
        self._spans: list[Span] = []
        self._counters: dict[str, int] = {}
        self._events: list[dict[str, Any]] = []

    def increment(self, name: str, amount: int = 1) -> int:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + amount
            value = self._counters[name]
        self.record("counter", name=name, value=value)
        return value

    def start_span(self, name: str, **attributes: Any) -> Span:
        span = Span(name=name, started_at=time.monotonic(), attributes=dict(attributes))
        with self._lock:
            self._spans.append(span)
        self.record("span.start", name=name, **attributes)
        return span

    def end_span(self, span: Span, status: str = "ok", error: str | None = None) -> Span:
        span.finished_at = time.monotonic()
        span.status = status
        span.error = error
        self.record("span.end", name=span.name, status=status, duration_ms=span.duration_ms(), error=error)
        return span

    def record(self, event: str, **fields: Any) -> dict[str, Any]:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "event": event,
            **{key: value for key, value in fields.items() if value is not None},
        }
        line = json.dumps(payload, default=str)
        with self._lock:
            self._events.append(payload)
            self._events[:] = self._events[-2000:]
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return payload

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "spans": [
                    {
                        "name": span.name,
                        "duration_ms": span.duration_ms(),
                        "status": span.status,
                        "error": span.error,
                    }
                    for span in self._spans[-50:]
                ],
                "events": list(self._events[-50:]),
                "log_path": str(self.log_path),
            }


_engine: ObservabilityEngine | None = None


def get_observability(workspace: Path | None = None) -> ObservabilityEngine:
    global _engine
    resolved = (workspace or Path.cwd()).resolve()
    if _engine is None or _engine.workspace != resolved:
        _engine = ObservabilityEngine(resolved)
    return _engine
