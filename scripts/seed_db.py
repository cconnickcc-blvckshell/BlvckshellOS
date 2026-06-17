"""Seed persistent memory with founding doctrine.

When Supabase is configured, this seeds a few founding doctrine entries so the
system starts with some accumulated wisdom. Without Supabase, persistence is
in-process and per-run, so this script simply prints guidance and the schema
location.

Usage:
    python -m scripts.seed_db
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from harness.config import settings
from harness.core.logging import get_logger
from harness.schemas.judgment import JudgmentEntry
from memory.doctrine_store import DoctrineStore

logger = get_logger(__name__)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

FOUNDING_DOCTRINE: list[str] = [
    "Decompose aggressively: smaller tasks complete faster and fail cleaner.",
    "Never route to a capability that is not registered and healthy.",
    "Prefer parallel execution over sequential when tasks are independent.",
    "When in doubt, escalate to the operator rather than assume.",
    "Every decision must be logged to the Judgment Ledger with its evidence.",
]


async def _seed() -> None:
    """Insert founding doctrine into the configured doctrine store."""
    if not settings.use_supabase:
        logger.warning(
            "Supabase is not configured; persistence is in-process and per-run. "
            "Apply %s to your Supabase project and set BLVCKSHELL_SUPABASE_URL/KEY "
            "to persist memory across runs.",
            SCHEMA_PATH,
        )

    store = DoctrineStore()
    for belief in FOUNDING_DOCTRINE:
        entry = JudgmentEntry(
            brain_id="harness",
            context_id="genesis",
            belief=belief,
            confidence=0.95,
            evidence=["founding doctrine"],
        )
        await store.append(entry)
    logger.info("Seeded %d founding doctrine entries.", len(FOUNDING_DOCTRINE))


def main() -> None:
    """CLI entry point for seeding the database."""
    asyncio.run(_seed())


if __name__ == "__main__":
    main()
