"""AV capability inspection (server-side). Browser permission is client-only."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _whisper_cache_present() -> bool:
    """True when a local faster-whisper / whisper HF cache dir exists.

    Does not download or construct a model (offline-safe probe).
    """
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    if not hub.is_dir():
        return False
    for child in hub.iterdir():
        name = child.name.lower()
        if "whisper" in name and child.is_dir():
            return True
    return False


def transcription_status() -> dict[str, Any]:
    """Probe faster-whisper import + local model cache without downloading."""
    try:
        import faster_whisper  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "reason": "service_unavailable",
            "detail": f"faster_whisper import failed: {type(exc).__name__}",
        }
    if not _whisper_cache_present():
        return {
            "available": False,
            "reason": "service_unavailable",
            "detail": "whisper model cache missing (no download attempted)",
        }
    return {
        "available": True,
        "reason": None,
        "detail": "faster_whisper importable with local whisper cache",
    }


def av_capability_report() -> dict[str, Any]:
    """Honest capability matrix for Phase E.

    Device capture and permission states are browser-side; this report only
    covers server-backed pieces. Video recording retention and speech scoring
    are not offered in E.1.
    """
    transcription = transcription_status()
    return {
        "device_capture": {
            "available": None,
            "reason": "client_only",
            "detail": (
                "Microphone/camera permission is determined in the browser "
                "(permission_not_requested / denied / no_device / "
                "unsupported_browser)."
            ),
        },
        "transcription": transcription,
        "interview_interaction": {
            "available": True,
            "reason": None,
            "detail": "Existing Interview page supports timed free-text rounds.",
        },
        "video_recording": {
            "available": False,
            "reason": "not_implemented",
            "detail": (
                "E.2: durable owned video artifacts need binary storage and "
                "retention tooling (ffmpeg absent; no blob column)."
            ),
        },
        "speech_scoring": {
            "available": False,
            "reason": "not_offered",
            "detail": (
                "No fluency or speech readiness score. Unavailable audio never "
                "contributes a zero to aggregates."
            ),
        },
        "feedback": {
            "available": True,
            "reason": None,
            "detail": (
                "Text answers use the existing deterministic interview scorer. "
                "Transcripts, when present, are text only."
            ),
        },
        "unavailable_states": [
            "permission_not_requested",
            "permission_denied",
            "no_device",
            "unsupported_browser",
            "service_unavailable",
            "capture_failed",
            "interrupted_recoverable",
        ],
    }
