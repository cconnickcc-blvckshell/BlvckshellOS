"""Judgment lifecycle — stage machine for brain decisions."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from harness.core.agent_loop import AgentLoopResult
from harness.core.memory import SharedMemory
from harness.core.observer import Observer
from harness.schemas.audit import AuditEventType
from harness.schemas.brain_info import BrainContext
from harness.schemas.judgment import JudgmentEntry
from harness.schemas.task import Task

from judgment.evidence import assess_evidence
from judgment.guards.harm_aware import apply_harm_guard
from judgment.guards.safe_divergence import apply_safe_divergence
from judgment.outcome import JudgmentOutcome
from judgment.profile import JudgmentProfile
from judgment.reasoning.case_retrieval import format_cases_for_prompt, retrieve_cases
from judgment.stages.confidence import adjust_confidence
from judgment.stages.exploration import run_exploration
from judgment.traces import (
    EvidenceBundle,
    JudgmentStage,
    LifecycleResult,
    LifecycleRunContext,
    StageTrace,
)


class JudgmentLifecycle:
    """Runs the nine-stage judgment cycle for one brain task."""

    async def run(
        self,
        *,
        brain_id: str,
        context_id: str,
        task: Task,
        context: BrainContext,
        profile: JudgmentProfile,
        gather_evidence: Callable[[], Awaitable[AgentLoopResult]],
        observer: Observer | None = None,
        memory: SharedMemory | None = None,
        run_context: LifecycleRunContext | None = None,
        run_index: int = 0,
    ) -> LifecycleResult:
        """Execute lifecycle stages and return a structured decision."""
        result = LifecycleResult()
        guard_blocks: list[str] = []
        ctx = run_context or LifecycleRunContext()
        adjusted_confidence = 0.7

        t0 = time.perf_counter()
        await self._emit_stage(
            observer,
            brain_id=brain_id,
            context_id=context_id,
            trace=StageTrace(
                stage=JudgmentStage.OBSERVATION,
                consumed_signals=["task.objective", "task.inputs", "task.capability"],
                ignored_signals=[],
                output={"objective": task.objective[:200], "capability": task.capability},
                duration_ms=(time.perf_counter() - t0) * 1000,
            ),
            result=result,
        )

        prior_outcome = _prior_outcome_from_context(context)
        belief_keyword = " ".join(task.objective.split()[:6])
        cases = []
        if profile.case_retrieval_enabled and memory is not None:
            cases = await retrieve_cases(
                memory.ledger,
                belief_keyword=belief_keyword,
                domain=profile.domain,
                limit=10,
                embeddings=memory.embeddings,
            )
            ctx.retrieved_cases = cases
            ctx.evidence_prompt_suffix = format_cases_for_prompt(cases)
            result.retrieved_cases = cases

        t0 = time.perf_counter()
        await self._emit_stage(
            observer,
            brain_id=brain_id,
            context_id=context_id,
            trace=StageTrace(
                stage=JudgmentStage.BELIEF,
                consumed_signals=["context.recent_judgments", "context.doctrine"]
                + (["case_retrieval.matches"] if cases else []),
                ignored_signals=[] if cases else ["case_retrieval"],
                output={
                    "prior_outcome": prior_outcome.value if prior_outcome else None,
                    "judgment_count": len(context.recent_judgments),
                    "doctrine_count": len(context.doctrine),
                    "cases_retrieved": len(cases),
                },
                duration_ms=(time.perf_counter() - t0) * 1000,
            ),
            result=result,
        )

        t0 = time.perf_counter()
        if profile.foundation_enabled:
            conf_trace = adjust_confidence(profile, context)
            adjusted_confidence = conf_trace.final_confidence
            result.confidence_trace = conf_trace
            conf_consumed = [*conf_trace.signals_consumed, "profile.confidence_ceiling"]
            conf_ignored: list[str] = []
        else:
            conf_trace = None
            adjusted_confidence = 0.7
            conf_consumed = ["profile.confidence_ceiling"]
            conf_ignored = ["foundation", "doctrine", "ledger.recent_outcomes"]

        await self._emit_stage(
            observer,
            brain_id=brain_id,
            context_id=context_id,
            trace=StageTrace(
                stage=JudgmentStage.CONFIDENCE,
                consumed_signals=conf_consumed,
                ignored_signals=conf_ignored,
                output={
                    "base_confidence": conf_trace.base_confidence if conf_trace else 0.7,
                    "final_confidence": adjusted_confidence,
                    "doctrine_adjustment": conf_trace.doctrine_adjustment if conf_trace else 0.0,
                    "outcome_adjustment": conf_trace.outcome_adjustment if conf_trace else 0.0,
                },
                duration_ms=(time.perf_counter() - t0) * 1000,
            ),
            result=result,
        )

        exploration_trace = None
        if profile.exploration_enabled:
            recent = context.recent_judgments
            if memory is not None:
                recent = await memory.ledger.get_recent_judgments(brain_id, limit=20)
            exploration_trace = run_exploration(profile, recent, run_index=run_index)
            result.exploration_trace = exploration_trace

        t0 = time.perf_counter()
        await self._emit_stage(
            observer,
            brain_id=brain_id,
            context_id=context_id,
            trace=StageTrace(
                stage=JudgmentStage.CHALLENGE,
                consumed_signals=["exploration.recommended_bias"] if exploration_trace else [],
                ignored_signals=["council", "debate"]
                if exploration_trace is None
                else ["council"],
                output={
                    "status": "pass_through",
                    "exploration_bias": exploration_trace.recommended_bias
                    if exploration_trace
                    else None,
                },
                duration_ms=(time.perf_counter() - t0) * 1000,
            ),
            result=result,
        )

        t0 = time.perf_counter()
        loop_outcome = await gather_evidence()
        evidence = assess_evidence(loop_outcome, domain=profile.domain)
        if exploration_trace and exploration_trace.opportunity_cost_signal:
            evidence.summary = (
                evidence.summary
                + "\n[missed_opportunity_signal: similar holds had positive outcomes]"
            )
        evidence.confidence = min(evidence.confidence, adjusted_confidence + 0.1)
        result.evidence = evidence
        result.agent_metrics = loop_outcome.metrics
        result.raw_analysis = loop_outcome.final_text
        await self._emit_stage(
            observer,
            brain_id=brain_id,
            context_id=context_id,
            trace=StageTrace(
                stage=JudgmentStage.EVIDENCE,
                consumed_signals=[
                    "agent_loop.final_text",
                    "agent_loop.tool_invocations",
                    "evidence_bundle",
                ]
                + (["case_retrieval.top_cases"] if cases else [])
                + (
                    ["exploration.opportunity_cost"]
                    if exploration_trace and exploration_trace.opportunity_cost_signal
                    else []
                ),
                ignored_signals=[] if cases else ["case_retrieval"],
                output={
                    "provisional_outcome": evidence.provisional_outcome.value,
                    "evidence_positive": evidence.evidence_positive,
                    "confidence": evidence.confidence,
                    "cases_injected": min(3, len(cases)),
                    "model_used": loop_outcome.metrics.get("model_used"),
                    "provider": loop_outcome.metrics.get("provider"),
                    "tokens": loop_outcome.metrics.get("tokens"),
                    "cost_usd": loop_outcome.metrics.get("cost_usd"),
                },
                duration_ms=(time.perf_counter() - t0) * 1000,
            ),
            result=result,
        )

        t0 = time.perf_counter()
        await self._emit_stage(
            observer,
            brain_id=brain_id,
            context_id=context_id,
            trace=StageTrace(
                stage=JudgmentStage.FORECAST,
                consumed_signals=["exploration.exploration_bonus"] if exploration_trace else [],
                ignored_signals=(
                    ["forecasting"] if exploration_trace else ["exploration", "forecasting"]
                ),
                output={
                    "exploration_bonus": exploration_trace.exploration_bonus
                    if exploration_trace
                    else None,
                    "recommended_bias": exploration_trace.recommended_bias
                    if exploration_trace
                    else None,
                },
                duration_ms=(time.perf_counter() - t0) * 1000,
            ),
            result=result,
        )

        baseline = JudgmentOutcome.PROCEED
        candidate = evidence.provisional_outcome

        if (
            profile.foundation_enabled
            and conf_trace is not None
            and conf_trace.outcome_adjustment < -0.04
            and run_index % 5 == 0
            and candidate == JudgmentOutcome.PROCEED
        ):
            candidate = JudgmentOutcome.STAGED_PROCEED

        if profile.case_retrieval_enabled and cases and run_index % 5 == 0:
            qualities = [c.outcome_quality for c in cases if c.outcome_quality is not None]
            if qualities:
                avg_quality = sum(qualities) / len(qualities)
                if avg_quality < 0.3 and candidate == JudgmentOutcome.PROCEED:
                    candidate = JudgmentOutcome.STAGED_PROCEED

        if (
            exploration_trace
            and exploration_trace.recommended_bias == "explore"
            and candidate == JudgmentOutcome.PROCEED
        ):
            candidate = JudgmentOutcome.STAGED_PROCEED

        after_divergence, divergence_block, tension = apply_safe_divergence(
            profile,
            baseline=baseline,
            candidate=candidate,
            evidence=evidence,
            confidence=evidence.confidence,
            prior_outcome=prior_outcome,
        )
        if divergence_block:
            guard_blocks.append(divergence_block)
            await self._emit_guard_block(
                observer,
                brain_id=brain_id,
                context_id=context_id,
                reason=divergence_block,
                proposed=candidate.value,
            )

        recent_for_guard = context.recent_judgments
        if memory is not None:
            recent_for_guard = await memory.ledger.get_recent_judgments(
                brain_id, limit=profile.recall_depth
            )

        final_outcome, block_reason = apply_harm_guard(
            profile,
            prior_outcome=prior_outcome,
            proposed=after_divergence,
            evidence=evidence,
            recent_judgments=recent_for_guard,
            belief_hint=task.objective,
        )
        if block_reason:
            guard_blocks.append(block_reason)
            await self._emit_guard_block(
                observer,
                brain_id=brain_id,
                context_id=context_id,
                reason=block_reason,
                proposed=after_divergence.value,
            )

        result.outcome = final_outcome
        result.confidence = min(
            evidence.confidence, profile.confidence_ceiling, adjusted_confidence
        )
        result.belief = evidence.summary
        result.guard_blocks = guard_blocks

        t0 = time.perf_counter()
        await self._emit_stage(
            observer,
            brain_id=brain_id,
            context_id=context_id,
            trace=StageTrace(
                stage=JudgmentStage.DECISION,
                consumed_signals=[
                    "evidence_bundle",
                    "evidence.provisional_outcome",
                    "guard.harm_aware",
                    "guard.safe_divergence",
                ]
                + (["exploration.recommended_bias"] if exploration_trace else []),
                ignored_signals=["council"],
                output={
                    "baseline": baseline.value,
                    "candidate": candidate.value,
                    "after_divergence": after_divergence.value,
                    "final_outcome": final_outcome.value,
                    "tension": tension.value if tension else None,
                    "guard_blocks": guard_blocks,
                },
                duration_ms=(time.perf_counter() - t0) * 1000,
            ),
            result=result,
        )

        t0 = time.perf_counter()
        await self._emit_stage(
            observer,
            brain_id=brain_id,
            context_id=context_id,
            trace=StageTrace(
                stage=JudgmentStage.OUTCOME,
                consumed_signals=["decision.final_outcome"],
                ignored_signals=["world_result"],
                output={"status": "pending_review"},
                duration_ms=(time.perf_counter() - t0) * 1000,
            ),
            result=result,
        )

        t0 = time.perf_counter()
        await self._emit_stage(
            observer,
            brain_id=brain_id,
            context_id=context_id,
            trace=StageTrace(
                stage=JudgmentStage.LEARNING,
                consumed_signals=["decision.final_outcome", "evidence_bundle"],
                ignored_signals=["world_outcome"],
                output={"belief_preview": evidence.summary[:120], "awaiting_outcome_record": True},
                duration_ms=(time.perf_counter() - t0) * 1000,
            ),
            result=result,
        )

        return result

    async def _emit_stage(
        self,
        observer: Observer | None,
        *,
        brain_id: str,
        context_id: str,
        trace: StageTrace,
        result: LifecycleResult,
    ) -> None:
        result.stages.append(trace)
        if observer is None:
            return
        await observer.record(
            AuditEventType.JUDGMENT_STAGE_COMPLETED,
            source=brain_id,
            context_id=context_id,
            message=f"judgment stage {trace.stage.value}",
            data={
                "stage": trace.stage.value,
                "consumed_signals": trace.consumed_signals,
                "ignored_signals": trace.ignored_signals,
                "output": trace.output,
                "duration_ms": trace.duration_ms,
            },
        )

    async def _emit_guard_block(
        self,
        observer: Observer | None,
        *,
        brain_id: str,
        context_id: str,
        reason: str,
        proposed: str,
    ) -> None:
        if observer is None:
            return
        await observer.record(
            AuditEventType.JUDGMENT_GUARD_BLOCKED,
            source=brain_id,
            context_id=context_id,
            message=reason,
            data={"proposed_outcome": proposed, "reason": reason},
        )


def build_ledger_entry(
    *,
    brain_id: str,
    context_id: str,
    lifecycle: LifecycleResult,
) -> JudgmentEntry:
    """Write conclusions to the ledger — not raw model traces."""
    evidence = lifecycle.evidence or EvidenceBundle(summary=lifecycle.belief)
    entry = JudgmentEntry(
        brain_id=brain_id,
        context_id=context_id,
        belief=lifecycle.belief,
        confidence=lifecycle.confidence,
        evidence=evidence.tool_evidence,
        assumptions=[f"judgment_outcome:{lifecycle.outcome.value}"],
    )
    entry.record_change(
        "judgment_lifecycle",
        {
            "trace_id": lifecycle.trace_id,
            "outcome": lifecycle.outcome.value,
            "guard_blocks": lifecycle.guard_blocks,
            "stages": [s.stage.value for s in lifecycle.stages],
        },
    )
    return entry


def result_status_for_outcome(outcome: JudgmentOutcome):
    """Map judgment outcome to harness task status."""
    from harness.schemas.result import ResultStatus

    if outcome == JudgmentOutcome.REQUEST_MORE_EVIDENCE:
        return ResultStatus.NEEDS_OPERATOR
    if outcome == JudgmentOutcome.HOLD:
        return ResultStatus.SUCCESS
    return ResultStatus.SUCCESS


def _prior_outcome_from_context(context: BrainContext) -> JudgmentOutcome | None:
    for entry in reversed(context.recent_judgments):
        for assumption in entry.assumptions:
            if assumption.startswith("judgment_outcome:"):
                raw = assumption.split(":", 1)[1]
                try:
                    return JudgmentOutcome(raw)
                except ValueError:
                    continue
    return None
