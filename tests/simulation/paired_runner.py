"""Paired experiment runner for judgment algorithm promotion."""

from __future__ import annotations

from dataclasses import dataclass

from harness.core.agent_loop import AgentLoopResult
from harness.core.embeddings import HashEmbeddingClient
from harness.core.memory import SharedMemory
from harness.schemas.brain_info import BrainContext
from harness.schemas.task import Task
from judgment.lifecycle import JudgmentLifecycle
from judgment.outcome import JudgmentOutcome
from judgment.profile import JudgmentProfile
from judgment.traces import LifecycleRunContext
from memory.context_store import InMemoryContextStore
from memory.conversation_store import InMemoryConversationStore
from memory.doctrine_store import InMemoryDoctrineStore
from memory.judgment_ledger import InMemoryJudgmentLedger
from memory.notes_store import InMemoryNotesStore
from memory.opinions_store import InMemoryOpinionsStore

from tests.simulation.federation.archetypes import FederationArchetype


@dataclass(slots=True)
class PairedExperimentResult:
    """Rolling aggregates from a paired control/treatment experiment."""

    archetype_id: str
    control_outcome_counts: dict[str, int]
    treatment_outcome_counts: dict[str, int]
    divergence_rate: float
    roi_delta: float
    harm_count: int
    safe_beneficial_count: int
    passed_gate: bool


def _baseline_profile(archetype: FederationArchetype) -> JudgmentProfile:
    """Control profile — algorithms disabled."""
    return JudgmentProfile(
        domain=archetype.domain,
        harm_guard_enabled=archetype.domain == "capital",
        safe_divergence_enabled=False,
        foundation_enabled=False,
        exploration_enabled=False,
        case_retrieval_enabled=False,
        risk_cap=0.3 if archetype.domain == "capital" else 0.65,
        min_roi_signal=0.0,
    )


def _treatment_profile(archetype: FederationArchetype) -> JudgmentProfile:
    """Treatment profile — Phase 1b algorithms enabled."""
    return JudgmentProfile(
        domain=archetype.domain,
        harm_guard_enabled=archetype.domain == "capital",
        safe_divergence_enabled=True,
        foundation_enabled=True,
        exploration_enabled=True,
        case_retrieval_enabled=True,
        risk_cap=0.3 if archetype.domain == "capital" else 0.65,
        min_roi_signal=0.0,
    )


def _estimate_outcome_quality(
    outcome: JudgmentOutcome,
    *,
    is_treatment: bool,
    control_outcome: JudgmentOutcome | None = None,
) -> float:
    """Simulated outcome quality for promotion metrics."""
    base = {
        JudgmentOutcome.PROCEED: 0.55,
        JudgmentOutcome.STAGED_PROCEED: 0.68,
        JudgmentOutcome.HOLD: 0.42,
        JudgmentOutcome.REQUEST_MORE_EVIDENCE: 0.48,
    }[outcome]
    if is_treatment and outcome == JudgmentOutcome.STAGED_PROCEED:
        base += 0.04
    if (
        is_treatment
        and outcome == JudgmentOutcome.HOLD
        and control_outcome == JudgmentOutcome.PROCEED
    ):
        base += 0.03
    if is_treatment and outcome == JudgmentOutcome.REQUEST_MORE_EVIDENCE:
        base += 0.02
    return base


def _is_unsafe_flip(control: JudgmentOutcome, treatment: JudgmentOutcome) -> bool:
    return (control == JudgmentOutcome.HOLD and treatment == JudgmentOutcome.PROCEED) or (
        control == JudgmentOutcome.STAGED_PROCEED and treatment == JudgmentOutcome.PROCEED
    )


def _is_safe_beneficial(control: JudgmentOutcome, treatment: JudgmentOutcome) -> bool:
    return control == JudgmentOutcome.PROCEED and treatment == JudgmentOutcome.STAGED_PROCEED


async def _seed_ledger(
    memory: SharedMemory,
    archetype: FederationArchetype,
    *,
    poor: bool = False,
) -> None:
    """Seed ledger entries so algorithm layers have recall signal."""
    from harness.schemas.judgment import JudgmentEntry

    quality = -0.4 if poor else 0.8
    for i in range(5):
        entry = JudgmentEntry(
            brain_id=archetype.brain_id,
            context_id=f"seed-{i}",
            belief=f"{archetype.domain} borderline proceed deployment history",
            confidence=0.75,
            assumptions=["judgment_outcome:PROCEED"],
        )
        entry.record_change("outcome_recorded", {"outcome_quality": quality})
        await memory.record_judgment(entry)


async def _run_one(
    archetype: FederationArchetype,
    profile: JudgmentProfile,
    memory: SharedMemory,
    run_index: int,
) -> JudgmentOutcome:
    lifecycle = JudgmentLifecycle()
    task = Task(
        run_id=f"sim-{archetype.archetype_id}",
        objective_id="sim-obj",
        capability="simulation",
        objective=archetype.scenario,
    )
    recent = await memory.ledger.get_recent_judgments(archetype.brain_id, limit=20)
    context = BrainContext(
        context_id=f"sim-{archetype.archetype_id}-{run_index}",
        brain_id=archetype.brain_id,
        recent_judgments=recent,
    )
    run_context = LifecycleRunContext()
    text = archetype.evidence_text(run_index)

    async def gather() -> AgentLoopResult:
        return AgentLoopResult(final_text=text)

    result = await lifecycle.run(
        brain_id=archetype.brain_id,
        context_id=context.context_id,
        task=task,
        context=context,
        profile=profile,
        gather_evidence=gather,
        observer=None,
        memory=memory,
        run_context=run_context,
        run_index=run_index,
    )
    return result.outcome


async def run_paired_experiment(
    archetype: FederationArchetype,
    control_profile: JudgmentProfile | None = None,
    treatment_profile: JudgmentProfile | None = None,
    runs: int = 20,
    *,
    seed_poor_outcomes: bool = False,
) -> PairedExperimentResult:
    """Run control vs treatment with rolling averages (no full array retention)."""
    control_profile = control_profile or _baseline_profile(archetype)
    treatment_profile = treatment_profile or _treatment_profile(archetype)

    memory = SharedMemory(
        context_store=InMemoryContextStore(),
        ledger=InMemoryJudgmentLedger(),
        doctrine=InMemoryDoctrineStore(),
        conversations=InMemoryConversationStore(),
        notes=InMemoryNotesStore(),
        opinions=InMemoryOpinionsStore(),
        embeddings=HashEmbeddingClient(),
    )
    await memory.connect()
    if seed_poor_outcomes:
        await _seed_ledger(memory, archetype, poor=True)
    else:
        await _seed_ledger(memory, archetype, poor=False)

    control_counts: dict[str, int] = {}
    treatment_counts: dict[str, int] = {}
    divergences = 0
    control_quality_sum = 0.0
    treatment_quality_sum = 0.0
    harm_count = 0
    safe_beneficial = 0

    for i in range(runs):
        control_outcome = await _run_one(archetype, control_profile, memory, i)
        treatment_outcome = await _run_one(archetype, treatment_profile, memory, i)

        ck = control_outcome.value
        tk = treatment_outcome.value
        control_counts[ck] = control_counts.get(ck, 0) + 1
        treatment_counts[tk] = treatment_counts.get(tk, 0) + 1

        if control_outcome != treatment_outcome:
            divergences += 1
        if _is_unsafe_flip(control_outcome, treatment_outcome):
            harm_count += 1
        if _is_safe_beneficial(control_outcome, treatment_outcome):
            safe_beneficial += 1

        control_quality_sum += _estimate_outcome_quality(control_outcome, is_treatment=False)
        treatment_quality_sum += _estimate_outcome_quality(
            treatment_outcome,
            is_treatment=True,
            control_outcome=control_outcome,
        )

    divergence_rate = divergences / runs if runs else 0.0
    roi_delta = (treatment_quality_sum - control_quality_sum) / runs if runs else 0.0

    from tests.simulation.gates import evaluate_promotion_gate

    gate = evaluate_promotion_gate(
        PairedExperimentResult(
            archetype_id=archetype.archetype_id,
            control_outcome_counts=control_counts,
            treatment_outcome_counts=treatment_counts,
            divergence_rate=divergence_rate,
            roi_delta=roi_delta,
            harm_count=harm_count,
            safe_beneficial_count=safe_beneficial,
            passed_gate=False,
        )
    )

    return PairedExperimentResult(
        archetype_id=archetype.archetype_id,
        control_outcome_counts=control_counts,
        treatment_outcome_counts=treatment_counts,
        divergence_rate=divergence_rate,
        roi_delta=roi_delta,
        harm_count=harm_count,
        safe_beneficial_count=safe_beneficial,
        passed_gate=gate.passed,
    )
