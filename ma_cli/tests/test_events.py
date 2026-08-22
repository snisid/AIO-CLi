"""Tests for event bus."""

import pytest
import asyncio
from datetime import datetime

from ma_cli.events.bus import EventBus, get_event_bus, emit_event
from ma_cli.core.models import Event, EventType


class TestEventBus:
    """Tests for EventBus."""
    
    def test_singleton_instance(self):
        """Test that EventBus is a singleton."""
        bus1 = EventBus.get_instance()
        bus2 = EventBus.get_instance()
        
        assert bus1 is bus2
    
    def test_subscribe_and_publish(self):
        """Test subscribing and publishing events."""
        bus = EventBus()
        received_events = []
        
        def callback(event):
            received_events.append(event)
        
        bus.subscribe(callback, [EventType.TASK_CREATED])
        
        # Create and publish event
        event = Event(
            event_type=EventType.TASK_CREATED,
            payload={"task_id": "test-123"},
            source="test"
        )
        
        asyncio.run(bus.publish(event))
        
        assert len(received_events) == 1
        assert received_events[0].event_type == EventType.TASK_CREATED
    
    def test_subscribe_all_events(self):
        """Test subscribing to all events."""
        bus = EventBus()
        received_events = []
        
        def callback(event):
            received_events.append(event)
        
        # Subscribe to all events (no event_types specified)
        bus.subscribe(callback)
        
        event1 = Event(event_type=EventType.TASK_CREATED, payload={}, source="test")
        event2 = Event(event_type=EventType.TASK_COMPLETED, payload={}, source="test")
        
        asyncio.run(bus.publish(event1))
        asyncio.run(bus.publish(event2))
        
        assert len(received_events) == 2
    
    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        bus = EventBus()
        call_count = [0]
        
        def callback(event):
            call_count[0] += 1
        
        bus.subscribe(callback, [EventType.TASK_CREATED])
        
        # Publish before unsubscribe
        event = Event(event_type=EventType.TASK_CREATED, payload={}, source="test")
        asyncio.run(bus.publish(event))
        assert call_count[0] == 1
        
        # Unsubscribe
        bus.unsubscribe(callback)
        
        # Publish after unsubscribe
        asyncio.run(bus.publish(event))
        assert call_count[0] == 1  # Should not have increased
    
    def test_once_subscription(self):
        """Test one-time subscription."""
        bus = EventBus()
        call_count = [0]
        
        def callback(event):
            call_count[0] += 1
        
        bus.subscribe(callback, [EventType.TASK_CREATED], once=True)
        
        event = Event(event_type=EventType.TASK_CREATED, payload={}, source="test")
        
        asyncio.run(bus.publish(event))
        asyncio.run(bus.publish(event))
        
        # Should only be called once
        assert call_count[0] == 1
    
    def test_event_history(self):
        """Test event history tracking."""
        bus = EventBus()
        
        for i in range(5):
            event = Event(
                event_type=EventType.TASK_CREATED,
                payload={"index": i},
                source="test"
            )
            asyncio.run(bus.publish(event))
        
        history = bus.get_history(limit=10)
        
        assert len(history) == 5
        # History should be newest first
        assert history[0].payload["index"] == 4
    
    def test_get_stats(self):
        """Test getting bus statistics."""
        bus = EventBus()
        
        def callback1(event): pass
        def callback2(event): pass
        
        bus.subscribe(callback1, [EventType.TASK_CREATED])
        bus.subscribe(callback2, [EventType.TASK_COMPLETED])
        
        stats = bus.get_stats()
        
        assert stats["total_subscribers"] == 2
        assert stats["event_types_subscribed"] == 2
    
    def test_clear_history(self):
        """Test clearing event history."""
        bus = EventBus()
        
        event = Event(event_type=EventType.TASK_CREATED, payload={}, source="test")
        asyncio.run(bus.publish(event))
        
        assert len(bus.get_history()) == 1
        
        bus.clear_history()
        
        assert len(bus.get_history()) == 0
    
    def test_emit_helper_function(self):
        """Test the emit_event helper function."""
        bus = get_event_bus()
        initial_count = len(bus.get_history())
        
        event = emit_event(
            EventType.TASK_CREATED,
            payload={"test": True},
            source="test_helper"
        )
        
        assert event.event_type == EventType.TASK_CREATED
        assert event.payload["test"] is True
        assert event.source == "test_helper"


class TestSubscription:
    """Tests for Subscription class."""
    
    def test_matches_with_no_filter(self):
        """Test subscription with no event type filter."""
        from ma_cli.events.bus import Subscription
        
        sub = Subscription(callback=lambda e: None, event_types=None)
        
        event = Event(event_type=EventType.TASK_CREATED, payload={}, source="test")
        assert sub.matches(event) is True
    
    def test_matches_with_filter(self):
        """Test subscription with event type filter."""
        from ma_cli.events.bus import Subscription
        
        sub = Subscription(callback=lambda e: None, event_types=[EventType.TASK_CREATED])
        
        matching = Event(event_type=EventType.TASK_CREATED, payload={}, source="test")
        non_matching = Event(event_type=EventType.TASK_COMPLETED, payload={}, source="test")
        
        assert sub.matches(matching) is True
        assert sub.matches(non_matching) is False
