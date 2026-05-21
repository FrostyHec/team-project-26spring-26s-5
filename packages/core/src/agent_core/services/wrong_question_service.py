"""Service layer for wrong question book operations."""

from agent_core.models.wrong_question import (
    WrongQuestion,
    WrongQuestionCreate,
    WrongQuestionListResponse,
    WrongQuestionResponse,
)
from agent_core.persistence.wrong_question_store import WrongQuestionStore


class WrongQuestionService:
    """Business logic for wrong question book."""

    def __init__(self, store: WrongQuestionStore) -> None:
        self._store = store

    async def add_wrong_question(self, data: WrongQuestionCreate) -> WrongQuestion:
        """Add a question to the wrong question book."""
        return await self._store.add(data)

    async def list_wrong_questions(
        self, question_type: str | None = None
    ) -> WrongQuestionListResponse:
        """List all wrong questions, optionally filtered by type."""
        questions = await self._store.list_all(question_type)
        return WrongQuestionListResponse(
            questions=[
                WrongQuestionResponse(
                    id=q.id,  # type: ignore[arg-type]
                    question_id=q.question_id,
                    question_type=q.question_type,
                    question=q.question,
                    options=q.options,
                    correct_answer=q.correct_answer,
                    explanation=q.explanation,
                    source_session_id=q.source_session_id,
                    created_at=q.created_at,
                )
                for q in questions
            ]
        )

    async def get_wrong_question(self, question_id: int) -> WrongQuestion | None:
        """Get a single wrong question by ID."""
        return await self._store.get(question_id)

    async def delete_wrong_question(self, question_id: int) -> bool:
        """Delete a wrong question by ID."""
        return await self._store.delete(question_id)
