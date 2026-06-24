"""Research Brain — sources and scores freelance leads (Upwork + manual Fiverr)."""

from __future__ import annotations

from typing import Any

from judgment.profile import JudgmentProfile, ModelConfig

from brains._base.brain import BrainRuntime, LLMBrain
from brains._base.tools import FunctionTool
from integrations.upwork_client import UpworkAPIError, UpworkAuthError, UpworkClient

RESEARCH_SYSTEM_PROMPT = (
    "You are the Research Brain for blvckbot, an autonomous freelance agent. "
    "Your job is to find and score freelance leads, not to act on them.\n\n"
    "Use upwork_search_jobs to pull live Upwork postings for relevant skills. "
    "Fiverr has no API access — leads from Fiverr only arrive via "
    "fiverr_manual_intake, where a human has pasted in a listing; never invent "
    "or assume Fiverr listings exist.\n\n"
    "For each candidate lead, use score_lead to rate fit (skills match), "
    "profitability (budget vs. effort), and client quality (history, clarity "
    "of the brief) on a 0-10 scale each.\n\n"
    "End with PROCEED if you found one or more leads worth pursuing (list "
    "them with their scores), HOLD if nothing qualifies, or "
    "REQUEST_MORE_EVIDENCE if the objective is too vague to search against."
)


async def _score_lead(arguments: dict[str, Any]) -> dict[str, Any]:
    """Average fit/profitability/client-quality factors (0-10 each) into one score."""
    factors = arguments.get("factors", {})
    if not isinstance(factors, dict) or not factors:
        return {"score": 0.0, "note": "no factors provided"}
    values = [float(v) for v in factors.values() if isinstance(v, (int, float))]
    score = round(sum(values) / (len(values) or 1), 2)
    return {"score": score, "max": 10.0, "factors": factors}


async def _fiverr_manual_intake(arguments: dict[str, Any]) -> dict[str, Any]:
    """Normalize a human-pasted Fiverr listing into the common lead shape.

    Fiverr has no sanctioned API and is never scraped or automated. A human
    pastes the listing text/fields in; this tool only reshapes it.
    """
    title = arguments.get("title", "")
    description = arguments.get("description", "")
    budget = arguments.get("budget")
    skills = arguments.get("skills") or []
    if not title and not description:
        return {"error": "title or description is required for a manually pasted listing"}
    return {
        "id": f"fiverr-manual-{abs(hash(title + description)) % 10_000_000}",
        "title": title,
        "description": description,
        "skills": skills,
        "budget_amount": budget,
        "budget_currency": arguments.get("currency", "USD"),
        "engagement_type": arguments.get("engagement_type"),
        "source": "fiverr_manual",
    }


class ResearchBrain(LLMBrain):
    """Finds and scores freelance job leads from Upwork (API) and Fiverr (manual paste-in)."""

    brain_id = "research"
    name = "Research Brain"
    description = (
        "Sources freelance job leads from Upwork (live API) and manually pasted "
        "Fiverr listings, and scores them for fit, profitability, and client quality."
    )
    capabilities = ["job_lead_research", "lead_scoring"]
    pipeline_participant = False
    judgment_profile = JudgmentProfile(
        domain="research",
        harm_guard_enabled=False,
        human_gate_enabled=False,
        model=ModelConfig(
            preferred_model="claude-sonnet-4-6",
            fallback_models=["gpt-4o"],
            temperature=0.4,
        ),
    )
    system_prompt = RESEARCH_SYSTEM_PROMPT

    def __init__(self, runtime: BrainRuntime) -> None:
        super().__init__(runtime)
        self.tools = [
            FunctionTool(
                name="upwork_search_jobs",
                description=(
                    "Search live Upwork job postings by free-text query "
                    "(skills/keywords). Requires Upwork credentials to be configured."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search keywords/skills."},
                        "limit": {
                            "type": "integer",
                            "description": "Max postings to return (default 20).",
                        },
                    },
                    "required": ["query"],
                },
                func=self._upwork_search_jobs,
            ),
            FunctionTool(
                name="fiverr_manual_intake",
                description=(
                    "Normalize a human-pasted Fiverr listing into a lead record. "
                    "Fiverr is never scraped — only use this with text a human provided."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "budget": {"type": "number"},
                        "currency": {"type": "string"},
                        "skills": {"type": "array", "items": {"type": "string"}},
                        "engagement_type": {"type": "string"},
                    },
                },
                func=_fiverr_manual_intake,
            ),
            FunctionTool(
                name="score_lead",
                description=(
                    "Average 0-10 fit/profitability/client_quality factors into one lead score."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "factors": {
                            "type": "object",
                            "description": "Map of factor name to a 0-10 rating.",
                        }
                    },
                    "required": ["factors"],
                },
                func=_score_lead,
            ),
        ]

    async def _upwork_search_jobs(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Search Upwork via the configured client, surfacing auth/API errors as data."""
        query = arguments.get("query", "")
        limit = int(arguments.get("limit", 20))
        try:
            client = UpworkClient(self.runtime.settings)
            jobs = await client.search_jobs(query, limit=limit)
        except (UpworkAuthError, UpworkAPIError) as exc:
            return {"error": str(exc), "jobs": []}
        return {"jobs": jobs, "count": len(jobs)}
