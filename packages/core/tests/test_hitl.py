"""Tests for Human-in-the-Loop agent behaviour."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage

from agent_core.engine.agent import ReactAgent
from agent_core.models.events import EventType
from agent_core.tools.calculator import register_calculator_tools
from agent_core.tools.registry import ToolRegistry
from agent_core.tools.weather import register_weather_tools


def _build_agent(
    *,
    include_weather: bool = True,
    approval_handler: object = None,
) -> tuple[ReactAgent, AsyncMock]:
    """Create a ReactAgent with a mock LLM for HITL testing.

    Args:
        include_weather: Whether to register the sensitive weather tool.
        approval_handler: Optional approval handler callback.

    Returns:
        Tuple of (agent, mock_llm).
    """
    mock_llm = AsyncMock()
    # bind_tools is synchronous, so use MagicMock to avoid coroutine
    mock_llm.bind_tools = MagicMock(return_value=mock_llm)

    registry = ToolRegistry()
    register_calculator_tools(registry)
    if include_weather:
        register_weather_tools(registry)
    # Mock tool execution to avoid real function calls
    registry.execute = AsyncMock(return_value="mocked_output")

    agent = ReactAgent(llm=mock_llm, tool_registry=registry)
    if approval_handler is not None:
        agent.approval_handler = approval_handler
    return agent, mock_llm


@pytest.mark.asyncio
async def test_safe_tool_no_approval_needed():
    """Test that safe tools execute without approval handler check."""
    agent, mock_llm = _build_agent()
    agent.tool_registry.execute = AsyncMock(return_value="5.0")

    first = AIMessage(
        content="",
        tool_calls=[{"name": "add", "args": {"a": 2, "b": 3}, "id": "c1"}],
    )
    second = AIMessage(content="The result is 5.")
    mock_llm.ainvoke.side_effect = [first, second]

    events = []
    async for event in agent.stream("add 2+3", session_id="hitl_safe"):
        events.append(event)

    # No approval_request events should appear for safe tools
    approval_events = [e for e in events if e["type"] == EventType.APPROVAL_REQUEST]
    assert len(approval_events) == 0

    # Tool should have executed normally
    tool_end = [e for e in events if e["type"] == EventType.TOOL_END]
    assert len(tool_end) == 1
    assert tool_end[0]["output"] == "5.0"


@pytest.mark.asyncio
async def test_sensitive_tool_rejected_without_handler():
    """Test sensitive tool is rejected when no approval handler is set."""
    agent, mock_llm = _build_agent(approval_handler=None)
    # Don't mock execute — it shouldn't be called for rejected tools

    first = AIMessage(
        content="",
        tool_calls=[{"name": "get_weather", "args": {"city": "Beijing"}, "id": "c2"}],
    )
    second = AIMessage(content="The tool was cancelled.")
    mock_llm.ainvoke.side_effect = [first, second]

    events = []
    async for event in agent.stream("weather Beijing", session_id="hitl_no"):
        events.append(event)

    # Should have approval request
    approval = [e for e in events if e["type"] == EventType.APPROVAL_REQUEST]
    assert len(approval) == 1
    assert approval[0]["tool_name"] == "get_weather"

    # Tool end should show cancellation
    tool_ends = [e for e in events if e["type"] == EventType.TOOL_END]
    assert len(tool_ends) == 1
    assert "cancelled" in tool_ends[0]["output"].lower()


@pytest.mark.asyncio
async def test_sensitive_tool_approved_with_handler():
    """Test sensitive tool executes when handler approves."""

    async def approve_all(name: str, args: dict, tool_id: str) -> bool:
        return True

    agent, mock_llm = _build_agent(approval_handler=approve_all)
    agent.tool_registry.execute = AsyncMock(return_value="Beijing: 22°C, Sunny")

    first = AIMessage(
        content="",
        tool_calls=[{"name": "get_weather", "args": {"city": "Beijing"}, "id": "c3"}],
    )
    second = AIMessage(content="It's 22°C and sunny in Beijing.")
    mock_llm.ainvoke.side_effect = [first, second]

    events = []
    async for event in agent.stream("weather Beijing", session_id="hitl_yes"):
        events.append(event)

    # Should still have approval request event
    approval = [e for e in events if e["type"] == EventType.APPROVAL_REQUEST]
    assert len(approval) == 1

    # Tool should have executed
    tool_end = [e for e in events if e["type"] == EventType.TOOL_END]
    assert len(tool_end) == 1
    assert "22°C" in tool_end[0]["output"]


@pytest.mark.asyncio
async def test_sensitive_tool_rejected_with_handler():
    """Test sensitive tool is cancelled when handler rejects."""

    async def reject_all(name: str, args: dict, tool_id: str) -> bool:
        return False

    agent, mock_llm = _build_agent(approval_handler=reject_all)

    first = AIMessage(
        content="",
        tool_calls=[{"name": "get_weather", "args": {"city": "Tokyo"}, "id": "c4"}],
    )
    second = AIMessage(content="The operation was cancelled.")
    mock_llm.ainvoke.side_effect = [first, second]

    events = []
    async for event in agent.stream("weather Tokyo", session_id="hitl_rej"):
        events.append(event)

    tool_end = [e for e in events if e["type"] == EventType.TOOL_END]
    assert len(tool_end) == 1
    assert "cancelled" in tool_end[0]["output"].lower()


@pytest.mark.asyncio
async def test_sync_approval_handler():
    """Test that a synchronous (non-async) handler also works."""

    def sync_approve(name: str, args: dict, tool_id: str) -> bool:
        return True

    agent, mock_llm = _build_agent(approval_handler=sync_approve)
    agent.tool_registry.execute = AsyncMock(return_value="London: 15°C, Rainy")

    first = AIMessage(
        content="",
        tool_calls=[{"name": "get_weather", "args": {"city": "London"}, "id": "c5"}],
    )
    second = AIMessage(content="It's rainy in London.")
    mock_llm.ainvoke.side_effect = [first, second]

    events = []
    async for event in agent.stream("weather London", session_id="hitl_sync"):
        events.append(event)

    tool_end = [e for e in events if e["type"] == EventType.TOOL_END]
    assert len(tool_end) == 1
    assert "15°C" in tool_end[0]["output"]


@pytest.mark.asyncio
async def test_mixed_safe_and_sensitive_tools():
    """Test mixed tool calls: safe tools run, sensitive ones need approval."""

    async def approve_all(name: str, args: dict, tool_id: str) -> bool:
        return True

    agent, mock_llm = _build_agent(approval_handler=approve_all)
    agent.tool_registry.execute = AsyncMock(
        side_effect=["5.0", "Shanghai: 28°C, Cloudy"]
    )

    first = AIMessage(
        content="",
        tool_calls=[
            {"name": "add", "args": {"a": 2, "b": 3}, "id": "c6"},
            {
                "name": "get_weather",
                "args": {"city": "Shanghai"},
                "id": "c7",
            },
        ],
    )
    second = AIMessage(content="2+3=5. Shanghai is 28°C and cloudy.")
    mock_llm.ainvoke.side_effect = [first, second]

    events = []
    async for event in agent.stream("calc and weather", session_id="hitl_mix"):
        events.append(event)

    # Only one approval (weather), not for add
    approval = [e for e in events if e["type"] == EventType.APPROVAL_REQUEST]
    assert len(approval) == 1
    assert approval[0]["tool_name"] == "get_weather"

    # Both tools should complete
    tool_ends = [e for e in events if e["type"] == EventType.TOOL_END]
    assert len(tool_ends) == 2


def test_approval_request_event_model():
    """Test ApprovalRequestEvent Pydantic model."""
    from agent_core.models.events import ApprovalRequestEvent

    event = ApprovalRequestEvent(
        tool_name="get_weather",
        tool_args={"city": "Beijing"},
        tool_call_id="call_123",
    )
    dumped = event.model_dump()
    assert dumped["type"] == EventType.APPROVAL_REQUEST
    assert dumped["tool_name"] == "get_weather"
    assert dumped["tool_args"] == {"city": "Beijing"}
    assert dumped["tool_call_id"] == "call_123"
