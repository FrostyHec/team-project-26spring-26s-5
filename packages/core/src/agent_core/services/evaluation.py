"""Quiz evaluation service — single source of truth for grading business logic.

Encapsulates scoring strategy, LLM invocation, fallback handling, and result
construction. Both the REST API controller and LLM tool functions delegate to
this service so that business rules are defined in exactly one place.

Architecture note (validation layers):
  - Controller/DTO: format validation (Pydantic types, enum types)
  - Service (this file): semantic/business logic (scoring, AI grading, fallback)
  - LLM: called by service for fill_blank/short_answer AI grading
"""

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agent_core.logging_utils import get_logger
from agent_core.models.course_assistant import (
    QuestionEvaluation,
    QuizQuestion,
)
from agent_core.prompts_loader import (
    DEFAULT_LANGUAGE,
    build_evaluation_prompt,
    get_evaluation_prompt,
    get_fallback_message,
)

logger = get_logger("services.evaluation")

# ---------------------------------------------------------------------------
# Magic numbers — single source of truth for default scores
# ---------------------------------------------------------------------------

DEFAULT_SCORE_MULTIPLE_CHOICE = 3.0
DEFAULT_SCORE_TRUE_FALSE = 1.0
DEFAULT_SCORE_FILL_BLANK = 5.0
DEFAULT_SCORE_SHORT_ANSWER = 10.0

# short_answer LLM score is on a 0–10 scale, scaled to question max_score
LLM_SCORE_MAX = 10.0

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AI_GRADING_TYPES = ("short_answer", "fill_blank")
"""Question types that support AI-assisted grading."""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _get_default_score(question: QuizQuestion) -> float:
    """Return the default max score for a question type when not specified."""
    match question.type:
        case "multiple_choice":
            return DEFAULT_SCORE_MULTIPLE_CHOICE
        case "true_false":
            return DEFAULT_SCORE_TRUE_FALSE
        case "fill_blank":
            return DEFAULT_SCORE_FILL_BLANK
        case "short_answer":
            return DEFAULT_SCORE_SHORT_ANSWER
        case _:
            return DEFAULT_SCORE_FILL_BLANK  # safe fallback


def _parse_llm_json_response(content: str) -> dict[str, Any]:
    """Extract and parse JSON from LLM response content."""
    json_start = content.find("{")
    json_end = content.rfind("}") + 1
    if json_start != -1 and json_end > json_start:
        return json.loads(content[json_start:json_end])
    return json.loads(content)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class QuizEvaluationService:
    """Quiz evaluation business logic — scoring, AI grading, and fallback."""

    def __init__(self, llm: ChatOpenAI, language: str = DEFAULT_LANGUAGE) -> None:
        """Initialize the service.

        Args:
            llm: ChatOpenAI instance for AI grading.
            language: Language code for prompts and fallback messages.
        """
        self._llm = llm
        self._language = language

    async def evaluate_all(
        self,
        questions: list[QuizQuestion],
        user_answers: dict[str, str],
        use_ai_grading: bool = True,
    ) -> dict[str, QuestionEvaluation]:
        """Evaluate all quiz questions.

        Args:
            questions: List of quiz questions with correct answers.
            user_answers: Dict mapping question id (str) to user's answer.
            use_ai_grading: Whether to use LLM for fill_blank/short_answer.

        Returns:
            Dict mapping question id to evaluation result.
        """
        evaluations: dict[str, QuestionEvaluation] = {}

        for question in questions:
            question_id = str(question.id)

            if question.type not in AI_GRADING_TYPES:
                evaluations[question_id] = self._evaluate_auto(
                    question, user_answers.get(question_id)
                )
                continue

            user_answer = user_answers.get(question_id, "")

            if question.type == "fill_blank" and not use_ai_grading:
                evaluations[question_id] = self._evaluate_fill_blank_exact(
                    question, user_answer
                )
                continue

            if question.type == "short_answer" and not use_ai_grading:
                evaluations[question_id] = self._evaluate_short_answer_manual(
                    question, user_answer
                )
                continue

            # AI grading path
            if not user_answer.strip():
                evaluations[question_id] = self._evaluate_empty_answer(question)
                continue

            evaluations[question_id] = await self._evaluate_with_ai(
                question, user_answer
            )

        return evaluations

    def _evaluate_auto(
        self,
        question: QuizQuestion,
        user_answer: str | None,
    ) -> QuestionEvaluation:
        """Auto-score multiple_choice and true_false questions."""
        max_score = (
            question.score
            if question.score is not None
            else _get_default_score(question)
        )
        user_answered = user_answer == question.correct_answer
        analysis_key = (
            "auto_scored" if question.type == "true_false" else "choice_no_manual"
        )
        return QuestionEvaluation(
            score=max_score if user_answered else 0.0,
            standard_answer=question.correct_answer,
            analysis=get_fallback_message(analysis_key, self._language),
            total_score_included=True,
        )

    def _evaluate_fill_blank_exact(
        self,
        question: QuizQuestion,
        user_answer: str,
    ) -> QuestionEvaluation:
        """Exact-match scoring for fill_blank when AI is disabled."""
        max_score = (
            question.score if question.score is not None else DEFAULT_SCORE_FILL_BLANK
        )
        correct = user_answer.strip() == question.correct_answer.strip()
        return QuestionEvaluation(
            score=max_score if correct else 0.0,
            standard_answer=question.correct_answer,
            analysis=get_fallback_message("auto_scored", self._language),
            total_score_included=True,
        )

    def _evaluate_short_answer_manual(
        self,
        question: QuizQuestion,
        user_answer: str,
    ) -> QuestionEvaluation:
        """Manual scoring placeholder for short_answer when AI is disabled."""
        return QuestionEvaluation(
            score=0.0,
            standard_answer=question.correct_answer,
            analysis="",
            total_score_included=False,
        )

    def _evaluate_empty_answer(self, question: QuizQuestion) -> QuestionEvaluation:
        """Score 0 for empty user answer, no LLM call."""
        return QuestionEvaluation(
            score=0.0,
            standard_answer=question.correct_answer,
            analysis=get_fallback_message("no_answer", self._language),
            total_score_included=True,
        )

    async def _evaluate_with_ai(
        self,
        question: QuizQuestion,
        user_answer: str,
    ) -> QuestionEvaluation:
        """Evaluate a single question using the LLM."""
        system_prompt = get_evaluation_prompt(question.type, self._language)
        prompt = build_evaluation_prompt(
            question.id,
            question.type,
            question.question,
            question.correct_answer,
            question.explanation or "",
            user_answer,
            self._language,
        )

        try:
            response = await self._llm.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=prompt),
                ],
            )
            content = (
                response.content if hasattr(response, "content") else str(response)
            )
            parsed = _parse_llm_json_response(content)

            if question.type == "fill_blank":
                return self._build_fill_blank_result(question, parsed)
            else:
                return self._build_short_answer_result(question, parsed)

        except (json.JSONDecodeError, ValueError, TypeError, Exception):
            logger.exception("LLM evaluation failed for question %s", question.id)
            return self._build_fallback_result(question, user_answer)

    def _build_fill_blank_result(
        self,
        question: QuizQuestion,
        parsed: dict[str, Any],
    ) -> QuestionEvaluation:
        """Build result for fill_blank from LLM-parsed JSON."""
        correct = parsed.get("correct", False)
        max_score = (
            question.score if question.score is not None else DEFAULT_SCORE_FILL_BLANK
        )
        return QuestionEvaluation(
            score=max_score if correct else 0.0,
            standard_answer=question.correct_answer,
            analysis=parsed.get(
                "analysis", get_fallback_message("no_analysis", self._language)
            ),
            total_score_included=True,
        )

    def _build_short_answer_result(
        self,
        question: QuizQuestion,
        parsed: dict[str, Any],
    ) -> QuestionEvaluation:
        """Build result for short_answer from LLM-parsed JSON."""
        raw_score = float(parsed.get("score", 0.0))
        raw_score = max(0.0, min(LLM_SCORE_MAX, raw_score))
        max_score = (
            question.score if question.score is not None else DEFAULT_SCORE_SHORT_ANSWER
        )
        max_score = max(0.0, max_score)
        score = (raw_score / LLM_SCORE_MAX) * max_score
        return QuestionEvaluation(
            score=score,
            standard_answer=parsed.get("standard_answer", question.correct_answer),
            analysis=parsed.get(
                "analysis", get_fallback_message("no_analysis", self._language)
            ),
            total_score_included=True,
        )

    def _build_fallback_result(
        self,
        question: QuizQuestion,
        user_answer: str,
    ) -> QuestionEvaluation:
        """Build fallback result when LLM call fails."""
        if question.type == "fill_blank":
            max_score = (
                question.score
                if question.score is not None
                else DEFAULT_SCORE_FILL_BLANK
            )
            correct = user_answer.strip() == question.correct_answer.strip()
            return QuestionEvaluation(
                score=max_score if correct else 0.0,
                standard_answer=question.correct_answer,
                analysis=get_fallback_message(
                    "service_unavailable_auto", self._language
                ),
                total_score_included=True,
            )
        else:
            return QuestionEvaluation(
                score=0.0,
                standard_answer=question.correct_answer,
                analysis=get_fallback_message(
                    "service_unavailable_manual", self._language
                ),
                total_score_included=True,
            )
