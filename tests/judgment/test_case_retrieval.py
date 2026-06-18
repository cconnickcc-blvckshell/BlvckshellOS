"""Unit tests for case retrieval (J12)."""

import pytest
from harness.schemas.judgment import JudgmentEntry
from judgment.reasoning.case_retrieval import format_cases_for_prompt, retrieve_cases
from memory.judgment_ledger import InMemoryJudgmentLedger


@pytest.fixture
async def ledger() -> InMemoryJudgmentLedger:
    store = InMemoryJudgmentLedger()
    await store.connect()
    await store.record(
        JudgmentEntry(
            brain_id="venture",
            context_id="c1",
            belief="Alpha trading thesis validated",
            confidence=0.85,
            assumptions=["judgment_outcome:PROCEED"],
        )
    )
    await store.record(
        JudgmentEntry(
            brain_id="capital",
            context_id="c2",
            belief="Beta allocation plan",
            confidence=0.8,
        )
    )
    return store


async def test_retrieve_cases_keyword_match(ledger: InMemoryJudgmentLedger) -> None:
    cases = await retrieve_cases(ledger, belief_keyword="trading", domain="venture")
    assert len(cases) == 1
    assert cases[0].belief.startswith("Alpha")
    assert cases[0].similarity_score > 0


async def test_format_cases_for_prompt(ledger: InMemoryJudgmentLedger) -> None:
    cases = await retrieve_cases(ledger, belief_keyword="trading", domain="venture")
    text = format_cases_for_prompt(cases)
    assert "SIMILAR PAST DECISIONS" in text
    assert "PROCEED" in text
