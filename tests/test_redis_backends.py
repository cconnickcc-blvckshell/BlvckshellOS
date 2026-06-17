"""Tests for the Redis-backed implementations using fakeredis.

These verify the production Redis code paths (queues, pub/sub, context hashes,
registry hash) without needing a real Redis server.
"""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest
from harness.core.message_bus import RedisMessageBus
from harness.core.registry import RedisBrainRegistry
from harness.schemas.brain_info import BrainInfo
from harness.schemas.message import HarnessMessage, MessageType
from memory.context_store import RedisContextStore


@pytest.fixture
def fake_redis() -> fakeredis.aioredis.FakeRedis:
    """Return a fresh decode-responses fake Redis client."""
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


async def test_redis_bus_queue_round_trip(fake_redis) -> None:
    bus = RedisMessageBus("redis://fake")
    bus._redis = fake_redis  # inject fake; skip real connect
    bus._connected = True
    msg = HarnessMessage(source="harness", destination="venture", message_type=MessageType.TASK)
    await bus.enqueue("venture", msg)
    out = await bus.dequeue("venture", timeout=1)
    assert out is not None
    assert out.id == msg.id


async def test_redis_bus_dequeue_timeout(fake_redis) -> None:
    bus = RedisMessageBus("redis://fake")
    bus._redis = fake_redis
    bus._connected = True
    assert await bus.dequeue("empty", timeout=1) is None


async def test_redis_bus_pub_sub(fake_redis) -> None:
    bus = RedisMessageBus("redis://fake")
    bus._redis = fake_redis
    bus._connected = True
    received: list[HarnessMessage] = []

    async def consume() -> None:
        async for message in bus.subscribe("chan"):
            received.append(message)
            break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    await bus.publish("chan", _msg())
    await asyncio.wait_for(task, timeout=2)
    assert len(received) == 1


def _msg() -> HarnessMessage:
    return HarnessMessage(source="harness", destination="chan", message_type=MessageType.EVENT)


async def test_redis_context_store(fake_redis) -> None:
    store = RedisContextStore("redis://fake", ttl_seconds=60)
    store._redis = fake_redis
    await store.set("c1", "idea", {"x": 1})
    assert await store.get("c1", "idea") == {"x": 1}
    await store.append("c1", "history", "a")
    await store.append("c1", "history", "b")
    assert (await store.get_all("c1"))["history"] == ["a", "b"]
    await store.delete("c1")
    assert await store.get_all("c1") == {}


async def test_redis_registry(fake_redis) -> None:
    reg = RedisBrainRegistry("redis://fake")
    reg._redis = fake_redis
    await reg.register(
        BrainInfo(brain_id="venture", name="V", description="d", capabilities=["x"])
    )
    assert (await reg.get("venture")).handles("x")
    assert len(await reg.list_all()) == 1
    matches = await reg.find_by_capability("x")
    assert matches[0].brain_id == "venture"
    await reg.deregister("venture")
    assert await reg.get("venture") is None
