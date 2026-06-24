"""Per-brain judgment configuration — config, not code."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    """Per-brain model preference and fallback chain."""

    preferred_model: str
    fallback_models: list[str] = Field(default_factory=list)
    provider: str | None = None  # anthropic | openai | ollama | None (auto-detect)
    temperature: float = 0.7
    max_tokens: int = 4096
    local: bool = False  # True = use local Ollama regardless of harness default


class JudgmentProfile(BaseModel):
    """Controls which lifecycle behaviors apply to a brain."""

    domain: str = "general"
    harm_guard_enabled: bool = False
    human_gate_enabled: bool = False
    safe_divergence_enabled: bool = True
    foundation_enabled: bool = True
    exploration_enabled: bool = True
    case_retrieval_enabled: bool = True
    recall_depth: int = Field(default=20, ge=1, le=200)
    risk_cap: float = Field(default=0.65, ge=0.0, le=1.0)
    min_roi_signal: float = Field(default=0.0, ge=-1.0, le=1.0)
    confidence_ceiling: float = Field(default=0.95, ge=0.0, le=1.0)
    model: ModelConfig | None = None

    @property
    def enable_harm_guard(self) -> bool:
        """Alias for harm_guard_enabled (V1 charter naming)."""
        return self.harm_guard_enabled
