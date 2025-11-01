import json
import logging
from pathlib import Path
from typing import List, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from starlette import status
from fastapi.staticfiles import StaticFiles

from gemini_utils import (
    generate_audio_response,
    generate_text_response,
    stream_audio_understanding,
    stream_writing_feedback,
)

logger = logging.getLogger(__name__)

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

SPEAKING_FEEDBACK_PROMPT_TEMPLATE = """
You are a certified TOEFL speaking evaluator. Listen to the student's response audio and assess it using the rubric below.

RUBRIC:
```
{rubric}
```

TASK PROMPT:
{question}

Write markdown feedback for the student with the following structure:

## Overall Evaluation
- Provide the score (0-4) with a brief justification.
- Summarize the student's overall performance in 2-3 sentences.

## Strengths
- Bullet list of concrete, encouraging observations tied to the rubric.

## Priority Improvements
- Bullet list of actionable advice tailored to this student's current proficiency.

Do not propose improved or rewritten responses in this section.
"""

SPEAKING_IMPROVEMENT_PROMPT_TEMPLATE = """
You are now the student's TOEFL speaking coach. Using the evaluation below, craft improved responses that the student could realistically deliver next time.

RUBRIC:
```
{rubric}
```

TASK PROMPT:
{question}

EVALUATION (do not repeat verbatim, use for guidance):
{feedback}

Listen again to the student's original audio response (provided). Produce exactly two improved responses that:
- Preserve the student's intent and personality.
- Incorporate the priority improvements from the evaluation.
- Sound natural for a learner at the student's current level.

Format the output in markdown as:

## Improved Response 1
<full transcript>

## Improved Response 2
<full transcript>

Do not provide scores or additional commentary beyond the improved transcripts.
"""

WRITING_FEEDBACK_PROMPT_TEMPLATE = """
You are a TOEFL writing evaluator. Review the student's essay according to the rubric below.

RUBRIC:
```
{rubric}
```

TASK PROMPT:
{question}

STUDENT RESPONSE:
{answer}

Write markdown feedback for the student with the following structure:

## Overall Evaluation
- Provide the score (0-5) with a concise justification (2-3 sentences).

## Strengths
- Bullet list of specific positives tied to the rubric categories.

## Priority Improvements
- Bullet list of the highest-impact revisions the student should focus on.

Do not rewrite the essay or provide improved versions in this section.
"""

WRITING_IMPROVEMENT_PROMPT_TEMPLATE = """
You are now the student's TOEFL writing tutor. Using the evaluation below, deliver two revised essays that the student can study and emulate.

RUBRIC:
```
{rubric}
```

TASK PROMPT:
{question}

EVALUATION (for reference):
{feedback}

ORIGINAL ESSAY:
{answer}

Produce exactly two improved essays that:
- Directly address the same task prompt.
- Incorporate the feedback while keeping a realistic tone and length for the student.
- Highlight better organization, vocabulary, and grammar without sounding far beyond the student's level.

Format the output in markdown as:

## Improved Essay 1
<full revised essay>

## Improved Essay 2
<full revised essay>

Do not include scores or additional commentary outside of the essays.
"""


def _map_mime(ct: str | None) -> str | None:
    if not ct:
        return None
    ct = ct.lower()
    if ct in {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"}:
        return "audio/wav"
    if ct in {"audio/mpeg", "audio/mp3", "audio/mpeg3", "audio/x-mp3", "audio/x-mpeg-3"}:
        return "audio/mpeg"
    return None


async def _load_audio_payloads(candidates: List[UploadFile | None]) -> List[Tuple[bytes, str | None]]:
    payloads: List[Tuple[bytes, str | None]] = []
    clips: List[UploadFile] = [clip for clip in candidates if clip is not None][:2]
    for index, audio in enumerate(clips, start=1):
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
        payloads.append((data, _map_mime(getattr(audio, "content_type", None))))
    return payloads


def _format_audio_payloads(payloads: List[Tuple[bytes, str | None]]):
    formatted = []
    for data, mime in payloads:
        if mime:
            formatted.append((data, mime))
        else:
            formatted.append(data)
    return formatted


def _validate_model_choice(model_choice: str) -> None:
    if model_choice not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported model '{model_choice}'. Allowed: {', '.join(sorted(ALLOWED_MODELS))}.",
        )


@app.post("/speaking-feedback")
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

    payloads = await _load_audio_payloads([prompt_audio, response_audio])
    if not payloads:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one audio clip must be provided.",
        )

    audio_input = _format_audio_payloads(payloads)
    clips_received = len(payloads)

    def _event_stream():
        yield _ndjson({"type": "meta", "clips_received": clips_received})
        try:
            for event in stream_audio_understanding(
                audio_input,
                model=model_choice,
                prompt=final_prompt,
                include_thoughts=True,
            ):
                yield _ndjson(event)
        except (RuntimeError, ValueError) as exc:
            logger.error("Streaming speaking feedback failed: %s", exc)
            yield _ndjson({"type": "error", "message": str(exc)})
            yield _ndjson({"type": "done"})

    return _streaming_response(_event_stream())


@app.post("/speaking-improvements")
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

    payloads = await _load_audio_payloads([prompt_audio, response_audio])
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

    audio_input = _format_audio_payloads(payloads)

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


@app.post("/writing-feedback")
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
                yield _ndjson(event)
        except (RuntimeError, ValueError) as exc:
            logger.error("Streaming writing feedback failed: %s", exc)
            yield _ndjson({"type": "error", "message": str(exc)})
            yield _ndjson({"type": "done"})

    return _streaming_response(_event_stream())


@app.post("/writing-improvements")
async def writing_improvements_endpoint(
    question_text: str = Form(..., description="Writing task question."),
    answer_text: str = Form(..., description="Student's written response."),
    feedback_text: str = Form(..., description="Feedback generated previously."),
    model_choice: str = Form("gemini-2.5-flash", description="Gemini model to use."),
):
    """Generate improved TOEFL writing responses using prior feedback."""

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

    if not feedback_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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


NDJSON_MEDIA_TYPE = "application/x-ndjson"


def _streaming_response(generator):
    headers = {
        "X-Accel-Buffering": "no",
        "Cache-Control": "no-cache",
    }
    return StreamingResponse(generator, media_type=NDJSON_MEDIA_TYPE, headers=headers)


def _ndjson(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")

# Serve frontend (index.html) for all other requests
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")