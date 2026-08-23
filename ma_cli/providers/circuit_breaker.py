"""
Circuit Breaker pattern for provider resilience.

Prevents cascading failures by temporarily disabling failing providers.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def _now_utc() -> datetime:
    """Get current UTC time in a timezone-aware manner."""
    return datetime.now(UTC)


logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitStats:
    """Statistics for circuit breaker."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: datetime | None = None
    last_success_time: datetime | None = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0

    def record_success(self) -> None:
        """Record a successful call."""
        self.total_calls += 1
        self.successful_calls += 1
        self.last_success_time = _now_utc()
        self.consecutive_failures = 0
        self.consecutive_successes += 1

    def record_failure(self) -> None:
        """Record a failed call."""
        self.total_calls += 1
        self.failed_calls += 1
        self.last_failure_time = _now_utc()
        self.consecutive_successes = 0
        self.consecutive_failures += 1

    def record_rejection(self) -> None:
        """Record a rejected call (circuit open)."""
        self.rejected_calls += 1

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls


@dataclass
class CircuitConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 3  # Successes in half-open to close
    timeout_seconds: int = 60  # Time before trying half-open
    half_open_max_calls: int = 3  # Max calls in half-open state
    excluded_exceptions: tuple = field(default_factory=lambda: (ValueError, TypeError))


class CircuitBreaker:
    """
    Circuit breaker for provider resilience.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Provider failing, requests rejected immediately
    - HALF_OPEN: Testing recovery, limited requests allowed
    """

    def __init__(self, name: str, config: CircuitConfig | None = None):
        self.name = name
        self.config = config or CircuitConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._opened_at: datetime | None = None
        self._half_open_calls: int = 0
        self._lock: Any = None  # Can use threading.Lock if needed

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for timeout transition."""
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._transition_to_half_open()
        return self._state

    @property
    def stats(self) -> CircuitStats:
        """Get circuit statistics."""
        return self._stats

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._opened_at is None:
            return False

        elapsed = (_now_utc() - self._opened_at).total_seconds()
        return elapsed >= self.config.timeout_seconds

    def _transition_to_half_open(self) -> None:
        """Transition from OPEN to HALF_OPEN state."""
        logger.info(f"Circuit '{self.name}' transitioning to HALF_OPEN")
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        self._opened_at = None

    def _transition_to_open(self) -> None:
        """Transition to OPEN state."""
        logger.warning(
            f"Circuit '{self.name}' OPENED after {self.config.failure_threshold} failures"
        )
        self._state = CircuitState.OPEN
        self._opened_at = _now_utc()
        self._half_open_calls = 0

    def _transition_to_closed(self) -> None:
        """Transition to CLOSED state (recovered)."""
        logger.info(f"Circuit '{self.name}' CLOSED (recovered)")
        self._state = CircuitState.CLOSED
        self._half_open_calls = 0
        self._opened_at = None

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Execute function through circuit breaker.

        Raises CircuitOpenError if circuit is open.
        Re-raises exceptions and updates state accordingly.
        """
        # Check if we should allow the call
        if not self._allow_request():
            self._stats.record_rejection()
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN. Provider unavailable.")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.config.excluded_exceptions as e:
            # These exceptions don't count as failures
            logger.debug(f"Circuit '{self.name}' ignored exception: {e}")
            raise

        except Exception:
            self._on_failure()
            raise

    async def call_async(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Async version of call."""
        if not self._allow_request():
            self._stats.record_rejection()
            raise CircuitOpenError(f"Circuit '{self.name}' is OPEN. Provider unavailable.")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result

        except self.config.excluded_exceptions as e:
            logger.debug(f"Circuit '{self.name}' ignored exception: {e}")
            raise

        except Exception:
            self._on_failure()
            raise

    def _allow_request(self) -> bool:
        """Determine if request should be allowed."""
        state = self.state  # This checks for timeout transition

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            return False

        # HALF_OPEN: allow limited calls
        if self._half_open_calls >= self.config.half_open_max_calls:
            return False

        self._half_open_calls += 1
        return True

    def _on_success(self) -> None:
        """Handle successful call."""
        self._stats.record_success()

        if self._state == CircuitState.HALF_OPEN:
            if self._stats.consecutive_successes >= self.config.success_threshold:
                self._transition_to_closed()

    def _on_failure(self) -> None:
        """Handle failed call."""
        self._stats.record_failure()

        if self._state == CircuitState.HALF_OPEN:
            # Any failure in half-open goes back to open
            self._transition_to_open()

        elif self._state == CircuitState.CLOSED:
            if self._stats.consecutive_failures >= self.config.failure_threshold:
                self._transition_to_open()

    def reset(self) -> None:
        """Manually reset circuit to closed state."""
        logger.info(f"Circuit '{self.name}' manually reset")
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._half_open_calls = 0

    def get_status(self) -> dict[str, Any]:
        """Get circuit status for monitoring."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_rate": self._stats.failure_rate,
            "total_calls": self._stats.total_calls,
            "failed_calls": self._stats.failed_calls,
            "rejected_calls": self._stats.rejected_calls,
            "consecutive_failures": self._stats.consecutive_failures,
            "last_failure": (
                self._stats.last_failure_time.isoformat() if self._stats.last_failure_time else None
            ),
            "last_success": (
                self._stats.last_success_time.isoformat() if self._stats.last_success_time else None
            ),
        }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.

    Provides centralized management for all provider circuits.
    """

    _instance: CircuitBreakerRegistry | None = None

    def __new__(cls) -> CircuitBreakerRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._breakers: dict[str, CircuitBreaker] = {}
        return cls._instance

    def get_or_create(self, name: str, config: CircuitConfig | None = None) -> CircuitBreaker:
        """Get existing circuit or create new one."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, config)
        return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """Get circuit by name."""
        return self._breakers.get(name)

    def remove(self, name: str) -> None:
        """Remove circuit from registry."""
        if name in self._breakers:
            del self._breakers[name]

    def list_all(self) -> list[str]:
        """List all registered circuit names."""
        return list(self._breakers.keys())

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all circuits."""
        return {name: breaker.get_status() for name, breaker in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuits to closed state."""
        for breaker in self._breakers.values():
            breaker.reset()

    def get_healthy_providers(self) -> list[str]:
        """Get list of providers with closed circuits."""
        return [
            name for name, breaker in self._breakers.items() if breaker.state == CircuitState.CLOSED
        ]

    def get_unhealthy_providers(self) -> list[str]:
        """Get list of providers with open/half-open circuits."""
        return [
            name for name, breaker in self._breakers.items() if breaker.state != CircuitState.CLOSED
        ]
