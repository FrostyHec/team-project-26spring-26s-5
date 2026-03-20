"""Chat routes — synchronous and streaming endpoints."""

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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
    """

    message: str
    session_id: str | None = None


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
