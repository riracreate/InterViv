"""Phase C coding catalog: candidate-safe problem list and detail.

Both endpoints require authentication and expose statements, starter
code, and visible examples only. Hidden tests, reference solutions,
and mutant solutions never leave the server.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, status

from backend.db.phase_c_coding_bank import (
    get_coding_problem,
    list_coding_problems,
    public_coding_problem,
)
from backend.routes.auth import require_user

router = APIRouter(prefix="/problems", tags=["problems"])

ALLOWED_DIFFICULTIES = ("easy", "medium", "hard")


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
        "problems": [public_coding_problem(p) for p in problems],
        "count": len(problems),
    }


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
    return public_coding_problem(problem)
