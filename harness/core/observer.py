"""The observer — audits everything that happens in the harness.

Every message, registration, task, LLM call, tool call, judgment and pipeline
transition flows through here. Events are kept in a bounded in-memory ring (for
the live frontend stream), optionally persisted, and broadcast to subscribers.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from harness.core.logging import get_logger
from harness.core.persistence import Table, create_table
from harness.schemas.event import EventType, ObserverEvent

logger = get_logger(__name__)

OBSERVER_TABLE = "observer_events"

EventSubscriber = Callable[[ObserverEvent], Awaitable[None]]


class Observer:
    """Central audit log. Records, persists and streams observer events."""

    def __init__(self, *, table: Table | None = None, ring_size: int = 1000) -> None:
        """Create the observer.

        Args:
            table: Persistence backend for events (defaults to configured).
            ring_size: How many recent events to keep in memory for the stream.
        """
        self._table = table or create_table(OBSERVER_TABLE)
        self._ring: deque[ObserverEvent] = deque(maxlen=ring_size)
        self._subscribers: list[EventSubscriber] = []
        self._lock = asyncio.Lock()

    def subscribe(self, subscriber: EventSubscriber) -> None:
        """Register a coroutine to receive every recorded event live."""
        self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: EventSubscriber) -> None:
        """Remove a previously-registered live subscriber."""
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    async def record(
        self,
        event_type: EventType,
        *,
        source: str,
        message: str = "",
        context_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> ObserverEvent:
        """Record a single audit event.

        Args:
            event_type: The kind of event.
            source: Subsystem or ``brain_id`` that emitted it.
            message: Human-readable description.
            context_id: Pipeline run id, when applicable.
            data: Structured event detail.

        Returns:
            The recorded :class:`ObserverEvent`.
        """
        event = ObserverEvent(
            event_type=event_type,
            source=source,
            message=message,
            context_id=context_id,
            data=data or {},
        )
        async with self._lock:
            self._ring.append(event)
        await self._table.upsert(event.model_dump(mode="json"))
        await self._fanout(event)
        logger.debug("[observer] %s from %s :: %s", event_type.value, source, message)
        return event

    async def record_message(
        self, message: Any, *, direction: str = "sent"
    ) -> ObserverEvent:
        """Audit a message crossing the bus.

        Args:
            message: A :class:`~harness.schemas.message.HarnessMessage`.
            direction: ``"sent"`` or ``"received"``.

        Returns:
            The recorded :class:`ObserverEvent`.
        """
        event_type = EventType.MESSAGE_SENT if direction == "sent" else EventType.MESSAGE_RECEIVED
        return await self.record(
            event_type,
            source=message.source,
            context_id=message.context_id,
            message=f"{message.message_type.value} -> {message.destination}",
            data={
                "message_id": message.id,
                "destination": message.destination,
                "type": message.message_type.value,
                "priority": message.priority,
                "parent_id": message.parent_id,
            },
        )

    async def _fanout(self, event: ObserverEvent) -> None:
        """Deliver an event to all live subscribers, isolating failures."""
        for subscriber in list(self._subscribers):
            try:
                await subscriber(event)
            except Exception:  # noqa: BLE001 - a bad subscriber must not break auditing
                logger.exception("Observer subscriber failed for event %s", event.id)

    def recent(self, limit: int = 100, *, context_id: str | None = None) -> list[ObserverEvent]:
        """Return recent events from the in-memory ring.

        Args:
            limit: Maximum number of events to return.
            context_id: If given, filter to a single pipeline run.

        Returns:
            Events newest-last, optionally filtered by context.
        """
        events = list(self._ring)
        if context_id is not None:
            events = [event for event in events if event.context_id == context_id]
        return events[-limit:]

    async def all(self) -> list[ObserverEvent]:
        """Return every persisted event."""
        rows = await self._table.all()
        return [ObserverEvent.model_validate(row) for row in rows]
