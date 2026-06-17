"""Persistence backends for episodic/doctrine/ledger tables.

Two interchangeable table backends live behind one async interface:

* :class:`InMemoryTable` — a dict-backed table for tests and local bring-up.
* :class:`SupabaseTable` — a thin async wrapper over the Supabase client.

Higher layers (Judgment Ledger, doctrine store, episodic memory) depend only on
the :class:`Table` interface, so swapping the backend never touches them.
"""

from __future__ import annotations

import abc
import asyncio
from copy import deepcopy
from typing import Any

from harness.config import settings
from harness.core.logging import get_logger

logger = get_logger(__name__)

Row = dict[str, Any]


class Table(abc.ABC):
    """An async key-addressable collection of JSON rows."""

    @abc.abstractmethod
    async def upsert(self, row: Row) -> Row:
        """Insert or replace a row keyed by its ``id`` and return it."""

    @abc.abstractmethod
    async def get(self, row_id: str) -> Row | None:
        """Return the row with ``id == row_id`` or ``None``."""

    @abc.abstractmethod
    async def query(self, **filters: Any) -> list[Row]:
        """Return all rows matching the given equality ``filters``."""

    @abc.abstractmethod
    async def all(self) -> list[Row]:
        """Return every row in the table."""


class InMemoryTable(Table):
    """Process-local table backed by a dict, safe for concurrent access."""

    def __init__(self, name: str) -> None:
        """Create an empty table named ``name``."""
        self._name = name
        self._rows: dict[str, Row] = {}
        self._lock = asyncio.Lock()

    async def upsert(self, row: Row) -> Row:
        """Store a deep copy of ``row`` keyed by its ``id``."""
        if "id" not in row:
            raise ValueError(f"row for table '{self._name}' is missing an 'id'")
        async with self._lock:
            self._rows[row["id"]] = deepcopy(row)
        return deepcopy(row)

    async def get(self, row_id: str) -> Row | None:
        """Return a deep copy of the requested row, if present."""
        async with self._lock:
            row = self._rows.get(row_id)
            return deepcopy(row) if row is not None else None

    async def query(self, **filters: Any) -> list[Row]:
        """Return deep copies of all rows matching every filter."""
        async with self._lock:
            return [
                deepcopy(row)
                for row in self._rows.values()
                if all(row.get(key) == value for key, value in filters.items())
            ]

    async def all(self) -> list[Row]:
        """Return deep copies of every row."""
        async with self._lock:
            return [deepcopy(row) for row in self._rows.values()]


class SupabaseTable(Table):
    """Supabase-backed table wrapping the (sync) client in a thread executor."""

    def __init__(self, name: str, client: Any) -> None:
        """Wrap an existing Supabase client for table ``name``."""
        self._name = name
        self._client = client

    async def _run(self, func: Any) -> Any:
        """Execute a blocking Supabase call in a worker thread."""
        return await asyncio.to_thread(func)

    async def upsert(self, row: Row) -> Row:
        """Upsert ``row`` into the Supabase table."""

        def _do() -> Row:
            self._client.table(self._name).upsert(row).execute()
            return row

        return await self._run(_do)

    async def get(self, row_id: str) -> Row | None:
        """Fetch a single row by id from Supabase."""

        def _do() -> Row | None:
            res = self._client.table(self._name).select("*").eq("id", row_id).limit(1).execute()
            return res.data[0] if res.data else None

        return await self._run(_do)

    async def query(self, **filters: Any) -> list[Row]:
        """Run an equality-filtered select against Supabase."""

        def _do() -> list[Row]:
            builder = self._client.table(self._name).select("*")
            for key, value in filters.items():
                builder = builder.eq(key, value)
            return builder.execute().data or []

        return await self._run(_do)

    async def all(self) -> list[Row]:
        """Select every row from the Supabase table."""

        def _do() -> list[Row]:
            return self._client.table(self._name).select("*").execute().data or []

        return await self._run(_do)


def _supabase_client() -> Any | None:
    """Build a Supabase client when configured, else return ``None``."""
    if not settings.use_supabase:
        return None
    try:
        from supabase import create_client

        return create_client(settings.supabase_url, settings.supabase_key)
    except Exception:  # noqa: BLE001 - fall back to in-memory if unavailable
        logger.exception("Failed to create Supabase client; falling back to in-memory")
        return None


def create_table(name: str) -> Table:
    """Create the configured backend for table ``name``.

    Args:
        name: Logical table name (also the Supabase table name).

    Returns:
        A :class:`SupabaseTable` when Supabase is configured and reachable,
        otherwise an :class:`InMemoryTable`.
    """
    client = _supabase_client()
    if client is not None:
        return SupabaseTable(name, client)
    return InMemoryTable(name)
