"""Judgment Ledger v1 — the system's record of belief and outcome.

Every meaningful decision a brain makes is written here with its confidence,
evidence and assumptions. When reality reports back, outcomes are recorded.
High-confidence, validated beliefs can be promoted into the doctrine store.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from harness.core.logging import get_logger
from harness.core.persistence import Table, create_table
from harness.schemas.judgment import JudgmentEntry

if TYPE_CHECKING:  # pragma: no cover - typing only
    from memory.doctrine_store import DoctrineStore

logger = get_logger(__name__)

LEDGER_TABLE = "judgment_ledger"


class JudgmentLedger:
    """Append-and-update store of :class:`JudgmentEntry` records."""

    def __init__(self, table: Table | None = None) -> None:
        """Bind the ledger to a persistence table (defaults to configured)."""
        self._table = table or create_table(LEDGER_TABLE)

    async def record(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Persist a new judgment entry.

        Args:
            entry: The belief to record.

        Returns:
            The persisted entry.
        """
        if not entry.changelog:
            entry.record_change(actor=entry.brain_id, field="belief", note="created")
        await self._table.upsert(entry.model_dump(mode="json"))
        logger.debug("Recorded judgment %s by %s", entry.id, entry.brain_id)
        return entry

    async def get(self, entry_id: str) -> JudgmentEntry | None:
        """Return a single ledger entry by id, or ``None``."""
        row = await self._table.get(entry_id)
        return JudgmentEntry.model_validate(row) if row else None

    async def for_context(self, context_id: str) -> list[JudgmentEntry]:
        """Return all entries recorded within a pipeline run."""
        rows = await self._table.query(context_id=context_id)
        return [JudgmentEntry.model_validate(row) for row in rows]

    async def for_brain(self, brain_id: str) -> list[JudgmentEntry]:
        """Return all entries recorded by a given brain."""
        rows = await self._table.query(brain_id=brain_id)
        return [JudgmentEntry.model_validate(row) for row in rows]

    async def all(self) -> list[JudgmentEntry]:
        """Return every ledger entry."""
        rows = await self._table.all()
        return [JudgmentEntry.model_validate(row) for row in rows]

    async def record_outcome(
        self,
        entry_id: str,
        *,
        outcome: str,
        was_correct: bool,
        actor: str = "harness",
    ) -> JudgmentEntry | None:
        """Attach a real-world outcome to a previously-recorded belief.

        Args:
            entry_id: The judgment to update.
            outcome: Description of what actually happened.
            was_correct: Whether the belief proved correct.
            actor: Who recorded the outcome.

        Returns:
            The updated entry, or ``None`` if it does not exist.
        """
        entry = await self.get(entry_id)
        if entry is None:
            return None
        entry.outcome = outcome
        entry.outcome_timestamp = datetime.now(UTC)
        entry.was_correct = was_correct
        entry.record_change(actor=actor, field="outcome", note=outcome)
        await self._table.upsert(entry.model_dump(mode="json"))
        return entry

    async def promote_to_doctrine(
        self,
        entry_id: str,
        doctrine_store: DoctrineStore,
        *,
        actor: str = "harness",
    ) -> JudgmentEntry | None:
        """Promote a validated belief into the append-only doctrine store.

        Args:
            entry_id: The judgment to promote.
            doctrine_store: Where validated wisdom is appended.
            actor: Who performed the promotion.

        Returns:
            The updated (now promoted) entry, or ``None`` if missing.
        """
        entry = await self.get(entry_id)
        if entry is None:
            return None
        entry.doctrine_promoted = True
        entry.record_change(actor=actor, field="doctrine_promoted", note="promoted to doctrine")
        await self._table.upsert(entry.model_dump(mode="json"))
        await doctrine_store.append(entry)
        return entry

    async def retire(self, entry_id: str, *, actor: str = "harness") -> JudgmentEntry | None:
        """Mark a belief as superseded without deleting it."""
        entry = await self.get(entry_id)
        if entry is None:
            return None
        entry.retired = True
        entry.record_change(actor=actor, field="retired", note="belief retired")
        await self._table.upsert(entry.model_dump(mode="json"))
        return entry
