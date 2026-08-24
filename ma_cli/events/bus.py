"""
Event Bus for MA-CLI.

This module implements an event-driven architecture for MA-CLI,
allowing components to communicate through events.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..core.models import Event, EventType


@dataclass
class Subscription:
    """Represents an event subscription."""

    callback: Callable[[Event], Any]
    event_types: list[EventType] = None  # None means all events
    once: bool = False  # If True, unsubscribe after first event

    def matches(self, event: Event) -> bool:
        """Check if this subscription matches an event."""
        if self.event_types is None:
            return True
        return event.event_type in self.event_types


class EventBus:
    """
    Central event bus for MA-CLI.

    Provides publish/subscribe functionality for system events.
    """

    _instance: EventBus | None = None

    def __init__(self):
        self._subscribers: dict[EventType, list[Subscription]] = defaultdict(list)
        self._all_subscribers: list[Subscription] = []
        self._event_history: list[Event] = []
        self._max_history = 1000
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> EventBus:
        """Get singleton instance of the event bus."""
        if cls._instance is None:
            cls._instance = EventBus()
        return cls._instance

    def subscribe(
        self,
        callback: Callable[[Event], Any],
        event_types: list[EventType] | None = None,
        once: bool = False,
    ) -> str:
        """
        Subscribe to events.

        Args:
            callback: Function to call when event occurs
            event_types: List of event types to subscribe to (None = all)
            once: If True, unsubscribe after first matching event

        Returns:
            Subscription ID (for debugging/logging)
        """
        subscription = Subscription(callback=callback, event_types=event_types, once=once)
        subscription_id = str(uuid.uuid4())[:8]

        if event_types is None:
            self._all_subscribers.append(subscription)
        else:
            for event_type in event_types:
                self._subscribers[event_type].append(subscription)

        return subscription_id

    def unsubscribe(self, callback: Callable[[Event], Any]) -> None:
        """Unsubscribe a callback from all events."""
        # Remove from type-specific subscribers
        for event_type in list(self._subscribers.keys()):
            self._subscribers[event_type] = [
                s for s in self._subscribers[event_type] if s.callback != callback
            ]

        # Remove from all-events subscribers
        self._all_subscribers = [s for s in self._all_subscribers if s.callback != callback]

    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers.

        Args:
            event: Event to publish
        """
        async with self._lock:
            # Add to history
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history :]

            # Collect all matching subscribers
            subscribers_to_notify = []

            # Add all-events subscribers
            subscribers_to_notify.extend(self._all_subscribers)

            # Add type-specific subscribers
            subscribers_to_notify.extend(self._subscribers.get(event.event_type, []))

        # Notify subscribers outside the lock
        tasks = []
        subscriptions_to_remove = []

        for sub in subscribers_to_notify:
            if sub.matches(event):
                try:
                    if asyncio.iscoroutinefunction(sub.callback):
                        tasks.append(asyncio.create_task(sub.callback(event)))
                    else:
                        tasks.append(
                            asyncio.create_task(
                                asyncio.get_event_loop().run_in_executor(None, sub.callback, event)
                            )
                        )
                except Exception:
                    # Log error but continue
                    pass

                if sub.once:
                    subscriptions_to_remove.append(sub)

        # Wait for all callbacks to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Remove one-time subscriptions
        if subscriptions_to_remove:
            async with self._lock:
                for sub in subscriptions_to_remove:
                    if sub in self._all_subscribers:
                        self._all_subscribers.remove(sub)
                    for event_type in list(self._subscribers.keys()):
                        if sub in self._subscribers[event_type]:
                            self._subscribers[event_type].remove(sub)

    def emit(
        self,
        event_type: EventType,
        payload: dict[str, Any] = None,
        source: str = "",
        correlation_id: str | None = None,
    ) -> Event:
        """
        Create and publish an event synchronously.

        Args:
            event_type: Type of event to emit
            payload: Event payload data
            source: Component that emitted the event
            correlation_id: ID for tracing related events

        Returns:
            The created event
        """
        event = Event(
            event_type=event_type,
            payload=payload or {},
            source=source,
            correlation_id=correlation_id,
        )

        # Schedule async publish
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.publish(event))
            else:
                loop.run_until_complete(self.publish(event))
        except RuntimeError:
            # No event loop, create new one
            asyncio.run(self.publish(event))

        return event

    def get_history(self, event_type: EventType | None = None, limit: int = 100) -> list[Event]:
        """
        Get event history.

        Args:
            event_type: Filter by event type (None = all)
            limit: Maximum number of events to return

        Returns:
            List of events, newest first
        """
        if event_type is None:
            return list(reversed(self._event_history[-limit:]))

        return list(
            reversed([e for e in self._event_history if e.event_type == event_type][-limit:])
        )

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history = []

    def get_stats(self) -> dict[str, Any]:
        """Get event bus statistics."""
        return {
            "total_subscribers": len(self._all_subscribers)
            + sum(len(v) for v in self._subscribers.values()),
            "event_types_subscribed": len(self._subscribers),
            "events_in_history": len(self._event_history),
            "max_history": self._max_history,
        }


# Global event bus instance
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get global event bus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus.get_instance()
    return _event_bus


def emit_event(
    event_type: EventType,
    payload: dict[str, Any] = None,
    source: str = "",
    correlation_id: str | None = None,
) -> Event:
    """Emit an event to the global event bus."""
    return get_event_bus().emit(event_type, payload, source, correlation_id)
