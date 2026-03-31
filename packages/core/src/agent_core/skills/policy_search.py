"""Policy search skill — search and explain campus policies."""

from agent_core.models.skills import SkillDefinition, SkillType

SKILL = SkillDefinition(
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
)
