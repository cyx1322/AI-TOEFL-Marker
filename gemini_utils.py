import logging
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


def _load_client() -> genai.Client:
    """Load Gemini API client with basic error handling."""
    load_dotenv()
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise RuntimeError("API_KEY environment variable is not set.")
    try:
        return genai.Client(api_key=api_key)
    except Exception as exc:  # pragma: no cover - depends on external SDK behaviour
        raise RuntimeError("Failed to initialize Gemini client.") from exc


client = _load_client()


def _sniff_mime(b: bytes) -> str:
    # WAV: 'RIFF'....'WAVE'
    try:
        if len(b) >= 12 and b[0:4] == b"RIFF" and b[8:12] == b"WAVE":
            return "audio/wav"
    except Exception:
        pass
    # MP3: ID3 tag or frame sync 0xFFEx
    if b[:3] == b"ID3":
        return "audio/mpeg"
    if len(b) >= 2 and b[0] == 0xFF and (b[1] & 0xE0) == 0xE0:
        return "audio/mpeg"
    # Fallback to MPEG
    return "audio/mpeg"


def _iter_audio_items(data):
    """Yield (bytes, mime) pairs from supported inputs with validation."""
    if isinstance(data, (bytes, bytearray, memoryview)):
        b = bytes(data)
        yield b, _sniff_mime(b)
        return
    if isinstance(data, (list, tuple)):
        if not data:
            raise ValueError("audio_data list must not be empty.")
        for idx, item in enumerate(data):
            if isinstance(item, (bytes, bytearray, memoryview)):
                b = bytes(item)
                yield b, _sniff_mime(b)
            elif (
                isinstance(item, (list, tuple))
                and len(item) == 2
                and isinstance(item[0], (bytes, bytearray, memoryview))
                and isinstance(item[1], str)
            ):
                b = bytes(item[0])
                mime = item[1]
                yield b, mime
            else:
                raise TypeError(
                    f"audio_data[{idx}] must be bytes-like or (bytes_like, mime_type) pair."
                )
        return
    raise TypeError(
        "audio_data must be bytes-like or a list/tuple of bytes-like or (bytes, mime) pairs."
    )


def _stream_generate_content(contents, model: str, include_thoughts: bool = True):
    """Yield structured events from Gemini's streaming API."""
    config_kwargs = {}
    if include_thoughts:
        config_kwargs["config"] = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                include_thoughts=True,
            ),
        )
    try:
        stream = client.models.generate_content_stream(
            model=model,
            contents=contents,
            **config_kwargs,
        )
    except Exception as exc:
        logger.error("Streaming request failed: %s", exc)
        raise RuntimeError("Failed to start Gemini streaming response.") from exc

    thought_fragments: list[str] = []
    thoughts_sent = False

    try:
        for chunk in stream:
            if not getattr(chunk, "candidates", None):
                continue
            candidate = chunk.candidates[0]
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []):
                text = getattr(part, "text", "")
                if not text:
                    continue
                if include_thoughts and getattr(part, "thought", False) and not thoughts_sent:
                    thought_fragments.append(text)
                    continue
                if include_thoughts and not thoughts_sent:
                    summary = "".join(thought_fragments).strip()
                    if summary:
                        yield {"type": "thoughts", "text": summary}
                    thoughts_sent = True
                yield {"type": "answer", "text": text}
    except Exception as exc:
        logger.error("Error while streaming Gemini content: %s", exc)
        raise RuntimeError("Gemini streaming failed mid-response.") from exc

    if include_thoughts and not thoughts_sent:
        summary = "".join(thought_fragments).strip()
        if summary:
            yield {"type": "thoughts", "text": summary}

    yield {"type": "done"}


def stream_audio_understanding(
    audio_data,
    model: str = "gemini-2.5-flash",
    prompt: str = "Summarize the audio using text.",
    include_thoughts: bool = True,
):
    """Stream structured events for an audio-understanding prompt."""
    audio_parts = [
        types.Part.from_bytes(data=b, mime_type=m)
        for (b, m) in _iter_audio_items(audio_data)
    ]
    contents = [prompt, *audio_parts]
    yield from _stream_generate_content(contents, model=model, include_thoughts=include_thoughts)


def stream_writing_feedback(
    prompt_text: str,
    model: str = "gemini-2.5-flash",
    include_thoughts: bool = True,
):
    """Stream structured events for a writing feedback prompt."""
    if not isinstance(prompt_text, str) or not prompt_text.strip():
        raise ValueError("prompt_text must be a non-empty string.")
    contents = [prompt_text]
    yield from _stream_generate_content(contents, model=model, include_thoughts=include_thoughts)


def _collect_stream_events(stream, require_answer: bool = True):
    answer_fragments: list[str] = []
    thought_fragments: list[str] = []
    for event in stream:
        event_type = event.get("type") if isinstance(event, dict) else None
        if event_type == "answer":
            answer_fragments.append(event.get("text", ""))
        elif event_type == "thoughts":
            thought_fragments.append(event.get("text", ""))
    answer = "".join(answer_fragments).strip()
    thoughts = "".join(thought_fragments).strip()
    if require_answer and not answer:
        raise ValueError("Gemini API did not return text for the provided input.")
    return answer, thoughts


def audio_understanding(audio_data, model="gemini-2.5-flash", prompt="Summarize the audio using text."):
    """Send audio clips to Gemini and return the aggregated textual summary."""
    answer, _ = _collect_stream_events(
        stream_audio_understanding(audio_data, model=model, prompt=prompt)
    )
    return answer


def writing_feedback(prompt_text: str, model: str = "gemini-2.5-flash") -> str:
    """Generate feedback on a writing submission using the provided prompt."""
    answer, _ = _collect_stream_events(
        stream_writing_feedback(prompt_text, model=model)
    )
    return answer


def generate_audio_response(
    audio_data,
    prompt: str,
    model: str = "gemini-2.5-flash",
    include_thoughts: bool = True,
):
    """Return aggregated Gemini response (and optional thoughts) for audio prompts."""
    return _collect_stream_events(
        stream_audio_understanding(
            audio_data,
            model=model,
            prompt=prompt,
            include_thoughts=include_thoughts,
        )
    )


def generate_text_response(
    prompt_text: str,
    model: str = "gemini-2.5-flash",
    include_thoughts: bool = True,
):
    """Return aggregated Gemini response (and optional thoughts) for text prompts."""
    return _collect_stream_events(
        stream_writing_feedback(
            prompt_text,
            model=model,
            include_thoughts=include_thoughts,
        )
    )
