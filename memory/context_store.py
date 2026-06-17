"""Working memory — short-term, TTL-bound pipeline context.

This is the first tier of the shared memory architecture. It holds active
pipeline context, current task state, and in-flight brain outputs. Entries live
in Redis with a TTL (default 24h) so working memory self-cleans.
"""

from __future__ import annotations

import abc
import json
from typing import Any

_PREFIX = "blvckshell:ctx:"


class ContextStore(abc.ABC):
    """Abstract key/value working-memory store scoped per pipeline run."""

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Tear down any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def set(self, context_id: str, key: str, value: Any) -> None:
        """Store a value under ``key`` within a pipeline's context.

        Args:
            context_id: The pipeline run identifier.
            key: The field name within the context.
            value: A JSON-serializable value.
        """

    @abc.abstractmethod
    async def get(self, context_id: str, key: str) -> Any | None:
        """Return the value for ``key`` in a context, or ``None`` if absent."""

    @abc.abstractmethod
    async def get_all(self, context_id: str) -> dict[str, Any]:
        """Return the entire working-memory dict for a context."""

    @abc.abstractmethod
    async def append(self, context_id: str, key: str, value: Any) -> None:
        """Append a value to a list stored under ``key`` in a context."""

    @abc.abstractmethod
    async def delete(self, context_id: str) -> None:
        """Delete all working memory for a context."""


class InMemoryContextStore(ContextStore):
    """An in-process context store for tests and offline operation."""

    def __init__(self) -> None:
        """Initialize the backing dictionary."""
        self._data: dict[str, dict[str, Any]] = {}

    async def connect(self) -> None:
        """No-op connect."""

    async def close(self) -> None:
        """No-op close."""

    async def set(self, context_id: str, key: str, value: Any) -> None:
        """Store a value in the in-memory context."""
        self._data.setdefault(context_id, {})[key] = value

    async def get(self, context_id: str, key: str) -> Any | None:
        """Return a value from the in-memory context."""
        return self._data.get(context_id, {}).get(key)

    async def get_all(self, context_id: str) -> dict[str, Any]:
        """Return the full in-memory context dict (a copy)."""
        return dict(self._data.get(context_id, {}))

    async def append(self, context_id: str, key: str, value: Any) -> None:
        """Append to a list within the in-memory context."""
        bucket = self._data.setdefault(context_id, {})
        current = bucket.get(key)
        if not isinstance(current, list):
            current = []
        current.append(value)
        bucket[key] = current

    async def delete(self, context_id: str) -> None:
        """Drop a context from memory."""
        self._data.pop(context_id, None)


class RedisContextStore(ContextStore):
    """A Redis-backed context store using a hash per context with a TTL."""

    def __init__(self, redis_url: str, ttl_seconds: int) -> None:
        """Create the store.

        Args:
            redis_url: The Redis connection URL.
            ttl_seconds: TTL applied to each context hash on write.
        """
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._redis = None  # type: ignore[assignment]

    async def connect(self) -> None:
        """Open the Redis connection lazily."""
        if self._redis is not None:
            return
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        await self._redis.ping()

    async def close(self) -> None:
        """Close the Redis connection if open."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    def _key(self, context_id: str) -> str:
        """Return the Redis hash key for a context."""
        return _PREFIX + context_id

    def _require(self):  # type: ignore[no-untyped-def]
        """Return the live Redis client or raise."""
        if self._redis is None:
            raise RuntimeError("RedisContextStore is not connected; call connect() first")
        return self._redis

    async def set(self, context_id: str, key: str, value: Any) -> None:
        """Store a JSON-encoded value in the context hash and refresh its TTL."""
        redis = self._require()
        await redis.hset(self._key(context_id), key, json.dumps(value))
        await redis.expire(self._key(context_id), self._ttl)

    async def get(self, context_id: str, key: str) -> Any | None:
        """Return and JSON-decode a value from the context hash."""
        raw = await self._require().hget(self._key(context_id), key)
        return None if raw is None else json.loads(raw)

    async def get_all(self, context_id: str) -> dict[str, Any]:
        """Return the whole context hash, JSON-decoding every value."""
        raw = await self._require().hgetall(self._key(context_id))
        return {k: json.loads(v) for k, v in raw.items()}

    async def append(self, context_id: str, key: str, value: Any) -> None:
        """Append to a JSON list stored under ``key`` in the context hash."""
        current = await self.get(context_id, key)
        if not isinstance(current, list):
            current = []
        current.append(value)
        await self.set(context_id, key, current)

    async def delete(self, context_id: str) -> None:
        """Delete the context hash."""
        await self._require().delete(self._key(context_id))
