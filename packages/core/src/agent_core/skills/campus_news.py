"""Campus news skill — daily campus news summaries."""

from agent_core.models.skills import SkillDefinition, SkillType

SKILL = SkillDefinition(
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
)
