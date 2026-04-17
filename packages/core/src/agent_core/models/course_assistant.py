"""Course assistant data models — structured types for quiz and document analysis.

Provides Pydantic models for quiz generation, document analysis, and related
functionality used by the course assistant skill and tools.
"""

from typing import Literal

from pydantic import BaseModel

from agent_core.models.events import WidgetData, WidgetType


class QuizQuestion(BaseModel):
    """A single quiz question with answer and explanation."""

    id: int
    type: Literal["multiple_choice", "true_false", "fill_blank", "short_answer"]
    question: str
    options: list[str] | None = None
    correct_answer: str
    explanation: str | None = None
    score: float | None = None  # Question score, None means use default


class QuizWidgetData(WidgetData):
    """Payload for the quiz widget."""

    widget_type: Literal[WidgetType.QUIZ] = WidgetType.QUIZ
    title: str = "Practice Quiz"
    questions: list[QuizQuestion] = []
    show_answers: bool = False
    source_content_preview: str = ""
    metadata: dict = {}


class QuestionEvaluation(BaseModel):
    """Evaluation result for a single question."""

    score: float
    standard_answer: str
    analysis: str
    total_score_included: bool = True


class QuizEvaluationData(BaseModel):
    """Evaluation result for all questions in a quiz."""

    evaluations: dict[str, QuestionEvaluation] = {}
