"""The Opinions Store — synthesized, explicitly revisable standing positions.

Where Doctrine is append-only validated belief about what works, Opinions are
the system's developing point of view about the operator, the project, and
the world — formed from accumulated notes, and revised (not just appended)
as understanding changes. Revising an opinion retires the old one and links
it to its replacement, so the full arc of how a view changed is never lost.
"""

from __future__ import annotations

import abc

from harness.core.embeddings import cosine_similarity
from harness.schemas.memory import Opinion


class OpinionsStore(abc.ABC):
    """Abstract revise-in-place store for standing opinions."""

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Tear down any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def add(self, opinion: Opinion) -> Opinion:
        """Persist a newly formed opinion and return the stored copy."""

    @abc.abstractmethod
    async def get(self, opinion_id: str) -> Opinion | None:
        """Return an opinion by id, or ``None`` if missing."""

    @abc.abstractmethod
    async def revise(self, opinion_id: str, replacement: Opinion) -> Opinion | None:
        """Retire ``opinion_id`` in favor of ``replacement``, linking the two.

        Returns:
            The newly stored replacement opinion, or ``None`` if the
            original opinion does not exist.
        """

    @abc.abstractmethod
    async def list_active(
        self, *, operator_id: str | None = None, limit: int = 200
    ) -> list[Opinion]:
        """Return active (non-retired) opinions, newest first."""

    @abc.abstractmethod
    async def list_all(
        self, *, operator_id: str | None = None, limit: int = 200
    ) -> list[Opinion]:
        """Return all opinions including retired ones, newest first."""

    @abc.abstractmethod
    async def recall(
        self, query_embedding: list[float], *, operator_id: str | None = None, limit: int = 5
    ) -> list[Opinion]:
        """Return the active opinions most semantically relevant to a query."""


class InMemoryOpinionsStore(OpinionsStore):
    """An in-process opinions store for tests and offline operation."""

    def __init__(self) -> None:
        """Initialize the backing store and insertion ordering."""
        self._opinions: dict[str, Opinion] = {}
        self._order: list[str] = []

    async def connect(self) -> None:
        """No-op connect."""

    async def close(self) -> None:
        """No-op close."""

    async def add(self, opinion: Opinion) -> Opinion:
        """Store a deep copy, marking it created in the changelog."""
        stored = opinion.model_copy(deep=True)
        stored.record_change("created")
        self._opinions[stored.id] = stored
        self._order.append(stored.id)
        return stored.model_copy(deep=True)

    async def get(self, opinion_id: str) -> Opinion | None:
        """Return a deep copy of the requested opinion, if present."""
        found = self._opinions.get(opinion_id)
        return None if found is None else found.model_copy(deep=True)

    async def revise(self, opinion_id: str, replacement: Opinion) -> Opinion | None:
        """Retire the old opinion and store the replacement, linked both ways."""
        old = self._opinions.get(opinion_id)
        if old is None:
            return None
        old.retired = True
        old.superseded_by = replacement.id
        old.record_change("superseded", {"superseded_by": replacement.id})

        new = replacement.model_copy(deep=True)
        new.supersedes = opinion_id
        new.record_change("revised", {"supersedes": opinion_id})
        self._opinions[new.id] = new
        self._order.append(new.id)
        return new.model_copy(deep=True)

    async def list_active(
        self, *, operator_id: str | None = None, limit: int = 200
    ) -> list[Opinion]:
        """Return active opinions, newest first."""
        result: list[Opinion] = []
        for oid in reversed(self._order):
            op = self._opinions[oid]
            if op.retired:
                continue
            if operator_id is not None and op.operator_id != operator_id:
                continue
            result.append(op.model_copy(deep=True))
            if len(result) >= limit:
                break
        return result

    async def list_all(
        self, *, operator_id: str | None = None, limit: int = 200
    ) -> list[Opinion]:
        """Return all opinions, newest first."""
        result: list[Opinion] = []
        for oid in reversed(self._order):
            op = self._opinions[oid]
            if operator_id is not None and op.operator_id != operator_id:
                continue
            result.append(op.model_copy(deep=True))
            if len(result) >= limit:
                break
        return result

    async def recall(
        self, query_embedding: list[float], *, operator_id: str | None = None, limit: int = 5
    ) -> list[Opinion]:
        """Rank active opinions by cosine similarity to ``query_embedding``."""
        candidates = [
            op
            for op in self._opinions.values()
            if not op.retired and (operator_id is None or op.operator_id == operator_id)
        ]
        ranked = sorted(
            candidates, key=lambda o: cosine_similarity(query_embedding, o.embedding), reverse=True
        )
        return [o.model_copy(deep=True) for o in ranked[:limit]]


class SupabaseOpinionsStore(OpinionsStore):
    """A Supabase-backed opinions store on the ``memory_opinions`` table."""

    TABLE = "memory_opinions"
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
            raise RuntimeError("SupabaseOpinionsStore is not connected; call connect() first")
        return self._client

    async def add(self, opinion: Opinion) -> Opinion:
        """Insert a newly formed opinion row."""
        opinion.record_change("created")
        self._require().table(self.TABLE).insert(opinion.model_dump(mode="json")).execute()
        return opinion

    async def get(self, opinion_id: str) -> Opinion | None:
        """Fetch a single opinion row by id."""
        res = self._require().table(self.TABLE).select("*").eq("id", opinion_id).execute()
        rows = res.data or []
        return Opinion.model_validate(rows[0]) if rows else None

    async def revise(self, opinion_id: str, replacement: Opinion) -> Opinion | None:
        """Retire the old row and insert the replacement, linked both ways."""
        old = await self.get(opinion_id)
        if old is None:
            return None
        old.retired = True
        old.superseded_by = replacement.id
        old.record_change("superseded", {"superseded_by": replacement.id})
        self._require().table(self.TABLE).upsert(old.model_dump(mode="json")).execute()

        replacement.supersedes = opinion_id
        replacement.record_change("revised", {"supersedes": opinion_id})
        self._require().table(self.TABLE).insert(replacement.model_dump(mode="json")).execute()
        return replacement

    async def list_active(
        self, *, operator_id: str | None = None, limit: int = 200
    ) -> list[Opinion]:
        """Return active opinion rows, newest first."""
        query = self._require().table(self.TABLE).select("*").eq("retired", False)
        if operator_id is not None:
            query = query.eq("operator_id", operator_id)
        res = query.order("created_at", desc=True).limit(limit).execute()
        return [Opinion.model_validate(r) for r in (res.data or [])]

    async def list_all(
        self, *, operator_id: str | None = None, limit: int = 200
    ) -> list[Opinion]:
        """Return all opinion rows, newest first."""
        query = self._require().table(self.TABLE).select("*")
        if operator_id is not None:
            query = query.eq("operator_id", operator_id)
        res = query.order("created_at", desc=True).limit(limit).execute()
        return [Opinion.model_validate(r) for r in (res.data or [])]

    async def recall(
        self, query_embedding: list[float], *, operator_id: str | None = None, limit: int = 5
    ) -> list[Opinion]:
        """Rank a bounded active candidate set by cosine similarity."""
        query = self._require().table(self.TABLE).select("*").eq("retired", False)
        if operator_id is not None:
            query = query.eq("operator_id", operator_id)
        res = query.order("created_at", desc=True).limit(self.CANDIDATE_LIMIT).execute()
        candidates = [Opinion.model_validate(r) for r in (res.data or [])]
        ranked = sorted(
            candidates, key=lambda o: cosine_similarity(query_embedding, o.embedding), reverse=True
        )
        return ranked[:limit]
