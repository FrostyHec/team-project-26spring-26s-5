"""Deadline REST routes — thin controller layer over :class:`DeadlineService`.

Provides endpoints for the frontend dashboard to list, delete, toggle
completion, create, update, and preview/commit sync operations on deadlines.

All business logic (business-rule validation, date sanitisation, record
construction) lives in :mod:`agent_core.services.deadline_service`.
This module is responsible only for HTTP semantics: status codes, request
parsing, and response shaping.

Format validation (datetime format, enum values) is handled automatically by
Pydantic — invalid inputs produce HTTP 422 before reaching the service.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_core.logging_utils import get_logger
from agent_core.models.deadline import (
    DateType,
    DeadlinePriority,
    DeadlineRecord,
    DeadlineRecordCreate,
)
from agent_core.persistence.deadline_provider import get_deadline_store
from agent_core.services.deadline_service import (
    DeadlineNotFoundError,
    DeadlineService,
    DeadlineValidationError,
)

logger = get_logger("api.deadlines")

router = APIRouter(prefix="/deadlines", tags=["deadlines"])


# ------------------------------------------------------------------
# Response / Request models
# ------------------------------------------------------------------


class DeadlineListResponse(BaseModel):
    """Response body for the list-deadlines endpoint."""

    deadlines: list[DeadlineRecord]


class DeadlineDeleteResponse(BaseModel):
    """Response body for the delete-deadline endpoint."""

    status: str
    id: str


class ToggleCompleteRequest(BaseModel):
    """Request body to set the completed flag on a deadline."""

    completed: bool


class ToggleCompleteResponse(BaseModel):
    """Response body after toggling a deadline's completed status."""

    id: str
    completed: bool


class UpdateDeadlineRequest(BaseModel):
    """Request body for partial-update of a deadline's fields.

    All fields are optional; only provided (non-``None``) fields are
    updated.  ``priority`` and ``date_type`` use their respective enums
    so FastAPI returns a standard 422 for invalid values automatically.
    ``due_date`` and ``start_date`` use ``datetime`` so Pydantic validates
    the format automatically (422 for non-ISO-8601 values).
    """

    title: str | None = None
    course: str | None = None
    due_date: datetime | None = None
    priority: DeadlinePriority | None = None
    description: str | None = None
    date_type: DateType | None = None
    start_date: datetime | None = None
    completed: bool | None = None


class CreateDeadlineRequest(BaseModel):
    """Request body for creating a new deadline.

    ``title`` is required; all other fields have sensible defaults.
    ``priority`` and ``date_type`` use their respective enums so FastAPI
    returns a standard 422 for invalid values automatically.
    ``due_date`` and ``start_date`` use ``datetime | None`` so Pydantic
    validates the format automatically.
    """

    title: str
    course: str = ""
    due_date: datetime | None = None
    priority: DeadlinePriority = DeadlinePriority.MEDIUM
    description: str = ""
    date_type: DateType = DateType.MOMENT_DAY
    start_date: datetime | None = None


class DuplicateEntry(BaseModel):
    """A candidate that duplicates an existing deadline."""

    candidate: DeadlineRecord
    existing_id: str


class SyncPreviewRequest(BaseModel):
    """Request body for sync-preview: list of candidate deadlines."""

    deadlines: list[DeadlineRecordCreate]


class SyncPreviewResponse(BaseModel):
    """Response body for sync-preview: new vs duplicate breakdown."""

    new_tasks: list[DeadlineRecord]
    duplicate_tasks: list[DuplicateEntry]


class SyncCommitRequest(BaseModel):
    """Request body for sync-commit: tasks the user confirmed to add."""

    tasks: list[DeadlineRecordCreate]


class SyncCommitResponse(BaseModel):
    """Response body after committing sync results."""

    added: list[DeadlineRecord]


# ------------------------------------------------------------------
# Helper: obtain a service instance
# ------------------------------------------------------------------


async def _get_service() -> DeadlineService:
    """Build a :class:`DeadlineService` backed by the shared store."""
    store = await get_deadline_store()
    return DeadlineService(store)


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@router.get("", response_model=DeadlineListResponse)
async def list_deadlines(
    course: str | None = None,
    priority: str | None = None,
) -> DeadlineListResponse:
    """List stored deadlines with optional filters.

    Args:
        course: Filter by course (case-insensitive).
        priority: Filter by priority level (case-insensitive; high/medium/low).

    Raises:
        HTTPException: 422 if priority is provided but not a valid value.
    """
    normalized_priority: DeadlinePriority | None = None
    if priority is not None:
        try:
            normalized_priority = DeadlinePriority(priority.strip().lower())
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid priority '{priority}'. Must be one of: high, medium, low."
                ),
            ) from None

    svc = await _get_service()
    records = await svc.list_deadlines(course=course, priority=normalized_priority)
    return DeadlineListResponse(deadlines=records)


@router.post("", response_model=DeadlineRecord, status_code=201)
async def create_deadline(body: CreateDeadlineRequest) -> DeadlineRecord:
    """Create a new deadline.

    Validates dates and ensures start_date <= due_date.
    Priority and date_type are validated automatically by Pydantic.

    Raises:
        HTTPException: 422 if date format or range is invalid.
    """
    svc = await _get_service()
    try:
        saved, _warnings = await svc.create(
            title=body.title,
            course=body.course,
            due_date=body.due_date,
            priority=body.priority,
            description=body.description,
            date_type=body.date_type,
            start_date=body.start_date,
        )
    except DeadlineValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return saved


@router.delete("/{deadline_id}", response_model=DeadlineDeleteResponse)
async def delete_deadline(deadline_id: str) -> DeadlineDeleteResponse:
    """Delete a deadline by ID.

    Raises:
        HTTPException: 404 if the deadline does not exist.
    """
    svc = await _get_service()
    try:
        await svc.delete(deadline_id)
    except DeadlineNotFoundError:
        raise HTTPException(status_code=404, detail="Deadline not found") from None
    return DeadlineDeleteResponse(status="deleted", id=deadline_id)


@router.patch("/{deadline_id}/complete", response_model=ToggleCompleteResponse)
async def toggle_complete(
    deadline_id: str, body: ToggleCompleteRequest
) -> ToggleCompleteResponse:
    """Toggle the completed status of a deadline.

    Raises:
        HTTPException: 404 if the deadline does not exist.
    """
    svc = await _get_service()
    try:
        updated = await svc.toggle_completed(deadline_id, body.completed)
    except DeadlineNotFoundError:
        raise HTTPException(status_code=404, detail="Deadline not found") from None
    return ToggleCompleteResponse(id=updated.id, completed=updated.completed)


@router.patch("/{deadline_id}", response_model=DeadlineRecord)
async def update_deadline(
    deadline_id: str, body: UpdateDeadlineRequest
) -> DeadlineRecord:
    """Update one or more fields of a deadline.

    Only the fields provided in the request body are updated; omitted
    fields keep their current values.  All field types are validated
    automatically by Pydantic (enums, date format).

    Raises:
        HTTPException: 404 if the deadline does not exist.
        HTTPException: 422 if date range is violated.
    """
    # Build fields dict from only the fields the caller actually sent
    # Values are already strongly typed (date, DeadlinePriority, DateType, etc.)
    fields: dict[str, object] = body.model_dump(exclude_unset=True)

    svc = await _get_service()
    try:
        updated, _warnings = await svc.update(deadline_id, fields)
    except DeadlineNotFoundError:
        raise HTTPException(status_code=404, detail="Deadline not found") from None
    except DeadlineValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return updated


@router.post("/sync-preview", response_model=SyncPreviewResponse)
async def sync_preview(body: SyncPreviewRequest) -> SyncPreviewResponse:
    """Preview which candidate deadlines are new vs duplicates."""
    svc = await _get_service()
    records = [DeadlineRecord.model_validate(d.model_dump()) for d in body.deadlines]
    new_tasks, dup_entries = await svc.sync_preview(records)
    duplicate_tasks = [
        DuplicateEntry(candidate=d["candidate"], existing_id=d["existing_id"])
        for d in dup_entries
    ]
    return SyncPreviewResponse(new_tasks=new_tasks, duplicate_tasks=duplicate_tasks)


@router.post("/sync-commit", response_model=SyncCommitResponse)
async def sync_commit(body: SyncCommitRequest) -> SyncCommitResponse:
    """Persist the set of tasks the user confirmed after sync preview."""
    svc = await _get_service()
    records = [DeadlineRecord.model_validate(t.model_dump()) for t in body.tasks]
    added = await svc.sync_commit(records)
    return SyncCommitResponse(added=added)
