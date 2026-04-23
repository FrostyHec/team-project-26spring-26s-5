"""SQLite-backed course persistence — SQLModel async ORM.

Provides async CRUD for course records using SQLModel + SQLAlchemy async engine.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from agent_core.logging_utils import get_logger
from agent_core.models.course import Course

logger = get_logger("persistence.course")


class CourseStore:
    """Async SQLite store for academic courses (SQLModel ORM)."""

    def __init__(self, db_path: str = "courses.db") -> None:
        self.db_path = db_path
        self._engine = None  # type: ignore[assignment]

    @property
    def is_connected(self) -> bool:
        return self._engine is not None

    async def initialize(self) -> None:
        url = f"sqlite+aiosqlite:///{self.db_path}"
        self._engine = create_async_engine(url, echo=False)
        async with self._engine.begin() as conn:
            await conn.run_sync(Course.metadata.create_all)
        logger.info("Course store initialised at %s", self.db_path)

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    def _session(self) -> AsyncSession:
        if self._engine is None:
            raise RuntimeError("CourseStore not initialised — call initialize() first")
        return AsyncSession(self._engine)

    async def add(self, record: Course) -> Course:
        if not record.id:
            record.id = str(uuid.uuid4())
        if not record.created_at:
            record.created_at = datetime.now(UTC)
        record.updated_at = datetime.now(UTC)
        async with self._session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
        logger.debug("Added course %s: %s", record.id, record.name)
        return record

    async def list_all(
        self,
        semester: str | None = None,
    ) -> list[Course]:
        statement = select(Course)
        if semester:
            statement = statement.where(Course.semester == semester)
        statement = statement.order_by(Course.name)
        async with self._session() as session:
            results = await session.exec(statement)
            return list(results.all())

    async def get(self, course_id: str) -> Course | None:
        async with self._session() as session:
            return await session.get(Course, course_id)

    async def delete(self, course_id: str) -> bool:
        async with self._session() as session:
            record = await session.get(Course, course_id)
            if record is None:
                return False
            await session.delete(record)
            await session.commit()
        return True

    async def update(
        self,
        course_id: str,
        fields: dict[str, object],
    ) -> Course | None:
        async with self._session() as session:
            record = await session.get(Course, course_id)
            if record is None:
                return None
            for key, value in fields.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            record.updated_at = datetime.now(UTC)
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return record


__all__ = ["CourseStore"]
