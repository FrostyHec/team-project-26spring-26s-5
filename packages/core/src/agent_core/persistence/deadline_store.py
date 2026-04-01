"""SQLite-backed deadline persistence.

Provides async CRUD for academic deadline records.  Designed as a
lightweight module that can share the same database file as the
session store or use its own.
"""

import uuid

import aiosqlite

from agent_core.logging_utils import get_logger
from agent_core.models.deadline import DeadlinePriority, DeadlineRecord, DeadlineSource

logger = get_logger("persistence.deadline")

_DEADLINE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS deadlines (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    course      TEXT NOT NULL DEFAULT '',
    due_date    TEXT NOT NULL DEFAULT '',
    priority    TEXT NOT NULL DEFAULT 'medium',
    source      TEXT NOT NULL DEFAULT 'manual',
    description TEXT NOT NULL DEFAULT ''
);
"""


class DeadlineStore:
    """Async SQLite store for academic deadlines.

    Usage::

        store = DeadlineStore(":memory:")
        await store.initialize()
        await store.add(DeadlineRecord(id="...", title="HW1", ...))
        items = await store.list_all()
        await store.close()
    """

    def __init__(self, db_path: str = "deadlines.db") -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open DB connection and ensure schema exists."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_DEADLINE_SCHEMA_SQL)
        await self._db.commit()
        logger.info(f"Deadline store initialized at {self.db_path}")

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        """Active database connection."""
        if self._db is None:
            raise RuntimeError(
                "DeadlineStore not initialized — call initialize() first"
            )
        return self._db

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def add(self, record: DeadlineRecord) -> DeadlineRecord:
        """Insert a new deadline.  Generates an id if empty."""
        if not record.id:
            record = record.model_copy(update={"id": str(uuid.uuid4())})
        await self.db.execute(
            "INSERT INTO deadlines"
            " (id, title, course, due_date,"
            " priority, source, description)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record.id,
                record.title,
                record.course,
                record.due_date,
                record.priority.value,
                record.source.value,
                record.description,
            ),
        )
        await self.db.commit()
        return record

    async def list_all(
        self,
        course: str | None = None,
        priority: str | None = None,
    ) -> list[DeadlineRecord]:
        """Return deadlines, optionally filtered.

        Args:
            course: Filter by course name
                (case-insensitive).
            priority: If given, only return deadlines matching this priority level.
        """
        query = "SELECT * FROM deadlines"
        params: list[str] = []
        clauses: list[str] = []

        if course:
            clauses.append("LOWER(course) = LOWER(?)")
            params.append(course)
        if priority:
            clauses.append("priority = ?")
            params.append(priority)

        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY due_date ASC"

        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_record(r) for r in rows]

    async def get(self, deadline_id: str) -> DeadlineRecord | None:
        """Fetch a single deadline by ID."""
        async with self.db.execute(
            "SELECT * FROM deadlines WHERE id = ?", (deadline_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_record(row) if row else None

    async def delete(self, deadline_id: str) -> bool:
        """Delete a deadline.  Returns True if a row was removed."""
        cursor = await self.db.execute(
            "DELETE FROM deadlines WHERE id = ?", (deadline_id,)
        )
        await self.db.commit()
        return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_record(row: aiosqlite.Row) -> DeadlineRecord:
        return DeadlineRecord(
            id=row["id"],
            title=row["title"],
            course=row["course"],
            due_date=row["due_date"],
            priority=DeadlinePriority(row["priority"]),
            source=DeadlineSource(row["source"]),
            description=row["description"],
        )
