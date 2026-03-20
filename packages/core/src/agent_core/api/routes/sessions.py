"""Session management routes — CRUD for chat sessions."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agent_core.api.dependencies import get_store
from agent_core.models.session import SessionDetail, SessionRecord, SessionSummary
from agent_core.persistence.session_store import SessionStore

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    """Request body for creating a new session.

    Attributes:
        title: Optional session title.
    """

    title: str = ""


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
    store: SessionStore = Depends(get_store),
) -> SessionDetail:
    """Get a session with its full message history.

    Args:
        session_id: The session UUID.
        store: Injected SessionStore.

    Returns:
        SessionDetail with session info and messages.

    Raises:
        HTTPException: 404 if session not found.
    """
    detail = await store.get_session_detail(session_id)
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
