"""Owned ML attempt history and the ML submission entry point.

Submissions run through the shared session finalization path
(``POST /session/answer``), so attempts, scores, progression and retries
behave like every other round type. When the trusted local runner is not
enabled, the source is stored unevaluated and the round stays open.
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.db import get_database, is_database_exception
from backend.ml_primitives.catalog import UNAVAILABLE_MESSAGE
from backend.routes.auth import require_authenticated, require_user

router = APIRouter(
    prefix="/ml-primitives",
    tags=["ml_primitives"],
    dependencies=[Depends(require_authenticated)],
)
ATTEMPT_FIELDS = (
    "id", "session_id", "round", "block_id", "problem_id", "problem_version",
    "language", "source", "status", "error_code", "created_at",
)
# Present only once an executor graded (or tried to run) the attempt.
RESULT_FIELDS = ("score", "result", "grader_version", "execution_status")


def store_graded_attempt(db, session, round_doc, source, scoring_result):
    """Record an executed, graded attempt (public result fields only)."""
    config = round_doc["config_json"]
    artifact = dict(scoring_result.get("artifact_json") or {})
    db["ml_primitives_attempts"].insert_one({
        "id": str(uuid4()), "user_id": str(session["user_id"]),
        "session_id": session["session_id"], "round": round_doc["round"],
        "block_id": round_doc.get("block_id") or "", "problem_id": config["problem_id"],
        "problem_version": config["problem_version"], "language": "python",
        "source": source or "", "status": "graded", "error_code": "",
        "created_at": datetime.now(timezone.utc),
        "score": scoring_result.get("final_score"),
        "result": {
            "cases_passed": artifact.get("cases_passed"),
            "cases_total": artifact.get("cases_total"),
            "cases": artifact.get("cases") or [],
            "properties": artifact.get("properties") or [],
            "static_findings": artifact.get("static_findings") or [],
        },
        "grader_version": artifact.get("grader_version"),
        "execution_status": artifact.get("execution_status"),
    })


def store_unavailable_attempt(db, session, round_doc, source):
    if not source or not source.strip() or len(source) > 100_000:
        raise HTTPException(422, "Python source must contain 1–100,000 characters.")
    config = round_doc["config_json"]
    attempt_id = str(uuid4())
    try:
        db["ml_primitives_attempts"].insert_one({
            "id": attempt_id, "user_id": str(session["user_id"]),
            "session_id": session["session_id"], "round": round_doc["round"],
            "block_id": round_doc.get("block_id") or "", "problem_id": config["problem_id"],
            "problem_version": config["problem_version"], "language": "python",
            "source": source, "status": "unavailable",
            "error_code": "execution_unavailable", "created_at": datetime.now(timezone.utc),
            "execution_status": "unavailable",
        })
    except Exception as exc:
        if is_database_exception(exc):
            raise HTTPException(503, detail={
                "code": "storage_unavailable", "submission_saved": False,
                "retryable": True, "message": "Submission could not be stored. Please retry.",
            }) from exc
        raise
    return {
        "code": "execution_unavailable", "submission_saved": True,
        "attempt_id": attempt_id, "retryable": True, "message": UNAVAILABLE_MESSAGE,
    }


def _public_attempt(row):
    public = {key: row.get(key) for key in ATTEMPT_FIELDS}
    public.update({key: row[key] for key in RESULT_FIELDS if row.get(key) is not None})
    return public


@router.get("/attempts")
def list_attempts(authorization: str | None = Header(default=None)):
    user = require_user(authorization)
    rows = get_database()["ml_primitives_attempts"].find({"user_id": str(user["id"])})
    safe = [_public_attempt(row) for row in rows]
    return {"attempts": safe, "count": len(safe)}


def _owned_attempt(attempt_id, authorization):
    user = require_user(authorization)
    collection = get_database()["ml_primitives_attempts"]
    row = collection.find_one({"id": attempt_id})
    if row is None:
        raise HTTPException(404, "Attempt not found.")
    if row["user_id"] != str(user["id"]):
        raise HTTPException(403, "You cannot access another user's attempts.")
    return collection, row


@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id: str, authorization: str | None = Header(default=None)):
    _, row = _owned_attempt(attempt_id, authorization)
    return _public_attempt(row)


@router.delete("/attempts/{attempt_id}")
def delete_attempt(attempt_id: str, authorization: str | None = Header(default=None)):
    collection, row = _owned_attempt(attempt_id, authorization)
    collection.delete_one({"id": row["id"], "user_id": row["user_id"]})
    return {"deleted": True, "id": row["id"]}


class MLSubmitRequest(BaseModel):
    session_id: str = Field(min_length=1)
    round: int = Field(ge=1)
    source: str = Field(min_length=1, max_length=100_000)


@router.post("/{problem_id}/submit")
def submit_ml_primitive(
    problem_id: str,
    body: MLSubmitRequest,
    authorization: str | None = Header(default=None),
):
    """Submit source for an owned ML round; delegates to session submission."""
    from backend.routes.answer import SubmitAnswerRequest, submit_answer
    from backend.routes.session_access import assert_session_access

    session = get_database()["sessions"].find_one({"session_id": body.session_id})
    if not session:
        raise HTTPException(404, "Session not found.")
    assert_session_access(session, authorization)
    round_doc = next((r for r in session.get("rounds") or [] if r.get("round") == body.round), None)
    if round_doc is None or round_doc.get("round_type") != "ml_primitives":
        raise HTTPException(404, "ML primitives round not found in this session.")
    if (round_doc.get("config_json") or {}).get("problem_id") != problem_id:
        raise HTTPException(409, "This round is assigned a different problem.")
    return submit_answer(
        SubmitAnswerRequest(session_id=body.session_id, round=body.round, answer_text=body.source),
        authorization=authorization,
    )
