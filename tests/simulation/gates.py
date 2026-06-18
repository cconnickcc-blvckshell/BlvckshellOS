"""Promotion gate evaluator for paired judgment experiments."""

from __future__ import annotations

from dataclasses import dataclass

from tests.simulation.paired_runner import PairedExperimentResult


@dataclass(slots=True)
class GateResult:
    """Result of evaluating a promotion gate."""

    passed: bool
    divergence_rate: float
    roi_delta: float
    harm_count: int
    safe_beneficial_count: int
    reasons: list[str]


def evaluate_promotion_gate(result: PairedExperimentResult) -> GateResult:
    """An algorithm layer is promoted only if ALL conditions pass."""
    reasons: list[str] = []
    if not (0.10 <= result.divergence_rate <= 0.30):
        reasons.append(
            f"divergence_rate {result.divergence_rate:.2%} outside 10-30% band"
        )
    if result.roi_delta < 0.01:
        reasons.append(f"roi_delta {result.roi_delta:.4f} below 0.01 minimum")
    if result.harm_count != 0:
        reasons.append(f"harm_count {result.harm_count} must be zero")
    if result.safe_beneficial_count <= 0:
        reasons.append("safe_beneficial_count must be > 0")

    return GateResult(
        passed=len(reasons) == 0,
        divergence_rate=result.divergence_rate,
        roi_delta=result.roi_delta,
        harm_count=result.harm_count,
        safe_beneficial_count=result.safe_beneficial_count,
        reasons=reasons,
    )
