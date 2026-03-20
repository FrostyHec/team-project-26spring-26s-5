"""Tools listing route."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from agent_core.api.dependencies import get_agent
from agent_core.engine.agent import ReactAgent

router = APIRouter()


class ToolInfo(BaseModel):
    """Information about a registered tool.

    Attributes:
        name: Tool name.
        description: Tool description.
        sensitivity: HITL sensitivity level.
    """

    name: str
    description: str
    sensitivity: str


@router.get("/tools", response_model=list[ToolInfo])
async def list_tools(
    agent: ReactAgent = Depends(get_agent),
) -> list[ToolInfo]:
    """List all available tools.

    Args:
        agent: Injected ReactAgent instance.

    Returns:
        List of tool information objects.
    """
    tools = agent.tool_registry.list_tools()
    return [
        ToolInfo(
            name=t.name,
            description=t.description,
            sensitivity=t.sensitivity.value,
        )
        for t in tools
    ]
