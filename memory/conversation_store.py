"""Persistent conversation history for Blvckbot."""

from __future__ import annotations

import abc
import uuid
from datetime import datetime

from harness.schemas.conversation import ConversationEntry, ConversationSession


class ConversationStore(abc.ABC):
    """Abstract store for operator ↔ brain conversation history."""

    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Tear down any underlying connection. Idempotent."""

    @abc.abstractmethod
    async def append(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
        *,
        brain_id: str | None = None,
    ) -> ConversationEntry:
        """Append a message to a session."""

    @abc.abstractmethod
    async def get_history(self, session_id: str, *, limit: int = 50) -> list[ConversationEntry]:
        """Return recent messages for a session, oldest first."""

    @abc.abstractmethod
    async def get_or_create_session(self, operator_id: str) -> str:
        """Return an existing active session or create a new session id."""

    @abc.abstractmethod
    async def search_history(self, query: str, *, limit: int = 10) -> list[ConversationEntry]:
        """Keyword search across conversation content."""

    @abc.abstractmethod
    async def list_sessions(self, *, limit: int = 50) -> list[ConversationSession]:
        """Return recent sessions with message counts."""


class InMemoryConversationStore(ConversationStore):
    """In-process conversation store for tests and offline mode."""

    def __init__(self) -> None:
        """Initialize backing stores."""
        self._entries: dict[str, list[ConversationEntry]] = {}
        self._sessions: dict[str, ConversationSession] = {}

    async def connect(self) -> None:
        """No-op connect."""

    async def close(self) -> None:
        """No-op close."""

    async def append(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
        *,
        brain_id: str | None = None,
    ) -> ConversationEntry:
        """Append a message and bump session metadata."""
        entry = ConversationEntry(
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata or {},
            brain_id=brain_id,
        )
        self._entries.setdefault(session_id, []).append(entry)
        session = self._sessions.get(session_id)
        if session is None:
            session = ConversationSession(session_id=session_id)
            self._sessions[session_id] = session
        session.message_count += 1
        return entry.model_copy(deep=True)

    async def get_history(self, session_id: str, *, limit: int = 50) -> list[ConversationEntry]:
        """Return the tail of a session's messages."""
        entries = self._entries.get(session_id, [])
        return [e.model_copy(deep=True) for e in entries[-limit:]]

    async def get_or_create_session(self, operator_id: str) -> str:
        """Reuse the latest session for an operator or create one."""
        for session in reversed(list(self._sessions.values())):
            if session.operator_id == operator_id:
                return session.session_id
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = ConversationSession(
            session_id=session_id,
            operator_id=operator_id,
        )
        self._entries[session_id] = []
        return session_id

    async def search_history(self, query: str, *, limit: int = 10) -> list[ConversationEntry]:
        """Case-insensitive substring search."""
        needle = query.lower()
        hits: list[ConversationEntry] = []
        for entries in self._entries.values():
            for entry in reversed(entries):
                if needle in entry.content.lower():
                    hits.append(entry.model_copy(deep=True))
                    if len(hits) >= limit:
                        return hits
        return hits

    async def list_sessions(self, *, limit: int = 50) -> list[ConversationSession]:
        """Return sessions newest first."""
        sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )
        return [s.model_copy(deep=True) for s in sessions[:limit]]


class SupabaseConversationStore(ConversationStore):
    """Supabase-backed conversation store."""

    TABLE = "conversations"
    SESSIONS_TABLE = "conversation_sessions"

    def __init__(self, url: str, key: str) -> None:
        """Create the store."""
        self._url = url
        self._key = key
        self._client = None  # type: ignore[assignment]
        self._session_cache: dict[str, ConversationSession] = {}

    async def connect(self) -> None:
        """Create the Supabase client lazily."""
        if self._client is not None:
            return
        from supabase import create_client

        self._client = create_client(self._url, self._key)

    async def close(self) -> None:
        """Drop the client reference."""
        self._client = None

    def _require(self):  # type: ignore[no-untyped-def]
        """Return the live client or raise."""
        if self._client is None:
            raise RuntimeError("SupabaseConversationStore is not connected")
        return self._client

    async def append(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
        *,
        brain_id: str | None = None,
    ) -> ConversationEntry:
        """Insert a conversation row."""
        entry = ConversationEntry(
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata or {},
            brain_id=brain_id,
        )
        row = entry.model_dump(mode="json")
        self._require().table(self.TABLE).insert(row).execute()
        if session_id in self._session_cache:
            self._session_cache[session_id].message_count += 1
        return entry

    async def get_history(self, session_id: str, *, limit: int = 50) -> list[ConversationEntry]:
        """Fetch session messages oldest first."""
        res = (
            self._require()
            .table(self.TABLE)
            .select("*")
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return [ConversationEntry.model_validate(r) for r in (res.data or [])]

    async def get_or_create_session(self, operator_id: str) -> str:
        """Return cached or new session id."""
        for session in self._session_cache.values():
            if session.operator_id == operator_id:
                return session.session_id
        session_id = str(uuid.uuid4())
        session = ConversationSession(session_id=session_id, operator_id=operator_id)
        self._session_cache[session_id] = session
        return session_id

    async def search_history(self, query: str, *, limit: int = 10) -> list[ConversationEntry]:
        """Keyword search via ilike."""
        res = (
            self._require()
            .table(self.TABLE)
            .select("*")
            .ilike("content", f"%{query}%")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [ConversationEntry.model_validate(r) for r in (res.data or [])]

    async def list_sessions(self, *, limit: int = 50) -> list[ConversationSession]:
        """Aggregate sessions from conversation rows."""
        res = (
            self._require()
            .table(self.TABLE)
            .select("session_id, created_at")
            .order("created_at", desc=True)
            .limit(limit * 20)
            .execute()
        )
        counts: dict[str, int] = {}
        first_seen: dict[str, datetime] = {}
        for row in res.data or []:
            sid = row["session_id"]
            counts[sid] = counts.get(sid, 0) + 1
            ts = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            first_seen.setdefault(sid, ts)
        sessions = [
            ConversationSession(
                session_id=sid,
                created_at=first_seen[sid],
                message_count=counts[sid],
            )
            for sid in counts
        ]
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions[:limit]
