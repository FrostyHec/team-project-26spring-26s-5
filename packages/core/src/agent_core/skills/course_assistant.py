"""Course assistant skill — help with course materials and exam prep."""

from agent_core.models.skills import SkillDefinition, SkillType

SKILL = SkillDefinition(
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
)
