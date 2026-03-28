"""SQLite-backed session and message persistence.

Provides async CRUD operations for chat sessions and messages
using aiosqlite. Designed as a singleton managed by the app
lifespan, injected into routes via FastAPI Depends.
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from agent_core.logging_utils import get_logger
from agent_core.models.session import (
    MessageRecord,
    MessageRole,
    SessionDetail,
    SessionRecord,
    SessionSummary,
)

logger = get_logger("persistence")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    pending_state TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role          TEXT NOT NULL,
    content       TEXT NOT NULL,
    tool_call_id  TEXT,
    tool_calls    TEXT,
    created_at    TEXT NOT NULL,
    ordinal       INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session
    ON messages(session_id, ordinal);
"""


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(UTC).isoformat()


class SessionStore:
    """SQLite-backed session and message storage.

    Usage:
        store = SessionStore("sessions.db")
        await store.initialize()
        ...
        await store.close()

    Attributes:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str = "sessions.db") -> None:
        """Initialize the session store.

        Args:
            db_path: Path to SQLite database. Use ':memory:' for tests.
        """
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open the database and create tables if needed."""
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.executescript(_SCHEMA_SQL)
        await self._db.commit()
        logger.info(f"Session store initialized at {self.db_path}")

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        """Get the active database connection.

        Raises:
            RuntimeError: If store is not initialized.
        """
        if self._db is None:
            raise RuntimeError("SessionStore not initialized")
        return self._db

    # ---- Session CRUD ----

    async def create_session(self, title: str = "") -> SessionRecord:
        """Create a new chat session with a unique UUID.

        Generates UUIDs until one is found that does not conflict
        with existing sessions.

        Args:
            title: Optional session title.

        Returns:
            The created SessionRecord.
        """
        for _ in range(10):
            session_id = str(uuid.uuid4())
            if not await self.session_exists(session_id):
                return await self.create_session_with_id(session_id, title)
        # Extremely unlikely: fallback after 10 collisions
        return await self.create_session_with_id(str(uuid.uuid4()), title)

    async def session_exists(self, session_id: str) -> bool:
        """Check if a session ID already exists (active or inactive).

        Args:
            session_id: The session UUID.

        Returns:
            True if the session ID is already in use.
        """
        cursor = await self.db.execute(
            "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
        )
        return await cursor.fetchone() is not None

    async def create_session_with_id(
        self, session_id: str, title: str = ""
    ) -> SessionRecord:
        """Create a session with a specific ID.

        Args:
            session_id: The session UUID to use.
            title: Optional session title.

        Returns:
            The created SessionRecord.
        """
        now = _now_iso()
        await self.db.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (session_id, title, now, now),
        )
        await self.db.commit()
        return SessionRecord(
            id=session_id,
            title=title,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    async def get_session(self, session_id: str) -> SessionRecord | None:
        """Get a session by ID.

        Args:
            session_id: The session UUID.

        Returns:
            SessionRecord if found, None otherwise.
        """
        cursor = await self.db.execute(
            "SELECT * FROM sessions WHERE id = ? AND is_active = 1",
            (session_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    async def list_sessions(self) -> list[SessionSummary]:
        """List all active sessions with message counts.

        Returns:
            List of SessionSummary objects.
        """
        cursor = await self.db.execute(
            "SELECT s.*, COUNT(m.id) as message_count "
            "FROM sessions s "
            "LEFT JOIN messages m ON s.id = m.session_id "
            "WHERE s.is_active = 1 "
            "GROUP BY s.id "
            "ORDER BY s.updated_at DESC",
        )
        rows = await cursor.fetchall()
        return [
            SessionSummary(
                id=row["id"],
                title=row["title"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                message_count=row["message_count"],
                can_resume=row["pending_state"] is not None,
            )
            for row in rows
        ]

    async def delete_session(self, session_id: str) -> bool:
        """Soft-delete a session.

        Args:
            session_id: The session UUID.

        Returns:
            True if session was found and deleted.
        """
        cursor = await self.db.execute(
            "UPDATE sessions SET is_active = 0 WHERE id = ? AND is_active = 1",
            (session_id,),
        )
        await self.db.commit()
        return cursor.rowcount > 0

    # ---- Message persistence ----

    async def add_message(self, msg: MessageRecord) -> MessageRecord:
        """Persist a message and update session timestamp.

        Args:
            msg: The message to persist.

        Returns:
            The persisted MessageRecord with assigned ID.
        """
        tool_calls_json = json.dumps(msg.tool_calls) if msg.tool_calls else None
        cursor = await self.db.execute(
            "INSERT INTO messages "
            "(session_id, role, content, tool_call_id, tool_calls, "
            "created_at, ordinal) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                msg.session_id,
                msg.role.value,
                msg.content,
                msg.tool_call_id,
                tool_calls_json,
                msg.created_at.isoformat(),
                msg.ordinal,
            ),
        )
        # Update session timestamp and auto-title
        now = _now_iso()
        if msg.role == MessageRole.HUMAN:
            # Auto-set title from first human message
            await self.db.execute(
                "UPDATE sessions SET updated_at = ?, "
                "title = CASE WHEN title = '' THEN ? ELSE title END "
                "WHERE id = ?",
                (now, msg.content[:80], msg.session_id),
            )
        else:
            await self.db.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, msg.session_id),
            )
        await self.db.commit()
        msg.id = cursor.lastrowid
        return msg

    async def get_messages(self, session_id: str) -> list[MessageRecord]:
        """Get all messages for a session in order.

        Args:
            session_id: The session UUID.

        Returns:
            Ordered list of MessageRecord objects.
        """
        cursor = await self.db.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY ordinal ASC",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_message(row) for row in rows]

    async def get_next_ordinal(self, session_id: str) -> int:
        """Get the next ordinal for a new message.

        Args:
            session_id: The session UUID.

        Returns:
            The next ordinal value.
        """
        cursor = await self.db.execute(
            "SELECT MAX(ordinal) FROM messages WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        max_ord = row[0] if row and row[0] is not None else -1
        return max_ord + 1

    # ---- ReAct resume support ----

    async def save_pending_state(self, session_id: str, pending: dict | None) -> None:
        """Save in-flight tool call state for crash recovery.

        Args:
            session_id: The session UUID.
            pending: The pending tool call state dict, or None to clear.
        """
        state_json = json.dumps(pending) if pending else None
        await self.db.execute(
            "UPDATE sessions SET pending_state = ? WHERE id = ?",
            (state_json, session_id),
        )
        await self.db.commit()

    async def clear_pending_state(self, session_id: str) -> None:
        """Clear the pending state after successful tool execution.

        Args:
            session_id: The session UUID.
        """
        await self.save_pending_state(session_id, None)

    # ---- Session detail ----

    async def get_session_detail(self, session_id: str) -> SessionDetail | None:
        """Get a session with its full message history.

        Args:
            session_id: The session UUID.

        Returns:
            SessionDetail if found, None otherwise.
        """
        session = await self.get_session(session_id)
        if session is None:
            return None
        messages = await self.get_messages(session_id)
        return SessionDetail(session=session, messages=messages)

    # ---- Row converters ----

    @staticmethod
    def _row_to_session(row: aiosqlite.Row) -> SessionRecord:
        """Convert a database row to a SessionRecord."""
        pending = None
        if row["pending_state"]:
            pending = json.loads(row["pending_state"])
        return SessionRecord(
            id=row["id"],
            title=row["title"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            is_active=bool(row["is_active"]),
            pending_state=pending,
        )

    @staticmethod
    def _row_to_message(row: aiosqlite.Row) -> MessageRecord:
        """Convert a database row to a MessageRecord."""
        tool_calls = None
        if row["tool_calls"]:
            tool_calls = json.loads(row["tool_calls"])
        return MessageRecord(
            id=row["id"],
            session_id=row["session_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            tool_call_id=row["tool_call_id"],
            tool_calls=tool_calls,
            created_at=datetime.fromisoformat(row["created_at"]),
            ordinal=row["ordinal"],
        )
