"""Structured data models for the agent framework."""

from agent_core.models.events import (
    CustomEventName,
    ErrorEvent,
    EventType,
    LangGraphEventKind,
    TokenEvent,
    ToolEndEvent,
    ToolStartEvent,
    WidgetData,
    WidgetType,
)
from agent_core.models.session import (
    MessageRecord,
    MessageRole,
    SessionDetail,
    SessionRecord,
    SessionSummary,
)
from agent_core.tools.widgets import (
    AnyWidgetData,
    CalendarWidgetData,
    CourseCardsWidgetData,
    DocumentWidgetData,
    SourcesWidgetData,
    WebPreviewWidgetData,
)

__all__ = [
    "AnyWidgetData",
    "CalendarWidgetData",
    "CourseCardsWidgetData",
    "CustomEventName",
    "DocumentWidgetData",
    "ErrorEvent",
    "EventType",
    "LangGraphEventKind",
    "MessageRecord",
    "MessageRole",
    "SessionDetail",
    "SessionRecord",
    "SessionSummary",
    "SourcesWidgetData",
    "TokenEvent",
    "ToolEndEvent",
    "ToolStartEvent",
    "WebPreviewWidgetData",
    "WidgetData",
    "WidgetType",
]
