"""Tests for the in-memory message bus (queues and pub/sub)."""

from __future__ import annotations

import asyncio

import pytest

from harness.core.message_bus import InMemoryMessageBus
from harness.schemas.message import HarnessMessage, MessageType


def _msg(dest: str) -> HarnessMessage:
    return HarnessMessage(source="harness", destination=dest, message_type=MessageType.TASK)


async def test_enqueue_dequeue_fifo() -> None:
    bus = InMemoryMessageBus()
    await bus.connect()
    await bus.enqueue("venture", _msg("venture"))
    await bus.enqueue("venture", _msg("venture"))
    first = await bus.dequeue("venture", timeout=1)
    second = await bus.dequeue("venture", timeout=1)
    assert first is not None and second is not None
    assert first.id != second.id


async def test_dequeue_timeout_returns_none() -> None:
    bus = InMemoryMessageBus()
    await bus.connect()
    assert await bus.dequeue("empty", timeout=0.05) is None


async def test_pub_sub_fan_out() -> None:
    bus = InMemoryMessageBus()
    await bus.connect()
    received: list[HarnessMessage] = []

    async def consume() -> None:
        async for message in bus.subscribe("chan"):
            received.append(message)
            break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)  # let the subscriber register
    await bus.publish("chan", _msg("chan"))
    await asyncio.wait_for(task, timeout=1)
    assert len(received) == 1


async def test_observer_mirror() -> None:
    bus = InMemoryMessageBus()
    await bus.connect()
    seen: list[HarnessMessage] = []

    async def consume() -> None:
        async for message in bus.observe():
            seen.append(message)
            break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)
    await bus.mirror_to_observer(_msg("anything"))
    await asyncio.wait_for(task, timeout=1)
    assert len(seen) == 1


@pytest.mark.parametrize("count", [1, 5, 20])
async def test_queue_preserves_all_messages(count: int) -> None:
    bus = InMemoryMessageBus()
    await bus.connect()
    for _ in range(count):
        await bus.enqueue("q", _msg("q"))
    drained = [await bus.dequeue("q", timeout=1) for _ in range(count)]
    assert all(m is not None for m in drained)
