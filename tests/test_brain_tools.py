"""Tests for specialist brain tools and the passthrough transcriber."""

from __future__ import annotations

from brains.examples.venture import VentureBrain, _feasibility_score
from intake.voice import PassthroughTranscriber, transcribe_to_idea


async def test_feasibility_score_averages_factors() -> None:
    out = await _feasibility_score({"factors": {"market": 8, "tech": 6, "moat": 4}})
    assert out["score"] == 6.0
    assert out["max"] == 10.0


async def test_feasibility_score_handles_empty() -> None:
    out = await _feasibility_score({"factors": {}})
    assert out["score"] == 0.0


def test_venture_brain_exposes_tool_schema() -> None:
    tool = next(t for t in VentureBrain.tools if t.name == "feasibility_score")
    schema = tool.to_schema()
    assert schema["name"] == "feasibility_score"
    assert "factors" in schema["input_schema"]["properties"]


def test_venture_brain_exposes_web_search() -> None:
    tool = next(t for t in VentureBrain.tools if t.name == "web_search")
    schema = tool.to_schema()
    assert schema["type"] == "web_search_20250305"


async def test_passthrough_transcriber_to_idea() -> None:
    idea = await transcribe_to_idea(PassthroughTranscriber(), b"  build   a thing  ")
    assert idea == "build a thing"
