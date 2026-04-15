import logging

from fastapi import APIRouter, File, Form, HTTPException, status, UploadFile
from fastapi.responses import StreamingResponse

from app.services.audio_process import load_audio_payloads, format_audio_payloads
from app.services.llm import stream_audio_understanding, streaming_response, ndjson

from app.services.prompt_loader import (
    SPEAKING_FEEDBACK_PROMPT_TEMPLATE, 
    SPEAKING_RUBRIC
    )

router = APIRouter(prefix="/api/speaking-feedback", tags=["speaking"])

ALLOWED_MODELS = ["gemini-2.5-pro","gemini-3-flash-preview"]

logger = logging.getLogger(__name__)

def _validate_model_choice(model_choice: str) -> None:
    if model_choice not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported model '{model_choice}'. Allowed: {', '.join(sorted(ALLOWED_MODELS))}.",
        )



@router.post("")
async def speaking_feedback(
    guidance_text: str = Form(..., description="Question in text."),
    prompt_audio: UploadFile | None = File(None, description="Prompt audio (optional)."),
    response_audio: UploadFile | None = File(None, description="Student's response audio (MP3 or WAV)."),
    model_choice: str = Form("gemini-2.5-flash", description="Gemini model to use."),
) -> StreamingResponse:
    """Stream rubric-based feedback on up to two TOEFL speaking clips."""

    _validate_model_choice(model_choice)

    final_prompt = SPEAKING_FEEDBACK_PROMPT_TEMPLATE.format(
        rubric=SPEAKING_RUBRIC,
        question=f"**{guidance_text.strip()}**",
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

    audio_input = format_audio_payloads(payloads)
    clips_received = len(payloads)

    def _event_stream():
        yield ndjson({"type": "meta", "clips_received": clips_received})
        try:
            for event in stream_audio_understanding(
                audio_input,
                model=model_choice,
                prompt=final_prompt,
                include_thoughts=True,
            ):
                yield ndjson(event)
        except (RuntimeError, ValueError) as exc:
            logger.error("Streaming speaking feedback failed: %s", exc)
            yield ndjson({"type": "error", "message": str(exc)})
            yield ndjson({"type": "done"})

    return streaming_response(_event_stream())
