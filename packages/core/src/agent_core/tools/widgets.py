"""Widget display tools — tools that trigger frontend widget rendering.

These tools are invoked by the agent when it needs to visually present
structured data in the frontend workspace panel. Each tool returns a
JSON payload that the streaming layer converts into a WidgetDisplayEvent.
"""

import json
from typing import Any

from agent_core.models.events import WidgetType
from agent_core.tools.registry import ToolRegistry


def show_calendar(events: str) -> str:
    """Display a calendar widget with upcoming events/deadlines.

    Args:
        events: JSON string of calendar events. Each event should have
            'title', 'date', 'priority' (high/medium/low), and optional
            'course' fields.

    Returns:
        Confirmation message with widget display instruction.
    """
    try:
        parsed = json.loads(events)
    except (json.JSONDecodeError, TypeError):
        parsed = [{"title": events, "date": "TBD", "priority": "medium"}]

    return json.dumps(
        {
            "__widget__": WidgetType.CALENDAR,
            "events": parsed if isinstance(parsed, list) else [parsed],
        }
    )


def show_document(title: str, content: str, doc_type: str = "text") -> str:
    """Display a document viewer widget with the given content.

    Args:
        title: Document title to display in the header.
        content: The document text content or description.
        doc_type: Type of document (text, pdf, markdown).

    Returns:
        Confirmation message with widget display instruction.
    """
    return json.dumps(
        {
            "__widget__": WidgetType.DOCUMENT,
            "title": title,
            "content": content,
            "doc_type": doc_type,
        }
    )


def show_courses(courses: str) -> str:
    """Display a course comparison widget with course cards.

    Args:
        courses: JSON string of course data. Each course should have
            'code', 'name', 'credits', 'workload', 'rating', and
            optional 'prerequisites' fields.

    Returns:
        Confirmation message with widget display instruction.
    """
    try:
        parsed = json.loads(courses)
    except (json.JSONDecodeError, TypeError):
        parsed = [{"code": "N/A", "name": courses, "credits": 0}]

    return json.dumps(
        {
            "__widget__": WidgetType.COURSE_CARDS,
            "courses": parsed if isinstance(parsed, list) else [parsed],
        }
    )


def show_web_preview(url: str, title: str = "") -> str:
    """Display a web preview widget for the given URL.

    Args:
        url: The URL to preview.
        title: Optional title for the preview header.

    Returns:
        Confirmation message with widget display instruction.
    """
    return json.dumps(
        {
            "__widget__": WidgetType.WEB_PREVIEW,
            "url": url,
            "title": title or url,
        }
    )


def show_sources(sources: str) -> str:
    """Display a sources/references widget with highlighted excerpts.

    Args:
        sources: JSON string of source references. Each source should
            have 'title', 'content' (excerpt), 'type' (official/article),
            and optional 'url' fields.

    Returns:
        Confirmation message with widget display instruction.
    """
    try:
        parsed = json.loads(sources)
    except (json.JSONDecodeError, TypeError):
        parsed = [{"title": "Reference", "content": sources, "type": "article"}]

    return json.dumps(
        {
            "__widget__": WidgetType.SOURCES,
            "sources": parsed if isinstance(parsed, list) else [parsed],
        }
    )


def register_widget_tools(registry: ToolRegistry) -> None:
    """Register all widget display tools with the given registry.

    Args:
        registry: The tool registry to register with.
    """
    _tools: list[tuple[Any, str]] = [
        (
            show_calendar,
            "Display a calendar widget showing upcoming deadlines and events. "
            "Pass a JSON array of events with title, date, priority, course fields. "
            "Call this after discussing deadlines or schedules.",
        ),
        (
            show_document,
            "Display a document viewer widget. Use this to show lecture notes, "
            "study materials, or any text content in the workspace panel.",
        ),
        (
            show_courses,
            "Display a course comparison widget with course cards. "
            "Pass a JSON array of courses with code, name, credits, "
            "workload, rating fields. "
            "Call this when comparing or recommending courses.",
        ),
        (
            show_web_preview,
            "Display a web page preview widget. Use this to show official "
            "university pages, policy documents, or external resources.",
        ),
        (
            show_sources,
            "Display a sources/references widget with highlighted excerpts. "
            "Use this to show policy documents, academic references, or news articles "
            "with key passages highlighted.",
        ),
    ]

    for func, description in _tools:
        registry.add_tool(func=func, description=description)
