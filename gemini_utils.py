import os
import logging

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

def audio_understanding(audio_data, model="gemini-2.5-flash", prompt="Summarize the audio using text."):
    """Send one or more audio clips to Gemini and return the textual summary.

    audio_data can be:
      - a single bytes-like object (audio clip)
      - a list/tuple of bytes-like objects (multiple clips)
      - a list/tuple of (bytes_like, mime_type) pairs for explicit type control

    Supported types include MP3 and WAV. If a mime type is not provided,
    a best-effort sniff is used to choose between 'audio/wav' and 'audio/mpeg'.
    """

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

    audio_parts = [
        types.Part.from_bytes(data=b, mime_type=m)
        for (b, m) in _iter_audio_items(audio_data)
    ]

    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                prompt,
                *audio_parts,
            ],
        )
    except Exception as exc:
        logger.error("Audio understanding request failed: %s", exc)
        raise RuntimeError("Failed to process audio with Gemini.") from exc

    if not getattr(response, "text", None):
        raise ValueError("Gemini API did not return text for the provided audio.")

    return response.text


def writing_feedback(prompt_text: str, model: str = "gemini-2.5-flash") -> str:
    """Generate feedback on a writing submission using the provided prompt."""
    if not isinstance(prompt_text, str) or not prompt_text.strip():
        raise ValueError("prompt_text must be a non-empty string.")

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt_text,
        )
    except Exception as exc:  # pragma: no cover - depends on external API call
        logger.error("Writing feedback request failed: %s", exc)
        raise RuntimeError("Failed to generate writing feedback with Gemini.") from exc

    if not getattr(response, "text", None):
        raise ValueError("Gemini API did not return text for the writing prompt.")

    return response.text
