"""Human gate guard — authoritative override for actions that always need a human.

Mirrors :mod:`judgment.guards.harm_aware`'s shape but for a different concern:
some actions (sending a proposal, submitting a deliverable, anything touching
money or an external account) must never be taken autonomously, regardless of
how confident the lifecycle is. This guard forces any outbound-action outcome
to ``REQUEST_MORE_EVIDENCE``, which the harness already renders as a
human-reviewable ``NEEDS_OPERATOR`` state rather than inventing a new one.
"""

from __future__ import annotations

from judgment.outcome import JudgmentOutcome
from judgment.profile import JudgmentProfile


def apply_human_gate(
    profile: JudgmentProfile,
    *,
    proposed: JudgmentOutcome,
) -> tuple[JudgmentOutcome, str | None]:
    """Force outbound-action outcomes to human review. Returns (outcome, block_reason)."""
    if not profile.human_gate_enabled:
        return proposed, None

    if proposed in (JudgmentOutcome.PROCEED, JudgmentOutcome.STAGED_PROCEED):
        return JudgmentOutcome.REQUEST_MORE_EVIDENCE, "human_gate:action_requires_operator"

    return proposed, None
