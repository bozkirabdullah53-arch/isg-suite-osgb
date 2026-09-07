from __future__ import annotations
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from app.api.deps import get_current_user
from app.core.config import contextual_assistant_active, contextual_assistant_transcription_active, settings
from app.models.entities import User
from app.services.contextual_assistant import (
    TRANSCRIPTION_UNAVAILABLE_MESSAGE,
    UNAVAILABLE_MESSAGE,
    TranscriptionUnavailableError,
    answer,
    transcribe_audio,
)

router = APIRouter(prefix="/assistant", tags=["Contextual OHS Assistant"])

class ContextualAssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    context: dict = Field(default_factory=dict)

@router.post("/contextual")
def contextual_assistant(payload: ContextualAssistantRequest, user: User = Depends(get_current_user)):
    if not contextual_assistant_active():
        raise HTTPException(status_code=503, detail=UNAVAILABLE_MESSAGE)
    try:
        return answer(question=payload.question, raw_context=payload.context, user=user)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=UNAVAILABLE_MESSAGE) from exc


_TRANSCRIPTION_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "application/ogg",
}
_TRANSCRIPTION_EXTENSIONS = {"webm", "ogg", "oga", "mp4", "m4a", "mp3", "wav"}


def _transcription_limit_bytes() -> int:
    try:
        megabytes = int(getattr(settings, "contextual_assistant_transcription_max_mb", 5) or 5)
    except (TypeError, ValueError):
        megabytes = 5
    return max(1, min(megabytes, 10)) * 1024 * 1024


@router.post("/transcribe")
async def contextual_assistant_transcribe(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    if not contextual_assistant_transcription_active():
        raise HTTPException(status_code=503, detail=TRANSCRIPTION_UNAVAILABLE_MESSAGE)

    content_type = str(file.content_type or "").split(";", 1)[0].strip().lower()
    filename = str(file.filename or "voice.webm").strip()
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if not (
        content_type.startswith("audio/")
        or content_type in _TRANSCRIPTION_TYPES
        or extension in _TRANSCRIPTION_EXTENSIONS
    ):
        raise HTTPException(status_code=415, detail="Ses dosyası biçimi desteklenmiyor.")

    payload = await file.read(_transcription_limit_bytes() + 1)
    if len(payload) > _transcription_limit_bytes():
        raise HTTPException(
            status_code=413,
            detail="Ses kaydı çok uzun veya büyük. Daha kısa bir kayıt deneyin.",
        )
    if not payload:
        raise HTTPException(status_code=400, detail="Ses kaydı boş geldi.")

    safe_extension = extension if extension in _TRANSCRIPTION_EXTENSIONS else "webm"
    try:
        text = transcribe_audio(
            audio_bytes=payload,
            filename=f"voice.{safe_extension}",
            content_type=content_type or "audio/webm",
        )
    except TranscriptionUnavailableError as exc:
        raise HTTPException(status_code=503, detail=TRANSCRIPTION_UNAVAILABLE_MESSAGE) from exc
    return {"text": text}
