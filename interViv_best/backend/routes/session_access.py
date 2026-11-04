"""Shared session ownership checks for answer, continue, and feedback routes.

A token is required. The session must have a user_id and it must match the
token. Sessions with no owner, and tokens for someone else, are 403.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status

from backend.routes.auth import require_user

PHASE2_ROUND_TYPES = frozenset(
    {"mcq", "sql", "coding", "system_design", "ml_primitives"}
)


def session_has_phase2_rounds(session: dict[str, Any]) -> bool:
    return any(
        (r.get("round_type") in PHASE2_ROUND_TYPES)
        for r in (session.get("rounds") or [])
    )


def assert_session_access(
    session: dict[str, Any],
    authorization: str | None,
    *,
    foreign_detail: str = "You cannot access another user's session.",
) -> dict:
    """Require the session owner.

    No token is 401. A session with no ``user_id``, or a token for someone
    else, is 403. There is no guest path.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required for this session.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = require_user(authorization)
    owner = session.get("user_id")
    if not owner or str(owner) != str(user["id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=foreign_detail,
        )
    return user


def session_assessment_completed(session: dict[str, Any]) -> bool:
    """True only when after_session review content may be revealed.

    ``content_blocked`` retains scored work but is not a completed assessment.
    """
    return session.get("status") == "completed"
