"""Tests for the AgentState definition."""

from agent_core.engine.state import AgentState


class TestAgentState:
    """Test suite for AgentState."""

    def test_state_creation(self) -> None:
        """Test creating an AgentState."""
        state: AgentState = {
            "messages": [],
            "pending_tool_call": None,
        }
        assert state["messages"] == []
        assert state["pending_tool_call"] is None

    def test_state_with_messages(self) -> None:
        """Test state with messages."""
        from langchain_core.messages import HumanMessage

        state: AgentState = {
            "messages": [HumanMessage(content="hello")],
            "pending_tool_call": None,
        }
        assert len(state["messages"]) == 1
        assert state["messages"][0].content == "hello"

    def test_state_with_pending_tool_call(self) -> None:
        """Test state with a pending tool call."""
        state: AgentState = {
            "messages": [],
            "pending_tool_call": {
                "name": "calculator",
                "args": {"a": 1, "b": 2},
            },
        }
        assert state["pending_tool_call"] is not None
        assert state["pending_tool_call"]["name"] == "calculator"
