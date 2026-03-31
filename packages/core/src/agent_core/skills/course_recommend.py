"""Course recommender skill — personalized course recommendations."""

from agent_core.models.skills import SkillDefinition, SkillType

SKILL = SkillDefinition(
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
)
