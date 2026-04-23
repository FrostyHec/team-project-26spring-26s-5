"""Course management service — business logic for course CRUD operations."""

import uuid
from datetime import UTC, datetime

from agent_core.logging_utils import get_logger
from agent_core.models.course import Course, CourseCreate
from agent_core.persistence.course_store import CourseStore

logger = get_logger("services.course")


class CourseNotFoundError(Exception):
    """Raised when a course ID does not exist in the store."""

    def __init__(self, course_id: str) -> None:
        self.course_id = course_id
        super().__init__(f"Course '{course_id}' not found.")


class CourseService:
    """Service encapsulating course business logic."""

    def __init__(self, store: CourseStore) -> None:
        self._store = store

    async def create(self, data: CourseCreate) -> Course:
        record = Course(
            id=str(uuid.uuid4()),
            name=data.name,
            code=data.code,
            credits=data.credits,
            instructor=data.instructor,
            description=data.description,
            tags=data.tags,
            semester=data.semester,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        return await self._store.add(record)

    async def list(self, semester: str | None = None) -> list[Course]:
        return await self._store.list_all(semester=semester)

    async def get(self, course_id: str) -> Course:
        record = await self._store.get(course_id)
        if record is None:
            raise CourseNotFoundError(course_id)
        return record

    async def update(self, course_id: str, fields: dict[str, object]) -> Course:
        existing = await self._store.get(course_id)
        if existing is None:
            raise CourseNotFoundError(course_id)
        updated = await self._store.update(course_id, fields)
        if updated is None:
            raise CourseNotFoundError(course_id)
        return updated

    async def delete(self, course_id: str) -> bool:
        existing = await self._store.get(course_id)
        if existing is None:
            raise CourseNotFoundError(course_id)
        return await self._store.delete(course_id)


__all__ = ["CourseService", "CourseNotFoundError"]
