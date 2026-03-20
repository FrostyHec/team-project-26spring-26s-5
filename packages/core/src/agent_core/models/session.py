"""Pydantic models for session and message persistence."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Return timezone-aware UTC now (replaces deprecated utcnow)."""
    return datetime.now(UTC)


class MessageRole(StrEnum):
    """Role of a message in the conversation."""

    HUMAN = "human"
    AI = "ai"
    TOOL = "tool"
    SYSTEM = "system"


class MessageRecord(BaseModel):
    """A persisted message within a session.

    Attributes:
        id: Auto-incremented database ID.
        session_id: ID of the owning session.
        role: Message role (human/ai/tool/system).
        content: Message text content.
        tool_call_id: Tool call ID (for tool messages only).
        tool_calls: Serialized tool call metadata (for AI messages).
        created_at: Timestamp of message creation.
        ordinal: Position in conversation (0-based).
    """

    id: int | None = None
    session_id: str
    role: MessageRole
    content: str
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    ordinal: int = 0


class SessionRecord(BaseModel):
    """A persisted chat session.

    Attributes:
        id: UUID string.
        title: User-facing label.
        created_at: Session creation timestamp.
        updated_at: Last activity timestamp.
        is_active: Soft-delete flag.
        pending_state: Serialized in-flight tool call state.
    """

    id: str
    title: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    is_active: bool = True
    pending_state: dict[str, Any] | None = None


class SessionSummary(BaseModel):
    """Lightweight session info for listing.

    Attributes:
        id: Session UUID.
        title: Session title.
        created_at: Session creation timestamp.
        updated_at: Last activity timestamp.
        message_count: Total messages in session.
        can_resume: True if an interrupted ReAct loop can be resumed.
    """

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    can_resume: bool = False


class SessionDetail(BaseModel):
    """Full session info with message history.

    Attributes:
        session: The session record.
        messages: All messages in the session.
    """

    session: SessionRecord
    messages: list[MessageRecord]
