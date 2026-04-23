"""SQLite-backed course material persistence — SQLModel async ORM.

Provides async CRUD for course material records using SQLModel + SQLAlchemy
async engine.  Delete operations also remove the physical file from disk.
"""

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from agent_core.logging_utils import get_logger
from agent_core.models.course_material import CourseMaterial

logger = get_logger("persistence.course_material")


class CourseMaterialStore:
    """Async SQLite store for course material files (SQLModel ORM)."""

    DEFAULT_ALLOWED_EXTENSIONS = frozenset(
        {".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md"}
    )
    DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    def __init__(
        self,
        db_path: str = "course_materials.db",
        max_size_bytes: int | None = None,
        allowed_extensions: frozenset[str] | None = None,
    ) -> None:
        self.db_path = db_path
        self.max_size_bytes = (
            max_size_bytes if max_size_bytes is not None else self.DEFAULT_MAX_FILE_SIZE
        )
        self.allowed_extensions = (
            allowed_extensions
            if allowed_extensions is not None
            else self.DEFAULT_ALLOWED_EXTENSIONS
        )
        self._engine = None  # type: ignore[assignment]

    @property
    def is_connected(self) -> bool:
        return self._engine is not None

    async def initialize(self) -> None:
        url = f"sqlite+aiosqlite:///{self.db_path}"
        self._engine = create_async_engine(url, echo=False)
        async with self._engine.begin() as conn:
            await conn.run_sync(CourseMaterial.metadata.create_all)
        logger.info("Course material store initialised at %s", self.db_path)

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    def _session(self) -> AsyncSession:
        if self._engine is None:
            raise RuntimeError(
                "CourseMaterialStore not initialised — call initialize() first"
            )
        return AsyncSession(self._engine)

    async def add(self, record: CourseMaterial) -> CourseMaterial:
        if not record.id:
            record.id = str(uuid.uuid4())
        if not record.created_at:
            record.created_at = datetime.now(UTC)
        async with self._session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
        logger.debug("Added material %s: %s", record.id, record.filename)
        return record

    async def list_all(
        self,
        course_id: str | None = None,
    ) -> list[CourseMaterial]:
        statement = select(CourseMaterial)
        if course_id:
            statement = statement.where(CourseMaterial.course_id == course_id)
        statement = statement.order_by(CourseMaterial.created_at.desc())
        async with self._session() as session:
            results = await session.exec(statement)
            return list(results.all())

    async def get(self, material_id: str) -> CourseMaterial | None:
        async with self._session() as session:
            return await session.get(CourseMaterial, material_id)

    async def delete(self, material_id: str) -> bool:
        """Delete a material record and its physical file."""
        record = await self.get(material_id)
        if record is None:
            return False
        stored_path = record.stored_path
        async with self._session() as session:
            db_record = await session.get(CourseMaterial, material_id)
            if db_record is None:
                return False
            await session.delete(db_record)
            await session.commit()
        # Remove physical file
        if stored_path:
            try:
                os.remove(stored_path)
                logger.debug("Removed physical file: %s", stored_path)
            except OSError as exc:
                logger.warning(
                    "Failed to remove physical file %s: %s", stored_path, exc
                )
        logger.debug("Deleted material %s", material_id)
        return True

    async def update(
        self,
        material_id: str,
        fields: dict[str, object],
    ) -> CourseMaterial | None:
        async with self._session() as session:
            record = await session.get(CourseMaterial, material_id)
            if record is None:
                return None
            for key, value in fields.items():
                if hasattr(record, key):
                    setattr(record, key, value)
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return record


def validate_file_extension(
    filename: str,
    allowed: frozenset[str] | None = None,
) -> str | None:
    """Return the lower-cased extension if allowed, else None."""
    ext = Path(filename).suffix.lower()
    allowed_set = (
        allowed
        if allowed is not None
        else CourseMaterialStore.DEFAULT_ALLOWED_EXTENSIONS
    )
    return ext if ext in allowed_set else None


def validate_file_size(
    size_bytes: int,
    max_size: int | None = None,
) -> bool:
    """Return True if file size is within the configured limit."""
    limit = (
        max_size if max_size is not None else CourseMaterialStore.DEFAULT_MAX_FILE_SIZE
    )
    return 0 < size_bytes <= limit


__all__ = [
    "CourseMaterialStore",
    "validate_file_extension",
    "validate_file_size",
]
