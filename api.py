from pathlib import Path
from typing import List, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from starlette import status

from gemini_utils import audio_understanding, writing_feedback

app = FastAPI()

ALLOWED_MODELS = {"gemini-2.5-flash", "gemini-2.5-pro"}

_BASE_DIR = Path(__file__).resolve().parent


def _load_markdown(filename: str) -> str:
    try:
        return (_BASE_DIR / filename).read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - depends on deployment environment
        raise RuntimeError(f"Unable to load rubric file '{filename}'.") from exc


SPEAKING_RUBRIC = _load_markdown("speaking-rubric.md")
WRITING_RUBRIC = _load_markdown("writing-rubric.md")

MARKER_PROMPT_TEMPLATE = """
Assume you are a marker for the TOEFL test. Grade the following student's speaking test.
If there are two audio files, then one is the question (a dialogue or monologue); the other is the student's answer.
RUBRICS:
```
{rubric}
```
QUESTION:
{question}

"""

WRITING_PROMPT_TEMPLATE = """
You are a TOEFL writing evaluator. Review the student's response based on the CRITERIA below.

CRITERIA:
```
{rubric}
```

QUESTION:
{question}

STUDENT RESPONSE:
{answer}

Provide detailed feedback and a score estimate in Markdown format. Include strengths, weaknesses, and actionable suggestions tied to the criteria.
"""


@app.post("/speaking-feedback")
async def speaking_feedback(
    guidance_text: str = Form(..., description="Question in text."),
    question_audio: UploadFile | None = File(None, description="Question Audio (Optional)."),
    answer_audio: UploadFile | None = File(None, description="Student's Answer (MP3 or WAV)."),
    model_choice: str = Form("gemini-2.5-flash", description="Gemini model to use."),
    # Backward-compatible field names used by the existing frontend
    audio_clip_one: UploadFile | None = File(None, description="Alt field: First audio clip."),
    audio_clip_two: UploadFile | None = File(None, description="Alt field: Second audio clip."),
) -> dict:
    """Provide feedback on up to two TOEFL speaking practice clips."""

    final_prompt = MARKER_PROMPT_TEMPLATE.format(
        rubric=SPEAKING_RUBRIC,
        question=f"**{guidance_text.strip()}**",
    )

    if model_choice not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported model '{model_choice}'. Allowed: {', '.join(sorted(ALLOWED_MODELS))}.",
        )
    # Collect up to two clips from any of the accepted field names
    candidates = [question_audio, answer_audio, audio_clip_one, audio_clip_two]
    audio_files = [clip for clip in candidates if clip is not None][:2]

    if not audio_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one audio clip must be provided.",
        )

    def _map_mime(ct: str | None) -> str | None:
        if not ct:
            return None
        ct = ct.lower()
        if ct in {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"}:
            return "audio/wav"
        if ct in {"audio/mpeg", "audio/mp3", "audio/mpeg3", "audio/x-mp3", "audio/x-mpeg-3"}:
            return "audio/mpeg"
        return None

    audio_payloads: List[Tuple[bytes, str | None]] = []
    for index, audio in enumerate(audio_files, start=1):
        try:
            data = await audio.read()
        except Exception as exc:  # pragma: no cover - depends on file backend
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to read audio clip {index}.",
            ) from exc
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Audio clip {index} is empty.",
            )
        audio_payloads.append((data, _map_mime(getattr(audio, "content_type", None))))

    try:
        # Pass (bytes, mime) items when available; the helper will sniff if None
        formatted = [
            (b, m) if m is not None else (b,)
            for (b, m) in audio_payloads
        ]
        if len(formatted) == 1:
            one = formatted[0]
            if len(one) == 1:
                payload = one[0]  # bytes only; helper will sniff
            else:
                payload = [one]   # list with (bytes, mime)
        else:
            payload = formatted  # list of items
        feedback = audio_understanding(payload, prompt=final_prompt, model=model_choice)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {
        "feedback": feedback,
        "clips_received": len(audio_payloads),
    }


@app.post("/writing-feedback")
async def writing_feedback_endpoint(
    question_text: str = Form(..., description="Writing task question."),
    answer_text: str = Form(..., description="Student's written response."),
    model_choice: str = Form("gemini-2.5-flash", description="Gemini model to use."),
) -> dict:
    """Return Gemini-generated feedback for a TOEFL writing task."""

    if model_choice not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported model '{model_choice}'. Allowed: {', '.join(sorted(ALLOWED_MODELS))}.",
        )

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

    final_prompt = WRITING_PROMPT_TEMPLATE.format(
        rubric=WRITING_RUBRIC,
        question=question_text.strip(),
        answer=answer_text.strip(),
    )

    try:
        feedback = writing_feedback(final_prompt, model=model_choice)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return {"feedback": feedback}
