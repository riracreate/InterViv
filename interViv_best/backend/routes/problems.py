"""Phase C coding catalog: candidate-safe problem list and detail.

Both endpoints require authentication and expose statements, starter
code, and visible examples only. Hidden tests, reference solutions,
and mutant solutions never leave the server.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.coding_coach import build_hint, coach_status
from backend.coding_languages import starter_codes
from backend.db.phase_c_coding_bank import (
    get_coding_problem,
    list_coding_problems,
    public_coding_problem,
)
from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.execution import get_execution_status
from backend.routes.auth import require_authenticated, require_user

router = APIRouter(prefix="/problems", tags=["problems"], dependencies=[Depends(require_authenticated)])

ALLOWED_DIFFICULTIES = ("easy", "medium", "hard")


class CodingCoachHintRequest(BaseModel):
    session_id: str
    round: int = Field(ge=1)
    level: int = Field(default=1, ge=1, le=3)
    source: str | None = None
    last_error: str | None = None


@router.get("")
def list_problems(
    authorization: str | None = Header(default=None),
    difficulty: str | None = Query(default=None),
    topic: str | None = Query(default=None),
) -> dict[str, Any]:
    """List coding problems (candidate-safe), optionally filtered."""
    require_user(authorization)
    if difficulty is not None:
        wanted = difficulty.strip().lower()
        if wanted not in ALLOWED_DIFFICULTIES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported difficulty '{difficulty}'. "
                f"Allowed: {list(ALLOWED_DIFFICULTIES)}.",
            )
    problems = list_coding_problems(difficulty=difficulty, topic=topic)
    return {
        "problems": [{**public_coding_problem(p), "starter_codes": starter_codes(p)} for p in problems],
        "count": len(problems),
    }


@router.get("/execution/status")
def execution_status(authorization: str | None = Header(default=None)) -> dict:
    require_user(authorization)
    status_payload = get_execution_status()
    status_payload["coach"] = coach_status()
    return status_payload


@router.get("/coach/status")
def coding_coach_status(authorization: str | None = Header(default=None)) -> dict:
    require_user(authorization)
    return coach_status()


@router.post("/coach/hint")
def coding_coach_hint(
    body: CodingCoachHintRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Progressive coding hint. Records assistance; never changes scores."""
    user = require_user(authorization)
    user_id = str(user["id"])
    try:
        db = get_database()
        session = db["sessions"].find_one({"session_id": body.session_id})
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    if str(session.get("user_id") or "") != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot request coaching on another user's session.",
        )
    rounds = list(session.get("rounds") or [])
    target = next((r for r in rounds if int(r.get("round") or 0) == int(body.round)), None)
    if not target or str(target.get("round_type") or "") != "coding":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Coach hints are only available on an active coding round.",
        )
    problem_id = str(
        (target.get("config_json") or {}).get("problem_id")
        or target.get("problem_id")
        or ""
    )
    problem = get_coding_problem(problem_id) if problem_id else None
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coding problem not found.")

    payload = build_hint(
        problem=problem,
        level=body.level,
        source=body.source,
        last_error=body.last_error,
        prefer_ai=True,
    )
    try:
        from modules.teaching_exposures import record_teaching_exposure

        record_teaching_exposure(
            db,
            kind="hint",
            item_type="coding",
            item_id=problem["id"],
            session=session,
            user_id=user_id,
            round_number=body.round,
            block_id=target.get("block_id"),
            content_fingerprint=f"coach:{payload.get('kind')}:{payload.get('level')}",
            also_legacy_assistance=True,
        )
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    return payload


@router.get("/{problem_id}")
def get_problem(
    problem_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return one coding problem (candidate-safe)."""
    require_user(authorization)
    problem = get_coding_problem(problem_id)
    if problem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown coding problem: {problem_id!r}.",
        )
    return {**public_coding_problem(problem), "starter_codes": starter_codes(problem)}
