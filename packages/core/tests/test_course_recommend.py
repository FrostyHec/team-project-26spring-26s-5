"""Tests for course recommendation tools."""

import json

import pytest

from agent_core.tools.course_recommend import (
    _completed_codes,
    _infer_language,
    _score_course,
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
            interests="machine learning",
            major="",
            completed_courses="",
            memory_context=(
                "Course preference profile: major computer science, "
                "prefers English courses, completed CS109."
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


class TestCompletedCodesFromMemory:
    """Codes embedded in memory must only count as completed in completion contexts."""

    def test_explicit_param_codes_always_completed(self) -> None:
        """Codes in the explicit completed_courses param are always treated as done."""
        assert _completed_codes("CS109, MATH201", "") == {"CS109", "MATH201"}

    def test_recommended_codes_in_memory_not_treated_as_completed(self) -> None:
        """Codes that memory describes as recommended/target must NOT be marked done."""
        memory = (
            "### 人工智能核心课程推荐\n"  # nosemgrep
            "1. **COE102 人工智能与应用**\n"  # nosemgrep
            "2. **COE201 人工智能大模型**\n"  # nosemgrep
            "3. **COE202 人工智能数学基础**\n"  # nosemgrep
        )
        assert _completed_codes("", memory) == set()

    def test_completed_section_marks_codes_as_done(self) -> None:
        """Codes under an explicit completed-section header count as done."""
        memory = (
            "## 已修课程\n"  # nosemgrep
            "- CS109\n"
            "- MATH201\n"
            "\n"
            "## 推荐课程\n"  # nosemgrep
            "- COE102\n"
            "- COE201\n"
        )
        assert _completed_codes("", memory) == {"CS109", "MATH201"}

    def test_inline_completion_phrase_marks_code(self) -> None:
        """Inline completion phrases should still mark the code as done."""
        memory = "学生已修 CS109，现在想学 COE102。"  # nosemgrep
        # Mixed sentence with recommend kw too — be conservative and not mark COE102.
        completed = _completed_codes("", memory)
        assert "COE102" not in completed

    def test_english_completed_keyword(self) -> None:
        """English completion keywords should also work."""
        memory = "Student has completed CS109 and is interested in COE102."
        completed = _completed_codes("", memory)
        assert "CS109" in completed
        assert "COE102" not in completed


class TestInferLanguagePreference:
    """Language preference must only be inferred from explicit preference phrases."""

    def test_descriptive_bilingual_in_memory_not_inferred(self) -> None:
        """Descriptive bilingual mentions should not infer a preference."""
        memory = (
            "### 人工智能核心课程推荐\n"  # nosemgrep
            "1. **COE102 人工智能与应用**（双语）\n"  # nosemgrep
            "2. **COE201 人工智能大模型**（双语）\n"  # nosemgrep
        )
        assert _infer_language(memory) == ""

    def test_explicit_bilingual_preference_is_inferred(self) -> None:
        """Explicit bilingual preference phrases must be recognized."""
        memory = "学生可接受双语或全英文授课。"  # nosemgrep
        assert _infer_language(memory) == "bilingual"

    def test_english_preference_phrase_is_inferred(self) -> None:
        """English preference phrases should be picked up too."""
        memory = "Student prefers English courses."
        assert _infer_language(memory) == "english"

    def test_no_preference_phrase_returns_empty(self) -> None:
        """If no preference phrase exists, no language is inferred."""
        memory = "Third-year computer science student interested in AI."
        assert _infer_language(memory) == ""


class TestScoreCourseIgnoresMemoryTokens:
    """Memory text must not pollute interest term matching with stray tokens."""

    def _ai_unrelated_course(self) -> dict:
        # A course whose class_name has nothing to do with AI/ML.
        return {
            "id": "2025-2026-2-FIN203-001",
            "system_id": "ABC123",
            "class_id": "2025-2026-2-FIN203-001",
            "course_code": "FIN203",
            "class_name": "财务会计-01班-英文",  # nosemgrep
            "department": "商学院",  # nosemgrep
            "instructor": "张教授",  # nosemgrep
            "schedule": "1-15周,星期一第3-4节",  # nosemgrep
            "course_type": "专业核心课",  # nosemgrep
            "course_language": "英文",  # nosemgrep
            "credits": 3.0,
            "total_hours": 48,
            "ug_quota": 50,
            "pg_quota": 0,
        }

    def test_memory_timestamp_tokens_do_not_match_interests(self) -> None:
        """Numeric tokens from memory frontmatter must not count as interests.

        Before the fix, a memory string containing 'last_updated:
        2026-05-25T14:22:38+00:00' caused 'expand_terms' to emit tokens like
        '00', '22', '38'; those then matched class_id substrings such as
        '2025-2026-2-FIN203-001', giving unrelated courses bogus interest hits.
        """
        course = self._ai_unrelated_course()
        memory_text = (
            "title: course preferences\n"
            "last_updated: '2026-05-25T14:22:38+00:00'\n"
            "用户对人工智能感兴趣。\n"  # nosemgrep
        )
        score, reasons = _score_course(
            course,
            interests="人工智能",  # nosemgrep
            major="",
            completed_courses="",
            preferred_language="",
            avoid_schedule="",
            memory_text=memory_text,
        )
        interest_reasons = [r for r in reasons if r.startswith("matches interest")]
        assert interest_reasons == [], (
            f"FIN203 should have no interest matches, but got: {interest_reasons}"
        )


class TestRecommendCoursesRespectsMemorySemantics:
    """End-to-end check that target courses listed in memory aren't excluded."""

    @pytest.mark.asyncio
    async def test_recommended_courses_in_memory_not_excluded(self) -> None:
        """Codes appearing in a memory's recommend section must remain recommendable.

        Before the fix, those codes were extracted by '_completed_codes' and
        eliminated with score=-100; they should now score normally.
        """
        memory_context = (
            "### 人工智能核心课程推荐\n"  # nosemgrep
            "- COE102 人工智能与应用\n"  # nosemgrep
            "- COE201 人工智能大模型\n"  # nosemgrep
            "- COE202 人工智能数学基础\n"  # nosemgrep
        )
        result = await recommend_courses(
            interests="人工智能",  # nosemgrep
            memory_context=memory_context,
            include_memory=False,
            limit=200,
        )
        payload = json.loads(result)
        codes = {item["code"] for item in payload["recommendations"]}
        # If the -100 bug returned, none of these would appear at all.
        assert codes & {"COE102", "COE201", "COE202"}
