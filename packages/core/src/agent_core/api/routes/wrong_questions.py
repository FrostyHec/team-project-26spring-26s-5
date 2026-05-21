"""Wrong question book API routes."""

from fastapi import APIRouter, Depends, HTTPException

from agent_core.api.dependencies import get_wrong_question_service
from agent_core.models.wrong_question import (
    WrongQuestionCreate,
    WrongQuestionListResponse,
    WrongQuestionResponse,
)
from agent_core.services.wrong_question_service import WrongQuestionService

router = APIRouter(prefix="/wrong-questions", tags=["wrong-questions"])


@router.post("", response_model=WrongQuestionResponse)
async def add_wrong_question(
    data: WrongQuestionCreate,
    service: WrongQuestionService = Depends(get_wrong_question_service),
) -> WrongQuestionResponse:
    """Add a question to the wrong question book.

    If the question already exists (same question_id and source_session_id),
    returns the existing entry without creating a duplicate.
    """
    result = await service.add_wrong_question(data)
    return WrongQuestionResponse(
        id=result.id,  # type: ignore[arg-type]
        question_id=result.question_id,
        question_type=result.question_type,
        question=result.question,
        options=result.options,
        correct_answer=result.correct_answer,
        explanation=result.explanation,
        source_session_id=result.source_session_id,
        created_at=result.created_at,
    )


@router.get("", response_model=WrongQuestionListResponse)
async def list_wrong_questions(
    type: str | None = None,
    service: WrongQuestionService = Depends(get_wrong_question_service),
) -> WrongQuestionListResponse:
    """List all wrong questions.

    Query params:
        type: Filter by question type
            (multiple_choice, true_false, fill_blank, short_answer)
    """
    return await service.list_wrong_questions(type)


@router.delete("/{question_id}")
async def delete_wrong_question(
    question_id: int,
    service: WrongQuestionService = Depends(get_wrong_question_service),
) -> dict[str, str]:
    """Delete a wrong question by ID.

    Returns 404 if the question does not exist.
    """
    success = await service.delete_wrong_question(question_id)
    if not success:
        raise HTTPException(status_code=404, detail="Wrong question not found")
    return {"status": "deleted"}
