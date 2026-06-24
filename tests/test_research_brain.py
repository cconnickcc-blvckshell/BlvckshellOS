"""Tests for the Research Brain (blvckbot freelance lead sourcing)."""

from __future__ import annotations

from harness.core.harness import Harness
from brains.blvckbot.research import ResearchBrain, _fiverr_manual_intake, _score_lead


async def test_score_lead_averages_factors() -> None:
    out = await _score_lead(
        {"factors": {"fit": 8, "profitability": 6, "client_quality": 7}}
    )
    assert out["score"] == 7.0
    assert out["max"] == 10.0


async def test_score_lead_handles_empty() -> None:
    out = await _score_lead({"factors": {}})
    assert out["score"] == 0.0


async def test_fiverr_manual_intake_normalizes_listing() -> None:
    out = await _fiverr_manual_intake(
        {
            "title": "Need a logo",
            "description": "Simple, modern logo for a coffee shop",
            "budget": 150,
            "skills": ["illustrator", "branding"],
        }
    )
    assert out["source"] == "fiverr_manual"
    assert out["title"] == "Need a logo"
    assert out["budget_amount"] == 150
    assert out["id"].startswith("fiverr-manual-")


async def test_fiverr_manual_intake_requires_content() -> None:
    out = await _fiverr_manual_intake({})
    assert "error" in out


async def test_research_brain_registered(harness: Harness) -> None:
    brains = await harness.registry.list_all()
    assert any(b.brain_id == "research" for b in brains)


def test_research_brain_exposes_tool_schemas(harness: Harness) -> None:
    brain = harness.get_worker("research")
    assert isinstance(brain, ResearchBrain)
    names = {tool.name for tool in brain.tools}
    assert names == {"upwork_search_jobs", "fiverr_manual_intake", "score_lead"}


async def test_upwork_search_jobs_tool_surfaces_auth_error_when_unconfigured(
    harness: Harness,
) -> None:
    """With no Upwork credentials configured, the tool returns an error, not a crash."""
    brain = harness.get_worker("research")
    out = await brain._upwork_search_jobs({"query": "python automation"})
    assert out["jobs"] == []
    assert "error" in out
