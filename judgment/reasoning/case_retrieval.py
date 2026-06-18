"""Keyword-based case retrieval from the judgment ledger."""

from __future__ import annotations

import re
from dataclasses import dataclass

from harness.schemas.judgment import JudgmentEntry

from judgment.outcome import JudgmentOutcome


@dataclass(slots=True)
class CaseRecord:
    """A similar past decision retrieved for lesson recall."""

    judgment_id: str
    belief: str
    confidence: float
    outcome_quality: float | None
    decision: str
    key_evidence: list[str]
    similarity_score: float


def _outcome_quality_from_entry(entry: JudgmentEntry) -> float | None:
    for change in reversed(entry.changelog):
        if change.get("action") == "outcome_recorded":
            details = change.get("details") or {}
            quality = details.get("outcome_quality")
            if quality is not None:
                return float(quality)
    return None


def _decision_from_entry(entry: JudgmentEntry) -> str:
    for assumption in entry.assumptions:
        if assumption.startswith("judgment_outcome:"):
            return assumption.split(":", 1)[1]
    return JudgmentOutcome.PROCEED.value


def _keyword_overlap(belief: str, keyword: str) -> float:
    tokens_a = set(re.findall(r"[a-z0-9]+", belief.lower()))
    tokens_b = set(re.findall(r"[a-z0-9]+", keyword.lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    overlap = len(tokens_a & tokens_b)
    return min(1.0, overlap / max(len(tokens_b), 1))


async def retrieve_cases(
    ledger,
    *,
    belief_keyword: str,
    domain: str,
    limit: int = 10,
    min_confidence: float = 0.5,
) -> list[CaseRecord]:
    """Query the ledger for similar past decisions.

    TODO: upgrade to semantic similarity in Phase 2.
    """
    tokens = [t for t in re.findall(r"[a-z0-9]+", belief_keyword.lower()) if len(t) > 3]
    search_terms = tokens[:3] if tokens else [belief_keyword.lower()]
    raw: list[JudgmentEntry] = []
    seen: set[str] = set()
    for term in search_terms:
        for entry in await ledger.list_by_belief_keyword(term, limit=limit * 3):
            if entry.id not in seen:
                seen.add(entry.id)
                raw.append(entry)
    cases: list[CaseRecord] = []
    for entry in raw:
        if entry.confidence < min_confidence:
            continue
        if entry.brain_id != domain and domain not in entry.belief.lower():
            similarity = _keyword_overlap(entry.belief, belief_keyword)
            if similarity < 0.2:
                continue
        else:
            similarity = _keyword_overlap(entry.belief, belief_keyword)
        cases.append(
            CaseRecord(
                judgment_id=entry.id,
                belief=entry.belief,
                confidence=entry.confidence,
                outcome_quality=_outcome_quality_from_entry(entry),
                decision=_decision_from_entry(entry),
                key_evidence=list(entry.evidence[:5]),
                similarity_score=similarity,
            )
        )
    cases.sort(key=lambda c: c.similarity_score, reverse=True)
    return cases[:limit]


def format_cases_for_prompt(cases: list[CaseRecord], *, top_n: int = 3) -> str:
    """Render retrieved cases as prompt context for the Evidence stage."""
    if not cases:
        return ""
    lines = ["\n\nSIMILAR PAST DECISIONS (lesson recall):"]
    for case in cases[:top_n]:
        quality = (
            f"{case.outcome_quality:.2f}" if case.outcome_quality is not None else "unknown"
        )
        lines.append(
            f"- [{case.decision}] {case.belief[:120]} "
            f"(confidence={case.confidence:.2f}, outcome_quality={quality})"
        )
    return "\n".join(lines)
