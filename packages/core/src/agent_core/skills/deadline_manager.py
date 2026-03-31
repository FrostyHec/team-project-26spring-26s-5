"""Deadline manager skill — track and manage academic deadlines."""

from agent_core.models.skills import SkillDefinition, SkillType

SKILL = SkillDefinition(
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
)
