"""Pydantic schemas shared across the entire harness.

These models are the contract between intake, the harness core, and every brain.
They have no external dependencies and are safe to import anywhere.
"""

from harness.schemas.audit import AuditEvent, AuditEventType
from harness.schemas.brain_info import BrainContext, BrainInfo, BrainState
from harness.schemas.judgment import JudgmentEntry
from harness.schemas.message import (
    BROADCAST_DESTINATION,
    HARNESS_DESTINATION,
    INTAKE_SOURCE,
    HarnessMessage,
    MessageType,
)
from harness.schemas.result import Result, ResultStatus
from harness.schemas.task import Task, TaskStatus

__all__ = [
    "BROADCAST_DESTINATION",
    "HARNESS_DESTINATION",
    "INTAKE_SOURCE",
    "AuditEvent",
    "AuditEventType",
    "BrainContext",
    "BrainInfo",
    "BrainState",
    "HarnessMessage",
    "JudgmentEntry",
    "MessageType",
    "Result",
    "ResultStatus",
    "Task",
    "TaskStatus",
]
