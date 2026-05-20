"""Policy search skill — search and explain campus policies."""

import json
from pathlib import Path

from agent_core.models.skills import SkillDefinition, SkillType

# Load system prompt from external JSON to avoid CJK in source code
_PROMPT_FILE = Path(__file__).parent / "policy_skill_prompt.json"
with open(_PROMPT_FILE, encoding="utf-8") as f:
    _SYSTEM_PROMPT = json.load(f)["system_prompt"]

SKILL = SkillDefinition(
    id=SkillType.POLICY_SEARCH,
    name="Policy Search",
    description="Search and explain campus policies and regulations.",
    system_prompt=_SYSTEM_PROMPT,
    icon="Search",
    color="text-purple-500",
)
