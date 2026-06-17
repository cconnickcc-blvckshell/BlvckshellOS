"""Tests for the wire-protocol schemas."""

from __future__ import annotations

import pytest
from harness.schemas.judgment import JudgmentEntry
from harness.schemas.message import HarnessMessage, MessageType
from pydantic import ValidationError


def test_message_defaults_are_populated() -> None:
    msg = HarnessMessage(source="intake", destination="ckos", message_type=MessageType.TASK)
    assert msg.id
    assert msg.context_id
    assert msg.timestamp.tzinfo is not None
    assert msg.priority == 3


def test_message_rejects_empty_addresses() -> None:
    with pytest.raises(ValidationError):
        HarnessMessage(source=" ", destination="ckos", message_type=MessageType.TASK)


def test_priority_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        HarnessMessage(
            source="a", destination="b", message_type=MessageType.TASK, priority=9
        )


def test_reply_links_context_and_parent() -> None:
    task = HarnessMessage(source="harness", destination="venture", message_type=MessageType.TASK)
    reply = task.reply(source="venture", message_type=MessageType.RESULT, payload={"ok": True})
    assert reply.context_id == task.context_id
    assert reply.parent_id == task.id
    assert reply.destination == task.source
    assert reply.message_type == MessageType.RESULT


def test_broadcast_detection() -> None:
    msg = HarnessMessage(
        source="harness", destination="broadcast", message_type=MessageType.BROADCAST
    )
    assert msg.is_broadcast


def test_judgment_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        JudgmentEntry(brain_id="x", context_id="c", belief="b", confidence=1.5)


def test_judgment_changelog_append() -> None:
    entry = JudgmentEntry(brain_id="x", context_id="c", belief="b", confidence=0.5)
    entry.record_change(actor="x", field="belief", note="created")
    assert len(entry.changelog) == 1
    assert entry.changelog[0]["actor"] == "x"
