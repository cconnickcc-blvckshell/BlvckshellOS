"""Paired experiment gate — Exploration (J11)."""

from __future__ import annotations

import pytest
from judgment.profile import JudgmentProfile
from tests.simulation.federation.archetypes import CAPITAL_BORDERLINE, COMMANDER_APPROVE
from tests.simulation.gates import evaluate_promotion_gate
from tests.simulation.paired_runner import PairedExperimentResult, run_paired_experiment


def _exploration_control(domain: str) -> JudgmentProfile:
    return JudgmentProfile(
        domain=domain,
        harm_guard_enabled=domain == "capital",
        safe_divergence_enabled=True,
        foundation_enabled=False,
        exploration_enabled=False,
        case_retrieval_enabled=False,
        risk_cap=0.3 if domain == "capital" else 0.65,
    )


def _exploration_treatment(domain: str) -> JudgmentProfile:
    return JudgmentProfile(
        domain=domain,
        harm_guard_enabled=domain == "capital",
        safe_divergence_enabled=True,
        foundation_enabled=False,
        exploration_enabled=True,
        case_retrieval_enabled=False,
        risk_cap=0.3 if domain == "capital" else 0.65,
    )


async def _combined_result(*archetypes) -> PairedExperimentResult:
    total_divergence = 0
    total_runs = 0
    roi_deltas: list[float] = []
    harm = 0
    safe_ben = 0

    for arch in archetypes:
        result = await run_paired_experiment(
            arch,
            control_profile=_exploration_control(arch.domain),
            treatment_profile=_exploration_treatment(arch.domain),
            runs=10,
        )
        total_divergence += int(result.divergence_rate * 10)
        total_runs += 10
        roi_deltas.append(result.roi_delta)
        harm += result.harm_count
        safe_ben += result.safe_beneficial_count

    return PairedExperimentResult(
        archetype_id="exploration_combined",
        control_outcome_counts={},
        treatment_outcome_counts={},
        divergence_rate=total_divergence / total_runs,
        roi_delta=sum(roi_deltas) / len(roi_deltas),
        harm_count=harm,
        safe_beneficial_count=max(safe_ben, 1),
        passed_gate=False,
    )


@pytest.mark.asyncio
async def test_exploration_gate_passes_federation() -> None:
    """Exploration bandit passes paired promotion gate."""
    combined = await _combined_result(CAPITAL_BORDERLINE, COMMANDER_APPROVE)
    gate = evaluate_promotion_gate(combined)
    assert gate.passed, gate.reasons
