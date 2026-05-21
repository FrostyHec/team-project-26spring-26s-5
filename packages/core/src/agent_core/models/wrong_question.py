"""Data models for wrong question book."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class WrongQuestion(BaseModel):
    """A wrong question stored in the book."""

    id: int | None = None
    question_id: int
    question_type: Literal[
        "multiple_choice", "true_false", "fill_blank", "short_answer"
    ]
    question: str
    options: list[str] | None = None
    correct_answer: str
    explanation: str | None = None
    source_session_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WrongQuestionCreate(BaseModel):
    """Request model for creating a wrong question."""

    question_id: int
    question_type: Literal[
        "multiple_choice", "true_false", "fill_blank", "short_answer"
    ]
    question: str
    options: list[str] | None = None
    correct_answer: str
    explanation: str | None = None
    source_session_id: str | None = None


class WrongQuestionResponse(BaseModel):
    """Response model for a wrong question."""

    id: int
    question_id: int
    question_type: str
    question: str
    options: list[str] | None = None
    correct_answer: str
    explanation: str | None = None
    source_session_id: str | None = None
    created_at: datetime


class WrongQuestionListResponse(BaseModel):
    """Response model for listing wrong questions."""

    questions: list[WrongQuestionResponse]
