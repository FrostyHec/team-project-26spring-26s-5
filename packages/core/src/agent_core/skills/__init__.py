"""Skill registry — manages preset prompt configurations.

Provides a centralized registry of built-in skills that shape agent behavior.
Each skill contains a specialized system prompt for a specific use-case.

Skills are auto-discovered from sibling modules: any module in
``agent_core.skills`` that exposes a module-level ``SKILL`` constant
of type :class:`SkillDefinition` is picked up automatically.
"""

import importlib
import pkgutil
from collections.abc import Callable

from agent_core.models.skills import SkillDefinition, SkillType
from agent_core.prompts_loader import (
    get_course_assistant_prompt,
)

# ---------------------------------------------------------------------------
# Prompt loaders — map skill IDs to their language-aware prompt loaders
# ---------------------------------------------------------------------------

# Language-aware prompt loaders for skills that support multi-language
_PROMPT_LOADERS: dict[str, Callable[[str], str]] = {
    SkillType.COURSE_ASSISTANT: get_course_assistant_prompt,
}


def _get_language_aware_prompt(skill_id: str, language: str) -> str | None:
    """Get the system prompt for a skill using its language-aware loader.

    Args:
        skill_id: The skill identifier.
        language: Language code (e.g., "en" or "zh").

    Returns:
        The system prompt string, or None if no language-aware loader exists.
    """
    loader = _PROMPT_LOADERS.get(skill_id)
    if loader:
        return loader(language)
    return None


# ---------------------------------------------------------------------------
# Auto-discovery
# ---------------------------------------------------------------------------

_SKILLS: dict[str, SkillDefinition] = {}


def _auto_discover_skills() -> None:
    """Scan all modules under ``agent_core.skills`` for ``SKILL`` constants."""
    package = importlib.import_module("agent_core.skills")
    for _importer, modname, _ispkg in pkgutil.iter_modules(package.__path__):
        if modname.startswith("_"):
            continue
        module = importlib.import_module(f"agent_core.skills.{modname}")
        skill = getattr(module, "SKILL", None)
        if isinstance(skill, SkillDefinition):
            _SKILLS[skill.id] = skill


# Run discovery once at import time.
_auto_discover_skills()


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


def get_system_prompt_for_skill(skill_id: str | None, language: str = "en") -> str:
    """Get the system prompt for a skill, falling back to general.

    For skills with language-aware loaders (e.g., course_assistant),
    the prompt is loaded dynamically using the provided language.

    Args:
        skill_id: Optional skill identifier.
        language: Language code for multi-language skills (default "en").

    Returns:
        The system prompt string.
    """
    if skill_id:
        # Try language-aware loader first
        lang_prompt = _get_language_aware_prompt(skill_id, language)
        if lang_prompt is not None:
            return lang_prompt
        # Fall back to stored prompt
        skill = get_skill(skill_id)
        if skill:
            return skill.system_prompt
    general = _SKILLS.get(SkillType.GENERAL)
    return general.system_prompt if general else ""
