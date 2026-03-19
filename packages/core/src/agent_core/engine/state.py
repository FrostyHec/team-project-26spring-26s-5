"""Agent state definition for the ReAct loop."""

from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """State maintained throughout the agent's ReAct loop.

    Attributes:
        messages: Conversation history with LLM, tools, and user.
        pending_tool_call: Tool call awaiting human approval (HITL).
    """

    messages: Annotated[list, add_messages]
    pending_tool_call: dict | None
