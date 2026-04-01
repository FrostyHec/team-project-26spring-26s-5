"""Deadline REST routes — direct CRUD access to stored deadlines.

Provides endpoints for the frontend dashboard to list and delete
deadlines without going through the chat/agent flow.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_core.logging_utils import get_logger
from agent_core.models.deadline import DeadlineRecord

logger = get_logger("api.deadlines")

router = APIRouter(prefix="/deadlines", tags=["deadlines"])

_VALID_PRIORITIES = {"high", "medium", "low"}


class DeadlineListResponse(BaseModel):
    """Response body for the list-deadlines endpoint."""

    deadlines: list[DeadlineRecord]


class DeadlineDeleteResponse(BaseModel):
    """Response body for the delete-deadline endpoint."""

    status: str
    id: str


async def _get_deadline_store():
    """Lazy import to get the module-level store from the tools module."""
    from agent_core.tools.deadline import _get_store

    return await _get_store()


@router.get("", response_model=DeadlineListResponse)
async def list_deadlines(
    course: str | None = None,
    priority: str | None = None,
) -> DeadlineListResponse:
    """List stored deadlines with optional filters.

    Args:
        course: Filter by course (case-insensitive).
        priority: Filter by priority level (case-insensitive; high/medium/low).

    Returns:
        List of matching deadline records.

    Raises:
        HTTPException: 422 if priority is provided but not a valid value.
    """
    normalized_priority: str | None = None
    if priority is not None:
        normalized_priority = priority.strip().lower()
        if normalized_priority not in _VALID_PRIORITIES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid priority '{priority}'. Must be one of: high, medium, low."
                ),
            )
    store = await _get_deadline_store()
    records = await store.list_all(course=course, priority=normalized_priority)
    return DeadlineListResponse(deadlines=records)


@router.delete("/{deadline_id}", response_model=DeadlineDeleteResponse)
async def delete_deadline(deadline_id: str) -> DeadlineDeleteResponse:
    """Delete a deadline by ID.

    Args:
        deadline_id: The UUID of the deadline to remove.

    Returns:
        Success confirmation.

    Raises:
        HTTPException: 404 if the deadline does not exist.
    """
    store = await _get_deadline_store()
    deleted = await store.delete(deadline_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Deadline not found")
    return DeadlineDeleteResponse(status="deleted", id=deadline_id)
