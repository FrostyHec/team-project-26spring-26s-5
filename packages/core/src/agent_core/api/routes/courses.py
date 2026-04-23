"""Course REST routes — thin controller layer over :class:`CourseService`.

Provides CRUD endpoints for persistent course records.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_core.models.course import Course, CourseCreate, CourseUpdate
from agent_core.persistence.course_material_provider import (
    get_course_material_store,
)
from agent_core.persistence.course_provider import get_course_store
from agent_core.services.course_service import CourseNotFoundError, CourseService

router = APIRouter(prefix="/courses", tags=["courses"])


class CourseListResponse(BaseModel):
    courses: list[Course]


class CourseDeleteResponse(BaseModel):
    status: str
    id: str


async def _get_service() -> CourseService:
    store = await get_course_store()
    return CourseService(store)


@router.get("", response_model=CourseListResponse)
async def list_courses(semester: str | None = None) -> CourseListResponse:
    """List all courses, optionally filtered by semester."""
    svc = await _get_service()
    records = await svc.list(semester=semester)
    return CourseListResponse(courses=records)


@router.post("", response_model=Course, status_code=201)
async def create_course(body: CourseCreate) -> Course:
    """Create a new course."""
    svc = await _get_service()
    saved = await svc.create(body)
    return saved


@router.get("/{course_id}", response_model=Course)
async def get_course(course_id: str) -> Course:
    """Get a course by ID."""
    svc = await _get_service()
    try:
        return await svc.get(course_id)
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="Course not found") from None


@router.patch("/{course_id}", response_model=Course)
async def update_course(course_id: str, body: CourseUpdate) -> Course:
    """Update one or more fields of a course."""
    svc = await _get_service()
    fields = body.model_dump(exclude_unset=True)
    try:
        if not fields:
            return await svc.get(course_id)
        return await svc.update(course_id, fields)
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="Course not found") from None


@router.delete("/{course_id}", response_model=CourseDeleteResponse)
async def delete_course(course_id: str) -> CourseDeleteResponse:
    """Delete a course and all its associated materials (records + physical files)."""
    svc = await _get_service()
    try:
        await svc.get(course_id)
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="Course not found") from None

    mat_store = await get_course_material_store()
    materials = await mat_store.list_all(course_id=course_id)
    for mat in materials:
        await mat_store.delete(mat.id)

    await svc.delete(course_id)
    return CourseDeleteResponse(status="deleted", id=course_id)
