"""The Doctrine Store — the system's accumulated, validated wisdom.

This is the third tier of shared memory: an append-only record of beliefs that
were promoted from the Judgment Ledger after proving correct. Doctrine is never
deleted, only superseded. It is the long-term memory the whole federation can
lean on.
"""

from __future__ import annotations

import abc
from datetime import UTC, datetime

from harness.schemas.judgment import JudgmentEntry


class DoctrineStore(abc.ABC):
    """Abstract append-only store for promoted doctrine."""

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Tear down any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def promote(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Append a validated belief to doctrine and return the stored copy."""

    @abc.abstractmethod
    async def supersede(self, doctrine_id: str, superseded_by: str) -> JudgmentEntry | None:
        """Mark a doctrine entry as superseded by a newer belief.

        Args:
            doctrine_id: The doctrine entry being retired.
            superseded_by: The id of the belief that replaces it.

        Returns:
            The updated doctrine entry, or ``None`` if not found.
        """

    @abc.abstractmethod
    async def list_active(self, *, limit: int = 200) -> list[JudgmentEntry]:
        """Return active (non-retired) doctrine, newest first."""

    @abc.abstractmethod
    async def list_all(self, *, limit: int = 200) -> list[JudgmentEntry]:
        """Return all doctrine entries including retired ones, newest first."""

    @abc.abstractmethod
    async def update(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Persist changes to an existing doctrine entry."""


class InMemoryDoctrineStore(DoctrineStore):
    """An in-process doctrine store for tests and offline operation."""

    def __init__(self) -> None:
        """Initialize the backing store and ordering."""
        self._entries: dict[str, JudgmentEntry] = {}
        self._order: list[str] = []

    async def connect(self) -> None:
        """No-op connect."""

    async def close(self) -> None:
        """No-op close."""

    async def promote(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Append a deep copy of the belief, flagged as promoted doctrine."""
        stored = entry.model_copy(deep=True)
        stored.doctrine_promoted = True
        stored.record_change("doctrine_promoted")
        self._entries[stored.id] = stored
        self._order.append(stored.id)
        return stored.model_copy(deep=True)

    async def supersede(self, doctrine_id: str, superseded_by: str) -> JudgmentEntry | None:
        """Retire a doctrine entry, recording what replaced it."""
        entry = self._entries.get(doctrine_id)
        if entry is None:
            return None
        entry.retired = True
        entry.record_change(
            "superseded",
            {"superseded_by": superseded_by, "at": datetime.now(UTC).isoformat()},
        )
        return entry.model_copy(deep=True)

    async def list_active(self, *, limit: int = 200) -> list[JudgmentEntry]:
        """Return active doctrine, newest first."""
        result: list[JudgmentEntry] = []
        for eid in reversed(self._order):
            entry = self._entries[eid]
            if entry.retired:
                continue
            result.append(entry.model_copy(deep=True))
            if len(result) >= limit:
                break
        return result

    async def list_all(self, *, limit: int = 200) -> list[JudgmentEntry]:
        """Return all doctrine, newest first."""
        return [
            self._entries[eid].model_copy(deep=True) for eid in reversed(self._order[-limit:])
        ]

    async def update(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Overwrite an existing doctrine entry."""
        if entry.id not in self._entries:
            raise KeyError(f"doctrine entry {entry.id} not found")
        self._entries[entry.id] = entry.model_copy(deep=True)
        return entry.model_copy(deep=True)


class SupabaseDoctrineStore(DoctrineStore):
    """A Supabase-backed doctrine store on the append-only ``doctrine`` table."""

    TABLE = "doctrine"

    def __init__(self, url: str, key: str) -> None:
        """Create the store.

        Args:
            url: Supabase project URL.
            key: Supabase service key.
        """
        self._url = url
        self._key = key
        self._client = None  # type: ignore[assignment]

    async def connect(self) -> None:
        """Create the Supabase client lazily."""
        if self._client is not None:
            return
        from supabase import create_client

        self._client = create_client(self._url, self._key)

    async def close(self) -> None:
        """Drop the Supabase client reference."""
        self._client = None

    def _require(self):  # type: ignore[no-untyped-def]
        """Return the live client or raise."""
        if self._client is None:
            raise RuntimeError("SupabaseDoctrineStore is not connected; call connect() first")
        return self._client

    async def promote(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Insert a promoted belief into the doctrine table."""
        entry.doctrine_promoted = True
        entry.record_change("doctrine_promoted")
        self._require().table(self.TABLE).insert(entry.model_dump(mode="json")).execute()
        return entry

    async def supersede(self, doctrine_id: str, superseded_by: str) -> JudgmentEntry | None:
        """Mark a doctrine row retired with a changelog note."""
        res = self._require().table(self.TABLE).select("*").eq("id", doctrine_id).execute()
        rows = res.data or []
        if not rows:
            return None
        entry = JudgmentEntry.model_validate(rows[0])
        entry.retired = True
        entry.record_change("superseded", {"superseded_by": superseded_by})
        self._require().table(self.TABLE).upsert(entry.model_dump(mode="json")).execute()
        return entry

    async def list_active(self, *, limit: int = 200) -> list[JudgmentEntry]:
        """Return active doctrine rows, newest first."""
        res = (
            self._require()
            .table(self.TABLE)
            .select("*")
            .eq("retired", False)
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return [JudgmentEntry.model_validate(r) for r in (res.data or [])]

    async def list_all(self, *, limit: int = 200) -> list[JudgmentEntry]:
        """Return all doctrine rows, newest first."""
        res = (
            self._require()
            .table(self.TABLE)
            .select("*")
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return [JudgmentEntry.model_validate(r) for r in (res.data or [])]

    async def update(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Upsert a doctrine row."""
        self._require().table(self.TABLE).upsert(entry.model_dump(mode="json")).execute()
        return entry
