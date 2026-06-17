"""Doctrine store — append-only, validated wisdom promoted from the ledger.

Doctrine is never deleted, only superseded. It is the system's accumulated,
trusted belief set, consulted as high-signal context on every pipeline run.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from harness.core.logging import get_logger
from harness.core.persistence import Table, create_table
from harness.schemas.judgment import JudgmentEntry

logger = get_logger(__name__)

DOCTRINE_TABLE = "doctrine"


class DoctrineStore:
    """Append-only store of validated beliefs (doctrine)."""

    def __init__(self, table: Table | None = None) -> None:
        """Bind the store to a persistence table (defaults to configured)."""
        self._table = table or create_table(DOCTRINE_TABLE)

    async def append(self, entry: JudgmentEntry) -> dict[str, Any]:
        """Append a promoted judgment entry as a doctrine record.

        Args:
            entry: The validated belief being promoted.

        Returns:
            The persisted doctrine record.
        """
        record: dict[str, Any] = {
            "id": entry.id,
            "brain_id": entry.brain_id,
            "context_id": entry.context_id,
            "belief": entry.belief,
            "confidence": entry.confidence,
            "evidence": entry.evidence,
            "promoted_at": datetime.now(UTC).isoformat(),
            "superseded_by": None,
        }
        await self._table.upsert(record)
        logger.info("Doctrine appended: %s", entry.belief[:80])
        return record

    async def all(self) -> list[dict[str, Any]]:
        """Return every doctrine record (including superseded ones)."""
        return await self._table.all()

    async def active(self) -> list[dict[str, Any]]:
        """Return only doctrine that has not been superseded."""
        return [row for row in await self._table.all() if not row.get("superseded_by")]

    async def supersede(self, old_id: str, new_id: str) -> dict[str, Any] | None:
        """Mark an existing doctrine record as superseded by a newer one.

        Args:
            old_id: The doctrine record being superseded.
            new_id: The doctrine record that replaces it.

        Returns:
            The updated old record, or ``None`` if it does not exist.
        """
        row = await self._table.get(old_id)
        if row is None:
            return None
        row["superseded_by"] = new_id
        await self._table.upsert(row)
        return row
