"""Shared session ownership checks for answer, continue, and feedback routes.

Matches GET /session/{id} policy:
- Phase-2 round types or a bound user_id require a valid JWT.
- Bound sessions must match the token owner (403 otherwise).
- Phase-2 types without user_id are rejected (401).
- Legacy technical sessions with no user_id remain guest-accessible.
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
) -> dict | None:
    """Enforce ownership. Returns the authenticated user when JWT is required.

    Returns ``None`` only for genuinely anonymous legacy technical sessions.
    """
    needs_auth = session_has_phase2_rounds(session) or bool(session.get("user_id"))
    if not needs_auth:
        return None
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required for this session.",
        )
    user = require_user(authorization)
    if session.get("user_id"):
        if str(session["user_id"]) != str(user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=foreign_detail,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Anonymous sessions are not permitted for this round type.",
        )
    return user


def session_assessment_completed(session: dict[str, Any]) -> bool:
    """True only when after_session review content may be revealed.

    ``content_blocked`` retains scored work but is not a completed assessment.
    """
    return session.get("status") == "completed"
