"""Tests for the core message and judgment schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from harness.schemas.judgment import JudgmentEntry
from harness.schemas.message import HarnessMessage, MessageType
from harness.schemas.result import Result, ResultStatus
from harness.schemas.task import Task


def test_message_defaults_are_populated() -> None:
    msg = HarnessMessage(source="intake", destination="ckos", message_type=MessageType.TASK)
    assert msg.id
    assert msg.context_id
    assert msg.timestamp.tzinfo is not None
    assert msg.priority == 3


def test_message_priority_bounds() -> None:
    with pytest.raises(ValidationError):
        HarnessMessage(
            source="a", destination="b", message_type=MessageType.TASK, priority=9
        )


def test_message_wire_round_trip() -> None:
    msg = HarnessMessage(
        source="ckos",
        destination="venture",
        message_type=MessageType.TASK,
        payload={"objective": "validate"},
    )
    restored = HarnessMessage.from_wire(msg.to_wire())
    assert restored == msg


def test_reply_preserves_context_and_links_parent() -> None:
    task = HarnessMessage(
        source="pipeline:abc", destination="venture", message_type=MessageType.TASK
    )
    reply = task.reply(source="venture", message_type=MessageType.RESULT, payload={"ok": True})
    assert reply.destination == "pipeline:abc"
    assert reply.context_id == task.context_id
    assert reply.parent_id == task.id
    assert reply.payload == {"ok": True}


def test_judgment_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        JudgmentEntry(brain_id="x", context_id="c", belief="b", confidence=1.5)


def test_judgment_changelog_records_changes() -> None:
    entry = JudgmentEntry(brain_id="x", context_id="c", belief="b", confidence=0.5)
    entry.record_change("created", {"k": "v"})
    assert entry.changelog[-1]["action"] == "created"
    assert entry.changelog[-1]["details"] == {"k": "v"}


def test_task_independence() -> None:
    independent = Task(capability="cap", objective="do")
    dependent = Task(capability="cap", objective="do", depends_on=["x"])
    assert independent.is_independent
    assert not dependent.is_independent


def test_result_succeeded_flag() -> None:
    ok = Result(task_id="t", brain_id="b", status=ResultStatus.SUCCESS)
    bad = Result(task_id="t", brain_id="b", status=ResultStatus.FAILURE)
    assert ok.succeeded
    assert not bad.succeeded
