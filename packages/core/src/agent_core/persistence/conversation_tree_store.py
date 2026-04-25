"""Conversation tree persistence store."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from agent_core.logging_utils import get_logger
from agent_core.models.session import (
    ChatNodeBookmarkTable,
    ChatNodeRecord,
    ChatNodeTable,
    ChatVersionSelectionTable,
    NodeLeafBookmarkRecord,
    VersionGroupSelectionRecord,
)

logger = get_logger("persistence.conversation_tree")


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(UTC)


class ConversationTreeStore:
    """Persistence layer for conversation tree nodes and branch state."""

    def __init__(
        self,
        db_path: str = "sessions.db",
        *,
        engine: AsyncEngine | None = None,
    ) -> None:
        self.db_path = db_path
        self._engine: AsyncEngine | None = engine
        self._owns_engine = engine is None

    async def initialize(self) -> None:
        """Create the async engine and ensure tree tables exist."""
        if self._engine is None:
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
            await conn.run_sync(self._ensure_chat_node_columns)

        logger.info("Conversation tree store initialized at %s", self.db_path)

    @staticmethod
    def _create_schema(connection: object) -> None:
        """Create the conversation tree tables if they do not exist."""
        ChatNodeTable.__table__.create(connection, checkfirst=True)
        ChatVersionSelectionTable.__table__.create(connection, checkfirst=True)
        ChatNodeBookmarkTable.__table__.create(connection, checkfirst=True)

    @staticmethod
    def _ensure_chat_node_columns(connection: object) -> None:
        """Add newer tree-node columns for existing databases."""
        existing_columns = {
            column["name"] for column in inspect(connection).get_columns("chat_nodes")
        }

        if "tool_calls" not in existing_columns:
            connection.execute(
                text("ALTER TABLE chat_nodes ADD COLUMN tool_calls TEXT")
            )
        if "trace_steps" not in existing_columns:
            connection.execute(
                text("ALTER TABLE chat_nodes ADD COLUMN trace_steps TEXT")
            )

    async def close(self) -> None:
        """Close the database engine."""
        if self._engine is not None and self._owns_engine:
            await self._engine.dispose()
            self._engine = None

    @property
    def db(self) -> AsyncEngine:
        """Return the active database engine."""
        if self._engine is None:
            raise RuntimeError(
                "ConversationTreeStore not initialized — call initialize() first"
            )
        return self._engine

    def _session(self) -> AsyncSession:
        """Create a new async ORM session."""
        return AsyncSession(self.db, expire_on_commit=False)

    async def add_node(self, node: ChatNodeRecord) -> ChatNodeRecord:
        """Persist a conversation node."""
        payload = node.model_dump()
        payload["tool_calls"] = (
            json.dumps(node.tool_calls) if node.tool_calls is not None else None
        )
        payload["trace_steps"] = (
            json.dumps(node.trace_steps) if node.trace_steps is not None else None
        )
        row = ChatNodeTable(**payload)
        async with self._session() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return self._table_to_node(row)

    async def add_versioned_node(
        self,
        node: ChatNodeRecord,
        *,
        max_retries: int = 3,
    ) -> ChatNodeRecord:
        """Persist a node with conflict retry on version_index uniqueness."""
        attempt = 0
        candidate = node
        while True:
            try:
                return await self.add_node(candidate)
            except IntegrityError:
                attempt += 1
                if attempt > max_retries:
                    raise
                next_index = (
                    await self.get_max_version_index(
                        candidate.session_id,
                        candidate.version_group_id,
                    )
                    + 1
                )
                candidate = candidate.model_copy(update={"version_index": next_index})

    async def get_node(self, session_id: str, node_id: str) -> ChatNodeRecord | None:
        """Return a node by session and node ID."""
        statement = select(ChatNodeTable).where(
            ChatNodeTable.session_id == session_id,
            ChatNodeTable.id == node_id,
        )
        async with self._session() as session:
            result = await session.exec(statement)
            row = result.first()
            return self._table_to_node(row) if row is not None else None

    async def update_node(
        self,
        session_id: str,
        node_id: str,
        fields: dict[str, object],
    ) -> ChatNodeRecord | None:
        """Update mutable node fields."""
        async with self._session() as session:
            statement = select(ChatNodeTable).where(
                ChatNodeTable.session_id == session_id,
                ChatNodeTable.id == node_id,
            )
            result = await session.exec(statement)
            row = result.first()
            if row is None:
                return None
            for key, value in fields.items():
                if key in {"tool_calls", "trace_steps"}:
                    setattr(row, key, json.dumps(value) if value is not None else None)
                    continue
                setattr(row, key, value)
            row.updated_at = _utcnow()
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._table_to_node(row)

    async def list_nodes(self, session_id: str) -> list[ChatNodeRecord]:
        """List all nodes for a session in created_at order."""
        statement = (
            select(ChatNodeTable)
            .where(ChatNodeTable.session_id == session_id)
            .order_by(ChatNodeTable.created_at.asc(), ChatNodeTable.id.asc())
        )
        async with self._session() as session:
            result = await session.exec(statement)
            return [self._table_to_node(row) for row in result.all()]

    async def list_version_group_nodes(
        self,
        session_id: str,
        version_group_id: str,
    ) -> list[ChatNodeRecord]:
        """List all nodes in a version group."""
        statement = (
            select(ChatNodeTable)
            .where(
                ChatNodeTable.session_id == session_id,
                ChatNodeTable.version_group_id == version_group_id,
            )
            .order_by(ChatNodeTable.version_index.asc(), ChatNodeTable.created_at.asc())
        )
        async with self._session() as session:
            result = await session.exec(statement)
            return [self._table_to_node(row) for row in result.all()]

    async def get_max_version_index(
        self, session_id: str, version_group_id: str
    ) -> int:
        """Return the current max version index for a version group."""
        nodes = await self.list_version_group_nodes(session_id, version_group_id)
        if not nodes:
            return -1
        return max(node.version_index for node in nodes)

    async def upsert_version_selection(
        self,
        record: VersionGroupSelectionRecord,
    ) -> VersionGroupSelectionRecord:
        """Persist the selected node for a version group."""
        payload = record.model_dump()
        statement = insert(ChatVersionSelectionTable).values(payload)
        statement = statement.on_conflict_do_update(
            index_elements=["session_id", "version_group_id"],
            set_={
                "selected_node_id": payload["selected_node_id"],
                "updated_at": payload["updated_at"],
            },
        )
        async with self._session() as session:
            await session.exec(statement)
            await session.commit()
        return record

    async def get_version_selection(
        self,
        session_id: str,
        version_group_id: str,
    ) -> VersionGroupSelectionRecord | None:
        """Return the persisted selected node for a version group."""
        statement = select(ChatVersionSelectionTable).where(
            ChatVersionSelectionTable.session_id == session_id,
            ChatVersionSelectionTable.version_group_id == version_group_id,
        )
        async with self._session() as session:
            result = await session.exec(statement)
            row = result.first()
            return self._table_to_version_selection(row) if row is not None else None

    async def upsert_node_bookmark(
        self,
        record: NodeLeafBookmarkRecord,
    ) -> NodeLeafBookmarkRecord:
        """Persist the preferred descendant leaf for a node."""
        payload = record.model_dump()
        statement = insert(ChatNodeBookmarkTable).values(payload)
        statement = statement.on_conflict_do_update(
            index_elements=["session_id", "node_id"],
            set_={
                "selected_leaf_id": payload["selected_leaf_id"],
                "updated_at": payload["updated_at"],
            },
        )
        async with self._session() as session:
            await session.exec(statement)
            await session.commit()
        return record

    async def get_node_bookmark(
        self,
        session_id: str,
        node_id: str,
    ) -> NodeLeafBookmarkRecord | None:
        """Return the stored bookmark for a node, if any."""
        statement = select(ChatNodeBookmarkTable).where(
            ChatNodeBookmarkTable.session_id == session_id,
            ChatNodeBookmarkTable.node_id == node_id,
        )
        async with self._session() as session:
            result = await session.exec(statement)
            row = result.first()
            return self._table_to_node_bookmark(row) if row is not None else None

    @staticmethod
    def _table_to_node(row: ChatNodeTable) -> ChatNodeRecord:
        """Convert an ORM row to a tree node record."""
        payload = row.model_dump()
        payload["tool_calls"] = json.loads(row.tool_calls) if row.tool_calls else None
        payload["trace_steps"] = (
            json.loads(row.trace_steps) if row.trace_steps else None
        )
        return ChatNodeRecord.model_validate(payload)

    @staticmethod
    def _table_to_version_selection(
        row: ChatVersionSelectionTable,
    ) -> VersionGroupSelectionRecord:
        """Convert an ORM row to a version selection record."""
        return VersionGroupSelectionRecord.model_validate(row.model_dump())

    @staticmethod
    def _table_to_node_bookmark(
        row: ChatNodeBookmarkTable,
    ) -> NodeLeafBookmarkRecord:
        """Convert an ORM row to a node bookmark record."""
        return NodeLeafBookmarkRecord.model_validate(row.model_dump())
