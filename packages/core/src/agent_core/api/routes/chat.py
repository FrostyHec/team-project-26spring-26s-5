"""Chat routes — synchronous, streaming, and approval endpoints."""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent_core.api.approval import resolve_pending
from agent_core.api.dependencies import (
    get_agent,
    get_agent_for_skill,
    get_config,
    get_conversation_tree_service,
    get_store,
)
from agent_core.api.routes.utils import get_language
from agent_core.config import AgentConfig, load_llm_settings
from agent_core.engine.agent import ReactAgent
from agent_core.logging_utils import get_logger
from agent_core.models.events import EventType, FailedEvent, ProviderSwitchEvent
from agent_core.models.session import FallbackMode, MessageStatus
from agent_core.persistence.session_store import SessionStore
from agent_core.services.conversation_tree_service import ConversationTreeService

logger = get_logger("api.chat")

router = APIRouter()


async def _run_first_round_title_generation(
    tree_service: ConversationTreeService,
    session_id: str,
    assistant_node_id: str,
    llm: Any,
) -> None:
    """Run the first-round title generation task in the background."""
    await tree_service.maybe_generate_first_round_title(
        session_id,
        assistant_node_id,
        llm,
    )


def _schedule_first_round_title_generation(
    tree_service: ConversationTreeService,
    session_id: str,
    assistant_node_id: str,
    llm: Any,
) -> None:
    """Fire-and-forget title generation after the first round completes."""
    asyncio.create_task(
        _run_first_round_title_generation(
            tree_service,
            session_id,
            assistant_node_id,
            llm,
        )
    )


def _append_trace_step(
    trace_steps: list[dict[str, Any]],
    event: dict[str, Any],
) -> None:
    """Normalize stream events into persisted trace-step state."""
    event_type = event.get("type")
    if event_type == EventType.LOOP_START:
        trace_steps.append({"type": EventType.LOOP_START})
    elif event_type == EventType.THINKING:
        content = event.get("content", "")
        if trace_steps and trace_steps[-1].get("type") == EventType.THINKING:
            trace_steps[-1]["content"] = (
                f"{trace_steps[-1].get('content', '')}{content}"
            )
            return
        trace_steps.append(
            {
                "type": EventType.THINKING,
                "content": content,
            }
        )
    elif event_type == EventType.TOOL_START:
        trace_steps.append(
            {
                "type": EventType.TOOL_START,
                "name": event.get("name", "unknown"),
                "input": event.get("input", {}),
            }
        )
    elif event_type == EventType.TOOL_END:
        trace_steps.append(
            {
                "type": EventType.TOOL_END,
                "name": event.get("name", "unknown"),
                "output": event.get("output", ""),
            }
        )
    elif event_type == EventType.LOOP_END:
        trace_steps.append({"type": EventType.LOOP_END})
    elif event_type == EventType.PROVIDER_SWITCH:
        trace_steps.append(
            {
                "type": EventType.PROVIDER_SWITCH,
                "fromProviderId": event.get("from_provider_id"),
                "toProviderId": event.get("to_provider_id"),
                "content": event.get("reason", ""),
            }
        )
    elif event_type == EventType.APPROVAL_REQUEST:
        trace_steps.append(
            {
                "type": EventType.APPROVAL_REQUEST,
                "name": event.get("tool_name", "unknown"),
                "input": event.get("tool_args", {}),
            }
        )
    elif event_type == EventType.WIDGET_DISPLAY:
        trace_steps.append(
            {
                "type": EventType.WIDGET_DISPLAY,
                "widgetType": event.get("widget_type"),
                "widgetData": event.get("data", {}),
            }
        )


def _update_tool_calls(
    tool_calls: list[dict[str, Any]],
    event: dict[str, Any],
) -> None:
    """Update persisted tool-call state from a stream event."""
    event_type = event.get("type")
    if event_type == EventType.TOOL_START:
        tool_calls.append(
            {
                "name": event.get("name", "unknown"),
                "input": event.get("input", {}),
                "status": "running",
            }
        )
        return

    if event_type != EventType.TOOL_END:
        return

    event_name = event.get("name")
    for tool_call in reversed(tool_calls):
        if tool_call.get("name") == event_name and tool_call.get("status") == "running":
            tool_call["output"] = event.get("output", "")
            tool_call["status"] = "completed"
            return

    tool_calls.append(
        {
            "name": event_name or "unknown",
            "input": {},
            "output": event.get("output", ""),
            "status": "completed",
        }
    )


class ChatRequest(BaseModel):
    """Request body for chat endpoints.

    Attributes:
        message: The user's message to the agent.
        session_id: Optional session ID for conversation persistence.
        skill: Optional skill ID for preset prompt selection.
        provider_id: Optional provider ID from YAML-backed LLM settings.
    """

    message: str
    session_id: str | None = None
    skill: str | None = None
    provider_id: str | None = None


class ChatResponse(BaseModel):
    """Response body from the synchronous chat endpoint.

    Attributes:
        response: The agent's text response.
    """

    response: str


def _resolve_target_agent(
    request: ChatRequest,
    language: str,
    agent: ReactAgent,
) -> ReactAgent:
    """Resolve the agent instance for the chat request."""
    if not request.skill and not request.provider_id:
        return agent
    try:
        return get_agent_for_skill(request.skill, language, request.provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _resolve_provider_attempts(
    request: ChatRequest,
    store: SessionStore,
    config: AgentConfig,
) -> list[str | None]:
    """Resolve the ordered provider attempts for this request."""
    if not request.session_id:
        return [request.provider_id]

    session = await store.get_session(request.session_id)
    if session is None or session.fallback_mode != FallbackMode.AUTO:
        return [request.provider_id]

    llm_settings = load_llm_settings(config.llm_settings_path)
    enabled_provider_ids = [
        provider.id for provider in llm_settings.providers if provider.enabled
    ]
    if not enabled_provider_ids:
        return [request.provider_id]

    primary_provider_id = request.provider_id or enabled_provider_ids[0]
    if primary_provider_id not in enabled_provider_ids:
        return [primary_provider_id]

    return [
        primary_provider_id,
        *[pid for pid in enabled_provider_ids if pid != primary_provider_id],
    ]


def _request_for_provider(request: ChatRequest, provider_id: str | None) -> ChatRequest:
    """Clone the chat request with a concrete provider attempt."""
    return request.model_copy(update={"provider_id": provider_id})


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    language: str = Depends(get_language),
    agent: ReactAgent = Depends(get_agent),
    store: SessionStore = Depends(get_store),
    config: AgentConfig = Depends(get_config),
) -> ChatResponse:
    """Send a message and get a complete response.

    Args:
        request: The chat request payload.
        language: Language code from X-Language header.
        agent: Injected ReactAgent instance.

    Returns:
        The agent's final response.

    Raises:
        HTTPException: 502 if the LLM call fails.
    """
    provider_attempts = await _resolve_provider_attempts(request, store, config)
    last_error: Exception | None = None

    for provider_id in provider_attempts:
        attempted_request = _request_for_provider(request, provider_id)
        try:
            target = _resolve_target_agent(attempted_request, language, agent)
            response = await target.chat(
                attempted_request.message,
                session_id=attempted_request.session_id,
            )
            return ChatResponse(response=response)
        except HTTPException:
            raise
        except Exception as exc:
            last_error = exc
            if provider_id != provider_attempts[-1]:
                logger.warning(
                    "Chat request failed for provider %s, trying next provider",
                    provider_id,
                )
                continue
            logger.exception("Chat request failed")

    raise HTTPException(status_code=502, detail=str(last_error)) from last_error


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    language: str = Depends(get_language),
    agent: ReactAgent = Depends(get_agent),
    store: SessionStore = Depends(get_store),
    config: AgentConfig = Depends(get_config),
    tree_service: ConversationTreeService = Depends(get_conversation_tree_service),
) -> StreamingResponse:
    """Stream agent execution steps as Server-Sent Events.

    Args:
        request: The chat request payload.
        language: Language code from X-Language header.
        agent: Injected ReactAgent instance.

    Returns:
        SSE stream of agent events.
    """
    provider_attempts = await _resolve_provider_attempts(request, store, config)

    if not request.session_id:

        async def event_generator() -> AsyncGenerator[str, None]:
            for provider_id in provider_attempts:
                attempted_request = _request_for_provider(request, provider_id)
                emitted_non_loop_event = False
                try:
                    target = _resolve_target_agent(attempted_request, language, agent)
                    async for event in target.stream(
                        attempted_request.message,
                        session_id=attempted_request.session_id,
                    ):
                        if event.get("type") != "loop_start":
                            emitted_non_loop_event = True
                        yield f"data: {json.dumps(event)}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                except HTTPException as exc:
                    logger.exception("Stream request rejected")
                    failed = FailedEvent(content=str(exc.detail))
                    yield f"data: {json.dumps(failed.model_dump())}\n\n"
                    return
                except Exception as exc:
                    if (
                        provider_id != provider_attempts[-1]
                        and not emitted_non_loop_event
                    ):
                        switch_event = ProviderSwitchEvent(
                            from_provider_id=provider_id,
                            to_provider_id=provider_attempts[
                                provider_attempts.index(provider_id) + 1
                            ],
                            reason=str(exc),
                        )
                        yield f"data: {json.dumps(switch_event.model_dump())}\n\n"
                        logger.warning(
                            "Stream request failed for provider %s before output, "
                            "trying next provider",
                            provider_id,
                        )
                        continue
                    logger.exception("Stream request failed")
                    failed = FailedEvent(content=str(exc))
                    yield f"data: {json.dumps(failed.model_dump())}\n\n"
                    return

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
        )

    continue_placeholder = request.message == ""
    if continue_placeholder:
        prepared_placeholder_stream = await tree_service.prepare_placeholder_stream(
            request.session_id,
        )
        if prepared_placeholder_stream is None:
            raise HTTPException(
                status_code=400,
                detail="No streaming placeholder is available for continuation.",
            )
        history_messages, placeholder = prepared_placeholder_stream
    else:
        (
            history_messages,
            _user_node,
            placeholder,
        ) = await tree_service.prepare_stream_turn(
            request.session_id,
            request.message,
        )

    async def event_generator() -> AsyncGenerator[str, None]:
        assistant_chunks: list[str] = []
        trace_steps: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        for provider_id in provider_attempts:
            attempted_request = _request_for_provider(request, provider_id)
            emitted_non_loop_event = False
            try:
                target = _resolve_target_agent(attempted_request, language, agent)
                stream = (
                    target.stream_from_messages(
                        history_messages,
                        session_id=attempted_request.session_id,
                        persist_messages=False,
                    )
                    if continue_placeholder
                    else target.stream_with_history(
                        attempted_request.message,
                        history_messages,
                        session_id=attempted_request.session_id,
                        persist_messages=False,
                    )
                )
                async for event in stream:
                    if event.get("type") != EventType.LOOP_START:
                        emitted_non_loop_event = True
                    if event.get("type") == EventType.TOKEN and isinstance(
                        event.get("content"), str
                    ):
                        assistant_chunks.append(str(event["content"]))
                    _append_trace_step(trace_steps, event)
                    _update_tool_calls(tool_calls, event)
                    yield f"data: {json.dumps(event)}\n\n"
                await tree_service.finalize_stream_turn(
                    request.session_id,
                    placeholder.id,
                    "".join(assistant_chunks),
                    status=MessageStatus.COMPLETED,
                    tool_calls=tool_calls,
                    trace_steps=trace_steps,
                )
                _schedule_first_round_title_generation(
                    tree_service,
                    request.session_id,
                    placeholder.id,
                    target.llm,
                )
                yield "data: [DONE]\n\n"
                return
            except HTTPException as exc:
                logger.exception("Stream request rejected")
                await tree_service.finalize_stream_turn(
                    request.session_id,
                    placeholder.id,
                    "".join(assistant_chunks) or str(exc.detail),
                    status=MessageStatus.FAILED,
                    tool_calls=tool_calls,
                    trace_steps=trace_steps,
                )
                failed = FailedEvent(content=str(exc.detail))
                yield f"data: {json.dumps(failed.model_dump())}\n\n"
                return
            except Exception as exc:
                if provider_id != provider_attempts[-1] and not emitted_non_loop_event:
                    switch_event = ProviderSwitchEvent(
                        from_provider_id=provider_id,
                        to_provider_id=provider_attempts[
                            provider_attempts.index(provider_id) + 1
                        ],
                        reason=str(exc),
                    )
                    yield f"data: {json.dumps(switch_event.model_dump())}\n\n"
                    logger.warning(
                        "Stream request failed for provider %s before output, "
                        "trying next provider",
                        provider_id,
                    )
                    continue
                logger.exception("Stream request failed")
                await tree_service.finalize_stream_turn(
                    request.session_id,
                    placeholder.id,
                    "".join(assistant_chunks) or str(exc),
                    status=MessageStatus.FAILED,
                    tool_calls=tool_calls,
                    trace_steps=trace_steps,
                )
                failed = FailedEvent(content=str(exc))
                yield f"data: {json.dumps(failed.model_dump())}\n\n"
                return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


class ApprovalRequest(BaseModel):
    """Request body for the tool approval endpoint.

    Attributes:
        tool_call_id: The unique ID of the tool invocation.
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
