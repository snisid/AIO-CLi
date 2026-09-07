"""Provider failure classification and durable failover policy."""
from __future__ import annotations

import random
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx


class FailureKind(str, Enum):
    RATE_LIMITED = "rate_limited"
    QUOTA_EXHAUSTED = "quota_exhausted"
    AUTH_FAILED = "auth_failed"
    CONTEXT_OVERFLOW = "context_overflow"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    TRANSIENT = "transient"
    INVALID_REQUEST = "invalid_request"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FailureInfo:
    kind: FailureKind
    retryable: bool
    cooldown_seconds: float
    detail: str
    status_code: int | None = None


def classify_failure(exc: BaseException) -> FailureInfo:
    """Classify common provider failures without depending on one SDK."""
    status: int | None = None
    detail = str(exc) or type(exc).__name__
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        status = exc.response.status_code
        try:
            body = exc.response.text.lower()
        except Exception:
            body = detail.lower()
        if status == 429:
            retry_after = exc.response.headers.get("retry-after")
            cooldown = _parse_retry_after(retry_after) or 5.0
            quota = any(token in body for token in ("quota", "credit", "insufficient balance", "billing"))
            return FailureInfo(
                FailureKind.QUOTA_EXHAUSTED if quota else FailureKind.RATE_LIMITED,
                True,
                cooldown,
                detail,
                status,
            )
        if status in (401, 403):
            return FailureInfo(FailureKind.AUTH_FAILED, False, 300.0, detail, status)
        if status in (408, 425, 429) or status >= 500:
            return FailureInfo(FailureKind.UNAVAILABLE, True, 2.0, detail, status)
        if status in (400, 413):
            context = any(token in body for token in ("context", "token limit", "too many tokens", "maximum context"))
            return FailureInfo(
                FailureKind.CONTEXT_OVERFLOW if context else FailureKind.INVALID_REQUEST,
                context,
                0.0,
                detail,
                status,
            )
    lower = detail.lower()
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)) or "timed out" in lower:
        return FailureInfo(FailureKind.TIMEOUT, True, 2.0, detail, status)
    if isinstance(exc, httpx.ConnectError) or any(token in lower for token in ("connection reset", "connection refused", "temporary failure")):
        return FailureInfo(FailureKind.UNAVAILABLE, True, 2.0, detail, status)
    if "context" in lower and "token" in lower:
        return FailureInfo(FailureKind.CONTEXT_OVERFLOW, True, 0.0, detail, status)
    if "quota" in lower or "insufficient balance" in lower:
        return FailureInfo(FailureKind.QUOTA_EXHAUSTED, True, 30.0, detail, status)
    return FailureInfo(FailureKind.UNKNOWN, True, 1.0, detail, status)


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
        return max(0.0, min(seconds, 3600.0))
    except ValueError:
        match = re.search(r"(\d+(?:\.\d+)?)", value)
        return float(match.group(1)) if match else None


@dataclass
class FailoverPolicy:
    """No fixed attempt cap; the caller controls cancellation/deadline."""
    max_attempts: int | None = None
    max_total_seconds: float | None = None
    initial_backoff_seconds: float = 0.5
    max_backoff_seconds: float = 30.0
    jitter: float = 0.2

    def backoff(self, failures: int, failure: FailureInfo) -> float:
        if failure.cooldown_seconds:
            base = failure.cooldown_seconds
        else:
            base = min(self.max_backoff_seconds, self.initial_backoff_seconds * (2 ** max(0, failures - 1)))
        return max(0.0, base * (1.0 + random.uniform(-self.jitter, self.jitter)))
