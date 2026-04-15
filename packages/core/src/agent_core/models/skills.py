"""Skill definitions — preset prompt configurations for agent personas.

Skills provide curated system prompts that shape the agent's behavior
for specific student use-cases (e.g., course assistant, deadline manager).
"""

from enum import StrEnum

from pydantic import BaseModel


class SkillType(StrEnum):
    """Identifiers for built-in agent skills/personas."""

    GENERAL = "general"
    COURSE_ASSISTANT = "course_assistant"
    DEADLINE_MANAGER = "deadline_manager"
    POLICY_SEARCH = "policy_search"
    COURSE_RECOMMEND = "course_recommend"
    CAMPUS_NEWS = "campus_news"
    EMAIL_ASSISTANT = "email_assistant"


class SkillDefinition(BaseModel):
    """A preset skill configuration for the agent.

    Attributes:
        id: Unique skill identifier matching SkillType.
        name: Human-readable display name.
        description: Brief description shown to users.
        system_prompt: The system prompt injected when this skill is active.
        icon: Icon identifier for UI rendering.
        color: CSS color class for UI theming.
    """

    id: str
    name: str
    description: str
    system_prompt: str
    icon: str
    color: str
