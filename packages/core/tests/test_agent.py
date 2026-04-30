from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agent_core.engine.agent import ReactAgent
from agent_core.engine.reasoning import (
    ReasoningSegmentKind,
    ReasoningStreamSplitter,
    split_reasoning_blocks,
    split_reasoning_segments,
)
from agent_core.models.events import EventType, LangGraphEventKind
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


def test_split_reasoning_blocks_removes_think_from_visible_answer():
    """Full-text splitting should keep visible text and extract thinking text."""
    thinking, visible = split_reasoning_blocks(
        "<think>Plan the reply.</think>\n\nVisible answer"
    )

    assert thinking == ["Plan the reply."]
    assert visible == "Visible answer"


def test_reasoning_stream_splitter_streams_thinking_across_chunk_boundaries():
    """Chunked `<think>` tags should still split thinking and visible text."""
    splitter = ReasoningStreamSplitter()

    visible_1, thinking_1 = splitter.feed("<thi")
    visible_2, thinking_2 = splitter.feed("nk>Plan")
    visible_3, thinking_3 = splitter.feed("</th")
    visible_4, thinking_4 = splitter.feed("ink>\n\nDone")
    visible_5, thinking_5 = splitter.flush()

    assert visible_1 == []
    assert thinking_1 == []
    assert visible_2 == []
    assert thinking_2 == ["Plan"]
    assert visible_3 == []
    assert thinking_3 == []
    assert visible_4 == ["Done"]
    assert thinking_4 == []
    assert visible_5 == []
    assert thinking_5 == []


def test_split_reasoning_segments_preserves_interleaved_order():
    """Ordered segment splitting should preserve think/text transitions."""
    segments = split_reasoning_segments("<think>A</think>foo<think>B</think>bar")

    assert [(segment.kind, segment.content) for segment in segments] == [
        (ReasoningSegmentKind.THINKING, "A"),
        (ReasoningSegmentKind.VISIBLE, "foo"),
        (ReasoningSegmentKind.THINKING, "B"),
        (ReasoningSegmentKind.VISIBLE, "bar"),
    ]


@pytest.mark.asyncio
async def test_agent_chat_strips_think_from_response_and_persistence():
    """chat() should return and persist only the visible assistant answer."""
    mock_llm = AsyncMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke.return_value = AIMessage(
        content="<think>Internal plan.</think>\n\nVisible answer"
    )

    agent = ReactAgent(llm=mock_llm, tool_registry=ToolRegistry())
    agent._ensure_session = AsyncMock()  # type: ignore[method-assign]
    agent._persist_messages = AsyncMock()  # type: ignore[method-assign]

    response = await agent.chat("hello", session_id="chat-session")

    assert response == "Visible answer"
    persisted_messages = agent._persist_messages.await_args.args[1]
    assert persisted_messages[0].content == "hello"
    assert persisted_messages[1].content == "Visible answer"


@pytest.mark.asyncio
async def test_agent_chat_with_history_strips_think_before_optional_persistence():
    """chat_with_history() should sanitize returned and persisted assistant text."""
    mock_llm = AsyncMock()
    mock_llm.bind_tools.return_value = mock_llm
    mock_llm.ainvoke.return_value = AIMessage(
        content="<think>Need context.</think>\n\nAnswer from history"
    )

    agent = ReactAgent(llm=mock_llm, tool_registry=ToolRegistry())
    agent._ensure_session = AsyncMock()  # type: ignore[method-assign]
    agent._persist_messages = AsyncMock()  # type: ignore[method-assign]

    response = await agent.chat_with_history(
        "new input",
        [HumanMessage(content="old input")],
        session_id="history-session",
        persist_messages=True,
    )

    assert response == "Answer from history"
    persisted_messages = agent._persist_messages.await_args.args[1]
    assert persisted_messages[0].content == "new input"
    assert persisted_messages[1].content == "Answer from history"


@pytest.mark.asyncio
async def test_agent_stream_emits_thinking_separately_and_persists_clean_content():
    """stream() should emit streamed thinking separately from the visible answer."""

    class _Chunk:
        def __init__(self, content: str) -> None:
            self.content = content

    class _GraphStub:
        async def astream_events(self, *_args, **_kwargs):
            yield {
                "event": LangGraphEventKind.CHAT_MODEL_STREAM,
                "data": {"chunk": _Chunk("<thi")},
            }
            yield {
                "event": LangGraphEventKind.CHAT_MODEL_STREAM,
                "data": {"chunk": _Chunk("nk>Plan")},
            }
            yield {
                "event": LangGraphEventKind.CHAT_MODEL_STREAM,
                "data": {"chunk": _Chunk("</think>\n\nDone")},
            }
            yield {
                "event": LangGraphEventKind.CHAT_MODEL_END,
                "data": {
                    "output": AIMessage(
                        content="<think>Plan</think>\n\nDone",
                    )
                },
            }

    mock_llm = AsyncMock()
    mock_llm.bind_tools.return_value = mock_llm

    agent = ReactAgent(llm=mock_llm, tool_registry=ToolRegistry())
    agent.graph = _GraphStub()
    agent._ensure_session = AsyncMock()  # type: ignore[method-assign]
    agent._persist_messages = AsyncMock()  # type: ignore[method-assign]

    events = []
    async for event in agent.stream("hello", session_id="stream-session"):
        events.append(event)

    thinking_events = [e for e in events if e["type"] == EventType.THINKING]
    token_events = [e for e in events if e["type"] == EventType.TOKEN]

    assert [event["type"] for event in events] == [
        EventType.LOOP_START,
        EventType.THINKING,
        EventType.TOKEN,
        EventType.LOOP_END,
    ]
    assert thinking_events[0]["content"] == "Plan"
    assert token_events[0]["content"] == "Done"

    persisted_messages = agent._persist_messages.await_args.args[1]
    assert persisted_messages[0].content == "hello"
    assert persisted_messages[1].content == "Done"


@pytest.mark.asyncio
async def test_agent_stream_preserves_interleaved_think_order_within_chunk():
    """stream() should preserve interleaved think/text ordering within one chunk."""

    class _Chunk:
        def __init__(self, content: str) -> None:
            self.content = content

    class _GraphStub:
        async def astream_events(self, *_args, **_kwargs):
            yield {
                "event": LangGraphEventKind.CHAT_MODEL_STREAM,
                "data": {"chunk": _Chunk("<think>A</think>foo<think>B</think>bar")},
            }
            yield {
                "event": LangGraphEventKind.CHAT_MODEL_END,
                "data": {
                    "output": AIMessage(
                        content="<think>A</think>foo<think>B</think>bar",
                    )
                },
            }

    mock_llm = AsyncMock()
    mock_llm.bind_tools.return_value = mock_llm

    agent = ReactAgent(llm=mock_llm, tool_registry=ToolRegistry())
    agent.graph = _GraphStub()
    agent._ensure_session = AsyncMock()  # type: ignore[method-assign]
    agent._persist_messages = AsyncMock()  # type: ignore[method-assign]

    events = []
    async for event in agent.stream("hello", session_id="ordered-stream"):
        events.append(event)

    assert [event["type"] for event in events] == [
        EventType.LOOP_START,
        EventType.THINKING,
        EventType.TOKEN,
        EventType.THINKING,
        EventType.TOKEN,
        EventType.LOOP_END,
    ]
    assert [event["content"] for event in events[1:-1]] == ["A", "foo", "B", "bar"]

    persisted_messages = agent._persist_messages.await_args.args[1]
    assert persisted_messages[1].content == "foobar"
