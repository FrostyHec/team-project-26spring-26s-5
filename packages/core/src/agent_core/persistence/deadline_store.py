"""SQLite-backed deadline persistence — powered by SQLModel async ORM.

Provides async CRUD for academic deadline records using SQLModel +
SQLAlchemy async engine, eliminating hand-written SQL strings.  The
Store layer is a pure executor: it receives well-typed ``DeadlineRecord``
objects from the Service layer and translates them into DB operations.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, text
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
        """Create the async engine and ensure the schema exists.

        After ``create_all`` (which only creates missing tables), this
        method runs a migration step to handle old database schemas where
        ``start_date`` and ``due_date`` columns were defined as
        ``NOT NULL DEFAULT ''``.  The current model requires these columns
        to be nullable so that ``None`` can be stored.

        SQLite does not support ``ALTER COLUMN``, so migration is done by
        recreating the table:  create a temp table with the correct schema,
        copy data, drop old table, rename temp to ``deadlines``.
        """
        url = f"sqlite+aiosqlite:///{self.db_path}"
        self._engine = create_async_engine(url, echo=False)
        async with self._engine.begin() as conn:
            await conn.run_sync(DeadlineRecord.metadata.create_all)
            await conn.run_sync(self._migrate_nullable_dates)
        logger.info("Deadline store initialised at %s", self.db_path)

    @staticmethod
    def _migrate_nullable_dates(connection: object) -> None:
        """Migrate old NOT NULL date columns to nullable (sync callback).

        This is passed to ``conn.run_sync()`` so it receives the
        underlying synchronous ``Connection`` object.

        The migration is idempotent: if the columns are already nullable,
        it is a no-op.
        """
        from sqlalchemy import Connection, inspect

        conn: Connection = connection  # type: ignore[assignment]

        inspector = inspect(conn)
        if "deadlines" not in inspector.get_table_names():
            return  # Table doesn't exist yet — create_all will handle it

        columns = {c["name"]: c for c in inspector.get_columns("deadlines")}

        # Check if migration is needed:
        # Old schema has NOT NULL on start_date and/or due_date
        needs_migration = False
        for col_name in ("start_date", "due_date"):
            col_info = columns.get(col_name)
            if col_info is not None and col_info.get("nullable") is False:
                needs_migration = True
                break

        if not needs_migration:
            return

        logger.info(
            "Migrating deadlines table: making start_date and due_date nullable"
        )

        # SQLite migration: recreate table with correct schema
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        conn.execute(
            text(
                """
                CREATE TABLE deadlines_new (
                    id          TEXT PRIMARY KEY,
                    title       TEXT NOT NULL,
                    course      TEXT NOT NULL DEFAULT '',
                    due_date    TEXT,
                    priority    TEXT NOT NULL DEFAULT 'medium',
                    source      TEXT NOT NULL DEFAULT 'manual',
                    description TEXT NOT NULL DEFAULT '',
                    date_type   TEXT NOT NULL DEFAULT 'moment_day',
                    start_date  TEXT,
                    completed   INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO deadlines_new
                    (id, title, course, due_date, priority, source,
                     description, date_type, start_date, completed)
                SELECT
                    id, title, course,
                    CASE WHEN due_date = '' THEN NULL ELSE due_date END,
                    priority, source, description, date_type,
                    CASE WHEN start_date = '' THEN NULL ELSE start_date END,
                    completed
                FROM deadlines
                """
            )
        )
        conn.execute(text("DROP TABLE deadlines"))
        conn.execute(text("ALTER TABLE deadlines_new RENAME TO deadlines"))
        conn.execute(text("PRAGMA foreign_keys = ON"))
        logger.info("Migration complete: date columns are now nullable")

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
