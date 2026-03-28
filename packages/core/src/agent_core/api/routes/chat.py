"""Chat routes — synchronous, streaming, and approval endpoints."""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent_core.api.approval import resolve_pending
from agent_core.api.dependencies import get_agent
from agent_core.engine.agent import ReactAgent
from agent_core.logging_utils import get_logger
from agent_core.models.events import ErrorEvent

logger = get_logger("api.chat")

router = APIRouter()


class ChatRequest(BaseModel):
    """Request body for chat endpoints.

    Attributes:
        message: The user's message to the agent.
        session_id: Optional session ID for conversation persistence.
        skill: Optional skill ID for preset prompt selection.
    """

    message: str
    session_id: str | None = None
    skill: str | None = None


class ChatResponse(BaseModel):
    """Response body from the synchronous chat endpoint.

    Attributes:
        response: The agent's text response.
    """

    response: str


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    agent: ReactAgent = Depends(get_agent),
) -> ChatResponse:
    """Send a message and get a complete response.

    Args:
        request: The chat request payload.
        agent: Injected ReactAgent instance.

    Returns:
        The agent's final response.

    Raises:
        HTTPException: 502 if the LLM call fails.
    """
    try:
        response = await agent.chat(request.message, session_id=request.session_id)
    except Exception as e:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=502, detail=str(e)) from e
    return ChatResponse(response=response)


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    agent: ReactAgent = Depends(get_agent),
) -> StreamingResponse:
    """Stream agent execution steps as Server-Sent Events.

    Args:
        request: The chat request payload.
        agent: Injected ReactAgent instance.

    Returns:
        SSE stream of agent events.
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for event in agent.stream(
                request.message, session_id=request.session_id
            ):
                yield f"data: {json.dumps(event)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("Stream request failed")
            error = ErrorEvent(content=str(e))
            yield f"data: {json.dumps(error.model_dump())}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


class ApprovalRequest(BaseModel):
    """Request body for the tool approval endpoint.

    Attributes:
        tool_call_id: The unique ID of the tool invocation.
        approved: Whether the user approves execution.
    """

    tool_call_id: str
    approved: bool


class ApprovalResponse(BaseModel):
    """Response body for the tool approval endpoint.

    Attributes:
        ok: Whether the approval was successfully processed.
    """

    ok: bool


@router.post("/chat/approve", response_model=ApprovalResponse)
async def approve_tool(request: ApprovalRequest) -> ApprovalResponse:
    """Approve or reject a pending sensitive tool call.

    Args:
        request: The approval decision payload.

    Returns:
        Success indicator.

    Raises:
        HTTPException: 404 if no matching pending approval is found.
    """
    resolved = resolve_pending(request.tool_call_id, request.approved)
    if not resolved:
        raise HTTPException(
            status_code=404,
            detail=f"No pending approval for tool_call_id: {request.tool_call_id}",
        )
    return ApprovalResponse(ok=True)
