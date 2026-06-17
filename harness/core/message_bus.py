"""The message bus — every brain communicates through here.

Two interchangeable implementations are provided behind one interface:

* :class:`InMemoryMessageBus` — a fully-featured asyncio pub/sub bus with no
  external dependencies. Used for tests and local single-process bring-up.
* :class:`RedisMessageBus` — Redis pub/sub for multi-container deployments.

The :func:`create_message_bus` factory selects the right one from configuration.
A handler is any async callable taking a :class:`HarnessMessage`.
"""

from __future__ import annotations

import abc
import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import TYPE_CHECKING

from harness.config import settings
from harness.core.logging import get_logger
from harness.schemas.message import (
    BROADCAST_DESTINATION,
    HarnessMessage,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from redis.asyncio import Redis

logger = get_logger(__name__)

Handler = Callable[[HarnessMessage], Awaitable[None]]


class MessageBus(abc.ABC):
    """Abstract pub/sub bus carrying :class:`HarnessMessage` envelopes.

    Channels are addresses: a ``brain_id``, ``"harness"``, ``"intake"`` or
    ``"broadcast"``. Publishing to a brain's address delivers to that brain;
    publishing to ``broadcast`` delivers to every subscriber.
    """

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish any underlying connection and start delivery."""

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Tear down delivery and close the underlying connection."""

    @abc.abstractmethod
    async def publish(self, message: HarnessMessage) -> None:
        """Publish a message to its ``destination`` channel."""

    @abc.abstractmethod
    async def subscribe(self, channel: str, handler: Handler) -> None:
        """Register ``handler`` to receive messages on ``channel``."""

    @abc.abstractmethod
    async def unsubscribe(self, channel: str, handler: Handler) -> None:
        """Remove a previously-registered ``handler`` from ``channel``."""


class InMemoryMessageBus(MessageBus):
    """In-process async pub/sub bus with no external dependencies.

    Delivery is concurrent and isolated: one handler raising never prevents
    other handlers from receiving the message, and never crashes the bus.
    """

    def __init__(self) -> None:
        """Initialize empty subscriber tables."""
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._connected = False

    async def connect(self) -> None:
        """Mark the bus as ready (no I/O required for the in-memory bus)."""
        self._connected = True
        logger.info("InMemoryMessageBus connected")

    async def disconnect(self) -> None:
        """Drop all subscriptions and mark the bus as closed."""
        self._handlers.clear()
        self._connected = False
        logger.info("InMemoryMessageBus disconnected")

    async def publish(self, message: HarnessMessage) -> None:
        """Deliver ``message`` to subscribers of its destination channel.

        Broadcast messages are fanned out to every subscribed channel.
        """
        channels: list[str]
        if message.destination == BROADCAST_DESTINATION:
            channels = list(self._handlers.keys())
        else:
            channels = [message.destination]

        delivered: list[Awaitable[None]] = []
        for channel in channels:
            for handler in list(self._handlers.get(channel, [])):
                delivered.append(self._safe_invoke(handler, message, channel))
        if delivered:
            await asyncio.gather(*delivered)

    async def _safe_invoke(self, handler: Handler, message: HarnessMessage, channel: str) -> None:
        """Invoke a handler, swallowing and logging any exception."""
        try:
            await handler(message)
        except Exception:  # noqa: BLE001 - a bad handler must never crash the bus
            logger.exception("Handler on channel '%s' failed for message %s", channel, message.id)

    async def subscribe(self, channel: str, handler: Handler) -> None:
        """Add ``handler`` to ``channel``'s subscriber list."""
        self._handlers[channel].append(handler)
        logger.debug("Subscribed handler to channel '%s'", channel)

    async def unsubscribe(self, channel: str, handler: Handler) -> None:
        """Remove ``handler`` from ``channel`` if present."""
        with suppress(ValueError):
            self._handlers[channel].remove(handler)


class RedisMessageBus(MessageBus):
    """Redis pub/sub message bus for multi-container deployments.

    Each subscribed channel maps to a namespaced Redis channel and a background
    reader task that decodes envelopes and dispatches to local handlers.
    """

    def __init__(self, redis_url: str, namespace: str = "blvckshell") -> None:
        """Store connection parameters; the connection is opened in ``connect``.

        Args:
            redis_url: Redis connection URL.
            namespace: Channel prefix isolating this harness instance.
        """
        self._redis_url = redis_url
        self._namespace = namespace
        self._redis: Redis | None = None
        self._pubsub = None
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._readers: dict[str, asyncio.Task[None]] = {}

    def _channel(self, channel: str) -> str:
        """Return the namespaced Redis channel name for ``channel``."""
        return f"{self._namespace}:{channel}"

    async def connect(self) -> None:
        """Open the Redis connection and pub/sub interface."""
        from redis.asyncio import Redis  # local import keeps redis optional

        self._redis = Redis.from_url(self._redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        await self._redis.ping()
        logger.info("RedisMessageBus connected to %s", self._redis_url)

    async def disconnect(self) -> None:
        """Cancel reader tasks and close the Redis connection."""
        for task in self._readers.values():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._readers.clear()
        if self._pubsub is not None:
            await self._pubsub.aclose()
        if self._redis is not None:
            await self._redis.aclose()
        logger.info("RedisMessageBus disconnected")

    async def publish(self, message: HarnessMessage) -> None:
        """Publish ``message`` to its destination channel on Redis."""
        if self._redis is None:
            raise RuntimeError("RedisMessageBus.publish called before connect()")
        await self._redis.publish(
            self._channel(message.destination),
            message.model_dump_json(),
        )

    async def subscribe(self, channel: str, handler: Handler) -> None:
        """Subscribe ``handler`` to ``channel``, starting a reader if needed."""
        if self._pubsub is None:
            raise RuntimeError("RedisMessageBus.subscribe called before connect()")
        first = channel not in self._handlers or not self._handlers[channel]
        self._handlers[channel].append(handler)
        if first:
            await self._pubsub.subscribe(self._channel(channel))
            self._readers[channel] = asyncio.create_task(self._reader(channel))

    async def unsubscribe(self, channel: str, handler: Handler) -> None:
        """Unsubscribe ``handler``; stop the reader when no handlers remain."""
        with suppress(ValueError):
            self._handlers[channel].remove(handler)
        if not self._handlers.get(channel) and channel in self._readers:
            self._readers.pop(channel).cancel()
            if self._pubsub is not None:
                await self._pubsub.unsubscribe(self._channel(channel))

    async def _reader(self, channel: str) -> None:
        """Background loop decoding messages for ``channel`` and dispatching."""
        assert self._pubsub is not None
        namespaced = self._channel(channel)
        async for raw in self._pubsub.listen():
            if raw.get("type") != "message" or raw.get("channel") != namespaced:
                continue
            try:
                message = HarnessMessage.model_validate_json(raw["data"])
            except Exception:  # noqa: BLE001 - never let a bad payload kill the reader
                logger.exception("Failed to decode message on channel '%s'", channel)
                continue
            for handler in list(self._handlers.get(channel, [])):
                try:
                    await handler(message)
                except Exception:  # noqa: BLE001 - isolate handler failures
                    logger.exception("Handler on '%s' failed for %s", channel, message.id)


def create_message_bus() -> MessageBus:
    """Construct the configured message bus.

    Returns:
        A :class:`RedisMessageBus` when a Redis URL is configured, otherwise an
        :class:`InMemoryMessageBus`.
    """
    if settings.use_redis and settings.redis_url:
        return RedisMessageBus(settings.redis_url, settings.bus_namespace)
    return InMemoryMessageBus()
