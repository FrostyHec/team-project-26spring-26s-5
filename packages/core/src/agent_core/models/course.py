"""Course data model — SQLModel ORM table for persistent course records.

Used as the canonical model for the course management layer: persistence,
service, and API routes all share this single definition.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import String
from sqlmodel import Field, SQLModel

from agent_core.models.deadline import LenientDateTime


class Course(SQLModel, table=True):
    """A persistent academic course record.

    Attributes:
        id: Unique identifier (UUID), primary key.
        name: Course name (required).
        code: Course code, e.g. "CS101" (optional).
        credits: Number of credits (optional).
        instructor: Name of the instructor (optional).
        description: Longer course description (optional).
        tags: Comma-separated tags (optional).
        semester: Academic semester, e.g. "2026Spring" (optional).
        created_at: When the record was first created.
        updated_at: When the record was last modified.
    """

    __tablename__ = "courses"  # type: ignore[assignment]

    id: str = Field(default="", primary_key=True)
    name: str
    code: str = Field(default="", sa_type=String())
    credits: float | None = Field(default=None, sa_type=sa.Float())
    instructor: str = Field(default="", sa_type=String())
    description: str = Field(default="", sa_type=String())
    tags: str = Field(default="", sa_type=String())
    semester: str = Field(default="", sa_type=String())
    created_at: datetime | None = Field(default=None, sa_type=LenientDateTime())
    updated_at: datetime | None = Field(default=None, sa_type=LenientDateTime())


class CourseCreate(SQLModel):
    """DTO for creating a new course (no table, no id required)."""

    name: str
    code: str = ""
    credits: float | None = None
    instructor: str = ""
    description: str = ""
    tags: str = ""
    semester: str = ""


class CourseUpdate(SQLModel):
    """DTO for partial-update of a course's fields (all optional)."""

    name: str | None = None
    code: str | None = None
    credits: float | None = None
    instructor: str | None = None
    description: str | None = None
    tags: str | None = None
    semester: str | None = None
