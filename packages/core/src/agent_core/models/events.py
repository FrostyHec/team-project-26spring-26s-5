"""Structured event models for the agent streaming protocol.

Defines the event types and Pydantic models used for communication
between the agent engine and frontends (API, Chainlit, Vue).
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class EventType(StrEnum):
    """Types of events emitted during agent streaming.

    Used consistently across backend and frontend to identify
    event payloads without relying on hardcoded strings.
    """

    TOKEN = "token"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    THINKING = "thinking"
    LOOP_START = "loop_start"
    LOOP_END = "loop_end"
    APPROVAL_REQUEST = "approval_request"
    ERROR = "error"


class TokenEvent(BaseModel):
    """A streamed text token from the LLM.

    Attributes:
        type: Always EventType.TOKEN.
        content: The text fragment.
    """

    type: str = EventType.TOKEN
    content: str


class ToolStartEvent(BaseModel):
    """Emitted when a tool execution begins.

    Attributes:
        type: Always EventType.TOOL_START.
        name: The tool name.
        input: The arguments passed to the tool.
    """

    type: str = EventType.TOOL_START
    name: str
    input: dict[str, Any]


class ToolEndEvent(BaseModel):
    """Emitted when a tool execution completes.

    Attributes:
        type: Always EventType.TOOL_END.
        name: The tool name.
        output: The string result of the tool execution.
    """

    type: str = EventType.TOOL_END
    name: str
    output: str


class ThinkingEvent(BaseModel):
    """Emitted when the LLM produces reasoning text before a tool call.

    Attributes:
        type: Always EventType.THINKING.
        content: The reasoning/analysis text.
    """

    type: str = EventType.THINKING
    content: str


class LoopStartEvent(BaseModel):
    """Emitted at the beginning of the ReAct loop.

    Attributes:
        type: Always EventType.LOOP_START.
    """

    type: str = EventType.LOOP_START


class LoopEndEvent(BaseModel):
    """Emitted at the end of the ReAct loop.

    Attributes:
        type: Always EventType.LOOP_END.
    """

    type: str = EventType.LOOP_END


class ApprovalRequestEvent(BaseModel):
    """Emitted when a sensitive tool requires user approval.

    The frontend should display a warning and ask the user
    whether to proceed with the tool execution.

    Attributes:
        type: Always EventType.APPROVAL_REQUEST.
        tool_name: Name of the sensitive tool.
        tool_args: Arguments the tool would be called with.
        tool_call_id: The tool call ID for matching approval.
    """

    type: str = EventType.APPROVAL_REQUEST
    tool_name: str
    tool_args: dict[str, Any]
    tool_call_id: str


class ErrorEvent(BaseModel):
    """Emitted when an error occurs during streaming.

    Attributes:
        type: Always EventType.ERROR.
        content: The error message.
    """

    type: str = EventType.ERROR
    content: str
