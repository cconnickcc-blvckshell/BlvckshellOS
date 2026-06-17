"""Tests for the observer / audit log."""

from __future__ import annotations

from harness.core.observer import Observer
from harness.schemas.event import EventType
from harness.schemas.message import HarnessMessage, MessageType


async def test_record_and_recent() -> None:
    observer = Observer()
    await observer.record(EventType.TASK_STARTED, source="venture", context_id="c1", message="go")
    recent = observer.recent(limit=10)
    assert recent[-1].event_type == EventType.TASK_STARTED
    assert recent[-1].source == "venture"


async def test_recent_filters_by_context() -> None:
    observer = Observer()
    await observer.record(EventType.LLM_CALL, source="a", context_id="c1")
    await observer.record(EventType.LLM_CALL, source="b", context_id="c2")
    assert len(observer.recent(context_id="c1")) == 1


async def test_subscriber_receives_events() -> None:
    observer = Observer()
    seen: list[str] = []

    async def sub(event) -> None:
        seen.append(event.event_type.value)

    observer.subscribe(sub)
    await observer.record(EventType.ERROR, source="x")
    assert seen == ["error"]


async def test_record_message_helper() -> None:
    observer = Observer()
    msg = HarnessMessage(source="harness", destination="venture", message_type=MessageType.TASK)
    event = await observer.record_message(msg, direction="sent")
    assert event.event_type == EventType.MESSAGE_SENT
    assert event.data["destination"] == "venture"


async def test_failing_subscriber_is_isolated() -> None:
    observer = Observer()

    async def bad(_event) -> None:
        raise RuntimeError("boom")

    observer.subscribe(bad)
    event = await observer.record(EventType.ERROR, source="x")
    assert event.event_type == EventType.ERROR
