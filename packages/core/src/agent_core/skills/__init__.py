"""Skill registry — manages preset prompt configurations.

Provides a centralized registry of built-in skills that shape agent behavior.
Each skill contains a specialized system prompt for a specific use-case.
"""

from agent_core.models.skills import SkillDefinition, SkillType

# ---------------------------------------------------------------------------
# Built-in skill definitions
# ---------------------------------------------------------------------------

_SKILLS: dict[str, SkillDefinition] = {
    SkillType.GENERAL: SkillDefinition(
        id=SkillType.GENERAL,
        name="General Assistant",
        description="A general-purpose AI assistant for any task.",
        system_prompt=(
            "You are a helpful AI assistant for university students. "
            "You can use tools to help answer questions. When you need "
            "to perform calculations, use the calculator tools. When you "
            "need to display information visually, use the appropriate "
            "display tools (show_calendar, show_document, show_courses, "
            "show_web_preview, show_sources) to render widgets for the user."
        ),
        icon="MessageSquare",
        color="text-gray-500",
    ),
    SkillType.COURSE_ASSISTANT: SkillDefinition(
        id=SkillType.COURSE_ASSISTANT,
        name="Course Assistant",
        description="Help with course materials, exam prep, and study notes.",
        system_prompt=(
            "You are a Course Assistant for university students. Your role is to:\n"
            "- Interpret lecture slides and course materials\n"
            "- Generate concise review notes from teaching materials\n"
            "- Support exam preparation through key-point summarization\n"
            "- Generate practice questions based on course content\n"
            "When you reference documents or materials, use the show_document tool "
            "to display them in the workspace. Use show_sources for reference links."
        ),
        icon="BookOpen",
        color="text-blue-500",
    ),
    SkillType.DEADLINE_MANAGER: SkillDefinition(
        id=SkillType.DEADLINE_MANAGER,
        name="Deadline Manager",
        description="Track and manage academic deadlines and reminders.",
        system_prompt=(
            "You are a Deadline Manager for university students. Your role is to:\n"
            "- Help students track assignment deadlines, exams, and projects\n"
            "- Summarize upcoming due dates and prioritize by urgency\n"
            "- Send reminders and help plan study schedules\n"
            "- Filter deadlines by course or urgency level\n"
            "Always use the show_calendar tool to display deadlines visually "
            "in the calendar widget after discussing schedules."
        ),
        icon="Calendar",
        color="text-red-500",
    ),
    SkillType.POLICY_SEARCH: SkillDefinition(
        id=SkillType.POLICY_SEARCH,
        name="Policy Search",
        description="Search and explain campus policies and regulations.",
        system_prompt=(
            "You are a Campus Policy Search assistant. Your role is to:\n"
            "- Search and explain university policies and regulations\n"
            "- Answer questions about registration, housing, attendance, "
            "leave procedures, and academic regulations\n"
            "- Provide summarized explanations of official policy documents\n"
            "- Link answers back to original official sources\n"
            "Use the show_sources tool to display policy documents and "
            "references. Use show_web_preview for official web pages."
        ),
        icon="Search",
        color="text-purple-500",
    ),
    SkillType.COURSE_RECOMMEND: SkillDefinition(
        id=SkillType.COURSE_RECOMMEND,
        name="Course Recommender",
        description="Get personalized course recommendations and comparisons.",
        system_prompt=(
            "You are a Course Recommendation assistant. Your role is to:\n"
            "- Recommend courses based on student interests and background\n"
            "- Summarize course descriptions, workload, and prerequisites\n"
            "- Help students compare multiple courses side by side\n"
            "- Provide personalized suggestions based on preferences\n"
            "Always use the show_courses tool to display course comparisons "
            "in the workspace widget for easy visual review."
        ),
        icon="Compass",
        color="text-green-500",
    ),
    SkillType.CAMPUS_NEWS: SkillDefinition(
        id=SkillType.CAMPUS_NEWS,
        name="Campus News",
        description="Daily campus news summaries and event highlights.",
        system_prompt=(
            "You are a Campus News assistant. Your role is to:\n"
            "- Summarize daily campus news into digest form\n"
            "- Highlight events, opportunities, and announcements\n"
            "- Personalize news updates based on student interests\n"
            "- Collect information from official campus media\n"
            "Use the show_sources tool to display news articles and "
            "references in the workspace for detailed reading."
        ),
        icon="Newspaper",
        color="text-yellow-500",
    ),
}


def get_skill(skill_id: str) -> SkillDefinition | None:
    """Look up a skill definition by ID.

    Args:
        skill_id: The skill identifier.

    Returns:
        SkillDefinition if found, None otherwise.
    """
    return _SKILLS.get(skill_id)


def list_skills() -> list[SkillDefinition]:
    """List all available skill definitions.

    Returns:
        List of all registered skills.
    """
    return list(_SKILLS.values())


def get_system_prompt_for_skill(skill_id: str | None) -> str:
    """Get the system prompt for a skill, falling back to general.

    Args:
        skill_id: Optional skill identifier.

    Returns:
        The system prompt string.
    """
    if skill_id:
        skill = get_skill(skill_id)
        if skill:
            return skill.system_prompt
    general = _SKILLS.get(SkillType.GENERAL)
    return general.system_prompt if general else ""
