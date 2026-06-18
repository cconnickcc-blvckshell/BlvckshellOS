"""Evidence parsing — classify model output before decision."""

from __future__ import annotations

import re

from harness.core.agent_loop import AgentLoopResult

from judgment.outcome import JudgmentOutcome
from judgment.traces import EvidenceBundle

_HOLD_PATTERNS = re.compile(
    r"\b(no-go|no go|reject|do not proceed|don't proceed|hold\b|not recommended)\b",
    re.IGNORECASE,
)
_STAGED_PATTERNS = re.compile(
    r"\b(conditional|staged|pilot|phase 1|limited rollout|de-risk|derisk)\b",
    re.IGNORECASE,
)
_EVIDENCE_GAP_PATTERNS = re.compile(
    r"\b(need more|insufficient evidence|more data|request evidence|unclear)\b",
    re.IGNORECASE,
)
_PROCEED_PATTERNS = re.compile(r"\b(go\b|proceed|approve|recommended)\b", re.IGNORECASE)


def assess_evidence(
    outcome: AgentLoopResult,
    *,
    domain: str,
) -> EvidenceBundle:
    """Turn agent-loop output into classified evidence for the Decision stage."""
    text = outcome.final_text or ""
    upper = text.upper()

    provisional = _parse_provisional_outcome(text)
    evidence_positive = _evidence_is_positive(text, upper)
    expected_roi = _extract_expected_roi(text)
    risk_score = _extract_risk_score(text, domain)

    if domain == "capital" and _HOLD_PATTERNS.search(text):
        evidence_positive = False

    confidence = _confidence_from_signals(
        evidence_positive=evidence_positive,
        has_tools=bool(outcome.tool_invocations),
        domain=domain,
    )

    return EvidenceBundle(
        summary=text[:500] or "Completed task.",
        tool_evidence=[f"tool:{inv['tool']}" for inv in outcome.tool_invocations],
        provisional_outcome=provisional,
        confidence=confidence,
        evidence_positive=evidence_positive,
        expected_roi=expected_roi,
        risk_score=risk_score,
    )


def _parse_provisional_outcome(text: str) -> JudgmentOutcome:
    if _EVIDENCE_GAP_PATTERNS.search(text):
        return JudgmentOutcome.REQUEST_MORE_EVIDENCE
    if _HOLD_PATTERNS.search(text):
        return JudgmentOutcome.HOLD
    if _STAGED_PATTERNS.search(text):
        return JudgmentOutcome.STAGED_PROCEED
    if _PROCEED_PATTERNS.search(text):
        return JudgmentOutcome.PROCEED
    return JudgmentOutcome.PROCEED


def _evidence_is_positive(text: str, upper: str) -> bool:
    if _HOLD_PATTERNS.search(text):
        return False
    if "NO-GO" in upper or "NO GO" in upper:
        return False
    if _PROCEED_PATTERNS.search(text) or "GO /" in upper:
        return True
    return True


def _extract_expected_roi(text: str) -> float | None:
    match = re.search(r"roi[:\s]+(-?\d+(?:\.\d+)?)\s*%?", text, re.IGNORECASE)
    if match:
        return float(match.group(1)) / 100.0 if "%" in match.group(0) else float(match.group(1))
    if re.search(r"negative roi|roi negative|unprofitable", text, re.IGNORECASE):
        return -0.1
    return None


def _extract_risk_score(text: str, domain: str) -> float | None:
    match = re.search(r"risk[:\s]+(\d+(?:\.\d+)?)\s*(?:/10|%)?", text, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        return value / 10.0 if value > 1.0 else value
    if domain == "capital" and _HOLD_PATTERNS.search(text):
        return 0.8
    return None


def _confidence_from_signals(*, evidence_positive: bool, has_tools: bool, domain: str) -> float:
    score = 0.65
    if evidence_positive:
        score += 0.1
    if has_tools:
        score += 0.05
    if domain == "capital":
        score -= 0.05
    return min(max(score, 0.0), 0.95)
