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
from memory.notes_store import (
    InMemoryNotesStore,
    NotesStore,
    SupabaseNotesStore,
)
from memory.opinions_store import (
    InMemoryOpinionsStore,
    OpinionsStore,
    SupabaseOpinionsStore,
)

from harness.config import Settings
from harness.core.embeddings import EmbeddingClient, build_embedding_client
from harness.core.observer import Observer
from harness.schemas.audit import AuditEventType
from harness.schemas.brain_info import BrainContext
from harness.schemas.judgment import JudgmentEntry, OutcomeRecord
from harness.schemas.memory import MemoryNote, Opinion

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
        notes: NotesStore,
        opinions: OpinionsStore,
        embeddings: EmbeddingClient,
        observer: Observer | None = None,
    ) -> None:
        """Create the shared-memory facade."""
        self.context_store = context_store
        self.ledger = ledger
        self.doctrine = doctrine
        self.conversations = conversations
        self.notes = notes
        self.opinions = opinions
        self.embeddings = embeddings
        self._observer = observer

    async def connect(self) -> None:
        """Connect every underlying store."""
        await self.context_store.connect()
        await self.ledger.connect()
        await self.doctrine.connect()
        await self.conversations.connect()
        await self.notes.connect()
        await self.opinions.connect()

    async def close(self) -> None:
        """Close every underlying store."""
        await self.context_store.close()
        await self.ledger.close()
        await self.doctrine.close()
        await self.conversations.close()
        await self.notes.close()
        await self.opinions.close()

    async def add_note(
        self,
        session_id: str,
        content: str,
        *,
        operator_id: str | None = None,
        topics: list[str] | None = None,
        source_entry_ids: list[str] | None = None,
    ) -> MemoryNote:
        """Embed and persist a new durable memory note."""
        note = MemoryNote(
            session_id=session_id,
            operator_id=operator_id,
            content=content,
            topics=topics or [],
            source_entry_ids=source_entry_ids or [],
        )
        note.embedding = await self.embeddings.embed(content)
        stored = await self.notes.add(note)
        if self._observer is not None:
            await self._observer.record(
                AuditEventType.NOTE_ADDED,
                source="reflection",
                message=stored.content[:160],
                data={"note_id": stored.id, "session_id": stored.session_id},
            )
        return stored

    async def recall_notes(
        self, query: str, *, operator_id: str | None = None, limit: int = 5
    ) -> list[MemoryNote]:
        """Return the notes most semantically relevant to ``query``."""
        query_embedding = await self.embeddings.embed(query)
        return await self.notes.recall(query_embedding, operator_id=operator_id, limit=limit)

    async def add_opinion(
        self,
        topic: str,
        statement: str,
        reasoning: str,
        *,
        confidence: float,
        operator_id: str | None = None,
        source_note_ids: list[str] | None = None,
    ) -> Opinion:
        """Form and persist a new standing opinion."""
        opinion = Opinion(
            operator_id=operator_id,
            topic=topic,
            statement=statement,
            reasoning=reasoning,
            confidence=confidence,
            source_note_ids=source_note_ids or [],
        )
        opinion.embedding = await self.embeddings.embed(statement)
        stored = await self.opinions.add(opinion)
        if self._observer is not None:
            await self._observer.record(
                AuditEventType.OPINION_FORMED,
                source="reflection",
                message=stored.statement[:160],
                data={
                    "opinion_id": stored.id,
                    "topic": stored.topic,
                    "confidence": stored.confidence,
                },
            )
        return stored

    async def revise_opinion(
        self,
        opinion_id: str,
        statement: str,
        reasoning: str,
        *,
        confidence: float,
        source_note_ids: list[str] | None = None,
    ) -> Opinion | None:
        """Revise a standing opinion, retiring the old one and linking to the new."""
        old = await self.opinions.get(opinion_id)
        if old is None:
            return None
        replacement = Opinion(
            operator_id=old.operator_id,
            topic=old.topic,
            statement=statement,
            reasoning=reasoning,
            confidence=confidence,
            source_note_ids=source_note_ids or [],
        )
        replacement.embedding = await self.embeddings.embed(statement)
        revised = await self.opinions.revise(opinion_id, replacement)
        if revised is not None and self._observer is not None:
            await self._observer.record(
                AuditEventType.OPINION_REVISED,
                source="reflection",
                message=revised.statement[:160],
                data={"opinion_id": revised.id, "supersedes": opinion_id},
            )
        return revised

    async def recall_opinions(
        self, query: str, *, operator_id: str | None = None, limit: int = 5
    ) -> list[Opinion]:
        """Return the active opinions most semantically relevant to ``query``."""
        query_embedding = await self.embeddings.embed(query)
        return await self.opinions.recall(query_embedding, operator_id=operator_id, limit=limit)

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
        self,
        context_id: str,
        brain_id: str,
        *,
        judgment_limit: int = 20,
        query: str | None = None,
        operator_id: str | None = None,
        memory_limit: int = 5,
    ) -> BrainContext:
        """Assemble the working context a brain needs before thinking.

        When ``query`` (typically the operator's current message) is given,
        also recalls the personal notes and standing opinions most
        semantically relevant to it.
        """
        working = await self.context_store.get_all(context_id)
        recent = await self.ledger.list_for_context(context_id)
        if not recent:
            recent = await self.ledger.get_recent_judgments(brain_id, limit=judgment_limit)
        doctrine = await self.doctrine.list_active(limit=judgment_limit)
        history = working.get("history", []) if isinstance(working.get("history"), list) else []

        notes: list[MemoryNote] = []
        opinions: list[Opinion] = []
        if query:
            notes = await self.recall_notes(query, operator_id=operator_id, limit=memory_limit)
            opinions = await self.recall_opinions(
                query, operator_id=operator_id, limit=memory_limit
            )

        return BrainContext(
            context_id=context_id,
            brain_id=brain_id,
            working_memory=working,
            recent_judgments=recent[-judgment_limit:],
            doctrine=doctrine,
            history=history,
            notes=notes,
            opinions=opinions,
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
        notes: NotesStore = SupabaseNotesStore(
            settings.supabase_url,  # type: ignore[arg-type]
            settings.supabase_key,  # type: ignore[arg-type]
        )
        opinions: OpinionsStore = SupabaseOpinionsStore(
            settings.supabase_url,  # type: ignore[arg-type]
            settings.supabase_key,  # type: ignore[arg-type]
        )
    else:
        ledger = InMemoryJudgmentLedger()
        doctrine = InMemoryDoctrineStore()
        notes = InMemoryNotesStore()
        opinions = InMemoryOpinionsStore()

    return SharedMemory(
        context_store=context_store,
        ledger=ledger,
        doctrine=doctrine,
        conversations=conversations,
        notes=notes,
        opinions=opinions,
        embeddings=build_embedding_client(settings),
        observer=observer,
    )
