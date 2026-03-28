"""Skills routes — list available agent skills/personas."""

from fastapi import APIRouter

from agent_core.models.skills import SkillDefinition
from agent_core.skills import list_skills

router = APIRouter(tags=["skills"])


@router.get("/skills", response_model=list[SkillDefinition])
async def get_skills() -> list[SkillDefinition]:
    """List all available agent skills.

    Returns:
        List of skill definitions with id, name, description, etc.
    """
    return list_skills()
