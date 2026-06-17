"""The standardized message envelope every layer of the harness speaks.

``HarnessMessage`` is the single, non-negotiable wire format. No object crosses
the message bus unless it conforms to this schema.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class MessageType(str, Enum):
    """The kind of traffic a message represents."""

    TASK = "TASK"
    """Harness (or a brain) assigning work to a brain."""
    RESULT = "RESULT"
    """A brain returning completed work."""
    EVENT = "EVENT"
    """A brain broadcasting that something happened."""
    BROADCAST = "BROADCAST"
    """The harness announcing to every brain."""
    ACK = "ACK"
    """Acknowledgment of receipt."""


def _new_id() -> str:
    """Generate a fresh UUID4 string for a message id."""
    return str(uuid4())


def _utcnow() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(UTC)


BROADCAST_DESTINATION = "broadcast"
HARNESS_ADDRESS = "harness"
INTAKE_ADDRESS = "intake"


class HarnessMessage(BaseModel):
    """The canonical envelope for all harness communication.

    Attributes:
        id: UUID generated at creation time.
        timestamp: UTC creation time.
        source: ``brain_id`` of the sender, or ``"intake"`` / ``"harness"``.
        destination: ``brain_id``, ``"harness"`` or ``"broadcast"``.
        message_type: One of :class:`MessageType`.
        priority: Integer 1-5, where 5 is highest.
        payload: Task/result/event content.
        context_id: Links every message in one pipeline run.
        parent_id: The message this one is responding to, if any.
        metadata: Tracing, timing, model used, tokens and cost.
    """

    id: str = Field(default_factory=_new_id)
    timestamp: datetime = Field(default_factory=_utcnow)
    source: str
    destination: str
    message_type: MessageType
    priority: int = Field(default=3, ge=1, le=5)
    payload: dict[str, Any] = Field(default_factory=dict)
    context_id: str = Field(default_factory=_new_id)
    parent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source", "destination")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        """Reject empty routing addresses early — they break the bus."""
        if not value or not value.strip():
            raise ValueError("source/destination must be a non-empty address")
        return value

    @property
    def is_broadcast(self) -> bool:
        """Whether this message targets every registered brain."""
        return self.destination == BROADCAST_DESTINATION

    def reply(
        self,
        *,
        source: str,
        message_type: MessageType,
        payload: dict[str, Any] | None = None,
        priority: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> HarnessMessage:
        """Build a child message that responds to this one.

        The reply automatically inherits ``context_id`` and links back via
        ``parent_id`` so the observer can reconstruct the full pipeline trace.

        Args:
            source: Address of the responder (usually a ``brain_id``).
            message_type: Type of the reply.
            payload: Reply content.
            priority: Optional override; defaults to the parent's priority.
            metadata: Optional extra metadata merged onto the reply.

        Returns:
            A new :class:`HarnessMessage` addressed back to this message's source.
        """
        return HarnessMessage(
            source=source,
            destination=self.source,
            message_type=message_type,
            priority=priority if priority is not None else self.priority,
            payload=payload or {},
            context_id=self.context_id,
            parent_id=self.id,
            metadata=metadata or {},
        )
