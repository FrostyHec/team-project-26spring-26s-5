"""Converters between LangChain messages and MessageRecord.

Enables round-tripping messages to/from SQLite storage while
preserving tool call metadata needed for LangGraph replay.
"""

from datetime import UTC, datetime

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from agent_core.models.session import MessageRecord, MessageRole, MessageStatus


def message_to_record(
    msg: BaseMessage,
    session_id: str,
    ordinal: int,
) -> MessageRecord:
    """Convert a LangChain message to a persistable MessageRecord.

    Args:
        msg: The LangChain message object.
        session_id: The owning session ID.
        ordinal: Position in conversation.

    Returns:
        A MessageRecord ready for storage.
    """
    role = _get_role(msg)
    tool_call_id = None
    tool_calls = None

    if isinstance(msg, ToolMessage):
        tool_call_id = msg.tool_call_id
    elif isinstance(msg, AIMessage) and msg.tool_calls:
        tool_calls = msg.tool_calls

    return MessageRecord(
        session_id=session_id,
        role=role,
        content=str(msg.content),
        tool_call_id=tool_call_id,
        tool_calls=tool_calls,
        status=MessageStatus.COMPLETED,
        created_at=datetime.now(UTC),
        ordinal=ordinal,
    )


def record_to_message(record: MessageRecord) -> BaseMessage:
    """Convert a MessageRecord back to a LangChain message.

    Args:
        record: The stored message record.

    Returns:
        The corresponding LangChain message object.

    Raises:
        ValueError: If the role is unknown.
    """
    if record.role == MessageRole.HUMAN:
        return HumanMessage(content=record.content)
    elif record.role == MessageRole.AI:
        kwargs: dict = {"content": record.content}
        if record.tool_calls:
            kwargs["tool_calls"] = record.tool_calls
        return AIMessage(**kwargs)
    elif record.role == MessageRole.TOOL:
        return ToolMessage(
            content=record.content,
            tool_call_id=record.tool_call_id or "",
        )
    elif record.role == MessageRole.SYSTEM:
        return SystemMessage(content=record.content)
    else:
        raise ValueError(f"Unknown message role: {record.role}")


def _get_role(msg: BaseMessage) -> MessageRole:
    """Map a LangChain message to a MessageRole.

    Args:
        msg: The LangChain message.

    Returns:
        The corresponding MessageRole.

    Raises:
        ValueError: If the message type is unsupported.
    """
    if isinstance(msg, HumanMessage):
        return MessageRole.HUMAN
    elif isinstance(msg, AIMessage):
        return MessageRole.AI
    elif isinstance(msg, ToolMessage):
        return MessageRole.TOOL
    elif isinstance(msg, SystemMessage):
        return MessageRole.SYSTEM
    else:
        raise ValueError(f"Unsupported message type: {type(msg)}")
