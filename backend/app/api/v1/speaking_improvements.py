import json
import logging

from fastapi import APIRouter, File, Form, HTTPException, status, UploadFile

from app.services.audio_process import load_audio_payloads, format_audio_payloads
from app.services.llm import generate_audio_response

from app.services.prompt_loader import (
    SPEAKING_IMPROVEMENT_PROMPT_TEMPLATE, 
    SPEAKING_RUBRIC
    )

router = APIRouter(prefix="/api/speaking-improvement", tags=["speaking"])

ALLOWED_MODELS = ["gemini-2.5-pro","gemini-3-flash-preview"]

logger = logging.getLogger(__name__)

def _validate_model_choice(model_choice: str) -> None:
    if model_choice not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported model '{model_choice}'. Allowed: {', '.join(sorted(ALLOWED_MODELS))}.",
        )



@router.post("")
async def speaking_improvements(
    guidance_text: str = Form(..., description="Question in text."),
    feedback_text: str = Form(..., description="Full feedback generated previously."),
    prompt_audio: UploadFile | None = File(None, description="Prompt audio (optional)."),
    response_audio: UploadFile | None = File(None, description="Student's response audio (MP3 or WAV)."),
    model_choice: str = Form("gemini-2.5-flash", description="Gemini model to use."),
):
    """Generate improved speaking responses using prior feedback and original audio."""

    _validate_model_choice(model_choice)

    if not feedback_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback text must not be empty.",
        )

    if response_audio is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student response audio must be provided.",
        )

    payloads = await load_audio_payloads([prompt_audio, response_audio])
    if not payloads:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one audio clip must be provided.",
        )

    final_prompt = SPEAKING_IMPROVEMENT_PROMPT_TEMPLATE.format(
        rubric=SPEAKING_RUBRIC,
        question=f"**{guidance_text.strip()}**",
        feedback=feedback_text.strip(),
    )

    audio_input = format_audio_payloads(payloads)

    try:
        improvements_text, _ = generate_audio_response(
            audio_input,
            prompt=final_prompt,
            model=model_choice,
            include_thoughts=False,
        )
    except (RuntimeError, ValueError) as exc:
        logger.error("Generating speaking improvements failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate speaking improvements.",
        ) from exc

    return {"improvements_markdown": improvements_text}
