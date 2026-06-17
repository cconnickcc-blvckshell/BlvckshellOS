"""Pydantic v2 schemas that define the harness wire protocol.

Every object that crosses a layer boundary is one of these models. They are the
single source of truth for the shape of the system.
"""

from harness.schemas.judgment import JudgmentChange, JudgmentEntry
from harness.schemas.message import HarnessMessage, MessageType
from harness.schemas.result import ResultPayload, ResultStatus
from harness.schemas.task import TaskPayload, TaskStatus

__all__ = [
    "HarnessMessage",
    "MessageType",
    "TaskPayload",
    "TaskStatus",
    "ResultPayload",
    "ResultStatus",
    "JudgmentEntry",
    "JudgmentChange",
]
