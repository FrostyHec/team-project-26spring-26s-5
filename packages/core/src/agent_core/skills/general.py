"""General assistant skill — default catch-all persona."""

from agent_core.models.skills import SkillDefinition, SkillType

SKILL = SkillDefinition(
    id=SkillType.GENERAL,
    name="General Assistant",
    description="A general-purpose AI assistant for any task.",
    system_prompt=(
        "You are a helpful AI assistant for university students. "
        "You can use tools to help answer questions. When you need "
        "to perform calculations, use the calculator tools. When you "
        "need to display information visually, use the appropriate "
        "display tools (show_courses, show_sources) to render widgets for the user."
    ),
    icon="MessageSquare",
    color="text-gray-500",
)
