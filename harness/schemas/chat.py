"""Chat API schemas for Blvckbot conversational interface."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AttachmentPayload(BaseModel):
    """A file attached to a chat message."""

    type: Literal["image", "video", "document"]
    filename: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    data: str = Field(min_length=1, description="Base64-encoded file content")


class ChatRequest(BaseModel):
    """POST /chat body."""

    message: str = ""
    session_id: str | None = None
    attachments: list[AttachmentPayload] | None = None

    @model_validator(mode="after")
    def require_content(self) -> ChatRequest:
        has_message = bool(self.message.strip())
        has_attachments = bool(self.attachments)
        if not has_message and not has_attachments:
            raise ValueError("message or attachments required")
        return self
