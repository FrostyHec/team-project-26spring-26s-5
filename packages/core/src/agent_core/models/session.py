"""Pydantic and SQLModel models for session and message persistence."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Index
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel


def _utcnow() -> datetime:
    """Return timezone-aware UTC now (replaces deprecated utcnow)."""
    return datetime.now(UTC)


class MessageRole(StrEnum):
    """Role of a message in the conversation."""

    HUMAN = "human"
    AI = "ai"
    TOOL = "tool"
    SYSTEM = "system"


class MessageStatus(StrEnum):
    """Persistence status for a message."""

    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    FAILED = "failed"
    STREAMING = "streaming"


class FallbackMode(StrEnum):
    """Fallback mode for selecting the next provider."""

    MANUAL = "manual"
    AUTO = "auto"


class NodeSourceKind(StrEnum):
    """Source of a conversation tree node version."""

    INITIAL = "initial"
    RETRY = "retry"
    USER_EDIT = "user_edit"
    ASSISTANT_EDIT = "assistant_edit"
    FALLBACK = "fallback"


class MessageRecord(BaseModel):
    """A persisted message within a session.

    Attributes:
        id: Auto-incremented database ID.
        session_id: ID of the owning session.
        role: Message role (human/ai/tool/system).
        content: Message text content.
        tool_call_id: Tool call ID (for tool messages only).
        tool_calls: Serialized tool call metadata (for AI messages).
        status: Persistence status (completed/interrupted/failed).
        created_at: Timestamp of message creation.
        ordinal: Position in conversation (0-based).
    """

    id: int | None = None
    session_id: str
    role: MessageRole
    content: str
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    status: MessageStatus = MessageStatus.COMPLETED
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
        selected_provider_id: Session-level provider preference.
        fallback_mode: Session-level fallback mode.
        current_leaf_node_id: Current visible leaf in the conversation tree.
    """

    id: str
    title: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    is_active: bool = True
    pending_state: dict[str, Any] | None = None
    selected_provider_id: str | None = None
    fallback_mode: FallbackMode = FallbackMode.MANUAL
    current_leaf_node_id: str | None = None


class SessionSummary(BaseModel):
    """Lightweight session info for listing.

    Attributes:
        id: Session UUID.
        title: Session title.
        created_at: Session creation timestamp.
        updated_at: Last activity timestamp.
        message_count: Total messages in session.
        can_resume: True if an interrupted ReAct loop can be resumed.
        selected_provider_id: Session-level provider preference.
        fallback_mode: Session-level fallback mode.
    """

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    can_resume: bool = False
    selected_provider_id: str | None = None
    fallback_mode: FallbackMode = FallbackMode.MANUAL


class ChatNodeRecord(BaseModel):
    """A persisted node in the conversation version tree."""

    id: str
    session_id: str
    parent_id: str | None = None
    role: MessageRole
    content: str
    status: MessageStatus = MessageStatus.COMPLETED
    version_group_id: str
    version_index: int = 0
    source_kind: NodeSourceKind = NodeSourceKind.INITIAL
    source_node_id: str | None = None
    response_to_node_id: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    trace_steps: list[dict[str, Any]] | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class VersionGroupSelectionRecord(BaseModel):
    """Selected node state for a version group in a session."""

    session_id: str
    version_group_id: str
    selected_node_id: str
    updated_at: datetime = Field(default_factory=_utcnow)


class NodeLeafBookmarkRecord(BaseModel):
    """Stored descendant leaf preference for a specific node."""

    session_id: str
    node_id: str
    selected_leaf_id: str
    updated_at: datetime = Field(default_factory=_utcnow)


class SessionVersionGroup(BaseModel):
    """A version group projection for the active visible path."""

    version_group_id: str
    node_ids: list[str]
    selected_node_id: str
    position_in_path: int


class SessionDetail(BaseModel):
    """Full session info with message history.

    Attributes:
        session: The session record.
        messages: Linear message history kept during the transition period.
        nodes: Tree nodes for the session.
        visible_path: Ordered node IDs for the currently visible branch.
        version_groups: Version-group projection for the visible path.
    """

    session: SessionRecord
    messages: list[MessageRecord] = Field(default_factory=list)
    nodes: list[ChatNodeRecord] = Field(default_factory=list)
    visible_path: list[str] = Field(default_factory=list)
    version_groups: list[SessionVersionGroup] = Field(default_factory=list)


class SessionTable(SQLModel, table=True):
    """SQLModel table for persisted chat sessions."""

    __tablename__ = "sessions"

    id: str = SQLField(primary_key=True)
    title: str = SQLField(default="")
    created_at: datetime = SQLField(default_factory=_utcnow)
    updated_at: datetime = SQLField(default_factory=_utcnow)
    is_active: bool = SQLField(default=True)
    pending_state: str | None = SQLField(default=None)
    selected_provider_id: str | None = SQLField(default=None)
    fallback_mode: FallbackMode = SQLField(default=FallbackMode.MANUAL)
    current_leaf_node_id: str | None = SQLField(default=None)


class MessageTable(SQLModel, table=True):
    """SQLModel table for persisted chat messages."""

    __tablename__ = "messages"
    __table_args__ = (Index("idx_messages_session", "session_id", "ordinal"),)

    id: int | None = SQLField(default=None, primary_key=True)
    session_id: str = SQLField(foreign_key="sessions.id")
    role: MessageRole
    content: str
    tool_call_id: str | None = SQLField(default=None)
    tool_calls: str | None = SQLField(default=None)
    status: MessageStatus = SQLField(default=MessageStatus.COMPLETED)
    created_at: datetime = SQLField(default_factory=_utcnow)
    ordinal: int


class ChatNodeTable(SQLModel, table=True):
    """SQLModel table for persisted conversation tree nodes."""

    __tablename__ = "chat_nodes"
    __table_args__ = (
        Index("idx_chat_nodes_session_parent", "session_id", "parent_id", "created_at"),
        Index(
            "idx_chat_nodes_version_group",
            "session_id",
            "version_group_id",
            "version_index",
            unique=True,
        ),
        Index("idx_chat_nodes_source", "session_id", "source_node_id"),
    )

    id: str = SQLField(primary_key=True)
    session_id: str = SQLField(foreign_key="sessions.id")
    parent_id: str | None = SQLField(default=None, foreign_key="chat_nodes.id")
    role: MessageRole
    content: str
    status: MessageStatus = SQLField(default=MessageStatus.COMPLETED)
    version_group_id: str
    version_index: int = SQLField(default=0)
    source_kind: NodeSourceKind = SQLField(default=NodeSourceKind.INITIAL)
    source_node_id: str | None = SQLField(default=None)
    response_to_node_id: str | None = SQLField(default=None)
    tool_calls: str | None = SQLField(default=None)
    trace_steps: str | None = SQLField(default=None)
    created_at: datetime = SQLField(default_factory=_utcnow)
    updated_at: datetime = SQLField(default_factory=_utcnow)


class ChatVersionSelectionTable(SQLModel, table=True):
    """Selected version state for a version group in a session."""

    __tablename__ = "chat_version_selections"
    __table_args__ = (
        Index(
            "idx_chat_version_selection_unique",
            "session_id",
            "version_group_id",
            unique=True,
        ),
    )

    session_id: str = SQLField(primary_key=True, foreign_key="sessions.id")
    version_group_id: str = SQLField(primary_key=True)
    selected_node_id: str
    updated_at: datetime = SQLField(default_factory=_utcnow)


class ChatNodeBookmarkTable(SQLModel, table=True):
    """Stored descendant leaf bookmark for a specific node."""

    __tablename__ = "chat_node_bookmarks"
    __table_args__ = (
        Index(
            "idx_chat_node_bookmark_unique",
            "session_id",
            "node_id",
            unique=True,
        ),
    )

    session_id: str = SQLField(primary_key=True, foreign_key="sessions.id")
    node_id: str = SQLField(primary_key=True, foreign_key="chat_nodes.id")
    selected_leaf_id: str
    updated_at: datetime = SQLField(default_factory=_utcnow)
