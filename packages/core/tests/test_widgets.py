"""Tests for widget display tools."""

import json

import pytest

from agent_core.models.events import WidgetType
from agent_core.tools.registry import ToolRegistry
from agent_core.tools.widgets import (
    register_widget_tools,
    show_calendar,
    show_courses,
    show_document,
    show_sources,
    show_web_preview,
)


class TestShowCalendar:
    """Tests for the show_calendar tool."""

    def test_valid_json_events(self) -> None:
        events = json.dumps(
            [{"title": "Math HW", "date": "2026-03-30", "priority": "high"}]
        )
        result = json.loads(show_calendar(events))
        assert result["__widget__"] == WidgetType.CALENDAR
        assert len(result["events"]) == 1
        assert result["events"][0]["title"] == "Math HW"

    def test_plain_string_fallback(self) -> None:
        result = json.loads(show_calendar("Math homework due Friday"))
        assert result["__widget__"] == WidgetType.CALENDAR
        assert len(result["events"]) == 1
        assert result["events"][0]["title"] == "Math homework due Friday"

    def test_multiple_events(self) -> None:
        events = json.dumps(
            [
                {"title": "Exam 1", "date": "2026-04-01", "priority": "high"},
                {"title": "Exam 2", "date": "2026-04-02", "priority": "medium"},
            ]
        )
        result = json.loads(show_calendar(events))
        assert len(result["events"]) == 2


class TestShowDocument:
    """Tests for the show_document tool."""

    def test_basic_document(self) -> None:
        result = json.loads(show_document("Lecture 8", "Recursion concepts..."))
        assert result["__widget__"] == WidgetType.DOCUMENT
        assert result["title"] == "Lecture 8"
        assert result["content"] == "Recursion concepts..."
        assert result["doc_type"] == "text"

    def test_custom_doc_type(self) -> None:
        result = json.loads(show_document("Notes", "# Markdown", doc_type="markdown"))
        assert result["doc_type"] == "markdown"


class TestShowCourses:
    """Tests for the show_courses tool."""

    def test_valid_courses(self) -> None:
        courses = json.dumps(
            [
                {"code": "CS101", "name": "Intro to CS", "credits": 3},
                {"code": "MATH202", "name": "Linear Algebra", "credits": 4},
            ]
        )
        result = json.loads(show_courses(courses))
        assert result["__widget__"] == WidgetType.COURSE_CARDS
        assert len(result["courses"]) == 2

    def test_plain_string_fallback(self) -> None:
        result = json.loads(show_courses("Advanced Biology"))
        assert result["__widget__"] == WidgetType.COURSE_CARDS
        assert result["courses"][0]["name"] == "Advanced Biology"


class TestShowWebPreview:
    """Tests for the show_web_preview tool."""

    def test_with_title(self) -> None:
        result = json.loads(
            show_web_preview("https://example.edu/policy", "Housing Policy")
        )
        assert result["__widget__"] == WidgetType.WEB_PREVIEW
        assert result["url"] == "https://example.edu/policy"
        assert result["title"] == "Housing Policy"

    def test_title_defaults_to_url(self) -> None:
        result = json.loads(show_web_preview("https://example.edu"))
        assert result["title"] == "https://example.edu"


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
        result = json.loads(show_sources(sources))
        assert result["__widget__"] == WidgetType.SOURCES
        assert len(result["sources"]) == 1

    def test_plain_string_fallback(self) -> None:
        result = json.loads(show_sources("Some reference text"))
        assert result["__widget__"] == WidgetType.SOURCES
        assert result["sources"][0]["content"] == "Some reference text"


class TestRegisterWidgetTools:
    """Tests for registering widget tools with a registry."""

    def test_registers_all_widget_tools(self) -> None:
        registry = ToolRegistry()
        register_widget_tools(registry)
        tools = registry.list_tools()
        tool_names = {t.name for t in tools}
        expected = {
            "show_calendar",
            "show_document",
            "show_courses",
            "show_web_preview",
            "show_sources",
        }
        assert expected == tool_names

    @pytest.mark.asyncio
    async def test_execute_show_calendar(self) -> None:
        registry = ToolRegistry()
        register_widget_tools(registry)
        events = json.dumps(
            [{"title": "Test", "date": "2026-04-01", "priority": "low"}]
        )
        result = await registry.execute("show_calendar", {"events": events})
        parsed = json.loads(result)
        assert parsed["__widget__"] == WidgetType.CALENDAR

    @pytest.mark.asyncio
    async def test_execute_show_document(self) -> None:
        registry = ToolRegistry()
        register_widget_tools(registry)
        result = await registry.execute(
            "show_document", {"title": "Test Doc", "content": "Hello"}
        )
        parsed = json.loads(result)
        assert parsed["__widget__"] == WidgetType.DOCUMENT
