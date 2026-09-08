"""Owned ML attempt history; submission stores source without evaluating it."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException

from backend.db import get_database, is_database_exception
from backend.ml_primitives.catalog import UNAVAILABLE_MESSAGE
from backend.routes.auth import require_user

router = APIRouter(prefix="/ml-primitives", tags=["ml_primitives"])
ATTEMPT_FIELDS = (
    "id", "session_id", "round", "block_id", "problem_id", "problem_version",
    "language", "source", "status", "error_code", "created_at",
)


def store_unavailable_attempt(db, session, round_doc, source):
    if not source or not source.strip() or len(source) > 100_000:
        raise HTTPException(422, "Python source must contain 1–100,000 characters.")
    config = round_doc["config_json"]
    attempt_id = str(uuid4())
    try:
        db["ml_primitives_attempts"].insert_one({
            "id": attempt_id, "user_id": str(session["user_id"]),
            "session_id": session["session_id"], "round": round_doc["round"],
            "block_id": round_doc["block_id"], "problem_id": config["problem_id"],
            "problem_version": config["problem_version"], "language": "python",
            "source": source, "status": "unavailable",
            "error_code": "execution_unavailable", "created_at": datetime.now(timezone.utc),
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
    return {key: row.get(key) for key in ATTEMPT_FIELDS}


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
