"""Course assistant skill — help with course materials and exam prep."""

from agent_core.models.skills import SkillDefinition, SkillType
from agent_core.prompts_loader import get_course_assistant_prompt

SKILL = SkillDefinition(
    id=SkillType.COURSE_ASSISTANT,
    name="Course Assistant",
    description="Help with course materials, exam prep, and study notes.",
    system_prompt=get_course_assistant_prompt(),
    icon="BookOpen",
    color="text-blue-500",
)
