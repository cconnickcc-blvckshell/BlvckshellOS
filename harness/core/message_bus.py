"""The message bus — every brain communicates through here.

The bus offers two complementary primitives:

- **pub/sub**: fan-out delivery used for broadcasts and live observation.
- **queues**: per-destination work queues so a brain reliably pulls the next
  task even if it was offline when the task was emitted.

Two interchangeable implementations are provided: a production
:class:`RedisMessageBus` and an :class:`InMemoryMessageBus` used for tests and
fully offline operation. Both honour the same :class:`MessageBus` contract, so
nothing downstream cares which is wired in.
"""

from __future__ import annotations

import abc
import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable

from harness.logging_config import get_logger
from harness.schemas.message import HarnessMessage

logger = get_logger("message_bus")

MessageHandler = Callable[[HarnessMessage], Awaitable[None]]

_QUEUE_PREFIX = "blvckshell:queue:"
_CHANNEL_PREFIX = "blvckshell:channel:"
_OBSERVER_CHANNEL = "blvckshell:observer"


class MessageBus(abc.ABC):
    """Abstract transport for harness messages."""

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish any underlying connections. Idempotent."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Tear down connections and background tasks. Idempotent."""

    @abc.abstractmethod
    async def publish(self, channel: str, message: HarnessMessage) -> None:
        """Publish a message to a pub/sub channel (fan-out).

        Args:
            channel: The logical channel name.
            message: The message to broadcast.
        """

    @abc.abstractmethod
    async def enqueue(self, destination: str, message: HarnessMessage) -> None:
        """Append a message to a destination's durable work queue.

        Args:
            destination: The ``brain_id`` (or component) that owns the queue.
            message: The message to deliver.
        """

    @abc.abstractmethod
    async def dequeue(
        self, destination: str, timeout: float | None = None
    ) -> HarnessMessage | None:
        """Pop the next message from a destination's queue, blocking if empty.

        Args:
            destination: The queue owner to read from.
            timeout: Max seconds to wait. ``None`` waits indefinitely.

        Returns:
            The next message, or ``None`` if the timeout elapsed.
        """

    @abc.abstractmethod
    def subscribe(self, channel: str) -> AsyncIterator[HarnessMessage]:
        """Return an async iterator yielding messages published to a channel.

        Args:
            channel: The channel name to subscribe to.
        """

    async def observe(self) -> AsyncIterator[HarnessMessage]:
        """Subscribe to the firehose channel mirroring every routed message."""
        async for message in self.subscribe(_OBSERVER_CHANNEL):
            yield message

    async def mirror_to_observer(self, message: HarnessMessage) -> None:
        """Publish a copy of a routed message to the observer firehose channel."""
        await self.publish(_OBSERVER_CHANNEL, message)


class InMemoryMessageBus(MessageBus):
    """An in-process bus backed by :class:`asyncio.Queue` objects.

    Suitable for tests and single-process deployments where Redis is not
    available. Subscriptions are delivered to live subscribers only (true
    pub/sub semantics); queues retain messages until consumed.
    """

    def __init__(self) -> None:
        """Initialize empty queue and subscriber registries."""
        self._queues: dict[str, asyncio.Queue[HarnessMessage]] = defaultdict(asyncio.Queue)
        self._subscribers: dict[str, list[asyncio.Queue[HarnessMessage]]] = defaultdict(list)
        self._connected = False

    async def connect(self) -> None:
        """Mark the bus as connected (no real connection is needed)."""
        self._connected = True

    async def close(self) -> None:
        """Drop all subscribers and mark the bus disconnected."""
        self._subscribers.clear()
        self._connected = False

    async def publish(self, channel: str, message: HarnessMessage) -> None:
        """Fan a message out to every live subscriber of ``channel``."""
        for queue in list(self._subscribers.get(channel, [])):
            await queue.put(message)

    async def enqueue(self, destination: str, message: HarnessMessage) -> None:
        """Append a message to ``destination``'s in-memory queue."""
        await self._queues[destination].put(message)

    async def dequeue(
        self, destination: str, timeout: float | None = None
    ) -> HarnessMessage | None:
        """Pop the next message from ``destination``'s queue."""
        queue = self._queues[destination]
        if timeout is None:
            return await queue.get()
        try:
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except TimeoutError:
            return None

    async def subscribe(self, channel: str) -> AsyncIterator[HarnessMessage]:
        """Yield messages published to ``channel`` while subscribed."""
        queue: asyncio.Queue[HarnessMessage] = asyncio.Queue()
        self._subscribers[channel].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            if queue in self._subscribers.get(channel, []):
                self._subscribers[channel].remove(queue)


class RedisMessageBus(MessageBus):
    """A Redis-backed bus using lists for queues and pub/sub for channels."""

    def __init__(self, redis_url: str) -> None:
        """Create the bus.

        Args:
            redis_url: The Redis connection URL.
        """
        self._redis_url = redis_url
        self._redis = None  # type: ignore[assignment]
        self._connected = False

    async def connect(self) -> None:
        """Open the Redis connection lazily and verify it with a ping."""
        if self._connected:
            return
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        await self._redis.ping()
        self._connected = True
        logger.info("message_bus_connected", url=self._redis_url)

    async def close(self) -> None:
        """Close the Redis connection if open."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        self._connected = False

    def _require_redis(self):  # type: ignore[no-untyped-def]
        """Return the live Redis client or raise if not connected."""
        if self._redis is None:
            raise RuntimeError("RedisMessageBus is not connected; call connect() first")
        return self._redis

    async def publish(self, channel: str, message: HarnessMessage) -> None:
        """Publish a message to a Redis pub/sub channel."""
        await self._require_redis().publish(_CHANNEL_PREFIX + channel, message.to_wire())

    async def enqueue(self, destination: str, message: HarnessMessage) -> None:
        """Push a message onto the destination's Redis list (queue)."""
        await self._require_redis().rpush(_QUEUE_PREFIX + destination, message.to_wire())

    async def dequeue(
        self, destination: str, timeout: float | None = None
    ) -> HarnessMessage | None:
        """Block-pop the next message from the destination's Redis list."""
        # redis blpop uses 0 to block forever; convert our None likewise.
        block_for = 0 if timeout is None else max(int(timeout), 1)
        result = await self._require_redis().blpop(
            [_QUEUE_PREFIX + destination], timeout=block_for
        )
        if result is None:
            return None
        _key, raw = result
        return HarnessMessage.from_wire(raw)

    async def subscribe(self, channel: str) -> AsyncIterator[HarnessMessage]:
        """Yield messages published to a Redis channel until cancelled."""
        pubsub = self._require_redis().pubsub()
        await pubsub.subscribe(_CHANNEL_PREFIX + channel)
        try:
            async for raw in pubsub.listen():
                if raw is None or raw.get("type") != "message":
                    continue
                yield HarnessMessage.from_wire(raw["data"])
        finally:
            await pubsub.unsubscribe(_CHANNEL_PREFIX + channel)
            await pubsub.aclose()


def build_message_bus(*, redis_url: str, use_in_memory: bool) -> MessageBus:
    """Construct the configured message bus implementation.

    Args:
        redis_url: Redis URL used when not in-memory.
        use_in_memory: When true, return the in-process bus.

    Returns:
        A concrete :class:`MessageBus`.
    """
    if use_in_memory:
        return InMemoryMessageBus()
    return RedisMessageBus(redis_url)
