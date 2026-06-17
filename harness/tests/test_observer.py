"""Tests for the Observer audit logging and live stream."""

from __future__ import annotations

import asyncio

from harness.core.observer import InMemoryAuditStore, Observer
from harness.schemas.audit import AuditEvent, AuditEventType


async def test_record_persists_and_lists() -> None:
    observer = Observer(InMemoryAuditStore())
    await observer.connect()
    await observer.record(AuditEventType.PIPELINE_STARTED, source="intake", context_id="c1")
    await observer.record(AuditEventType.LLM_CALL, source="venture", context_id="c1")
    events = await observer.list_recent(context_id="c1")
    assert len(events) == 2
    assert events[0].event_type == AuditEventType.LLM_CALL  # newest first


async def test_list_filters_by_context() -> None:
    observer = Observer(InMemoryAuditStore())
    await observer.connect()
    await observer.record(AuditEventType.PIPELINE_STARTED, source="intake", context_id="a")
    await observer.record(AuditEventType.PIPELINE_STARTED, source="intake", context_id="b")
    assert len(await observer.list_recent(context_id="a")) == 1


async def test_stream_receives_live_events() -> None:
    observer = Observer(InMemoryAuditStore())
    await observer.connect()
    received: list[AuditEvent] = []

    async def consume() -> None:
        async for event in observer.stream():
            received.append(event)
            break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)
    await observer.record(AuditEventType.TASK_STARTED, source="venture")
    await asyncio.wait_for(task, timeout=1)
    assert received[0].event_type == AuditEventType.TASK_STARTED
