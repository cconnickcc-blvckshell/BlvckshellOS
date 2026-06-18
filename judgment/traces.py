"""Stage traces for the judgment lifecycle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from judgment.outcome import JudgmentOutcome
from judgment.reasoning.case_retrieval import CaseRecord
from judgment.stages.confidence import ConfidenceAdjustTrace
from judgment.stages.exploration import ExplorationTrace


class JudgmentStage(str, Enum):
    """Nine-stage judgment cycle."""

    OBSERVATION = "OBSERVATION"
    BELIEF = "BELIEF"
    CONFIDENCE = "CONFIDENCE"
    CHALLENGE = "CHALLENGE"
    EVIDENCE = "EVIDENCE"
    FORECAST = "FORECAST"
    DECISION = "DECISION"
    OUTCOME = "OUTCOME"
    LEARNING = "LEARNING"


@dataclass(slots=True)
class StageTrace:
    """Audit record for one lifecycle stage."""

    stage: JudgmentStage
    consumed_signals: list[str] = field(default_factory=list)
    ignored_signals: list[str] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass(slots=True)
class EvidenceBundle:
    """Structured advisor output — models supply evidence, not decisions."""

    summary: str
    tool_evidence: list[str] = field(default_factory=list)
    provisional_outcome: JudgmentOutcome = JudgmentOutcome.PROCEED
    confidence: float = 0.7
    evidence_positive: bool = True
    expected_roi: float | None = None
    risk_score: float | None = None


@dataclass(slots=True)
class LifecycleRunContext:
    """Mutable context shared between lifecycle and evidence gathering."""

    evidence_prompt_suffix: str = ""
    retrieved_cases: list[CaseRecord] = field(default_factory=list)


@dataclass(slots=True)
class LifecycleResult:
    """Complete output of one judgment cycle."""

    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    outcome: JudgmentOutcome = JudgmentOutcome.PROCEED
    confidence: float = 0.7
    belief: str = ""
    evidence: EvidenceBundle | None = None
    stages: list[StageTrace] = field(default_factory=list)
    guard_blocks: list[str] = field(default_factory=list)
    agent_metrics: dict[str, Any] = field(default_factory=dict)
    raw_analysis: str = ""
    confidence_trace: ConfidenceAdjustTrace | None = None
    exploration_trace: ExplorationTrace | None = None
    retrieved_cases: list[CaseRecord] = field(default_factory=list)


def get_stage_trace(traces: list[StageTrace], stage: str | JudgmentStage) -> StageTrace | None:
    """Return the trace for a named stage."""
    name = stage.value if isinstance(stage, JudgmentStage) else stage
    for trace in traces:
        if trace.stage.value == name:
            return trace
    return None
