"""Shared memory updates for outcome capture and conversations."""

from __future__ import annotations

from judgment.stages.learning import apply_belief_update
from memory.context_store import (
    ContextStore,
    InMemoryContextStore,
    RedisContextStore,
)
from memory.conversation_store import (
    ConversationStore,
    InMemoryConversationStore,
    SupabaseConversationStore,
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
from harness.schemas.judgment import JudgmentEntry, OutcomeRecord

# Confidence at or above which a correct belief is eligible for doctrine.
DOCTRINE_PROMOTION_THRESHOLD = 0.8
OUTCOME_PROMOTION_QUALITY = 0.8
NEGATIVE_OUTCOME_THRESHOLD = -0.5
DOCTRINE_CONFIDENCE_PENALTY = 0.15


class SharedMemory:
    """Composite facade over working memory, the ledger, doctrine, and conversations."""

    def __init__(
        self,
        *,
        context_store: ContextStore,
        ledger: JudgmentLedger,
        doctrine: DoctrineStore,
        conversations: ConversationStore,
        observer: Observer | None = None,
    ) -> None:
        """Create the shared-memory facade."""
        self.context_store = context_store
        self.ledger = ledger
        self.doctrine = doctrine
        self.conversations = conversations
        self._observer = observer

    async def connect(self) -> None:
        """Connect every underlying store."""
        await self.context_store.connect()
        await self.ledger.connect()
        await self.doctrine.connect()
        await self.conversations.connect()

    async def close(self) -> None:
        """Close every underlying store."""
        await self.context_store.close()
        await self.ledger.close()
        await self.doctrine.close()
        await self.conversations.close()

    async def remember(self, context_id: str, key: str, value) -> None:
        """Store a value in working memory for a pipeline run."""
        await self.context_store.set(context_id, key, value)

    async def recall(self, context_id: str, key: str):
        """Return a value from working memory, or ``None``."""
        return await self.context_store.get(context_id, key)

    async def append_working(self, context_id: str, key: str, value) -> None:
        """Append a value to a list in working memory."""
        await self.context_store.append(context_id, key, value)

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

    async def record_outcome(
        self, judgment_id: str, outcome_data: OutcomeRecord
    ) -> JudgmentEntry | None:
        """Close the learning loop: record outcome, promote or penalize doctrine."""
        entry = await self.ledger.record_outcome(judgment_id, outcome_data)
        if entry is None:
            return None

        entry, belief_trace = apply_belief_update(entry, outcome_data)
        await self.ledger.update(entry)
        if self._observer is not None:
            await self._observer.record(
                AuditEventType.BELIEF_UPDATED,
                source=entry.brain_id,
                context_id=entry.context_id,
                message=(
                    f"confidence {belief_trace.confidence_before:.2f}"
                    f" -> {belief_trace.confidence_after:.2f}"
                ),
                data={
                    "judgment_id": entry.id,
                    "confidence_before": belief_trace.confidence_before,
                    "confidence_after": belief_trace.confidence_after,
                    "consumed_signals": belief_trace.signals_consumed,
                },
            )

        if (
            outcome_data.outcome_quality >= OUTCOME_PROMOTION_QUALITY
            and entry.confidence >= DOCTRINE_PROMOTION_THRESHOLD
        ):
            await self.promote_to_doctrine(entry.id)

        if outcome_data.outcome_quality <= NEGATIVE_OUTCOME_THRESHOLD:
            await self._penalize_related_doctrine(entry)
            if self._observer is not None:
                await self._observer.record(
                    AuditEventType.DOCTRINE_FLAGGED,
                    source=entry.brain_id,
                    context_id=entry.context_id,
                    message=entry.belief[:120],
                    data={
                        "judgment_id": entry.id,
                        "outcome_quality": outcome_data.outcome_quality,
                    },
                )

        if self._observer is not None:
            await self._observer.record(
                AuditEventType.OUTCOME_RECORDED,
                source=entry.brain_id,
                context_id=entry.context_id,
                message=outcome_data.actual_outcome[:160],
                data={
                    "judgment_id": entry.id,
                    "outcome_quality": outcome_data.outcome_quality,
                    "lessons": outcome_data.lessons,
                },
            )
        return entry

    async def promote_to_doctrine(self, entry_id: str) -> JudgmentEntry | None:
        """Promote a validated belief from the ledger to doctrine."""
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

    async def _penalize_related_doctrine(self, entry: JudgmentEntry) -> None:
        """Reduce confidence on doctrine entries related to a failed judgment."""
        keywords = [word.lower() for word in entry.belief.split() if len(word) > 4][:5]
        if not keywords:
            return

        active = await self.doctrine.list_active(limit=200)
        for doc in active:
            belief_lower = doc.belief.lower()
            if not any(keyword in belief_lower for keyword in keywords):
                continue
            doc.confidence = max(0.1, doc.confidence - DOCTRINE_CONFIDENCE_PENALTY)
            doc.record_change(
                "confidence_reduced",
                {"reason": "negative_outcome", "judgment_id": entry.id},
            )
            await self.doctrine.update(doc)
            if self._observer is not None:
                await self._observer.record(
                    AuditEventType.DOCTRINE_CONFIDENCE_REDUCED,
                    source=entry.brain_id,
                    context_id=entry.context_id,
                    message=doc.belief[:120],
                    data={"doctrine_id": doc.id, "new_confidence": doc.confidence},
                )

    async def load_context(
        self, context_id: str, brain_id: str, *, judgment_limit: int = 20
    ) -> BrainContext:
        """Assemble the working context a brain needs before thinking."""
        working = await self.context_store.get_all(context_id)
        recent = await self.ledger.list_for_context(context_id)
        if not recent:
            recent = await self.ledger.get_recent_judgments(brain_id, limit=judgment_limit)
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
    """Construct the shared-memory facade from settings."""
    if settings.use_in_memory_bus:
        context_store: ContextStore = InMemoryContextStore()
        conversations: ConversationStore = InMemoryConversationStore()
    else:
        context_store = RedisContextStore(settings.redis_url, settings.working_memory_ttl_seconds)
        conversations = InMemoryConversationStore()

    if settings.supabase_enabled:
        ledger: JudgmentLedger = SupabaseJudgmentLedger(
            settings.supabase_url,  # type: ignore[arg-type]
            settings.supabase_key,  # type: ignore[arg-type]
        )
        doctrine: DoctrineStore = SupabaseDoctrineStore(
            settings.supabase_url,  # type: ignore[arg-type]
            settings.supabase_key,  # type: ignore[arg-type]
        )
        conversations = SupabaseConversationStore(
            settings.supabase_url,  # type: ignore[arg-type]
            settings.supabase_key,  # type: ignore[arg-type]
        )
    else:
        ledger = InMemoryJudgmentLedger()
        doctrine = InMemoryDoctrineStore()

    return SharedMemory(
        context_store=context_store,
        ledger=ledger,
        doctrine=doctrine,
        conversations=conversations,
        observer=observer,
    )
