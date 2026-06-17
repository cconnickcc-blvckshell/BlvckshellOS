"""Shared memory interface — the unified view over all three memory tiers.

Brains never talk to Redis or Supabase directly. They go through
:class:`SharedMemory`, which composes:

- working memory (:class:`~memory.context_store.ContextStore`),
- the Judgment Ledger (:class:`~memory.judgment_ledger.JudgmentLedger`),
- the Doctrine Store (:class:`~memory.doctrine_store.DoctrineStore`).

It also assembles the :class:`~harness.schemas.brain_info.BrainContext` a brain
loads before it thinks, and handles promotion of validated beliefs to doctrine.
"""

from __future__ import annotations

from typing import Any

from memory.context_store import (
    ContextStore,
    InMemoryContextStore,
    RedisContextStore,
)
from memory.doctrine_store import (
    DoctrineStore,
    InMemoryDoctrineStore,
    SupabaseDoctrineStore,
)
from memory.judgment_ledger import (
    InMemoryJudgmentLedger,
    JudgmentLedger,
    SupabaseJudgmentLedger,
)

from harness.config import Settings
from harness.core.observer import Observer
from harness.schemas.audit import AuditEventType
from harness.schemas.brain_info import BrainContext
from harness.schemas.judgment import JudgmentEntry

# Confidence at or above which a correct belief is eligible for doctrine.
DOCTRINE_PROMOTION_THRESHOLD = 0.8


class SharedMemory:
    """Composite facade over working memory, the ledger, and doctrine."""

    def __init__(
        self,
        *,
        context_store: ContextStore,
        ledger: JudgmentLedger,
        doctrine: DoctrineStore,
        observer: Observer | None = None,
    ) -> None:
        """Create the shared-memory facade.

        Args:
            context_store: The working-memory backend.
            ledger: The Judgment Ledger backend.
            doctrine: The Doctrine Store backend.
            observer: Optional Observer for auditing memory writes.
        """
        self.context_store = context_store
        self.ledger = ledger
        self.doctrine = doctrine
        self._observer = observer

    async def connect(self) -> None:
        """Connect every underlying store."""
        await self.context_store.connect()
        await self.ledger.connect()
        await self.doctrine.connect()

    async def close(self) -> None:
        """Close every underlying store."""
        await self.context_store.close()
        await self.ledger.close()
        await self.doctrine.close()

    # -- working memory ----------------------------------------------------

    async def remember(self, context_id: str, key: str, value: Any) -> None:
        """Store a value in working memory for a pipeline run."""
        await self.context_store.set(context_id, key, value)

    async def recall(self, context_id: str, key: str) -> Any | None:
        """Return a value from working memory, or ``None``."""
        return await self.context_store.get(context_id, key)

    async def append_working(self, context_id: str, key: str, value: Any) -> None:
        """Append a value to a list in working memory."""
        await self.context_store.append(context_id, key, value)

    # -- judgments ---------------------------------------------------------

    async def record_judgment(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Record a belief in the Judgment Ledger and audit it."""
        stored = await self.ledger.record(entry)
        if self._observer is not None:
            await self._observer.record(
                AuditEventType.JUDGMENT_CREATED,
                source=stored.brain_id,
                context_id=stored.context_id,
                message=stored.belief[:160],
                data={"judgment_id": stored.id, "confidence": stored.confidence},
            )
        return stored

    async def update_judgment(self, entry: JudgmentEntry) -> JudgmentEntry:
        """Update an existing Judgment Ledger entry and audit it."""
        stored = await self.ledger.update(entry)
        if self._observer is not None:
            await self._observer.record(
                AuditEventType.JUDGMENT_UPDATED,
                source=stored.brain_id,
                context_id=stored.context_id,
                data={"judgment_id": stored.id},
            )
        return stored

    async def promote_to_doctrine(self, entry_id: str) -> JudgmentEntry | None:
        """Promote a validated belief from the ledger to doctrine.

        The belief must exist, be confirmed correct, and meet the confidence
        threshold. Returns the promoted doctrine entry, or ``None`` if it was
        not eligible.

        Args:
            entry_id: The Judgment Ledger entry to promote.
        """
        entry = await self.ledger.get(entry_id)
        if entry is None:
            return None
        if not entry.was_correct or entry.confidence < DOCTRINE_PROMOTION_THRESHOLD:
            return None

        entry.doctrine_promoted = True
        await self.ledger.update(entry)
        promoted = await self.doctrine.promote(entry)
        if self._observer is not None:
            await self._observer.record(
                AuditEventType.DOCTRINE_PROMOTED,
                source=entry.brain_id,
                context_id=entry.context_id,
                message=entry.belief[:160],
                data={"judgment_id": entry.id},
            )
        return promoted

    # -- context assembly --------------------------------------------------

    async def load_context(
        self, context_id: str, brain_id: str, *, judgment_limit: int = 20
    ) -> BrainContext:
        """Assemble the working context a brain needs before thinking.

        Args:
            context_id: The pipeline run identifier.
            brain_id: The brain the context is for.
            judgment_limit: Max recent judgments to include.

        Returns:
            A populated :class:`BrainContext`.
        """
        working = await self.context_store.get_all(context_id)
        recent = await self.ledger.list_for_context(context_id)
        doctrine = await self.doctrine.list_active(limit=judgment_limit)
        history = working.get("history", []) if isinstance(working.get("history"), list) else []
        return BrainContext(
            context_id=context_id,
            brain_id=brain_id,
            working_memory=working,
            recent_judgments=recent[-judgment_limit:],
            doctrine=doctrine,
            history=history,
        )


def build_shared_memory(settings: Settings, observer: Observer | None = None) -> SharedMemory:
    """Construct the shared-memory facade from settings.

    Working memory uses Redis unless ``use_in_memory_bus`` is set. The ledger and
    doctrine use Supabase when configured, otherwise in-memory backends.

    Args:
        settings: Runtime settings.
        observer: Optional Observer to audit memory writes.

    Returns:
        A wired :class:`SharedMemory`.
    """
    if settings.use_in_memory_bus:
        context_store: ContextStore = InMemoryContextStore()
    else:
        context_store = RedisContextStore(settings.redis_url, settings.working_memory_ttl_seconds)

    if settings.supabase_enabled:
        ledger: JudgmentLedger = SupabaseJudgmentLedger(
            settings.supabase_url,  # type: ignore[arg-type]
            settings.supabase_key,  # type: ignore[arg-type]
        )
        doctrine: DoctrineStore = SupabaseDoctrineStore(
            settings.supabase_url,  # type: ignore[arg-type]
            settings.supabase_key,  # type: ignore[arg-type]
        )
    else:
        ledger = InMemoryJudgmentLedger()
        doctrine = InMemoryDoctrineStore()

    return SharedMemory(
        context_store=context_store, ledger=ledger, doctrine=doctrine, observer=observer
    )
