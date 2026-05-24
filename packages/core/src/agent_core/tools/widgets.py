"""Widget display tools — tools that trigger frontend widget rendering.

These tools are invoked by the agent when it needs to visually present
structured data in the frontend workspace panel. Each tool returns a
JSON payload that the streaming layer converts into a WidgetDisplayEvent.

Concrete WidgetData subclasses are defined here alongside the tools that
produce them, keeping the payload schema and the tool logic co-located.
"""

import json
from typing import Annotated, Any, Literal

from pydantic import Field

from agent_core.models.events import WidgetData, WidgetType
from agent_core.tools.registry import ToolRegistry

# ---------------------------------------------------------------------------
# Typed widget payload models
# ---------------------------------------------------------------------------


class CalendarWidgetData(WidgetData):
    """Payload for the calendar widget."""

    widget_type: Literal[WidgetType.CALENDAR] = WidgetType.CALENDAR
    events: list[dict[str, Any]] = []


# class DocumentWidgetData(WidgetData):
#     """Payload for the document viewer widget."""
#
#     widget_type: Literal[WidgetType.DOCUMENT] = WidgetType.DOCUMENT
#     title: str = ""
#     content: str = ""
#     doc_type: str = "text"


class CourseCardsWidgetData(WidgetData):
    """Payload for the course comparison widget."""

    widget_type: Literal[WidgetType.COURSE_CARDS] = WidgetType.COURSE_CARDS
    courses: list[dict[str, Any]] = []


# class WebPreviewWidgetData(WidgetData):
#     """Payload for the web preview widget."""
#
#     widget_type: Literal[WidgetType.WEB_PREVIEW] = WidgetType.WEB_PREVIEW
#     url: str = ""
#     title: str = ""


# class SourcesWidgetData(WidgetData):
#     """Payload for the sources/references widget."""
#
#     widget_type: Literal[WidgetType.SOURCES] = WidgetType.SOURCES
#     sources: list[dict[str, Any]] = []


class PolicySearchWidgetData(WidgetData):
    """Payload for the campus policy search widget."""

    widget_type: Literal[WidgetType.POLICY_SEARCH] = WidgetType.POLICY_SEARCH
    query: str = ""
    results: list[dict[str, Any]] = []
    totalCount: int = 0


# Discriminated union used by TypeAdapter in the agent for isinstance checks.
AnyWidgetData = Annotated[
    CalendarWidgetData | CourseCardsWidgetData | PolicySearchWidgetData,
    Field(discriminator="widget_type"),
]

# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


# def show_document(title: str, content: str, doc_type: str = "text") -> str:
#     """Display a document viewer widget with the given content.
#
#     Args:
#         title: Document title to display in the header.
#         content: The document text content or description.
#         doc_type: Type of document (text, pdf, markdown).
#
#     Returns:
#         Confirmation message with widget display instruction.
#     """
#     return DocumentWidgetData(
#         title=title, content=content, doc_type=doc_type
#     ).model_dump_json()


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

    courses_list = parsed if isinstance(parsed, list) else [parsed]
    return CourseCardsWidgetData(courses=courses_list).model_dump_json()


# _ALLOWED_URL_SCHEMES = ("http://", "https://")
#
#
# def show_web_preview(url: str, title: str = "") -> str:
#     """Display a web preview widget for the given URL.
#
#     Args:
#         url: The URL to preview (must be http or https).
#         title: Optional title for the preview header.
#
#     Returns:
#         Confirmation message with widget display instruction.
#     """
#     if not url.lower().startswith(_ALLOWED_URL_SCHEMES):
#         return json.dumps({"error": "Only http/https URLs are allowed."})
#
#     return WebPreviewWidgetData(url=url, title=title or url).model_dump_json()


# def show_sources(sources: str) -> str:
#     """Display a sources/references widget with highlighted excerpts.
#
#     Args:
#         sources: JSON string of source references. Each source should
#             have 'title', 'content' (excerpt), 'type' (official/article),
#             and optional 'url' fields.
#
#     Returns:
#         Confirmation message with widget display instruction.
#     """
#     try:
#         parsed = json.loads(sources)
#     except (json.JSONDecodeError, TypeError):
#         parsed = [{"title": "Reference", "content": sources, "type": "article"}]
#
#     sources_list = parsed if isinstance(parsed, list) else [parsed]
#     return SourcesWidgetData(sources=sources_list).model_dump_json()


def register_widget_tools(registry: ToolRegistry) -> None:
    """Register all widget display tools with the given registry.

    Args:
        registry: The tool registry to register with.
    """
    _tools: list[tuple[Any, str]] = [
        # (
        #     show_document,
        #     "Display a document viewer widget. Use this to show lecture notes, "
        #     "study materials, or any text content in the workspace panel.",
        # ),
        (
            show_courses,
            "Display a course comparison widget with course cards. "
            "Pass a JSON array of courses with code, name, credits, "
            "workload, rating fields. "
            "Call this when comparing or recommending courses.",
        ),
        # (
        #     show_web_preview,
        #     "Display a web page preview widget. Use this to show official "
        #     "university pages, policy documents, or external resources.",
        # ),
        # (
        #     show_sources,
        #     "Display a sources/references widget with highlighted excerpts. "
        #     "Use this to show policy documents or academic references.",
        # ),
    ]

    for func, description in _tools:
        registry.add_tool(func=func, description=description)
