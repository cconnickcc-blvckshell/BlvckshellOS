"""Capital Brain (stub) — flags capital/financial domains for later build-out."""

from __future__ import annotations

from judgment.profile import JudgmentProfile, ModelConfig

from brains._base.brain import LLMBrain


class CapitalBrain(LLMBrain):
    """A deliberate stub that flags an idea's capital/financial dimension.

    This brain exists so CKOS can route capital-related concerns today, while the
    full implementation (modeling, allocation, risk) is built out later. It is
    fully wired into the harness — only its depth is intentionally shallow.
    """

    brain_id = "capital"
    name = "Capital Brain"
    description = "Flags the capital/financial dimension as a target domain (stub)"
    capabilities = ["capital_flagging", "financial_screening"]
    max_iterations = 1
    judgment_profile = JudgmentProfile(
        domain="capital",
        harm_guard_enabled=True,
        risk_cap=0.3,
        min_roi_signal=0.0,
        recall_depth=20,
        model=ModelConfig(
            preferred_model="claude-sonnet-4-6",
            fallback_models=["gpt-4o", "qwen2.5:72b"],
            temperature=0.3,
        ),
    )
    system_prompt = (
        "You are the Capital Brain, currently a stub. Do not attempt deep financial "
        "modeling. In 2-4 sentences, flag the capital/financial dimension of the "
        "request: what would need funding or capital modeling, and mark it as a "
        "TARGET DOMAIN for a future full Capital Brain build-out."
    )
