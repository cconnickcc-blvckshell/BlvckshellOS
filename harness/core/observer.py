"""The Observer — audit everything.

Every meaningful event in the harness flows through the Observer: messages,
registrations, task lifecycle, LLM calls, tool calls, judgment writes, doctrine
promotions, and pipeline boundaries. Events are (1) structured-logged, (2)
persisted to an :class:`AuditStore`, and (3) fanned out to live subscribers for
the real-time Observer view in the UI.

Logging here is non-negotiable — it is how the system is debugged, improved, and
eventually trained on real pipeline data.
"""

from __future__ import annotations

import abc
import asyncio
import contextlib
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

from harness.logging_config import get_logger
from harness.schemas.audit import AuditEvent, AuditEventType

logger = get_logger("observer")


class AuditStore(abc.ABC):
    """Abstract durable store for :class:`AuditEvent` records."""

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Tear down any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def append(self, event: AuditEvent) -> None:
        """Persist a single audit event."""

    @abc.abstractmethod
    async def list_recent(
        self, *, context_id: str | None = None, limit: int = 200
    ) -> list[AuditEvent]:
        """Return the most recent events, optionally filtered by pipeline run."""


class InMemoryAuditStore(AuditStore):
    """A bounded in-process audit store for tests and offline operation."""

    def __init__(self, maxlen: int = 10_000) -> None:
        """Initialize the ring buffer.

        Args:
            maxlen: Maximum number of events retained in memory.
        """
        self._events: deque[AuditEvent] = deque(maxlen=maxlen)

    async def connect(self) -> None:
        """No-op connect."""

    async def close(self) -> None:
        """No-op close."""

    async def append(self, event: AuditEvent) -> None:
        """Append an event to the ring buffer."""
        self._events.append(event)

    async def list_recent(
        self, *, context_id: str | None = None, limit: int = 200
    ) -> list[AuditEvent]:
        """Return recent events newest-first, optionally filtered."""
        result: list[AuditEvent] = []
        for event in reversed(self._events):
            if context_id is not None and event.context_id != context_id:
                continue
            result.append(event)
            if len(result) >= limit:
                break
        return result


class SupabaseAuditStore(AuditStore):
    """A Supabase-backed audit store on the ``audit_log`` table."""

    TABLE = "audit_log"

    def __init__(self, url: str, key: str) -> None:
        """Create the store.

        Args:
            url: Supabase project URL.
            key: Supabase service key.
        """
        self._url = url
        self._key = key
        self._client = None  # type: ignore[assignment]

    async def connect(self) -> None:
        """Create the Supabase client lazily."""
        if self._client is not None:
            return
        from supabase import create_client

        self._client = create_client(self._url, self._key)

    async def close(self) -> None:
        """Drop the Supabase client reference."""
        self._client = None

    def _require(self):  # type: ignore[no-untyped-def]
        """Return the live client or raise."""
        if self._client is None:
            raise RuntimeError("SupabaseAuditStore is not connected; call connect() first")
        return self._client

    async def append(self, event: AuditEvent) -> None:
        """Insert an audit event row."""
        self._require().table(self.TABLE).insert(event.model_dump(mode="json")).execute()

    async def list_recent(
        self, *, context_id: str | None = None, limit: int = 200
    ) -> list[AuditEvent]:
        """Return recent rows newest-first, optionally filtered by context."""
        query = self._require().table(self.TABLE).select("*")
        if context_id is not None:
            query = query.eq("context_id", context_id)
        res = query.order("timestamp", desc=True).limit(limit).execute()
        return [AuditEvent.model_validate(r) for r in (res.data or [])]


class Observer:
    """Records audit events to durable storage, logs, and live subscribers."""

    def __init__(self, store: AuditStore) -> None:
        """Create the Observer.

        Args:
            store: The durable audit store to persist events to.
        """
        self._store = store
        self._subscribers: list[asyncio.Queue[AuditEvent]] = []

    async def connect(self) -> None:
        """Connect the underlying audit store."""
        await self._store.connect()

    async def close(self) -> None:
        """Close the underlying audit store and drop subscribers."""
        await self._store.close()
        self._subscribers.clear()

    async def record(
        self,
        event_type: AuditEventType,
        *,
        source: str,
        message: str = "",
        context_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Record an audit event everywhere it needs to go.

        Args:
            event_type: The category of event.
            source: The component or ``brain_id`` producing the event.
            message: A short human-readable description.
            context_id: The pipeline run this event belongs to, if any.
            data: Structured detail to attach.

        Returns:
            The persisted :class:`AuditEvent`.
        """
        event = AuditEvent(
            event_type=event_type,
            source=source,
            message=message,
            context_id=context_id,
            data=data or {},
        )
        try:
            await self._store.append(event)
        except Exception:
            logger.error("audit_persist_failed", event_type=event_type.value, source=source)
        logger.info(
            "audit_event",
            event_type=event_type.value,
            source=source,
            context_id=context_id,
            message=message,
            **{f"data_{k}": v for k, v in (data or {}).items()},
        )
        self._fanout(event)
        return event

    def _fanout(self, event: AuditEvent) -> None:
        """Deliver an event to all live subscribers without blocking."""
        for queue in list(self._subscribers):
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(event)

    async def list_recent(
        self, *, context_id: str | None = None, limit: int = 200
    ) -> list[AuditEvent]:
        """Return recent events from the durable store."""
        return await self._store.list_recent(context_id=context_id, limit=limit)

    async def stream(self) -> AsyncIterator[AuditEvent]:
        """Yield audit events live as they are recorded.

        Intended for the real-time Observer view. The subscriber is registered
        on first iteration and cleaned up when the consumer stops.
        """
        queue: asyncio.Queue[AuditEvent] = asyncio.Queue(maxsize=1000)
        self._subscribers.append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            if queue in self._subscribers:
                self._subscribers.remove(queue)
