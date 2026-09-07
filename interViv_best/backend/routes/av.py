"""Phase E AV capability and owned system-design attempt surfaces.

Audio/video binary artifacts are not stored in E.1. This router exposes:
- honest capability status (no fabricated transcripts or speech scores)
- ownership-scoped read/delete of system-design attempts
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, status

from backend.db import DatabaseConnectionError, get_database
from backend.routes.auth import require_user
from modules.av_capabilities import av_capability_report

router = APIRouter(tags=["av"])

# Retention policy (documented for operators and candidates).
AV_RETENTION = {
    "audio_video_artifacts": (
        "E.1 does not persist audio or video blobs. Capture stays in the "
        "browser; server transcription receives a temporary upload that is "
        "deleted after processing and never written to durable storage."
    ),
    "transcription": (
        "Only the returned transcript text may be pasted into an answer by "
        "the candidate. The server does not retain upload bytes."
    ),
    "system_design_attempts": (
        "Owned by the submitting user. Deletable by the owner. Never exposed "
        "in catalogs or to other users."
    ),
    "speech_scoring": "Not offered. Unavailable audio never contributes a score.",
}


@router.get("/av/capabilities")
def get_av_capabilities(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Auth optional for capability probe; no private data returned."""
    _ = authorization  # probe is public; auth unused
    report = av_capability_report()
    report["retention"] = AV_RETENTION
    return report


@router.get("/av/system-design-attempts")
def list_system_design_attempts(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    rows = list(db["system_design_attempts"].find({"user_id": user["id"]}))
    # Never expose storage paths (none exist) or other users' rows.
    safe = [
        {
            "id": r.get("id"),
            "session_id": r.get("session_id"),
            "round": r.get("round"),
            "prompt_id": r.get("prompt_id"),
            "evaluation_mode": r.get("evaluation_mode"),
            "status": r.get("status"),
            "score": r.get("score"),
            "incomplete": r.get("incomplete"),
            "rubric_json": r.get("rubric_json") or {},
            "created_at": (
                r["created_at"].isoformat()
                if hasattr(r.get("created_at"), "isoformat")
                else r.get("created_at")
            ),
            # answer_text is user-owned content; include for the owner only.
            "answer_text": r.get("answer_text") or "",
        }
        for r in rows
    ]
    return {"attempts": safe, "count": len(safe)}


@router.delete("/av/system-design-attempts/{attempt_id}")
def delete_system_design_attempt(
    attempt_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    row = db["system_design_attempts"].find_one({"id": attempt_id})
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found."
        )
    if str(row.get("user_id")) != str(user["id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot delete another user's data.",
        )
    db["system_design_attempts"].delete_one({"id": attempt_id})
    return {"deleted": True, "id": attempt_id}
