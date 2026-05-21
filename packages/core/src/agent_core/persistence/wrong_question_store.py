"""SQLite-backed wrong question persistence — SQLModel async ORM."""

import json
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from agent_core.logging_utils import get_logger
from agent_core.models.wrong_question import WrongQuestion, WrongQuestionCreate

logger = get_logger("persistence.wrong_question")


class WrongQuestionTable(SQLModel, table=True):
    """SQLModel table for wrong questions."""

    __tablename__ = "wrong_questions"

    id: int | None = SQLField(default=None, primary_key=True)
    question_id: int = SQLField()
    question_type: str = SQLField()
    question: str = SQLField()
    options: str | None = SQLField(default=None)  # JSON string
    correct_answer: str = SQLField()
    explanation: str | None = SQLField(default=None)
    source_session_id: str | None = SQLField(default=None)
    created_at: datetime = SQLField(default_factory=lambda: datetime.now(UTC))


class WrongQuestionStore:
    """Async SQLite store for wrong questions (SQLModel ORM)."""

    def __init__(self, db_path: str = "wrong_questions.db") -> None:
        self.db_path = db_path
        self._engine = None  # type: ignore[assignment]

    @property
    def is_connected(self) -> bool:
        return self._engine is not None

    async def initialize(self) -> None:
        url = f"sqlite+aiosqlite:///{self.db_path}"
        self._engine = create_async_engine(url, echo=False)
        async with self._engine.begin() as conn:
            await conn.run_sync(WrongQuestionTable.metadata.create_all)
        logger.info("WrongQuestion store initialised at %s", self.db_path)

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    def _session(self) -> AsyncSession:
        if self._engine is None:
            msg = "WrongQuestionStore not initialised — call initialize() first"
            raise RuntimeError(msg)
        return AsyncSession(self._engine)

    def _table_to_model(self, row: WrongQuestionTable) -> WrongQuestion:
        """Convert table row to Pydantic model."""
        options: list[str] | None = None
        if row.options:
            options = json.loads(row.options)
        return WrongQuestion(
            id=row.id,
            question_id=row.question_id,
            question_type=row.question_type,  # type: ignore[arg-type]
            question=row.question,
            options=options,
            correct_answer=row.correct_answer,
            explanation=row.explanation,
            source_session_id=row.source_session_id,
            created_at=row.created_at,
        )

    async def add(self, data: WrongQuestionCreate) -> WrongQuestion:
        """Add a new wrong question."""
        # Check for duplicates
        existing = await self._get_by_question_and_session(
            data.question_id, data.source_session_id
        )
        if existing:
            logger.debug(
                "Duplicate wrong question: question_id=%s, session=%s",
                data.question_id,
                data.source_session_id,
            )
            return self._table_to_model(existing)

        table = WrongQuestionTable(
            question_id=data.question_id,
            question_type=data.question_type,
            question=data.question,
            options=json.dumps(data.options) if data.options else None,
            correct_answer=data.correct_answer,
            explanation=data.explanation,
            source_session_id=data.source_session_id,
            created_at=datetime.now(UTC),
        )
        async with self._session() as session:
            session.add(table)
            await session.commit()
            await session.refresh(table)
        logger.debug("Added wrong question: question_id=%s", data.question_id)
        return self._table_to_model(table)

    async def _get_by_question_and_session(
        self, question_id: int, source_session_id: str | None
    ) -> WrongQuestionTable | None:
        """Find existing question by question_id and source_session_id."""
        statement = select(WrongQuestionTable).where(
            WrongQuestionTable.question_id == question_id,
            WrongQuestionTable.source_session_id == source_session_id,
        )
        async with self._session() as session:
            result = await session.exec(statement)
            return result.first()

    async def list_all(self, question_type: str | None = None) -> list[WrongQuestion]:
        """List all wrong questions, optionally filtered by type."""
        statement = select(WrongQuestionTable)
        if question_type:
            statement = statement.where(
                WrongQuestionTable.question_type == question_type
            )
        statement = statement.order_by(WrongQuestionTable.created_at.desc())
        async with self._session() as session:
            results = await session.exec(statement)
            return [self._table_to_model(row) for row in results.all()]

    async def get(self, question_id: int) -> WrongQuestion | None:
        """Get a wrong question by its ID."""
        async with self._session() as session:
            row = await session.get(WrongQuestionTable, question_id)
            if row is None:
                return None
            return self._table_to_model(row)

    async def delete(self, question_id: int) -> bool:
        """Delete a wrong question by its ID."""
        async with self._session() as session:
            row = await session.get(WrongQuestionTable, question_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            logger.debug("Deleted wrong question: id=%s", question_id)
            return True
