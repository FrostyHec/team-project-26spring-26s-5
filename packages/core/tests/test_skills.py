"""Tests for the skills system."""

from agent_core.models.skills import SkillDefinition, SkillType
from agent_core.skills import get_skill, get_system_prompt_for_skill, list_skills


class TestSkillType:
    """Tests for the SkillType enum."""

    def test_all_skill_types_are_strings(self) -> None:
        for skill in SkillType:
            assert isinstance(skill.value, str)

    def test_expected_skills_exist(self) -> None:
        expected = {
            "general",
            "course_assistant",
            "deadline_manager",
            "policy_search",
            "course_recommend",
            "campus_news",
        }
        actual = {s.value for s in SkillType}
        assert expected == actual


class TestSkillDefinition:
    """Tests for the SkillDefinition model."""

    def test_valid_definition(self) -> None:
        skill = SkillDefinition(
            id="test",
            name="Test Skill",
            description="A test skill.",
            system_prompt="You are a test assistant.",
            icon="TestIcon",
            color="text-red-500",
        )
        assert skill.id == "test"
        assert skill.name == "Test Skill"

    def test_serialization(self) -> None:
        skill = SkillDefinition(
            id="test",
            name="Test",
            description="Desc",
            system_prompt="Prompt",
            icon="Icon",
            color="color",
        )
        data = skill.model_dump()
        assert data["id"] == "test"
        assert "system_prompt" in data


class TestSkillRegistry:
    """Tests for the skill lookup functions."""

    def test_list_skills_returns_all(self) -> None:
        skills = list_skills()
        assert len(skills) == len(SkillType)
        ids = {s.id for s in skills}
        for skill_type in SkillType:
            assert skill_type.value in ids

    def test_get_skill_existing(self) -> None:
        skill = get_skill(SkillType.COURSE_ASSISTANT)
        assert skill is not None
        assert skill.name == "Course Assistant"
        assert "Course Assistant" in skill.system_prompt

    def test_get_skill_nonexistent(self) -> None:
        assert get_skill("nonexistent_skill") is None

    def test_get_system_prompt_for_valid_skill(self) -> None:
        prompt = get_system_prompt_for_skill(SkillType.DEADLINE_MANAGER)
        assert "Deadline Manager" in prompt

    def test_get_system_prompt_fallback_to_general(self) -> None:
        prompt = get_system_prompt_for_skill(None)
        assert len(prompt) > 0
        # Should be the general prompt
        general = get_skill(SkillType.GENERAL)
        assert general is not None
        assert prompt == general.system_prompt

    def test_get_system_prompt_unknown_falls_back(self) -> None:
        prompt = get_system_prompt_for_skill("unknown_skill")
        general = get_skill(SkillType.GENERAL)
        assert general is not None
        assert prompt == general.system_prompt

    def test_all_skills_have_nonempty_prompts(self) -> None:
        for skill in list_skills():
            assert len(skill.system_prompt) > 20, f"{skill.id} has empty prompt"

    def test_all_skills_have_valid_fields(self) -> None:
        for skill in list_skills():
            assert skill.icon, f"{skill.id} missing icon"
            assert skill.color, f"{skill.id} missing color"
            assert skill.description, f"{skill.id} missing description"
