"""The standardized message format that flows through the entire harness.

Every piece of communication between intake, the harness core, and brains is a
:class:`HarnessMessage`. No exceptions. Getting this schema right is the
foundation everything else builds on.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


def _new_id() -> str:
    """Return a fresh UUID4 string."""
    return str(uuid.uuid4())


class MessageType(str, Enum):
    """The kind of message being sent across the bus.

    - ``TASK``: the harness assigning work to a brain.
    - ``RESULT``: a brain returning completed work.
    - ``EVENT``: a brain broadcasting that something happened.
    - ``BROADCAST``: the harness announcing to all brains.
    - ``ACK``: acknowledgment of receipt.
    """

    TASK = "TASK"
    RESULT = "RESULT"
    EVENT = "EVENT"
    BROADCAST = "BROADCAST"
    ACK = "ACK"


# Reserved logical destinations that are not brain identifiers.
BROADCAST_DESTINATION = "broadcast"
HARNESS_DESTINATION = "harness"
INTAKE_SOURCE = "intake"


class HarnessMessage(BaseModel):
    """A single message flowing through the harness.

    Attributes:
        id: UUID generated at creation time.
        timestamp: Creation time in UTC.
        source: ``brain_id`` or ``"intake"`` or ``"harness"``.
        destination: ``brain_id`` or ``"harness"`` or ``"broadcast"``.
        message_type: One of :class:`MessageType`.
        priority: ``1``-``5`` where ``5`` is highest.
        payload: Task/result/event content.
        context_id: Links all related messages in one pipeline run.
        parent_id: The message this one is responding to, if any.
        metadata: Tracing, timing, model used, tokens, cost, etc.
    """

    id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_now)
    source: str
    destination: str
    message_type: MessageType
    priority: int = Field(default=3, ge=1, le=5)
    payload: dict[str, Any] = Field(default_factory=dict)
    context_id: str = Field(default_factory=_new_id)
    parent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def reply(
        self,
        *,
        source: str,
        message_type: MessageType,
        payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        priority: int | None = None,
    ) -> HarnessMessage:
        """Build a reply to this message, preserving the pipeline ``context_id``.

        Args:
            source: The ``brain_id`` (or component) emitting the reply.
            message_type: The type of the reply message.
            payload: Optional payload for the reply.
            metadata: Optional metadata for the reply.
            priority: Optional priority override; defaults to this message's.

        Returns:
            A new :class:`HarnessMessage` addressed back to this message's source.
        """
        return HarnessMessage(
            source=source,
            destination=self.source,
            message_type=message_type,
            priority=self.priority if priority is None else priority,
            payload=payload or {},
            context_id=self.context_id,
            parent_id=self.id,
            metadata=metadata or {},
        )

    def to_wire(self) -> str:
        """Serialize the message to a JSON string for transport over the bus."""
        return self.model_dump_json()

    @classmethod
    def from_wire(cls, raw: str | bytes) -> HarnessMessage:
        """Deserialize a message from a JSON string or bytes received off the bus."""
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return cls.model_validate_json(raw)
