import logging

from fastapi import APIRouter, File, Form, HTTPException, status, UploadFile
from fastapi.responses import StreamingResponse

from app.services.audio_process import load_audio_payloads, format_audio_payloads
from app.services.llm import stream_writing_feedback, streaming_response, ndjson

from app.services.prompt_loader import (
    WRITING_FEEDBACK_PROMPT_TEMPLATE, 
    WRITING_RUBRIC
    )

router = APIRouter(prefix="/api/writing-feedback", tags=["writing"])

ALLOWED_MODELS = ["gemini-2.5-pro","gemini-3-flash-preview"]

logger = logging.getLogger(__name__)

def _validate_model_choice(model_choice: str) -> None:
    if model_choice not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported model '{model_choice}'. Allowed: {', '.join(sorted(ALLOWED_MODELS))}.",
        )



@router.post("")
async def writing_feedback_endpoint(
    question_text: str = Form(..., description="Writing task question."),
    answer_text: str = Form(..., description="Student's written response."),
    model_choice: str = Form("gemini-2.5-flash", description="Gemini model to use."),
) -> StreamingResponse:
    """Stream Gemini-generated feedback for a TOEFL writing task."""

    _validate_model_choice(model_choice)

    if not question_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question text must not be empty.",
        )

    if not answer_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student response must not be empty.",
        )

    final_prompt = WRITING_FEEDBACK_PROMPT_TEMPLATE.format(
        rubric=WRITING_RUBRIC,
        question=question_text.strip(),
        answer=answer_text.strip(),
    )

    def _event_stream():
        try:
            for event in stream_writing_feedback(
                final_prompt,
                model=model_choice,
                include_thoughts=True,
            ):
                yield ndjson(event)
        except (RuntimeError, ValueError) as exc:
            logger.error("Streaming writing feedback failed: %s", exc)
            yield ndjson({"type": "error", "message": str(exc)})
            yield ndjson({"type": "done"})

    return streaming_response(_event_stream())
