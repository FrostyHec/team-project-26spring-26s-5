"""Quiz evaluation route — delegates to QuizEvaluationService."""

from fastapi import APIRouter, Depends
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from agent_core.api.dependencies import get_llm
from agent_core.api.routes.utils import get_language
from agent_core.models.course_assistant import (
    QuestionEvaluation,
    QuizQuestion,
)
from agent_core.services.evaluation import QuizEvaluationService

router = APIRouter()


class EvaluateRequest(BaseModel):
    """Request body for quiz evaluation.

    Attributes:
        questions: List of quiz questions with correct answers.
        user_answers: Dict mapping question id (str) to user's answer.
        use_ai_grading: Whether to use LLM for fill_blank/short_answer questions.
            When False, fill_blank uses exact match scoring and short_answer
            is not scored (total_score_included=False).
    """

    questions: list[QuizQuestion]
    user_answers: dict[str, str]
    use_ai_grading: bool = True


class EvaluateResponse(BaseModel):
    """Response body from the synchronous chat endpoint.

    Attributes:
        evaluations: Dict mapping question id (str) to evaluation result.
    """

    evaluations: dict[str, QuestionEvaluation]


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_quiz(
    request: EvaluateRequest,
    language: str = Depends(get_language),
    llm: ChatOpenAI = Depends(get_llm),
) -> EvaluateResponse:
    """Evaluate user quiz answers.

    Scoring strategy per question type:
    - **multiple_choice / true_false**: always auto-scored against correct_answer
      (no LLM call, no use_ai_grading effect).
    - **fill_blank**: when use_ai_grading=true the LLM decides correctness; when
      false (or the LLM returns unparseable output) an exact-match fallback is
      applied.
    - **short_answer**: when use_ai_grading=true the LLM returns a 0–10 score which
      is scaled to the question's max score; when false the question is not scored
      (score=0, total_score_included=False) so the answer is shown to the student
      without a computed grade.

    When the LLM is unavailable or returns malformed JSON for fill_blank, the
    exact-match fallback is used and the analysis field carries a service-
    unavailable message. For short_answer the fallback always yields score=0.

    The language for prompts is determined by the X-Language header
    sent from the frontend (defaults to English).

    Args:
        request: Questions and user answers.
        language: Language code from X-Language header.
        llm: Injected ChatOpenAI instance.

    Returns:
        Evaluation results for each question with score, standard answer,
        and detailed analysis.
    """
    service = QuizEvaluationService(llm, language)
    evaluations = await service.evaluate_all(
        request.questions,
        request.user_answers,
        request.use_ai_grading,
    )
    return EvaluateResponse(evaluations=evaluations)
