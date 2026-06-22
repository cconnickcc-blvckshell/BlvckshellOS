"""The Notes Store — durable, semantically searchable conversation memory.

Notes are summaries distilled from conversations and kept forever, each
carrying an embedding so they can be recalled by meaning rather than exact
keyword match. This is the durable substrate the reflection job writes to and
the brain reads from when building context for a new request.
"""

from __future__ import annotations

import abc

from harness.core.embeddings import cosine_similarity
from harness.schemas.memory import MemoryNote


class NotesStore(abc.ABC):
    """Abstract append-only store for personal memory notes."""

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Tear down any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def add(self, note: MemoryNote) -> MemoryNote:
        """Persist a new note and return the stored copy."""

    @abc.abstractmethod
    async def list_recent(
        self, *, operator_id: str | None = None, limit: int = 50
    ) -> list[MemoryNote]:
        """Return the most recent notes, newest first."""

    @abc.abstractmethod
    async def recall(
        self, query_embedding: list[float], *, operator_id: str | None = None, limit: int = 5
    ) -> list[MemoryNote]:
        """Return the notes most semantically similar to ``query_embedding``."""


class InMemoryNotesStore(NotesStore):
    """An in-process notes store for tests and offline operation."""

    def __init__(self) -> None:
        """Initialize the backing store and insertion ordering."""
        self._notes: dict[str, MemoryNote] = {}
        self._order: list[str] = []

    async def connect(self) -> None:
        """No-op connect."""

    async def close(self) -> None:
        """No-op close."""

    async def add(self, note: MemoryNote) -> MemoryNote:
        """Store a deep copy of the note."""
        stored = note.model_copy(deep=True)
        self._notes[stored.id] = stored
        self._order.append(stored.id)
        return stored.model_copy(deep=True)

    async def list_recent(
        self, *, operator_id: str | None = None, limit: int = 50
    ) -> list[MemoryNote]:
        """Return recent notes, newest first."""
        result: list[MemoryNote] = []
        for nid in reversed(self._order):
            note = self._notes[nid]
            if operator_id is not None and note.operator_id != operator_id:
                continue
            result.append(note.model_copy(deep=True))
            if len(result) >= limit:
                break
        return result

    async def recall(
        self, query_embedding: list[float], *, operator_id: str | None = None, limit: int = 5
    ) -> list[MemoryNote]:
        """Rank stored notes by cosine similarity to ``query_embedding``."""
        candidates = [
            n for n in self._notes.values() if operator_id is None or n.operator_id == operator_id
        ]
        ranked = sorted(
            candidates, key=lambda n: cosine_similarity(query_embedding, n.embedding), reverse=True
        )
        return [n.model_copy(deep=True) for n in ranked[:limit]]


class SupabaseNotesStore(NotesStore):
    """A Supabase-backed notes store on the ``memory_notes`` table.

    There is no pgvector dependency here: embeddings are stored as a plain
    JSON float array and similarity ranking happens in Python over a bounded
    recent-rows candidate set, mirroring the existing ``ilike`` keyword-search
    fallback used elsewhere in this codebase.
    """

    TABLE = "memory_notes"
    CANDIDATE_LIMIT = 500

    def __init__(self, url: str, key: str) -> None:
        """Create the store."""
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
            raise RuntimeError("SupabaseNotesStore is not connected; call connect() first")
        return self._client

    async def add(self, note: MemoryNote) -> MemoryNote:
        """Insert a note row."""
        self._require().table(self.TABLE).insert(note.model_dump(mode="json")).execute()
        return note

    async def list_recent(
        self, *, operator_id: str | None = None, limit: int = 50
    ) -> list[MemoryNote]:
        """Return recent note rows, newest first."""
        query = self._require().table(self.TABLE).select("*")
        if operator_id is not None:
            query = query.eq("operator_id", operator_id)
        res = query.order("created_at", desc=True).limit(limit).execute()
        return [MemoryNote.model_validate(r) for r in (res.data or [])]

    async def recall(
        self, query_embedding: list[float], *, operator_id: str | None = None, limit: int = 5
    ) -> list[MemoryNote]:
        """Rank a bounded recent candidate set by cosine similarity."""
        query = self._require().table(self.TABLE).select("*")
        if operator_id is not None:
            query = query.eq("operator_id", operator_id)
        res = query.order("created_at", desc=True).limit(self.CANDIDATE_LIMIT).execute()
        candidates = [MemoryNote.model_validate(r) for r in (res.data or [])]
        ranked = sorted(
            candidates, key=lambda n: cosine_similarity(query_embedding, n.embedding), reverse=True
        )
        return ranked[:limit]
