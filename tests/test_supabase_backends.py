"""Tests for the Supabase-backed stores using a lightweight fake client.

The fake mimics the subset of the supabase-py query builder the harness uses
(insert / upsert / select / eq / order / limit / execute), so the production
persistence code paths are exercised without a real Supabase project.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harness.core.observer import SupabaseAuditStore
from harness.schemas.audit import AuditEvent, AuditEventType
from harness.schemas.judgment import JudgmentEntry
from memory.doctrine_store import SupabaseDoctrineStore
from memory.judgment_ledger import SupabaseJudgmentLedger


@dataclass
class _Result:
    data: list[dict[str, Any]]


class _Query:
    """A chainable query over one table's row list."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._op: str | None = None
        self._payload: dict[str, Any] | None = None
        self._filters: list[tuple[str, Any]] = []
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None

    def insert(self, row: dict[str, Any]) -> _Query:
        self._op, self._payload = "insert", row
        return self

    def upsert(self, row: dict[str, Any]) -> _Query:
        self._op, self._payload = "upsert", row
        return self

    def select(self, *_cols: str) -> _Query:
        self._op = "select"
        return self

    def eq(self, col: str, val: Any) -> _Query:
        self._filters.append((col, val))
        return self

    def order(self, col: str, desc: bool = False) -> _Query:
        self._order = (col, desc)
        return self

    def limit(self, n: int) -> _Query:
        self._limit = n
        return self

    def execute(self) -> _Result:
        if self._op == "insert":
            self._rows.append(dict(self._payload or {}))
            return _Result([self._payload or {}])
        if self._op == "upsert":
            payload = dict(self._payload or {})
            for i, existing in enumerate(self._rows):
                if existing.get("id") == payload.get("id"):
                    self._rows[i] = payload
                    break
            else:
                self._rows.append(payload)
            return _Result([payload])
        rows = [r for r in self._rows if all(r.get(c) == v for c, v in self._filters)]
        if self._order is not None:
            col, desc = self._order
            rows = sorted(rows, key=lambda r: r.get(col, ""), reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return _Result(list(rows))


@dataclass
class _FakeSupabase:
    tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def table(self, name: str) -> _Query:
        return _Query(self.tables.setdefault(name, []))


async def test_supabase_judgment_ledger_round_trip() -> None:
    ledger = SupabaseJudgmentLedger("url", "key")
    ledger._client = _FakeSupabase()
    entry = JudgmentEntry(brain_id="venture", context_id="c1", belief="b", confidence=0.9)
    await ledger.record(entry)

    fetched = await ledger.get(entry.id)
    assert fetched is not None and fetched.belief == "b"

    updated = await ledger.record_outcome(entry.id, outcome="ok", was_correct=True)
    assert updated is not None and updated.was_correct is True

    by_ctx = await ledger.list_for_context("c1")
    assert len(by_ctx) == 1
    recent = await ledger.list_recent(brain_id="venture", limit=10)
    assert recent[0].brain_id == "venture"


async def test_supabase_doctrine_store() -> None:
    doctrine = SupabaseDoctrineStore("url", "key")
    doctrine._client = _FakeSupabase()
    entry = JudgmentEntry(brain_id="venture", context_id="c1", belief="wisdom", confidence=0.95)
    promoted = await doctrine.promote(entry)
    assert promoted.doctrine_promoted is True

    active = await doctrine.list_active()
    assert len(active) == 1

    superseded = await doctrine.supersede(entry.id, "new-belief")
    assert superseded is not None and superseded.retired is True
    assert await doctrine.list_active() == []
    assert len(await doctrine.list_all()) == 1


async def test_supabase_audit_store() -> None:
    store = SupabaseAuditStore("url", "key")
    store._client = _FakeSupabase()
    await store.append(
        AuditEvent(event_type=AuditEventType.LLM_CALL, source="venture", context_id="c1")
    )
    await store.append(
        AuditEvent(event_type=AuditEventType.TASK_STARTED, source="venture", context_id="c2")
    )
    assert len(await store.list_recent(context_id="c1")) == 1
    assert len(await store.list_recent()) == 2
