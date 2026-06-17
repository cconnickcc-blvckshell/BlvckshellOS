"""Brain Registry — registration, discovery, and health.

Brains register on startup, advertise their capabilities, and report heartbeats.
CKOS routes work strictly to capabilities advertised here — it must never
hallucinate a brain that is not registered.

A Redis-backed implementation lets brains in separate containers share one
registry; an in-memory implementation backs tests and single-process runs.
"""

from __future__ import annotations

import abc
from datetime import UTC, datetime

from harness.logging_config import get_logger
from harness.schemas.brain_info import BrainInfo, BrainState

logger = get_logger("registry")

_REGISTRY_KEY = "blvckshell:registry"


def _now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


class BrainRegistry(abc.ABC):
    """Abstract registry of brains and their advertised capabilities."""

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Tear down any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def register(self, info: BrainInfo) -> None:
        """Add or replace a brain's registration record."""

    @abc.abstractmethod
    async def deregister(self, brain_id: str) -> None:
        """Remove a brain's registration record."""

    @abc.abstractmethod
    async def get(self, brain_id: str) -> BrainInfo | None:
        """Return a brain's record, or ``None`` if unregistered."""

    @abc.abstractmethod
    async def list_all(self) -> list[BrainInfo]:
        """Return every registered brain's record."""

    async def find_by_capability(self, capability: str) -> list[BrainInfo]:
        """Return all registered brains advertising a capability.

        Args:
            capability: The capability to match.
        """
        return [b for b in await self.list_all() if b.handles(capability)]

    async def heartbeat(
        self, brain_id: str, *, state: BrainState | None = None
    ) -> BrainInfo | None:
        """Record a heartbeat (and optional state) for a brain.

        Args:
            brain_id: The brain reporting in.
            state: An optional new live state to record.

        Returns:
            The updated record, or ``None`` if the brain is unregistered.
        """
        info = await self.get(brain_id)
        if info is None:
            return None
        info.last_heartbeat = _now()
        if state is not None:
            info.state = state
        await self.register(info)
        return info

    async def set_state(self, brain_id: str, state: BrainState) -> BrainInfo | None:
        """Update a brain's live state (drives the UI status orbs)."""
        info = await self.get(brain_id)
        if info is None:
            return None
        info.state = state
        await self.register(info)
        return info

    async def stale_brains(self, timeout_seconds: int) -> list[BrainInfo]:
        """Return brains whose last heartbeat is older than the timeout.

        Args:
            timeout_seconds: Seconds since last heartbeat to consider stale.
        """
        cutoff = _now().timestamp() - timeout_seconds
        stale: list[BrainInfo] = []
        for info in await self.list_all():
            if info.last_heartbeat.timestamp() < cutoff:
                stale.append(info)
        return stale


class InMemoryBrainRegistry(BrainRegistry):
    """An in-process registry for tests and single-process runs."""

    def __init__(self) -> None:
        """Initialize the backing dictionary."""
        self._brains: dict[str, BrainInfo] = {}

    async def connect(self) -> None:
        """No-op connect."""

    async def close(self) -> None:
        """No-op close."""

    async def register(self, info: BrainInfo) -> None:
        """Store a deep copy of the brain record."""
        self._brains[info.brain_id] = info.model_copy(deep=True)

    async def deregister(self, brain_id: str) -> None:
        """Remove a brain record if present."""
        self._brains.pop(brain_id, None)

    async def get(self, brain_id: str) -> BrainInfo | None:
        """Return a deep copy of a brain record, if present."""
        found = self._brains.get(brain_id)
        return None if found is None else found.model_copy(deep=True)

    async def list_all(self) -> list[BrainInfo]:
        """Return deep copies of all brain records."""
        return [b.model_copy(deep=True) for b in self._brains.values()]


class RedisBrainRegistry(BrainRegistry):
    """A Redis-backed registry storing records in a single hash."""

    def __init__(self, redis_url: str) -> None:
        """Create the registry.

        Args:
            redis_url: The Redis connection URL.
        """
        self._redis_url = redis_url
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

    def _require(self):  # type: ignore[no-untyped-def]
        """Return the live Redis client or raise."""
        if self._redis is None:
            raise RuntimeError("RedisBrainRegistry is not connected; call connect() first")
        return self._redis

    async def register(self, info: BrainInfo) -> None:
        """Write the brain record JSON into the registry hash."""
        await self._require().hset(_REGISTRY_KEY, info.brain_id, info.model_dump_json())

    async def deregister(self, brain_id: str) -> None:
        """Remove the brain record from the registry hash."""
        await self._require().hdel(_REGISTRY_KEY, brain_id)

    async def get(self, brain_id: str) -> BrainInfo | None:
        """Fetch and parse a brain record from the registry hash."""
        raw = await self._require().hget(_REGISTRY_KEY, brain_id)
        return None if raw is None else BrainInfo.model_validate_json(raw)

    async def list_all(self) -> list[BrainInfo]:
        """Fetch and parse every brain record in the registry hash."""
        raw = await self._require().hgetall(_REGISTRY_KEY)
        return [BrainInfo.model_validate_json(v) for v in raw.values()]


def build_registry(*, redis_url: str, use_in_memory: bool) -> BrainRegistry:
    """Construct the configured registry implementation.

    Args:
        redis_url: Redis URL used when not in-memory.
        use_in_memory: When true, return the in-process registry.
    """
    if use_in_memory:
        return InMemoryBrainRegistry()
    return RedisBrainRegistry(redis_url)
