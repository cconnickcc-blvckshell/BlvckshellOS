"""Brain registry — brains register, advertise capabilities, and heartbeat.

The registry is the harness's directory of who is online and what they can do.
The router never invents capabilities; it can only route to brains the registry
knows about and considers healthy.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from harness.config import settings
from harness.core.logging import get_logger
from harness.core.observer import Observer
from harness.schemas.brain import BrainInfo, BrainStatus
from harness.schemas.event import EventType

logger = get_logger(__name__)


class BrainRegistry:
    """In-memory directory of registered brains and their health."""

    def __init__(self, *, observer: Observer | None = None) -> None:
        """Create an empty registry, optionally wired to an observer."""
        self._brains: dict[str, BrainInfo] = {}
        self._observer = observer
        self._lock = asyncio.Lock()

    async def register(self, info: BrainInfo) -> BrainInfo:
        """Register or refresh a brain's advertisement.

        Args:
            info: The brain's identity and capabilities.

        Returns:
            The stored :class:`BrainInfo`.
        """
        async with self._lock:
            info.last_heartbeat = datetime.now(UTC)
            self._brains[info.brain_id] = info
        if self._observer is not None:
            await self._observer.record(
                EventType.BRAIN_REGISTERED,
                source=info.brain_id,
                message=f"{info.name} registered",
                data={"capabilities": info.capabilities, "model": info.model},
            )
        logger.info("Registered brain '%s' (%s)", info.brain_id, ", ".join(info.capabilities))
        return info

    async def deregister(self, brain_id: str) -> None:
        """Remove a brain from the registry."""
        async with self._lock:
            self._brains.pop(brain_id, None)
        if self._observer is not None:
            await self._observer.record(
                EventType.BRAIN_DEREGISTERED, source=brain_id, message="deregistered"
            )

    async def heartbeat(self, brain_id: str, status: BrainStatus | None = None) -> None:
        """Record a heartbeat (and optional status) for a brain.

        Args:
            brain_id: The brain reporting in.
            status: Optional new activity/health status.
        """
        async with self._lock:
            info = self._brains.get(brain_id)
            if info is None:
                return
            info.last_heartbeat = datetime.now(UTC)
            if status is not None:
                info.status = status

    async def set_status(
        self, brain_id: str, status: BrainStatus, *, task_id: str | None = None
    ) -> None:
        """Update a brain's status orb and current task."""
        async with self._lock:
            info = self._brains.get(brain_id)
            if info is None:
                return
            info.status = status
            info.current_task_id = task_id

    async def get(self, brain_id: str) -> BrainInfo | None:
        """Return a brain's info by id, or ``None``."""
        async with self._lock:
            return self._brains.get(brain_id)

    async def all(self) -> list[BrainInfo]:
        """Return info for every registered brain."""
        async with self._lock:
            return list(self._brains.values())

    async def find_by_capability(self, capability: str) -> list[BrainInfo]:
        """Return healthy brains advertising ``capability``.

        Args:
            capability: The capability to match.

        Returns:
            Healthy brains that advertise the capability, best-effort ordered by
            most-recent heartbeat first.
        """
        async with self._lock:
            candidates = [
                info
                for info in self._brains.values()
                if capability in info.capabilities and self._is_healthy(info)
            ]
        candidates.sort(key=lambda info: info.last_heartbeat, reverse=True)
        return candidates

    async def capabilities(self) -> dict[str, list[str]]:
        """Return a map of ``brain_id`` to its advertised capabilities."""
        async with self._lock:
            return {info.brain_id: list(info.capabilities) for info in self._brains.values()}

    def _is_healthy(self, info: BrainInfo) -> bool:
        """Return whether a brain has heartbeated within the grace window."""
        if info.status == BrainStatus.OFFLINE:
            return False
        age = (datetime.now(UTC) - info.last_heartbeat).total_seconds()
        return age <= settings.heartbeat_grace_seconds

    async def prune_stale(self) -> list[str]:
        """Mark brains that missed the heartbeat grace window as offline.

        Returns:
            The ids of brains that were marked offline.
        """
        stale: list[str] = []
        async with self._lock:
            for info in self._brains.values():
                if info.status != BrainStatus.OFFLINE and not self._is_healthy(info):
                    info.status = BrainStatus.OFFLINE
                    stale.append(info.brain_id)
        for brain_id in stale:
            if self._observer is not None:
                await self._observer.record(
                    EventType.BRAIN_DEREGISTERED,
                    source=brain_id,
                    message="marked offline (stale heartbeat)",
                )
        return stale
