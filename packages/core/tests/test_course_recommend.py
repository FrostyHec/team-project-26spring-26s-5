"""Tests for course recommendation tools."""

import json

import pytest

from agent_core.tools.course_recommend import (
    compare_courses,
    get_course_catalog,
    get_course_detail,
    recommend_courses,
    register_course_recommend_tools,
)
from agent_core.tools.registry import ToolRegistry


class TestCourseRecommendTools:
    """Test suite for catalog-backed course recommendation tools."""

    def setup_method(self) -> None:
        """Register course recommendation tools for each test."""
        self.registry = ToolRegistry()
        register_course_recommend_tools(self.registry)

    def test_all_tools_registered(self) -> None:
        """Test that all course recommendation tools are registered."""
        tools = self.registry.list_tools()
        names = {t.name for t in tools}
        assert names == {
            "get_course_catalog",
            "recommend_courses",
            "get_course_detail",
            "compare_courses",
        }

    def test_get_course_catalog(self) -> None:
        """Test fetching filtered courses from the packaged catalog."""
        result = get_course_catalog(department="Computer Science", limit=10)
        courses = json.loads(result)

        assert len(courses) >= 3
        assert any(course["code"].startswith("CS") for course in courses)
        assert all("schedule" in course for course in courses)

    @pytest.mark.asyncio
    async def test_recommend_courses_for_ai_interest(self) -> None:
        """Test recommending courses using interest and profile matching."""
        result = await recommend_courses(
            interests="AI machine learning",
            major="Computer Science",
            year="junior",
            completed_courses="CS109, MATH201",
            preferred_language="English",
            include_memory=False,
            limit=3,
        )
        payload = json.loads(result)

        assert payload["count"] >= 1
        assert payload["recommendations"][0]["code"] == "CS405"
        assert payload["recommendations"][0]["score"] > 0
        assert payload["recommendations"][0]["reasons"]

    @pytest.mark.asyncio
    async def test_recommend_courses_penalizes_missing_prerequisites(self) -> None:
        """Test recommendations skip courses already completed by the student."""
        result = await recommend_courses(
            interests="machine learning",
            major="Computer Science",
            year="junior",
            completed_courses="CS405",
            include_memory=False,
            limit=5,
        )
        payload = json.loads(result)

        assert all(item["code"] != "CS405" for item in payload["recommendations"])

    @pytest.mark.asyncio
    async def test_recommend_courses_exposes_memory_context(self) -> None:
        """Test explicit memory context affects and is visible in recommendations."""
        result = await recommend_courses(
            interests="",
            major="",
            completed_courses="",
            memory_context=(
                "Course preference profile: interested in machine learning, "
                "major computer science, prefers English courses, completed CS109."
            ),
            include_memory=False,
            limit=3,
        )
        payload = json.loads(result)

        assert payload["memory_used"]["explicit_context_provided"] is True
        assert payload["profile"]["major"] == "computer science"
        assert payload["profile"]["preferred_language"] == "english"
        assert payload["recommendations"][0]["code"] == "CS405"

    def test_get_course_detail(self) -> None:
        """Test fetching full detail for one course."""
        result = get_course_detail(course_id="CS405")
        course = json.loads(result)

        assert course["code"] == "CS405"
        assert "description" in course
        assert course["credits"] == 3.0

    def test_get_course_detail_missing(self) -> None:
        """Test missing course lookup returns an error object."""
        result = get_course_detail(course_id="MISSING101")
        payload = json.loads(result)

        assert "error" in payload

    def test_compare_courses(self) -> None:
        """Test side-by-side course comparison."""
        result = compare_courses(course_ids_json='["CS405", "CS310", "NOPE101"]')
        payload = json.loads(result)

        assert [course["code"] for course in payload["courses"]] == ["CS405", "CS310"]
        assert payload["missing"] == ["NOPE101"]
