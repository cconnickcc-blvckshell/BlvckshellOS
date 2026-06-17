"""Shared memory facade — one interface over the three memory tiers.

Brains and the agent loop talk to :class:`SharedMemory`; it composes working
memory, episodic memory, the doctrine store and the Judgment Ledger, and knows
how to assemble a :class:`BrainContext` for a pipeline run.
"""

from __future__ import annotations

from typing import Any

from memory.context_store import ContextStore, create_context_store
from memory.doctrine_store import DoctrineStore
from memory.episodic_store import EpisodicStore
from memory.judgment_ledger import JudgmentLedger

from harness.schemas.brain import BrainContext
from harness.schemas.judgment import JudgmentEntry


class SharedMemory:
    """Unified access to working, episodic and doctrine memory + ledger."""

    def __init__(
        self,
        *,
        context_store: ContextStore | None = None,
        episodic: EpisodicStore | None = None,
        doctrine: DoctrineStore | None = None,
        ledger: JudgmentLedger | None = None,
    ) -> None:
        """Compose the memory tiers, defaulting each to its configured backend."""
        self.context: ContextStore = context_store or create_context_store()
        self.episodic: EpisodicStore = episodic or EpisodicStore()
        self.doctrine: DoctrineStore = doctrine or DoctrineStore()
        self.ledger: JudgmentLedger = ledger or JudgmentLedger()

    async def assemble_context(self, *, context_id: str, brain_id: str) -> BrainContext:
        """Build the working context a brain loads before it thinks.

        Args:
            context_id: The pipeline run to load context for.
            brain_id: The brain the context is being assembled for.

        Returns:
            A populated :class:`BrainContext`.
        """
        working = await self.context.get_all(context_id)
        doctrine = await self.doctrine.active()
        judgments = await self.ledger.for_context(context_id)
        episodic = await self.episodic.recent(limit=5)
        return BrainContext(
            context_id=context_id,
            brain_id=brain_id,
            working=working,
            episodic=episodic,
            doctrine=doctrine,
            recent_judgments=[j.model_dump(mode="json") for j in judgments],
        )

    async def put_working(self, context_id: str, field: str, value: Any) -> None:
        """Write a value into a pipeline's working memory."""
        await self.context.set(context_id, field, value)

    async def log_judgment(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Record a judgment entry in the ledger."""
        return await self.ledger.record(entry)

    async def promote_doctrine(self, entry_id: str) -> JudgmentEntry | None:
        """Promote a validated belief from the ledger into doctrine."""
        return await self.ledger.promote_to_doctrine(entry_id, self.doctrine)
