"""SQLite-backed deadline persistence — powered by SQLModel async ORM.

Provides async CRUD for academic deadline records using SQLModel +
SQLAlchemy async engine, eliminating hand-written SQL strings.  The
Store layer is a pure executor: it receives well-typed ``DeadlineRecord``
objects from the Service layer and translates them into DB operations.
"""

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from agent_core.logging_utils import get_logger
from agent_core.models.deadline import (
    DeadlinePriority,
    DeadlineRecord,
)

logger = get_logger("persistence.deadline")

# Columns that callers may update (all DeadlineRecord fields except ``id``).
_UPDATABLE_FIELDS = frozenset(set(DeadlineRecord.model_fields) - {"id"})


class DeadlineStore:
    """Async SQLite store for academic deadlines (SQLModel ORM).

    Uses SQLModel + SQLAlchemy async engine so that all queries are
    expressed via the ORM — no hand-written SQL strings.

    Usage::

        store = DeadlineStore(":memory:")
        await store.initialize()
        record = DeadlineRecord(title="HW1", ...)
        saved = await store.add(record)
        items = await store.list_all()
        await store.close()
    """

    def __init__(self, db_path: str = "deadlines.db") -> None:
        self.db_path = db_path
        self._engine = None  # type: ignore[assignment]

    @property
    def is_connected(self) -> bool:
        """Return *True* if the engine has been initialised."""
        return self._engine is not None

    async def initialize(self) -> None:
        """Create the async engine and ensure the schema exists."""
        url = f"sqlite+aiosqlite:///{self.db_path}"
        self._engine = create_async_engine(url, echo=False)
        async with self._engine.begin() as conn:
            await conn.run_sync(DeadlineRecord.metadata.create_all)
        logger.info("Deadline store initialised at %s", self.db_path)

    async def close(self) -> None:
        """Dispose the engine and release connections."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    # ------------------------------------------------------------------
    # Session factory
    # ------------------------------------------------------------------

    def _session(self) -> AsyncSession:
        """Return a new async ORM session."""
        if self._engine is None:
            raise RuntimeError(
                "DeadlineStore not initialised — call initialize() first"
            )
        return AsyncSession(self._engine)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def add(self, record: DeadlineRecord) -> DeadlineRecord:
        """Insert a new deadline.  Generates an ``id`` if empty."""
        if not record.id:
            record.id = str(uuid.uuid4())
        async with self._session() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
        logger.debug("Added deadline %s: %s", record.id, record.title)
        return record

    async def list_all(
        self,
        course: str | None = None,
        priority: DeadlinePriority | None = None,
    ) -> list[DeadlineRecord]:
        """Return deadlines, optionally filtered.

        Args:
            course: Filter by course name (case-insensitive).
            priority: If given, only return deadlines matching this level.
        """
        statement = select(DeadlineRecord)
        if course:
            statement = statement.where(
                func.lower(DeadlineRecord.course) == course.lower()
            )
        if priority is not None:
            statement = statement.where(DeadlineRecord.priority == priority)
        # Sort: rows with due_date=None last, then ascending
        statement = statement.order_by(
            col(DeadlineRecord.due_date).is_(None),
            col(DeadlineRecord.due_date).asc(),
        )
        async with self._session() as session:
            results = await session.exec(statement)
            return list(results.all())

    async def get(self, deadline_id: str) -> DeadlineRecord | None:
        """Fetch a single deadline by ID."""
        async with self._session() as session:
            return await session.get(DeadlineRecord, deadline_id)

    async def delete(self, deadline_id: str) -> bool:
        """Delete a deadline.  Returns *True* if a row was removed."""
        async with self._session() as session:
            record = await session.get(DeadlineRecord, deadline_id)
            if record is None:
                return False
            await session.delete(record)
            await session.commit()
        return True

    async def toggle_completed(
        self, deadline_id: str, completed: bool
    ) -> DeadlineRecord | None:
        """Set the completed status of a deadline.

        Returns the updated record, or ``None`` if the id does not exist.
        """
        async with self._session() as session:
            record = await session.get(DeadlineRecord, deadline_id)
            if record is None:
                return None
            record.completed = completed
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return record

    async def update(
        self,
        deadline_id: str,
        fields: dict[str, object],
    ) -> DeadlineRecord | None:
        """Update specific columns of an existing deadline.

        *fields* maps attribute names to strongly-typed values.  Only
        whitelisted columns are accepted; unknown keys are silently
        ignored.  Callers (the Service layer) are responsible for
        passing correct types — e.g. ``datetime`` objects for date/time
        fields and enum instances for enum fields.

        Returns the updated record, or ``None`` if the id does not exist.
        """
        _ALLOWED = _UPDATABLE_FIELDS
        to_update = {k: v for k, v in fields.items() if k in _ALLOWED}
        if not to_update:
            return await self.get(deadline_id)

        async with self._session() as session:
            record = await session.get(DeadlineRecord, deadline_id)
            if record is None:
                return None
            for key, value in to_update.items():
                setattr(record, key, value)
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return record

    async def find_duplicate(
        self, title: str, due_date: datetime | None
    ) -> DeadlineRecord | None:
        """Find an existing deadline with the same title and due_date.

        Comparison is case-insensitive on title.  Returns the first match
        or ``None``.
        """
        statement = select(DeadlineRecord).where(
            func.lower(DeadlineRecord.title) == title.lower(),
            DeadlineRecord.due_date == due_date,
        )
        async with self._session() as session:
            results = await session.exec(statement)
            return results.first()


__all__ = ["DeadlineStore"]
