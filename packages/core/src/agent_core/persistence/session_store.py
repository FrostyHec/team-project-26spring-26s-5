"""SQLite-backed session and message persistence via SQLModel ORM."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from agent_core.logging_utils import get_logger
from agent_core.models.session import (
    FallbackMode,
    MessageRecord,
    MessageRole,
    MessageStatus,
    MessageTable,
    SessionDetail,
    SessionRecord,
    SessionSummary,
    SessionTable,
)

logger = get_logger("persistence")


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _now_utc() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


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
        self._engine: AsyncEngine | None = None

    async def initialize(self) -> None:
        """Open the database engine and create tables if needed."""
        if self.db_path == ":memory:":
            database_url = "sqlite+aiosqlite://"
            engine_kwargs: dict[str, object] = {
                "echo": False,
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            }
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite+aiosqlite:///{self.db_path}"
            engine_kwargs = {"echo": False}

        self._engine = create_async_engine(database_url, **engine_kwargs)

        async with self._engine.begin() as conn:
            await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            if self.db_path != ":memory:":
                await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            await conn.run_sync(self._create_schema)
            await conn.run_sync(self._ensure_session_columns)
            await conn.run_sync(self._ensure_message_columns)

        logger.info(f"Session store initialized at {self.db_path}")

    @staticmethod
    def _create_schema(connection: object) -> None:
        """Create the SQLModel tables if they do not exist."""
        SessionTable.__table__.create(connection, checkfirst=True)
        MessageTable.__table__.create(connection, checkfirst=True)

    @staticmethod
    def _ensure_session_columns(connection: object) -> None:
        """Add newer session columns for existing databases."""
        existing_columns = {
            column["name"] for column in inspect(connection).get_columns("sessions")
        }

        if "selected_provider_id" not in existing_columns:
            connection.execute(
                text("ALTER TABLE sessions ADD COLUMN selected_provider_id TEXT")
            )
        if "fallback_mode" not in existing_columns:
            connection.execute(
                text(
                    "ALTER TABLE sessions "
                    "ADD COLUMN fallback_mode TEXT NOT NULL DEFAULT 'manual'"
                )
            )
        if "current_leaf_node_id" not in existing_columns:
            connection.execute(
                text("ALTER TABLE sessions ADD COLUMN current_leaf_node_id TEXT")
            )

    @staticmethod
    def _ensure_message_columns(connection: object) -> None:
        """Add newer message columns for existing databases."""
        existing_columns = {
            column["name"] for column in inspect(connection).get_columns("messages")
        }

        if "status" not in existing_columns:
            connection.execute(
                text(
                    "ALTER TABLE messages "
                    "ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'"
                )
            )

    async def close(self) -> None:
        """Close the database engine."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    @property
    def db(self) -> AsyncEngine:
        """Get the active database engine.

        Raises:
            RuntimeError: If store is not initialized.
        """
        if self._engine is None:
            raise RuntimeError("SessionStore not initialized")
        return self._engine

    def _session(self) -> AsyncSession:
        """Create a new async ORM session."""
        return AsyncSession(self.db, expire_on_commit=False)

    async def _get_session_row(
        self,
        session: AsyncSession,
        session_id: str,
        *,
        require_active: bool,
    ) -> SessionTable | None:
        """Fetch a session row by ID, optionally requiring active status."""
        statement = select(SessionTable).where(SessionTable.id == session_id)
        if require_active:
            statement = statement.where(SessionTable.is_active.is_(True))
        result = await session.exec(statement)
        return result.first()

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
        async with self._session() as session:
            result = await session.exec(
                select(SessionTable.id).where(SessionTable.id == session_id)
            )
            return result.first() is not None

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
        now = _now_utc()
        session_row = SessionTable(
            id=session_id,
            title=title,
            created_at=now,
            updated_at=now,
        )
        async with self._session() as session:
            session.add(session_row)
            await session.commit()
            await session.refresh(session_row)
        return self._table_to_session(session_row)

    async def get_session(self, session_id: str) -> SessionRecord | None:
        """Get a session by ID.

        Args:
            session_id: The session UUID.

        Returns:
            SessionRecord if found, None otherwise.
        """
        async with self._session() as session:
            session_row = await self._get_session_row(
                session,
                session_id,
                require_active=True,
            )
            if session_row is None:
                return None
            return self._table_to_session(session_row)

    async def list_sessions(self) -> list[SessionSummary]:
        """List all active sessions with message counts.

        Returns:
            List of SessionSummary objects.
        """
        statement = (
            select(SessionTable, func.count(MessageTable.id))
            .outerjoin(MessageTable, SessionTable.id == MessageTable.session_id)
            .where(SessionTable.is_active.is_(True))
            .group_by(
                SessionTable.id,
                SessionTable.title,
                SessionTable.created_at,
                SessionTable.updated_at,
                SessionTable.is_active,
                SessionTable.pending_state,
                SessionTable.selected_provider_id,
                SessionTable.fallback_mode,
            )
            .order_by(SessionTable.updated_at.desc())
        )
        async with self._session() as session:
            result = await session.exec(statement)
            return [
                self._table_to_summary(session_row, int(message_count or 0))
                for session_row, message_count in result.all()
            ]

    async def update_session_preferences(
        self, session_id: str, fields: dict[str, object]
    ) -> SessionRecord | None:
        """Update session-level provider/fallback preferences."""
        if not fields:
            return await self.get_session(session_id)

        async with self._session() as session:
            session_row = await self._get_session_row(
                session,
                session_id,
                require_active=True,
            )
            if session_row is None:
                return None

            for key, value in fields.items():
                normalized_value = value
                if key == "fallback_mode" and value is not None:
                    normalized_value = (
                        value
                        if isinstance(value, FallbackMode)
                        else FallbackMode(str(value))
                    )
                setattr(session_row, key, normalized_value)

            session_row.updated_at = _now_utc()
            session.add(session_row)
            await session.commit()
            await session.refresh(session_row)
            return self._table_to_session(session_row)

    async def clear_invalid_selected_providers(
        self,
        valid_provider_ids: set[str],
    ) -> int:
        """Clear session-level provider preferences that no longer exist.

        Args:
            valid_provider_ids: Provider IDs that remain valid after a settings update.

        Returns:
            Number of sessions whose selected_provider_id was cleared.
        """
        async with self._session() as session:
            statement = select(SessionTable).where(
                SessionTable.selected_provider_id.is_not(None)
            )
            result = await session.exec(statement)
            session_rows = result.all()

            updated_count = 0
            for session_row in session_rows:
                selected_provider_id = session_row.selected_provider_id
                if (
                    selected_provider_id is not None
                    and selected_provider_id not in valid_provider_ids
                ):
                    session_row.selected_provider_id = None
                    session_row.updated_at = _now_utc()
                    session.add(session_row)
                    updated_count += 1

            if updated_count > 0:
                await session.commit()

            return updated_count

    async def update_session_title(
        self,
        session_id: str,
        title: str,
    ) -> SessionRecord | None:
        """Update the user-visible title for a session."""
        async with self._session() as session:
            session_row = await self._get_session_row(
                session,
                session_id,
                require_active=True,
            )
            if session_row is None:
                return None

            session_row.title = title
            session_row.updated_at = _now_utc()
            session.add(session_row)
            await session.commit()
            await session.refresh(session_row)
            return self._table_to_session(session_row)

    async def update_current_leaf(
        self,
        session_id: str,
        current_leaf_node_id: str | None,
    ) -> SessionRecord | None:
        """Update the current visible conversation-tree leaf for a session."""
        async with self._session() as session:
            session_row = await self._get_session_row(
                session,
                session_id,
                require_active=True,
            )
            if session_row is None:
                return None

            session_row.current_leaf_node_id = current_leaf_node_id
            session_row.updated_at = _now_utc()
            session.add(session_row)
            await session.commit()
            await session.refresh(session_row)
            return self._table_to_session(session_row)

    async def delete_session(self, session_id: str) -> bool:
        """Soft-delete a session.

        Args:
            session_id: The session UUID.

        Returns:
            True if session was found and deleted.
        """
        async with self._session() as session:
            session_row = await self._get_session_row(
                session,
                session_id,
                require_active=True,
            )
            if session_row is None:
                return False

            session_row.is_active = False
            session.add(session_row)
            await session.commit()
            return True

    # ---- Message persistence ----

    async def add_message(self, msg: MessageRecord) -> MessageRecord:
        """Persist a message and update session timestamp.

        Args:
            msg: The message to persist.

        Returns:
            The persisted MessageRecord with assigned ID.
        """
        tool_calls_json = json.dumps(msg.tool_calls) if msg.tool_calls else None
        message_row = MessageTable(
            session_id=msg.session_id,
            role=msg.role,
            content=msg.content,
            tool_call_id=msg.tool_call_id,
            tool_calls=tool_calls_json,
            status=msg.status,
            created_at=msg.created_at,
            ordinal=msg.ordinal,
        )
        async with self._session() as session:
            session_row = await session.get(SessionTable, msg.session_id)
            if session_row is None:
                raise ValueError(f"Unknown session: {msg.session_id}")

            session.add(message_row)
            session_row.updated_at = _now_utc()
            if msg.role == MessageRole.HUMAN and session_row.title == "":
                session_row.title = msg.content[:80]
            session.add(session_row)

            await session.commit()
            await session.refresh(message_row)

        msg.id = message_row.id
        return msg

    async def get_messages(self, session_id: str) -> list[MessageRecord]:
        """Get all messages for a session in order.

        Args:
            session_id: The session UUID.

        Returns:
            Ordered list of MessageRecord objects.
        """
        statement = (
            select(MessageTable)
            .where(MessageTable.session_id == session_id)
            .order_by(MessageTable.ordinal.asc())
        )
        async with self._session() as session:
            result = await session.exec(statement)
            return [self._table_to_message(row) for row in result.all()]

    async def get_next_ordinal(self, session_id: str) -> int:
        """Get the next ordinal for a new message.

        Args:
            session_id: The session UUID.

        Returns:
            The next ordinal value.
        """
        statement = select(func.max(MessageTable.ordinal)).where(
            MessageTable.session_id == session_id
        )
        async with self._session() as session:
            result = await session.exec(statement)
            max_ordinal = result.one()
            if max_ordinal is None:
                return 0
            return int(max_ordinal) + 1

    async def persist_partial_response(
        self,
        session_id: str,
        user_content: str,
        assistant_content: str,
        assistant_status: MessageStatus,
    ) -> SessionDetail | None:
        """Persist a user message and partial assistant output."""
        session = await self.get_session(session_id)
        if session is None:
            return None

        next_ordinal = await self.get_next_ordinal(session_id)
        await self.add_message(
            MessageRecord(
                session_id=session_id,
                role=MessageRole.HUMAN,
                content=user_content,
                status=MessageStatus.COMPLETED,
                ordinal=next_ordinal,
            )
        )
        await self.add_message(
            MessageRecord(
                session_id=session_id,
                role=MessageRole.AI,
                content=assistant_content,
                status=assistant_status,
                ordinal=next_ordinal + 1,
            )
        )
        return await self.get_session_detail(session_id)

    async def persist_interrupted_messages(
        self,
        session_id: str,
        user_content: str,
        assistant_content: str,
    ) -> SessionDetail | None:
        """Backward-compatible helper for interrupted partial output."""
        return await self.persist_partial_response(
            session_id,
            user_content,
            assistant_content,
            MessageStatus.INTERRUPTED,
        )

    # ---- ReAct resume support ----

    async def save_pending_state(self, session_id: str, pending: dict | None) -> None:
        """Save in-flight tool call state for crash recovery.

        Args:
            session_id: The session UUID.
            pending: The pending tool call state dict, or None to clear.
        """
        state_json = json.dumps(pending) if pending else None
        async with self._session() as session:
            session_row = await session.get(SessionTable, session_id)
            if session_row is None:
                return
            session_row.pending_state = state_json
            session.add(session_row)
            await session.commit()

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
    def _table_to_session(row: SessionTable) -> SessionRecord:
        """Convert a SQLModel row to a SessionRecord."""
        pending = json.loads(row.pending_state) if row.pending_state else None
        fallback_mode = (
            row.fallback_mode
            if isinstance(row.fallback_mode, FallbackMode)
            else FallbackMode(row.fallback_mode or "manual")
        )
        return SessionRecord(
            id=row.id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
            is_active=row.is_active,
            pending_state=pending,
            selected_provider_id=row.selected_provider_id,
            fallback_mode=fallback_mode,
            current_leaf_node_id=row.current_leaf_node_id,
        )

    @classmethod
    def _table_to_summary(
        cls,
        row: SessionTable,
        message_count: int,
    ) -> SessionSummary:
        """Convert a SQLModel row to a SessionSummary."""
        session_record = cls._table_to_session(row)
        return SessionSummary(
            id=session_record.id,
            title=session_record.title,
            created_at=session_record.created_at,
            updated_at=session_record.updated_at,
            message_count=message_count,
            can_resume=session_record.pending_state is not None,
            selected_provider_id=session_record.selected_provider_id,
            fallback_mode=session_record.fallback_mode,
        )

    @staticmethod
    def _table_to_message(row: MessageTable) -> MessageRecord:
        """Convert a SQLModel row to a MessageRecord."""
        tool_calls = json.loads(row.tool_calls) if row.tool_calls else None
        role = row.role if isinstance(row.role, MessageRole) else MessageRole(row.role)
        status = (
            row.status
            if isinstance(row.status, MessageStatus)
            else MessageStatus(row.status or "completed")
        )
        return MessageRecord(
            id=row.id,
            session_id=row.session_id,
            role=role,
            content=row.content,
            tool_call_id=row.tool_call_id,
            tool_calls=tool_calls,
            status=status,
            created_at=row.created_at,
            ordinal=row.ordinal,
        )
