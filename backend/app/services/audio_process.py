from fastapi import HTTPException, UploadFile
from typing import List, Tuple
from starlette import status

async def load_audio_payloads(candidates: List[UploadFile | None]) -> List[Tuple[bytes, str | None]]:
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

def _map_mime(ct: str | None) -> str | None:
    if not ct:
        return None
    ct = ct.lower()
    if ct in {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"}:
        return "audio/wav"
    if ct in {"audio/mpeg", "audio/mp3", "audio/mpeg3", "audio/x-mp3", "audio/x-mpeg-3"}:
        return "audio/mpeg"
    return None

def format_audio_payloads(payloads: List[Tuple[bytes, str | None]]):
    formatted = []
    for data, mime in payloads:
        if mime:
            formatted.append((data, mime))
        else:
            formatted.append(data)
    return formatted
