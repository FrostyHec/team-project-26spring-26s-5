"""Structured event models for the agent streaming protocol.

Defines the event types and Pydantic models used for communication
between the agent engine and frontends (API, Chainlit, Vue).
"""

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


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
    WIDGET_DISPLAY = "widget_display"
    ERROR = "error"


class WidgetType(StrEnum):
    """Types of widgets that can be rendered in the frontend workspace.

    Each value corresponds to a Vue component in the right panel.
    """

    CALENDAR = "calendar"
    DOCUMENT = "document"
    WEB_PREVIEW = "web_preview"
    COURSE_CARDS = "course_cards"
    SOURCES = "sources"
    INBOX = "inbox"
    EMPTY = "empty"


class CustomEventName(StrEnum):
    """Names of custom LangGraph events dispatched by the agent engine.

    Used as the ``name`` field in ``adispatch_custom_event`` calls so
    that the streaming layer can match events without magic strings.
    """

    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    APPROVAL_REQUEST = "approval_request"


class LangGraphEventKind(StrEnum):
    """LangGraph ``astream_events`` ``event`` field values consumed by the stream loop.

    Centralises the LangGraph-internal event kind strings so they are
    not scattered as magic strings throughout the agent code.
    """

    CHAT_MODEL_STREAM = "on_chat_model_stream"
    CHAT_MODEL_END = "on_chat_model_end"
    CUSTOM_EVENT = "on_custom_event"


# ---------------------------------------------------------------------------
# Widget data models — returned (as JSON) by widget tools.
# The agent detects them via isinstance(obj, WidgetData) after Pydantic parsing,
# eliminating the need for a magic dict key.
# ---------------------------------------------------------------------------


class WidgetData(BaseModel):
    """Base class for all widget data payloads returned by widget tools.

    Subclasses are discriminated on ``widget_type`` so Pydantic can
    round-trip them automatically without any magic key.
    """

    widget_type: WidgetType


class CalendarWidgetData(WidgetData):
    """Payload for the calendar widget."""

    widget_type: Literal[WidgetType.CALENDAR] = WidgetType.CALENDAR
    events: list[dict[str, Any]] = []


class DocumentWidgetData(WidgetData):
    """Payload for the document viewer widget."""

    widget_type: Literal[WidgetType.DOCUMENT] = WidgetType.DOCUMENT
    title: str = ""
    content: str = ""
    doc_type: str = "text"


class CourseCardsWidgetData(WidgetData):
    """Payload for the course comparison widget."""

    widget_type: Literal[WidgetType.COURSE_CARDS] = WidgetType.COURSE_CARDS
    courses: list[dict[str, Any]] = []


class WebPreviewWidgetData(WidgetData):
    """Payload for the web preview widget."""

    widget_type: Literal[WidgetType.WEB_PREVIEW] = WidgetType.WEB_PREVIEW
    url: str = ""
    title: str = ""


class SourcesWidgetData(WidgetData):
    """Payload for the sources/references widget."""

    widget_type: Literal[WidgetType.SOURCES] = WidgetType.SOURCES
    sources: list[dict[str, Any]] = []


# Discriminated union — used by TypeAdapter in the agent for isinstance checks.
AnyWidgetData = Annotated[
    CalendarWidgetData
    | DocumentWidgetData
    | CourseCardsWidgetData
    | WebPreviewWidgetData
    | SourcesWidgetData,
    Field(discriminator="widget_type"),
]


class TokenEvent(BaseModel):
    """A streamed text token from the LLM.

    Attributes:
        type: Always EventType.TOKEN.
        content: The text fragment.
    """

    type: EventType = EventType.TOKEN
    content: str


class ToolStartEvent(BaseModel):
    """Emitted when a tool execution begins.

    Attributes:
        type: Always EventType.TOOL_START.
        name: The tool name.
        input: The arguments passed to the tool.
    """

    type: EventType = EventType.TOOL_START
    name: str
    input: dict[str, Any]


class ToolEndEvent(BaseModel):
    """Emitted when a tool execution completes.

    Attributes:
        type: Always EventType.TOOL_END.
        name: The tool name.
        output: The string result of the tool execution.
    """

    type: EventType = EventType.TOOL_END
    name: str
    output: str


class ThinkingEvent(BaseModel):
    """Emitted when the LLM produces reasoning text before a tool call.

    Attributes:
        type: Always EventType.THINKING.
        content: The reasoning/analysis text.
    """

    type: EventType = EventType.THINKING
    content: str


class LoopStartEvent(BaseModel):
    """Emitted at the beginning of the ReAct loop.

    Attributes:
        type: Always EventType.LOOP_START.
    """

    type: EventType = EventType.LOOP_START


class LoopEndEvent(BaseModel):
    """Emitted at the end of the ReAct loop.

    Attributes:
        type: Always EventType.LOOP_END.
    """

    type: EventType = EventType.LOOP_END


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

    type: EventType = EventType.APPROVAL_REQUEST
    tool_name: str
    tool_args: dict[str, Any]
    tool_call_id: str


class WidgetDisplayEvent(BaseModel):
    """Emitted when the agent wants to display a widget in the workspace.

    The frontend should switch the right panel to render the specified
    widget type with the provided data payload.

    Attributes:
        type: Always EventType.WIDGET_DISPLAY.
        widget_type: The kind of widget to render.
        data: Arbitrary payload for the widget component.
    """

    type: EventType = EventType.WIDGET_DISPLAY
    widget_type: WidgetType
    data: dict[str, Any] = {}

    @classmethod
    def from_widget_data(cls, widget: WidgetData) -> "WidgetDisplayEvent":
        """Construct a WidgetDisplayEvent from a typed WidgetData instance.

        Extracts ``widget_type`` from the model and collects the remaining
        fields into ``data``, so callers never need to touch raw dicts.
        """
        payload = widget.model_dump(exclude={"widget_type"})
        return cls(widget_type=widget.widget_type, data=payload)


class ErrorEvent(BaseModel):
    """Emitted when an error occurs during streaming.

    Attributes:
        type: Always EventType.ERROR.
        content: Error message text.
    """

    type: EventType = EventType.ERROR
    content: str
