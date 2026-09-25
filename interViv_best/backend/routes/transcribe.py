from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.routes.auth import require_authenticated
from fastapi.responses import JSONResponse

router = APIRouter(dependencies=[Depends(require_authenticated)])

_MODEL = None
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def get_model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    return _MODEL


@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)) -> JSONResponse:
    data = await audio.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large (max 10 MB)")

    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    tmp_path: str | None = None
    try:
        model = get_model()
    except Exception:
        return JSONResponse(status_code=503, content={"error": "transcription_unavailable"})

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        segments, _ = model.transcribe(tmp_path, language="en")
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return JSONResponse({"text": text})
    except Exception:
        return JSONResponse(status_code=503, content={"error": "transcription_unavailable"})
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
