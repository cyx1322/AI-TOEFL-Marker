import json
import logging
import uuid

from fastapi import APIRouter, Form, HTTPException, status, Depends
from app.services.llm import generate_text_response
from app.services.prompt_loader import (
    WRITING_IMPROVEMENT_PROMPT_TEMPLATE, 
    WRITING_RUBRIC
    )
from app.services.auth import get_current_user_id
from app.schemas import WritingImprovementsRequest

router = APIRouter(prefix="/api/writing-improvement", tags=["writing"])

ALLOWED_MODELS = ["gemini-2.5-pro","gemini-3-flash-preview"]

logger = logging.getLogger(__name__)

def _validate_model_choice(model_choice: str) -> None:
    if model_choice not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported model '{model_choice}'. Allowed: {', '.join(sorted(ALLOWED_MODELS))}.",
        )



@router.post("")
async def writing_improvements_endpoint(
    req: WritingImprovementsRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
):
    """Generate improved TOEFL writing responses using prior feedback."""
    question_text, answer_text, feedback_text, model_choice = req.question_text, req.answer_text, req.feedback_text, req.model_choice
    _validate_model_choice(req.model_choice)

    if not question_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question text must not be empty.",
        )

    if not answer_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Student response must not be empty.",
        )

    if not feedback_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Feedback text must not be empty.",
        )

    final_prompt = WRITING_IMPROVEMENT_PROMPT_TEMPLATE.format(
        rubric=WRITING_RUBRIC,
        question=question_text.strip(),
        answer=answer_text.strip(),
        feedback=feedback_text.strip(),
    )

    try:
        improvements_text, _ = generate_text_response(
            final_prompt,
            model=model_choice,
            include_thoughts=False,
        )
    except (RuntimeError, ValueError) as exc:
        logger.error("Generating writing improvements failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate writing improvements.",
        ) from exc

    return {"improvements_markdown": improvements_text}
