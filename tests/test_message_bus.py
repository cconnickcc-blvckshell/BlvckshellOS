"""Tests for the in-memory message bus."""

from __future__ import annotations

import asyncio

from harness.core.message_bus import InMemoryMessageBus
from harness.schemas.message import HarnessMessage, MessageType


async def test_publish_delivers_to_subscriber() -> None:
    bus = InMemoryMessageBus()
    await bus.connect()
    received: list[HarnessMessage] = []

    async def handler(msg: HarnessMessage) -> None:
        received.append(msg)

    await bus.subscribe("venture", handler)
    await bus.publish(
        HarnessMessage(source="harness", destination="venture", message_type=MessageType.TASK)
    )
    assert len(received) == 1


async def test_broadcast_fans_out_to_all_channels() -> None:
    bus = InMemoryMessageBus()
    await bus.connect()
    hits: list[str] = []

    async def make(name: str):
        async def handler(_: HarnessMessage) -> None:
            hits.append(name)

        return handler

    await bus.subscribe("a", await make("a"))
    await bus.subscribe("b", await make("b"))
    await bus.publish(
        HarnessMessage(
            source="harness", destination="broadcast", message_type=MessageType.BROADCAST
        )
    )
    assert set(hits) == {"a", "b"}


async def test_failing_handler_does_not_break_bus() -> None:
    bus = InMemoryMessageBus()
    await bus.connect()
    good: list[int] = []

    async def bad(_: HarnessMessage) -> None:
        raise RuntimeError("boom")

    async def good_handler(_: HarnessMessage) -> None:
        good.append(1)

    await bus.subscribe("x", bad)
    await bus.subscribe("x", good_handler)
    await bus.publish(
        HarnessMessage(source="h", destination="x", message_type=MessageType.TASK)
    )
    assert good == [1]


async def test_unsubscribe_stops_delivery() -> None:
    bus = InMemoryMessageBus()
    await bus.connect()
    count = 0

    async def handler(_: HarnessMessage) -> None:
        nonlocal count
        count += 1

    await bus.subscribe("x", handler)
    await bus.unsubscribe("x", handler)
    await bus.publish(HarnessMessage(source="h", destination="x", message_type=MessageType.TASK))
    assert count == 0


async def test_concurrent_publish_is_safe() -> None:
    bus = InMemoryMessageBus()
    await bus.connect()
    received: list[int] = []

    async def handler(_: HarnessMessage) -> None:
        received.append(1)

    await bus.subscribe("x", handler)
    await asyncio.gather(
        *(
            bus.publish(
                HarnessMessage(source="h", destination="x", message_type=MessageType.TASK)
            )
            for _ in range(20)
        )
    )
    assert len(received) == 20
