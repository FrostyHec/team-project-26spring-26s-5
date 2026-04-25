"""Session management routes — CRUD for chat sessions."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agent_core.api.dependencies import get_conversation_tree_service, get_store
from agent_core.models.session import (
    FallbackMode,
    MessageStatus,
    SessionDetail,
    SessionRecord,
    SessionSummary,
)
from agent_core.persistence.session_store import SessionStore
from agent_core.services.conversation_tree_service import ConversationTreeService

router = APIRouter(prefix="/sessions", tags=["sessions"])

type TerminalPartialResponseStatus = Literal[
    MessageStatus.INTERRUPTED,
    MessageStatus.FAILED,
]


class CreateSessionRequest(BaseModel):
    """Request body for creating a new session.

    Attributes:
        title: Optional session title.
    """

    title: str = ""


class UpdateSessionPreferencesRequest(BaseModel):
    """Request body for updating session-level preferences."""

    selected_provider_id: str | None = None
    fallback_mode: FallbackMode | None = None


class UpdateSessionRequest(BaseModel):
    """Request body for updating session fields."""

    title: str


class InterruptSessionRequest(BaseModel):
    """Request body for persisting interrupted partial output."""

    user_message: str
    assistant_content: str = ""


class PersistPartialResponseRequest(BaseModel):
    """Request body for persisting partial assistant output with status."""

    user_message: str
    assistant_content: str = ""
    assistant_status: TerminalPartialResponseStatus


class SelectVersionRequest(BaseModel):
    """Request body for switching the selected version in a group."""

    node_id: str


class EditNodeRequest(BaseModel):
    """Request body for editing a user or assistant node."""

    content: str


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    store: SessionStore = Depends(get_store),
) -> list[SessionSummary]:
    """List all active chat sessions.

    Args:
        store: Injected SessionStore.

    Returns:
        List of session summaries.
    """
    return await store.list_sessions()


@router.post("", response_model=SessionRecord, status_code=201)
async def create_session(
    request: CreateSessionRequest,
    store: SessionStore = Depends(get_store),
) -> SessionRecord:
    """Create a new chat session.

    Args:
        request: Optional title for the session.
        store: Injected SessionStore.

    Returns:
        The created SessionRecord.
    """
    return await store.create_session(title=request.title)


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    tree_service: ConversationTreeService = Depends(get_conversation_tree_service),
) -> SessionDetail:
    """Get a session with its full message history.

    Args:
        session_id: The session UUID.
        tree_service: Injected ConversationTreeService.

    Returns:
        SessionDetail with session info and messages.

    Raises:
        HTTPException: 404 if session not found.
    """
    detail = await tree_service.build_session_detail(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    store: SessionStore = Depends(get_store),
) -> dict[str, bool]:
    """Soft-delete a session.

    Args:
        session_id: The session UUID.
        store: Injected SessionStore.

    Returns:
        Success indicator.

    Raises:
        HTTPException: 404 if session not found.
    """
    deleted = await store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@router.patch("/{session_id}/preferences", response_model=SessionRecord)
async def update_session_preferences(
    session_id: str,
    request: UpdateSessionPreferencesRequest,
    store: SessionStore = Depends(get_store),
) -> SessionRecord:
    """Update session-level provider selection and fallback mode."""
    updated = await store.update_session_preferences(
        session_id,
        request.model_dump(exclude_unset=True),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return updated


@router.patch("/{session_id}", response_model=SessionRecord)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    store: SessionStore = Depends(get_store),
) -> SessionRecord:
    """Update mutable session fields such as the title."""
    updated = await store.update_session_title(session_id, request.title)
    if updated is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return updated


@router.post("/{session_id}/interrupt", response_model=SessionDetail)
async def interrupt_session(
    session_id: str,
    request: InterruptSessionRequest,
    store: SessionStore = Depends(get_store),
    tree_service: ConversationTreeService = Depends(get_conversation_tree_service),
) -> SessionDetail:
    """Persist an interrupted user/assistant exchange."""
    detail = await tree_service.persist_stream_terminal_state(
        session_id,
        request.assistant_content,
        MessageStatus.INTERRUPTED,
    )
    if detail is None:
        detail = await store.persist_interrupted_messages(
            session_id,
            request.user_message,
            request.assistant_content,
        )
    if detail is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail


@router.post("/{session_id}/partial-response", response_model=SessionDetail)
async def persist_partial_response(
    session_id: str,
    request: PersistPartialResponseRequest,
    store: SessionStore = Depends(get_store),
    tree_service: ConversationTreeService = Depends(get_conversation_tree_service),
) -> SessionDetail:
    """Persist partial assistant output with an explicit terminal status."""
    detail = await tree_service.persist_stream_terminal_state(
        session_id,
        request.assistant_content,
        request.assistant_status,
    )
    if detail is None:
        detail = await store.persist_partial_response(
            session_id,
            request.user_message,
            request.assistant_content,
            request.assistant_status,
        )
    if detail is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail


@router.patch(
    "/{session_id}/version-groups/{version_group_id}/select",
    response_model=SessionDetail,
)
async def select_version(
    session_id: str,
    version_group_id: str,
    request: SelectVersionRequest,
    tree_service: ConversationTreeService = Depends(get_conversation_tree_service),
) -> SessionDetail:
    """Switch the selected node in a version group."""
    try:
        detail = await tree_service.select_version(
            session_id,
            version_group_id,
            request.node_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if detail is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail


@router.post(
    "/{session_id}/nodes/{assistant_node_id}/retry",
    response_model=SessionDetail,
)
async def retry_assistant(
    session_id: str,
    assistant_node_id: str,
    tree_service: ConversationTreeService = Depends(get_conversation_tree_service),
) -> SessionDetail:
    """Create a new assistant retry version and make it current."""
    try:
        detail = await tree_service.retry_assistant(session_id, assistant_node_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if detail is None:
        raise HTTPException(status_code=404, detail="Session or node not found")
    return detail


@router.patch(
    "/{session_id}/nodes/{node_id}/edit",
    response_model=SessionDetail,
)
async def edit_node(
    session_id: str,
    node_id: str,
    request: EditNodeRequest,
    tree_service: ConversationTreeService = Depends(get_conversation_tree_service),
) -> SessionDetail:
    """Create a new edited version for a user or assistant node."""
    try:
        detail = await tree_service.edit_node(
            session_id,
            node_id,
            request.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if detail is None:
        raise HTTPException(status_code=404, detail="Session or node not found")
    return detail
