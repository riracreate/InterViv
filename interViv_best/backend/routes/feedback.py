"""Candidate feedback delivery for a scored session round (Phase 3B).

Returns committed rules feedback immediately plus a bounded narration status.
Response is an explicit allowlist — never snapshots, ideals, calibration,
prompts, or scoring-breakdown internals beyond the listed fields.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status

from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.integrations import normalize_feedback
from backend.routes.auth import require_authenticated
from backend.routes.session_access import (
    assert_session_access,
    session_assessment_completed,
)
from modules.narration_jobs import narration_job_id
from modules.teaching_exposures import record_teaching_exposure
from modules.assistance_policy import item_identity_for_round
from modules.follow_ups import is_inline_bundle_follow_up_round

router = APIRouter(prefix="/session", tags=["feedback"])

_TERMINAL_WITH_SCRIPT = frozenset({"done", "skipped"})
_KNOWN_STATUSES = frozenset({
    "queued", "processing", "done", "failed", "skipped", "unavailable",
})


def _round_submitted(round_doc: dict[str, Any]) -> bool:
    if round_doc.get("final_score") is not None:
        return True
    return str(round_doc.get("status") or "").lower() == "submitted"


def _feedback_allowlist(feedback: Any) -> dict[str, Any]:
    normalized = normalize_feedback(feedback or {})
    return {
        "content": list(normalized.get("content") or []),
        "strengths": list(normalized.get("strengths") or []),
        "weakness": list(normalized.get("weakness") or []),
        "next_step": normalized.get("next_step") or "",
    }


def _narration_payload(
    job: dict[str, Any] | None,
    *,
    assessment_completed: bool,
) -> dict[str, Any]:
    if job is None:
        return {
            "status": "unavailable",
            "source": None,
            "script": None,
            "label": None,
            "details": {},
        }

    status_value = str(job.get("status") or "unavailable")
    if status_value not in _KNOWN_STATUSES:
        status_value = "unavailable"

    artifact = job.get("artifact") if isinstance(job.get("artifact"), dict) else {}
    metadata = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
    source_raw = artifact.get("source") or metadata.get("source")
    validation = metadata.get("validation")

    if source_raw == "rules_feedback" or source_raw in (None, ""):
        api_source: str | None = "rules_feedback" if artifact else None
        provider_validated = False
    else:
        # Any non-rules artifact source is reported as provider (model lives in details).
        api_source = "provider"
        provider_validated = validation == "passed" and status_value == "done"

    if provider_validated:
        label: str | None = "AI narration"
    elif api_source == "rules_feedback" or (
        status_value in ("skipped", "done") and artifact
    ):
        label = "Rules feedback"
        api_source = "rules_feedback"
    else:
        label = None

    script = None
    if status_value in _TERMINAL_WITH_SCRIPT and artifact:
        # Assessment disclosure: never surface reference material via narration.
        # Rules/provider scripts are claim-validated and must not carry ideals;
        # still withhold script text if a non-rules artifact somehow retained
        # reference-shaped keys before assessment completion.
        if not assessment_completed:
            if any(key in artifact for key in ("ideal_answer", "ideal_keywords", "reference")):
                script = None
            else:
                script = artifact.get("script")
        else:
            script = artifact.get("script")
        if not isinstance(script, str):
            script = None

    details: dict[str, Any] = {}
    if metadata.get("snapshot_digest"):
        details["snapshot_digest"] = metadata["snapshot_digest"]
    elif job.get("snapshot_digest"):
        details["snapshot_digest"] = job.get("snapshot_digest")
    if metadata.get("model"):
        details["model"] = metadata["model"]
    elif api_source == "provider" and source_raw not in (None, "", "provider", "rules_feedback"):
        details["model"] = source_raw
    if metadata.get("schema_version") is not None:
        details["schema_version"] = metadata["schema_version"]
    if validation is not None:
        details["validation"] = validation

    return {
        "status": status_value,
        "source": api_source if status_value != "unavailable" else None,
        "script": script,
        "label": label,
        "details": details,
    }


@router.get(
    "/{session_id}/rounds/{round_number}/feedback",
    dependencies=[Depends(require_authenticated)],
)
def get_round_feedback(
    session_id: str,
    round_number: int,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return allowlisted practice feedback + narration status for one round."""
    try:
        db = get_database()
        session = db["sessions"].find_one({"session_id": session_id})
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found.",
            )
        assert_session_access(session, authorization)

        round_doc = next(
            (
                item for item in (session.get("rounds") or [])
                if int(item.get("round") or 0) == int(round_number)
            ),
            None,
        )
        if round_doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Round {round_number} not found.",
            )
        if not _round_submitted(round_doc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Round has not been submitted yet; feedback is unavailable.",
            )

        assessment_done = session_assessment_completed(session)
        job = db["narration_jobs"].find_one({
            "id": narration_job_id(session_id, int(round_number)),
        })

        # Explicit teaching delivery for allowlisted feedback content. Does not
        # advance session progression. Idempotent on delivery_id. Occurs after
        # submission so it cannot retroactively mark the committed attempt.
        item_type, item_id = item_identity_for_round(round_doc)
        try:
            record_teaching_exposure(
                db,
                kind="feedback_reveal",
                item_type=item_type,
                item_id=item_id or f"round:{round_number}",
                session=session,
                user_id=session.get("user_id"),
                round_number=int(round_number),
                block_id=round_doc.get("block_id"),
                content_fingerprint="feedback_allowlist_v1",
                also_legacy_assistance=False,
            )
        except Exception:
            pass

        is_inline_fu = is_inline_bundle_follow_up_round(round_doc)
        cfg = round_doc.get("config_json") or {}
        follow_up_outcome = (
            round_doc.get("follow_up_outcome")
            or (cfg.get("follow_up_outcome") if isinstance(cfg, dict) else None)
        )
        response = {
            "session_id": session_id,
            "round": int(round_number),
            "session_status": session.get("status"),
            "feedback": _feedback_allowlist(round_doc.get("feedback")),
            "final_score": None if is_inline_fu else round_doc.get("final_score"),
            "narration": _narration_payload(
                job,
                assessment_completed=assessment_done,
            ),
            "assessment_completed": assessment_done,
            "assessment_eligibility": round_doc.get("assessment_eligibility"),
            "eligibility_exclusion_reasons": round_doc.get(
                "eligibility_exclusion_reasons"
            )
            or [],
        }
        if is_inline_fu and isinstance(follow_up_outcome, dict):
            response["follow_up_outcome"] = dict(follow_up_outcome)
        if not is_inline_fu and round_doc.get("guard_applied") is not None:
            response["guard_applied"] = round_doc.get("guard_applied")
        return response
    except HTTPException:
        raise
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        if is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
        raise
