"""Episodic memory — completed pipeline runs and interaction history."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from harness.core.logging import get_logger
from harness.core.persistence import Table, create_table

logger = get_logger(__name__)

EPISODIC_TABLE = "episodic_memory"


class EpisodicStore:
    """Persistent record of completed pipeline runs."""

    def __init__(self, table: Table | None = None) -> None:
        """Bind the store to a persistence table (defaults to configured)."""
        self._table = table or create_table(EPISODIC_TABLE)

    async def record_run(
        self,
        *,
        context_id: str,
        objective: str,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist a completed pipeline run.

        Args:
            context_id: The pipeline run identifier (used as the row id).
            objective: The original operator intent.
            result: The aggregated final result.

        Returns:
            The persisted episodic record.
        """
        record = {
            "id": context_id,
            "context_id": context_id,
            "objective": objective,
            "result": result,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        await self._table.upsert(record)
        logger.debug("Episodic run recorded for context %s", context_id)
        return record

    async def get(self, context_id: str) -> dict[str, Any] | None:
        """Return a single completed run by context id."""
        return await self._table.get(context_id)

    async def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the most recent completed runs.

        Args:
            limit: Maximum number of runs to return.

        Returns:
            Runs sorted newest-first, truncated to ``limit``.
        """
        rows = await self._table.all()
        rows.sort(key=lambda row: row.get("recorded_at", ""), reverse=True)
        return rows[:limit]
