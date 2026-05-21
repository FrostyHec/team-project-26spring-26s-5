"""Course material REST routes — controller layer over :class:`CourseMaterialService`.

Provides CRUD + file upload / download endpoints for course materials.
"""

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent_core.logging_utils import get_logger
from agent_core.models.course_material import CourseMaterial
from agent_core.persistence.course_material_provider import get_course_material_store
from agent_core.persistence.course_provider import get_course_store
from agent_core.services.course_material_service import (
    CourseMaterialService,
    MaterialNotFoundError,
    MaterialValidationError,
    resolve_course_material_storage_root,
)
from agent_core.services.course_service import CourseNotFoundError, CourseService

logger = get_logger("api.course_materials")

router = APIRouter(prefix="/course-materials", tags=["course-materials"])


class MaterialListResponse(BaseModel):
    materials: list[CourseMaterial]


class MaterialDeleteResponse(BaseModel):
    status: str
    id: str


async def _get_service() -> CourseMaterialService:
    course_store = await get_course_store()
    material_store = await get_course_material_store()
    course_service = CourseService(course_store)
    return CourseMaterialService(
        store=material_store,
        course_service=course_service,
        storage_root=str(resolve_course_material_storage_root()),
    )


@router.get("", response_model=MaterialListResponse)
async def list_materials(course_id: str | None = None) -> MaterialListResponse:
    """List course materials, optionally filtered by course."""
    svc = await _get_service()
    records = await svc.list(course_id=course_id)
    return MaterialListResponse(materials=records)


@router.post("", response_model=CourseMaterial, status_code=201)
async def upload_material(
    file: UploadFile,
    course_id: str = Form(...),
    description: str = Form(""),
    tags: str = Form(""),
) -> CourseMaterial:
    """Upload a file and attach it to a course.

    Validates file type (.pdf, .docx, .pptx, .xlsx, .txt, .md) and size (≤10 MB).
    """
    svc = await _get_service()
    file_bytes = await file.read()
    try:
        return await svc.create_from_upload(
            course_id=course_id,
            filename=file.filename or "unknown",
            file_bytes=file_bytes,
            description=description,
            tags=tags,
        )
    except CourseNotFoundError:
        raise HTTPException(status_code=404, detail="Course not found") from None
    except MaterialValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None


@router.get("/{material_id}", response_model=CourseMaterial)
async def get_material(material_id: str) -> CourseMaterial:
    """Get a material record by ID."""
    svc = await _get_service()
    try:
        return await svc.get(material_id)
    except MaterialNotFoundError:
        raise HTTPException(status_code=404, detail="Material not found") from None


@router.get("/{material_id}/download")
async def download_material(material_id: str) -> FileResponse:
    """Download the physical file for a material."""
    svc = await _get_service()
    try:
        record, _ = await svc.get_file_bytes(material_id)
    except MaterialNotFoundError:
        raise HTTPException(status_code=404, detail="Material not found") from None

    import os

    path = record.stored_path
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=path,
        media_type="application/octet-stream",
        filename=record.filename,
    )


@router.patch("/{material_id}", response_model=CourseMaterial)
async def update_material(
    material_id: str,
    description: str | None = Form(None),
    tags: str | None = Form(None),
) -> CourseMaterial:
    """Update description and/or tags of a material."""
    svc = await _get_service()
    fields = {}
    if description is not None:
        fields["description"] = description
    if tags is not None:
        fields["tags"] = tags
    try:
        if not fields:
            return await svc.get(material_id)
        return await svc.update(material_id, fields)
    except MaterialNotFoundError:
        raise HTTPException(status_code=404, detail="Material not found") from None


@router.delete("/{material_id}", response_model=MaterialDeleteResponse)
async def delete_material(material_id: str) -> MaterialDeleteResponse:
    """Delete a material (record + physical file)."""
    svc = await _get_service()
    try:
        await svc.delete(material_id)
    except MaterialNotFoundError:
        raise HTTPException(status_code=404, detail="Material not found") from None
    return MaterialDeleteResponse(status="deleted", id=material_id)
