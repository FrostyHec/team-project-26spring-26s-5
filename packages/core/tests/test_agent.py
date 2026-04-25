from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agent_core.engine.agent import ReactAgent
from agent_core.models.events import EventType
from agent_core.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_agent_stream_tool_events():
    """Test that stream correctly yields tool_start and tool_end."""
    mock_llm = AsyncMock()
    mock_llm.bind_tools.return_value = mock_llm

    registry = ToolRegistry()
    registry.execute = AsyncMock(return_value="mocked_tool_output")

    # LLM returns a tool call on first turn
    first_response = AIMessage(
        content="",
        tool_calls=[{"name": "mock_tool", "args": {"x": 1}, "id": "call_1"}],
    )
    # LLM returns final answer on second turn
    second_response = AIMessage(content="Final answer")

    mock_llm.ainvoke.side_effect = [first_response, second_response]

    agent = ReactAgent(llm=mock_llm, tool_registry=registry)

    events = []
    async for event in agent.stream("test input", session_id="test_session"):
        events.append(event)

    tool_start_events = [e for e in events if e["type"] == EventType.TOOL_START]
    tool_end_events = [e for e in events if e["type"] == EventType.TOOL_END]

    # We expect custom events emitted from _execute_tools
    assert len(tool_start_events) == 1
    assert tool_start_events[0]["name"] == "mock_tool"
    assert tool_start_events[0]["input"] == {"x": 1}

    assert len(tool_end_events) == 1
    assert tool_end_events[0]["name"] == "mock_tool"
    assert tool_end_events[0]["output"] == "mocked_tool_output"


@pytest.mark.asyncio
async def test_agent_stream_loop_events():
    """Test that stream emits loop_start and loop_end events."""
    mock_llm = AsyncMock()
    mock_llm.bind_tools.return_value = mock_llm

    registry = ToolRegistry()

    response = AIMessage(content="Hello!")
    mock_llm.ainvoke.return_value = response

    agent = ReactAgent(llm=mock_llm, tool_registry=registry)

    events = []
    async for event in agent.stream("hi", session_id="test_loop"):
        events.append(event)

    # First event should be loop_start, last should be loop_end
    assert events[0]["type"] == EventType.LOOP_START
    assert events[-1]["type"] == EventType.LOOP_END


@pytest.mark.asyncio
async def test_agent_stream_thinking_event():
    """Test ThinkingEvent model is well-formed.

    Note: The actual thinking event is emitted during on_chat_model_end
    in LangGraph, which requires a real LLM. This test validates the
    event model itself and its integration with EventType.
    """
    from agent_core.models.events import ThinkingEvent

    event = ThinkingEvent(content="Let me calculate that for you.")
    dumped = event.model_dump()
    assert dumped["type"] == EventType.THINKING
    assert dumped["content"] == "Let me calculate that for you."


@pytest.mark.asyncio
async def test_agent_stream_with_history_uses_override_without_persistence():
    """stream_with_history should use caller history and skip persistence by default."""
    mock_llm = AsyncMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke.return_value = AIMessage(content="Hello from branch")

    registry = ToolRegistry()
    agent = ReactAgent(llm=mock_llm, tool_registry=registry)
    agent._ensure_session = AsyncMock()  # type: ignore[method-assign]
    agent._persist_messages = AsyncMock()  # type: ignore[method-assign]

    events = []
    history = [HumanMessage(content="history message")]
    async for event in agent.stream_with_history(
        "branch input",
        history,
        session_id="branch-session",
    ):
        events.append(event)

    assert events[0]["type"] == EventType.LOOP_START
    assert events[-1]["type"] == EventType.LOOP_END
    agent._ensure_session.assert_awaited_once_with("branch-session")
    agent._persist_messages.assert_not_called()
    llm_input = mock_llm.ainvoke.await_args.args[0]
    assert len(llm_input) == 2
    assert llm_input[0].content == "history message"
    assert llm_input[1].content == "branch input"


@pytest.mark.asyncio
async def test_agent_stream_from_messages_uses_explicit_messages():
    """stream_from_messages should run the graph from the provided full message list."""
    mock_llm = AsyncMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke.return_value = AIMessage(content="Hello again")

    registry = ToolRegistry()
    agent = ReactAgent(llm=mock_llm, tool_registry=registry)
    agent._ensure_session = AsyncMock()  # type: ignore[method-assign]
    agent._persist_messages = AsyncMock()  # type: ignore[method-assign]

    messages = [HumanMessage(content="existing user")]
    events = []
    async for event in agent.stream_from_messages(
        messages, session_id="explicit-session"
    ):
        events.append(event)

    assert events[0]["type"] == EventType.LOOP_START
    assert events[-1]["type"] == EventType.LOOP_END
    agent._ensure_session.assert_awaited_once_with("explicit-session")
    agent._persist_messages.assert_not_called()
    llm_input = mock_llm.ainvoke.await_args.args[0]
    assert len(llm_input) == 1
    assert llm_input[0].content == "existing user"
