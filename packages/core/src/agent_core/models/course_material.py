"""CourseMaterial data model — SQLModel ORM table for uploaded course files.

Each record represents a single file attached to a course, stored under
``course_materials/{course_id}/{uuid}_{filename}``.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import String
from sqlmodel import Field, SQLModel

from agent_core.models.deadline import LenientDateTime


class CourseMaterial(SQLModel, table=True):
    """A course material file record persisted in the store.

    Used as both the SQLModel ORM table and the Pydantic schema for API
    responses.  The physical file lives under
    ``{storage_root}/course_materials/{course_id}/{uuid}_{filename}``.

    Attributes:
        id: Unique identifier (UUID), primary key.
        course_id: ID of the owning course.
        filename: Original filename as uploaded.
        stored_path: Relative path under the storage root.
        file_type: File extension including dot, e.g. ".pdf".
        file_size: Size in bytes.
        description: Optional description or notes.
        tags: Optional comma-separated tags.
        created_at: When the file was uploaded.
    """

    __tablename__ = "course_materials"  # type: ignore[assignment]

    id: str = Field(default="", primary_key=True)
    course_id: str = Field(default="", sa_type=String())
    filename: str = Field(default="", sa_type=String())
    stored_path: str = Field(default="", sa_type=String())
    file_type: str = Field(default="", sa_type=String())
    file_size: int = Field(default=0, sa_type=sa.Integer())
    description: str = Field(default="", sa_type=String())
    tags: str = Field(default="", sa_type=String())
    created_at: datetime | None = Field(default=None, sa_type=LenientDateTime())


class CourseMaterialCreate(SQLModel):
    """DTO for creating a material record (no table, no id required)."""

    course_id: str
    filename: str
    stored_path: str
    file_type: str
    file_size: int = 0
    description: str = ""
    tags: str = ""


class CourseMaterialUpdate(SQLModel):
    """DTO for partial-update of a material's fields (all optional)."""

    description: str | None = None
    tags: str | None = None
