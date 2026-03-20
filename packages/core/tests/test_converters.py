"""Tests for message converters — LangChain ↔ MessageRecord round-trip."""

import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from agent_core.models.session import MessageRecord, MessageRole
from agent_core.persistence.converters import (
    _get_role,
    message_to_record,
    record_to_message,
)


class TestMessageToRecord:
    """Test converting LangChain messages to MessageRecord."""

    def test_human_message(self) -> None:
        """HumanMessage should convert to HUMAN role."""
        msg = HumanMessage(content="Hello")
        record = message_to_record(msg, "session-1", 0)
        assert record.role == MessageRole.HUMAN
        assert record.content == "Hello"
        assert record.session_id == "session-1"
        assert record.ordinal == 0
        assert record.tool_calls is None
        assert record.tool_call_id is None

    def test_ai_message_no_tools(self) -> None:
        """AIMessage without tool_calls should have no tool metadata."""
        msg = AIMessage(content="I can help with that.")
        record = message_to_record(msg, "session-1", 1)
        assert record.role == MessageRole.AI
        assert record.content == "I can help with that."
        assert record.tool_calls is None

    def test_ai_message_with_tool_calls(self) -> None:
        """AIMessage with tool_calls should preserve them."""
        tool_calls = [{"name": "add", "args": {"a": 1, "b": 2}, "id": "call_1"}]
        msg = AIMessage(content="", tool_calls=tool_calls)
        record = message_to_record(msg, "session-1", 2)
        assert record.role == MessageRole.AI
        assert record.tool_calls is not None
        assert len(record.tool_calls) == 1
        assert record.tool_calls[0]["name"] == "add"
        assert record.tool_calls[0]["args"] == {"a": 1, "b": 2}
        assert record.tool_calls[0]["id"] == "call_1"

    def test_tool_message(self) -> None:
        """ToolMessage should preserve tool_call_id."""
        msg = ToolMessage(content="42", tool_call_id="call_1")
        record = message_to_record(msg, "session-1", 3)
        assert record.role == MessageRole.TOOL
        assert record.content == "42"
        assert record.tool_call_id == "call_1"

    def test_system_message(self) -> None:
        """SystemMessage should convert to SYSTEM role."""
        msg = SystemMessage(content="You are helpful.")
        record = message_to_record(msg, "session-1", 0)
        assert record.role == MessageRole.SYSTEM
        assert record.content == "You are helpful."


class TestRecordToMessage:
    """Test converting MessageRecord back to LangChain messages."""

    def test_human_record(self) -> None:
        """HUMAN record should convert to HumanMessage."""
        record = MessageRecord(
            session_id="s1",
            role=MessageRole.HUMAN,
            content="Hi",
            ordinal=0,
        )
        msg = record_to_message(record)
        assert isinstance(msg, HumanMessage)
        assert msg.content == "Hi"

    def test_ai_record_no_tools(self) -> None:
        """AI record without tool_calls should be plain AIMessage."""
        record = MessageRecord(
            session_id="s1",
            role=MessageRole.AI,
            content="Reply",
            ordinal=1,
        )
        msg = record_to_message(record)
        assert isinstance(msg, AIMessage)
        assert msg.content == "Reply"
        assert not msg.tool_calls

    def test_ai_record_with_tool_calls(self) -> None:
        """AI record with tool_calls should restore them."""
        tool_calls = [{"name": "multiply", "args": {"a": 3, "b": 4}, "id": "call_2"}]
        record = MessageRecord(
            session_id="s1",
            role=MessageRole.AI,
            content="",
            tool_calls=tool_calls,
            ordinal=2,
        )
        msg = record_to_message(record)
        assert isinstance(msg, AIMessage)
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0]["name"] == "multiply"
        assert msg.tool_calls[0]["args"] == {"a": 3, "b": 4}
        assert msg.tool_calls[0]["id"] == "call_2"

    def test_tool_record(self) -> None:
        """TOOL record should convert to ToolMessage."""
        record = MessageRecord(
            session_id="s1",
            role=MessageRole.TOOL,
            content="12",
            tool_call_id="call_2",
            ordinal=3,
        )
        msg = record_to_message(record)
        assert isinstance(msg, ToolMessage)
        assert msg.content == "12"
        assert msg.tool_call_id == "call_2"

    def test_system_record(self) -> None:
        """SYSTEM record should convert to SystemMessage."""
        record = MessageRecord(
            session_id="s1",
            role=MessageRole.SYSTEM,
            content="Be helpful.",
            ordinal=0,
        )
        msg = record_to_message(record)
        assert isinstance(msg, SystemMessage)
        assert msg.content == "Be helpful."

    def test_unknown_role_raises(self) -> None:
        """Unknown role should raise during validation."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            MessageRecord(
                session_id="s1",
                role="unknown",  # type: ignore[arg-type]
                content="???",
                ordinal=0,
            )


class TestRoundTrip:
    """Test full round-trip: LangChain → Record → LangChain."""

    def test_human_round_trip(self) -> None:
        """HumanMessage should survive a round-trip."""
        original = HumanMessage(content="Round trip test")
        record = message_to_record(original, "s1", 0)
        restored = record_to_message(record)
        assert isinstance(restored, HumanMessage)
        assert restored.content == original.content

    def test_ai_with_tools_round_trip(self) -> None:
        """AIMessage with tool_calls should survive a round-trip."""
        tool_calls = [{"name": "add", "args": {"a": 5, "b": 3}, "id": "call_rt"}]
        original = AIMessage(content="", tool_calls=tool_calls)
        record = message_to_record(original, "s1", 1)
        restored = record_to_message(record)
        assert isinstance(restored, AIMessage)
        assert len(restored.tool_calls) == 1
        assert restored.tool_calls[0]["name"] == "add"
        assert restored.tool_calls[0]["args"] == {"a": 5, "b": 3}
        assert restored.tool_calls[0]["id"] == "call_rt"

    def test_tool_message_round_trip(self) -> None:
        """ToolMessage should survive a round-trip."""
        original = ToolMessage(content="8", tool_call_id="call_rt")
        record = message_to_record(original, "s1", 2)
        restored = record_to_message(record)
        assert isinstance(restored, ToolMessage)
        assert restored.content == "8"
        assert restored.tool_call_id == "call_rt"


class TestGetRole:
    """Test the _get_role helper."""

    def test_unsupported_type_raises(self) -> None:
        """Unsupported message types should raise ValueError."""
        from langchain_core.messages import ChatMessage

        msg = ChatMessage(content="test", role="custom")
        with pytest.raises(ValueError, match="Unsupported message type"):
            _get_role(msg)
