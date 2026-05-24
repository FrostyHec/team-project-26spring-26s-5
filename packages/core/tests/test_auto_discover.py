"""Tests for auto-discovery of tools and skills."""

from agent_core.models.skills import SkillType
from agent_core.skills import list_skills
from agent_core.tools import auto_discover_and_register
from agent_core.tools.registry import ToolRegistry


class TestToolAutoDiscover:
    """Verify that auto_discover_and_register finds all tool modules."""

    def test_discovers_calculator_tools(self) -> None:
        registry = ToolRegistry()
        auto_discover_and_register(registry)
        tool_names = {t.name for t in registry.list_tools()}
        assert "add" in tool_names
        assert "multiply" in tool_names

    def test_discovers_widget_tools(self) -> None:
        registry = ToolRegistry()
        auto_discover_and_register(registry)
        tool_names = {t.name for t in registry.list_tools()}
        expected_widgets = {
            "show_courses",
        }
        assert expected_widgets.issubset(tool_names)

    def test_discovers_weather_tools(self) -> None:
        registry = ToolRegistry()
        auto_discover_and_register(registry)
        tool_names = {t.name for t in registry.list_tools()}
        assert "get_weather" in tool_names

    def test_discovers_deadline_tools(self) -> None:
        registry = ToolRegistry()
        auto_discover_and_register(registry)
        tool_names = {t.name for t in registry.list_tools()}
        expected_deadline = {
            "get_announcements",
            "query_email",
            "get_exams",
            "save_deadlines",
            "list_deadlines",
            "add_deadline",
            "show_deadline_dashboard",
        }
        assert expected_deadline.issubset(tool_names)

    def test_discovers_news_tools(self) -> None:
        registry = ToolRegistry()
        auto_discover_and_register(registry)
        tool_names = {t.name for t in registry.list_tools()}
        expected_news = {
            "get_latest_news",
            "get_daily_news",
            "search_news",
            "get_news_detail",
            "create_news_digest",
        }
        assert expected_news.issubset(tool_names)

    def test_discovers_course_recommend_tools(self) -> None:
        registry = ToolRegistry()
        auto_discover_and_register(registry)
        tool_names = {t.name for t in registry.list_tools()}
        expected_course_recommend = {
            "get_course_catalog",
            "recommend_courses",
            "get_course_detail",
            "compare_courses",
        }
        assert expected_course_recommend.issubset(tool_names)

    def test_no_duplicate_registration(self) -> None:
        registry = ToolRegistry()
        auto_discover_and_register(registry)
        tool_names = [t.name for t in registry.list_tools()]
        assert len(tool_names) == len(set(tool_names))


class TestSkillAutoDiscover:
    """Verify that skill auto-discovery picks up all skill modules."""

    def test_discovers_all_skills(self) -> None:
        skills = list_skills()
        ids = {s.id for s in skills}
        for skill_type in SkillType:
            assert skill_type.value in ids, f"Missing skill: {skill_type.value}"

    def test_skill_count_matches_enum(self) -> None:
        skills = list_skills()
        assert len(skills) == len(SkillType)
