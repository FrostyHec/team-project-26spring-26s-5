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


class ErrorEvent(BaseModel):
    """Emitted when an error occurs during streaming.

    Attributes:
        type: Always EventType.ERROR.
        content: The error message.
    """

    type: str = EventType.ERROR
    content: str
