"""Working memory — short-term, TTL'd pipeline context.

Backed by Redis in production (with a real TTL) and by an in-process expiring
dict for tests/local bring-up. Stores arbitrary JSON keyed by ``context_id``
and field name.
"""

from __future__ import annotations

import abc
import asyncio
import json
import time
from typing import TYPE_CHECKING, Any

from harness.config import settings
from harness.core.logging import get_logger

if TYPE_CHECKING:  # pragma: no cover - typing only
    from redis.asyncio import Redis

logger = get_logger(__name__)


class ContextStore(abc.ABC):
    """Abstract working-memory store for active pipeline context."""

    @abc.abstractmethod
    async def set(self, context_id: str, field: str, value: Any) -> None:
        """Set ``field`` to ``value`` within ``context_id``'s working set."""

    @abc.abstractmethod
    async def get(self, context_id: str, field: str) -> Any | None:
        """Return the value of ``field`` within ``context_id`` or ``None``."""

    @abc.abstractmethod
    async def get_all(self, context_id: str) -> dict[str, Any]:
        """Return all fields stored for ``context_id``."""

    @abc.abstractmethod
    async def delete(self, context_id: str) -> None:
        """Delete all working memory for ``context_id``."""


class InMemoryContextStore(ContextStore):
    """Expiring in-process working memory keyed by context id and field."""

    def __init__(self, ttl_seconds: int) -> None:
        """Create the store with a per-context TTL in seconds."""
        self._ttl = ttl_seconds
        self._data: dict[str, dict[str, Any]] = {}
        self._expiry: dict[str, float] = {}
        self._lock = asyncio.Lock()

    def _purge_if_expired(self, context_id: str) -> None:
        """Drop a context's data if its TTL has elapsed (caller holds lock)."""
        expiry = self._expiry.get(context_id)
        if expiry is not None and expiry < time.monotonic():
            self._data.pop(context_id, None)
            self._expiry.pop(context_id, None)

    async def set(self, context_id: str, field: str, value: Any) -> None:
        """Store ``value`` and (re)arm the context TTL."""
        async with self._lock:
            self._purge_if_expired(context_id)
            self._data.setdefault(context_id, {})[field] = value
            self._expiry[context_id] = time.monotonic() + self._ttl

    async def get(self, context_id: str, field: str) -> Any | None:
        """Return a stored field value, honoring expiry."""
        async with self._lock:
            self._purge_if_expired(context_id)
            return self._data.get(context_id, {}).get(field)

    async def get_all(self, context_id: str) -> dict[str, Any]:
        """Return a copy of all live fields for a context."""
        async with self._lock:
            self._purge_if_expired(context_id)
            return dict(self._data.get(context_id, {}))

    async def delete(self, context_id: str) -> None:
        """Forget all working memory for a context."""
        async with self._lock:
            self._data.pop(context_id, None)
            self._expiry.pop(context_id, None)


class RedisContextStore(ContextStore):
    """Redis-backed working memory using hashes with a sliding TTL."""

    def __init__(self, redis_url: str, ttl_seconds: int, namespace: str = "blvckshell") -> None:
        """Store connection parameters; connect lazily on first use."""
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._namespace = namespace
        self._redis: Redis | None = None

    async def _conn(self) -> Redis:
        """Return a live Redis connection, opening it on first use."""
        if self._redis is None:
            from redis.asyncio import Redis

            self._redis = Redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    def _key(self, context_id: str) -> str:
        """Return the namespaced Redis hash key for a context."""
        return f"{self._namespace}:working:{context_id}"

    async def set(self, context_id: str, field: str, value: Any) -> None:
        """Set a hash field (JSON-encoded) and refresh the TTL."""
        redis = await self._conn()
        key = self._key(context_id)
        await redis.hset(key, field, json.dumps(value))
        await redis.expire(key, self._ttl)

    async def get(self, context_id: str, field: str) -> Any | None:
        """Return a decoded hash field value or ``None``."""
        redis = await self._conn()
        raw = await redis.hget(self._key(context_id), field)
        return json.loads(raw) if raw is not None else None

    async def get_all(self, context_id: str) -> dict[str, Any]:
        """Return all decoded fields for a context."""
        redis = await self._conn()
        raw = await redis.hgetall(self._key(context_id))
        return {key: json.loads(value) for key, value in raw.items()}

    async def delete(self, context_id: str) -> None:
        """Delete the context's Redis hash."""
        redis = await self._conn()
        await redis.delete(self._key(context_id))


def create_context_store() -> ContextStore:
    """Construct the configured working-memory store.

    Returns:
        A :class:`RedisContextStore` when Redis is configured, otherwise an
        :class:`InMemoryContextStore`.
    """
    if settings.use_redis and settings.redis_url:
        return RedisContextStore(
            settings.redis_url,
            settings.working_memory_ttl_seconds,
            settings.bus_namespace,
        )
    return InMemoryContextStore(settings.working_memory_ttl_seconds)
