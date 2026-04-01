"""Tests for widget display tools."""

import json

import pytest
from pydantic import TypeAdapter

from agent_core.models.events import WidgetType
from agent_core.tools.registry import ToolRegistry
from agent_core.tools.widgets import (
    AnyWidgetData,
    CourseCardsWidgetData,
    DocumentWidgetData,
    SourcesWidgetData,
    WebPreviewWidgetData,
    WidgetData,
    register_widget_tools,
    show_courses,
    show_document,
    show_sources,
    show_web_preview,
)

_WIDGET_ADAPTER: TypeAdapter[AnyWidgetData] = TypeAdapter(AnyWidgetData)


def _parse_widget(raw: str) -> WidgetData:
    """Parse a tool's JSON output into a typed WidgetData instance."""
    return _WIDGET_ADAPTER.validate_json(raw)


class TestShowDocument:
    """Tests for the show_document tool."""

    def test_basic_document(self) -> None:
        result = _parse_widget(show_document("Lecture 8", "Recursion concepts..."))
        assert isinstance(result, DocumentWidgetData)
        assert result.widget_type == WidgetType.DOCUMENT
        assert result.title == "Lecture 8"
        assert result.content == "Recursion concepts..."
        assert result.doc_type == "text"

    def test_custom_doc_type(self) -> None:
        result = _parse_widget(
            show_document("Notes", "# Markdown", doc_type="markdown")
        )
        assert isinstance(result, DocumentWidgetData)
        assert result.doc_type == "markdown"


class TestShowCourses:
    """Tests for the show_courses tool."""

    def test_valid_courses(self) -> None:
        courses = json.dumps(
            [
                {"code": "CS101", "name": "Intro to CS", "credits": 3},
                {"code": "MATH202", "name": "Linear Algebra", "credits": 4},
            ]
        )
        result = _parse_widget(show_courses(courses))
        assert isinstance(result, CourseCardsWidgetData)
        assert result.widget_type == WidgetType.COURSE_CARDS
        assert len(result.courses) == 2

    def test_plain_string_fallback(self) -> None:
        result = _parse_widget(show_courses("Advanced Biology"))
        assert isinstance(result, CourseCardsWidgetData)
        assert result.courses[0]["name"] == "Advanced Biology"


class TestShowWebPreview:
    """Tests for the show_web_preview tool."""

    def test_with_title(self) -> None:
        result = _parse_widget(
            show_web_preview("https://example.edu/policy", "Housing Policy")
        )
        assert isinstance(result, WebPreviewWidgetData)
        assert result.widget_type == WidgetType.WEB_PREVIEW
        assert result.url == "https://example.edu/policy"
        assert result.title == "Housing Policy"

    def test_title_defaults_to_url(self) -> None:
        result = _parse_widget(show_web_preview("https://example.edu"))
        assert isinstance(result, WebPreviewWidgetData)
        assert result.title == "https://example.edu"

    def test_rejects_javascript_url(self) -> None:
        raw = show_web_preview("javascript:alert(1)")
        result = json.loads(raw)
        assert "error" in result

    def test_rejects_data_url(self) -> None:
        raw = show_web_preview("data:text/html,<h1>Bad</h1>")
        result = json.loads(raw)
        assert "error" in result

    def test_accepts_http_url(self) -> None:
        result = _parse_widget(show_web_preview("http://example.com"))
        assert isinstance(result, WebPreviewWidgetData)
        assert result.widget_type == WidgetType.WEB_PREVIEW


class TestShowSources:
    """Tests for the show_sources tool."""

    def test_valid_sources(self) -> None:
        sources = json.dumps(
            [
                {
                    "title": "Housing Policy 2024",
                    "content": "Section 4.2: Extended absence...",
                    "type": "official",
                }
            ]
        )
        result = _parse_widget(show_sources(sources))
        assert isinstance(result, SourcesWidgetData)
        assert result.widget_type == WidgetType.SOURCES
        assert len(result.sources) == 1

    def test_plain_string_fallback(self) -> None:
        result = _parse_widget(show_sources("Some reference text"))
        assert isinstance(result, SourcesWidgetData)
        assert result.sources[0]["content"] == "Some reference text"


class TestRegisterWidgetTools:
    """Tests for registering widget tools with a registry."""

    def test_registers_all_widget_tools(self) -> None:
        registry = ToolRegistry()
        register_widget_tools(registry)
        tools = registry.list_tools()
        tool_names = {t.name for t in tools}
        # show_calendar removed; deadline_manager uses show_deadline_dashboard
        expected = {
            "show_document",
            "show_courses",
            "show_web_preview",
            "show_sources",
        }
        assert expected == tool_names

    @pytest.mark.asyncio
    async def test_execute_show_document(self) -> None:
        registry = ToolRegistry()
        register_widget_tools(registry)
        result = _parse_widget(
            await registry.execute(
                "show_document", {"title": "Test Doc", "content": "Hello"}
            )
        )
        assert isinstance(result, DocumentWidgetData)
        assert result.widget_type == WidgetType.DOCUMENT
