"""The Judgment Ledger — episodic memory of every belief a brain has held.

This is the second tier of shared memory and the heart of the system's ability
to learn. Each :class:`~harness.schemas.judgment.JudgmentEntry` records what a
brain believed, the evidence and assumptions behind it, and — once known — the
outcome. Correct, high-confidence beliefs can later be promoted to doctrine.

A Supabase (PostgreSQL) implementation persists entries durably; an in-memory
implementation backs tests and offline runs.
"""

from __future__ import annotations

import abc
from datetime import UTC, datetime

from harness.schemas.judgment import JudgmentEntry


class JudgmentLedger(abc.ABC):
    """Abstract append-and-amend store for Judgment Ledger entries."""

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Tear down any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def record(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Persist a new judgment entry and return the stored value."""

    @abc.abstractmethod
    async def get(self, entry_id: str) -> JudgmentEntry | None:
        """Return a judgment entry by id, or ``None`` if missing."""

    @abc.abstractmethod
    async def update(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Persist changes to an existing entry and return the stored value."""

    @abc.abstractmethod
    async def list_for_context(self, context_id: str) -> list[JudgmentEntry]:
        """Return all entries belonging to a pipeline run."""

    @abc.abstractmethod
    async def list_recent(
        self, *, brain_id: str | None = None, limit: int = 50
    ) -> list[JudgmentEntry]:
        """Return the most recent entries, optionally filtered by brain."""

    async def record_outcome(
        self, entry_id: str, *, outcome: str, was_correct: bool
    ) -> JudgmentEntry | None:
        """Record the real-world outcome of a previously logged belief.

        Args:
            entry_id: The judgment entry to update.
            outcome: A description of what actually happened.
            was_correct: Whether the original belief proved correct.

        Returns:
            The updated entry, or ``None`` if the entry does not exist.
        """
        entry = await self.get(entry_id)
        if entry is None:
            return None
        entry.outcome = outcome
        entry.outcome_timestamp = datetime.now(UTC)
        entry.was_correct = was_correct
        entry.record_change("outcome_recorded", {"was_correct": was_correct})
        return await self.update(entry)


class InMemoryJudgmentLedger(JudgmentLedger):
    """An in-process ledger for tests and offline operation."""

    def __init__(self) -> None:
        """Initialize the backing store and insertion ordering."""
        self._entries: dict[str, JudgmentEntry] = {}
        self._order: list[str] = []

    async def connect(self) -> None:
        """No-op connect."""

    async def close(self) -> None:
        """No-op close."""

    async def record(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Store a copy of the entry, preserving insertion order."""
        stored = entry.model_copy(deep=True)
        stored.record_change("created")
        self._entries[stored.id] = stored
        self._order.append(stored.id)
        return stored.model_copy(deep=True)

    async def get(self, entry_id: str) -> JudgmentEntry | None:
        """Return a deep copy of the requested entry, if present."""
        found = self._entries.get(entry_id)
        return None if found is None else found.model_copy(deep=True)

    async def update(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Overwrite an existing entry with a deep copy of ``entry``."""
        if entry.id not in self._entries:
            raise KeyError(f"judgment entry {entry.id} not found")
        self._entries[entry.id] = entry.model_copy(deep=True)
        return entry.model_copy(deep=True)

    async def list_for_context(self, context_id: str) -> list[JudgmentEntry]:
        """Return all entries for a context in insertion order."""
        return [
            self._entries[eid].model_copy(deep=True)
            for eid in self._order
            if self._entries[eid].context_id == context_id
        ]

    async def list_recent(
        self, *, brain_id: str | None = None, limit: int = 50
    ) -> list[JudgmentEntry]:
        """Return the most recent entries, newest first."""
        result: list[JudgmentEntry] = []
        for eid in reversed(self._order):
            entry = self._entries[eid]
            if brain_id is not None and entry.brain_id != brain_id:
                continue
            result.append(entry.model_copy(deep=True))
            if len(result) >= limit:
                break
        return result


class SupabaseJudgmentLedger(JudgmentLedger):
    """A Supabase-backed ledger persisting entries to the ``judgment_ledger`` table."""

    TABLE = "judgment_ledger"

    def __init__(self, url: str, key: str) -> None:
        """Create the ledger.

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
            raise RuntimeError("SupabaseJudgmentLedger is not connected; call connect() first")
        return self._client

    @staticmethod
    def _to_row(entry: JudgmentEntry) -> dict:
        """Serialize an entry to a JSON-safe row dict."""
        return entry.model_dump(mode="json")

    @staticmethod
    def _from_row(row: dict) -> JudgmentEntry:
        """Deserialize a row dict back into an entry."""
        return JudgmentEntry.model_validate(row)

    async def record(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Insert a new entry row and return the stored entry."""
        entry.record_change("created")
        self._require().table(self.TABLE).insert(self._to_row(entry)).execute()
        return entry

    async def get(self, entry_id: str) -> JudgmentEntry | None:
        """Fetch a single entry row by id."""
        res = self._require().table(self.TABLE).select("*").eq("id", entry_id).execute()
        rows = res.data or []
        return self._from_row(rows[0]) if rows else None

    async def update(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Upsert the entry row."""
        self._require().table(self.TABLE).upsert(self._to_row(entry)).execute()
        return entry

    async def list_for_context(self, context_id: str) -> list[JudgmentEntry]:
        """Return all rows for a context, oldest first."""
        res = (
            self._require()
            .table(self.TABLE)
            .select("*")
            .eq("context_id", context_id)
            .order("timestamp", desc=False)
            .execute()
        )
        return [self._from_row(r) for r in (res.data or [])]

    async def list_recent(
        self, *, brain_id: str | None = None, limit: int = 50
    ) -> list[JudgmentEntry]:
        """Return the most recent rows, newest first, optionally per brain."""
        query = self._require().table(self.TABLE).select("*")
        if brain_id is not None:
            query = query.eq("brain_id", brain_id)
        res = query.order("timestamp", desc=True).limit(limit).execute()
        return [self._from_row(r) for r in (res.data or [])]
