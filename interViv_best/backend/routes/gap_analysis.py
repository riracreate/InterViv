"""Gap Analysis route.

Surface area:

  GET /gap-analysis/{user_id}/{role_id}  -> GapAnalysisReport as JSON
  GET /gap-analysis/me/{role_id}         -> same, but for the auth'd user

The handler is read-only and graceful: an unauthenticated request to
``/me/{role_id}`` returns 401, an unknown role returns 404, and a user with
no skill graph yet returns a report with overall_readiness_percentage = 0
and all required skills surfaced as Untested.

The formula and design are documented in modules/gap_analysis.py — keep
that file as the single source of truth for the math.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, status

from backend.routes.auth import get_user_from_authorization, require_matching_user
from modules.gap_analysis import GapAnalysisError, GapAnalyzer


router = APIRouter(prefix="/gap-analysis", tags=["gap-analysis"])


# IMPORTANT: register the literal "/me/..." route BEFORE the catch-all
# "/{user_id}/..." so FastAPI doesn't bind user_id="me" and skip the auth
# check.

@router.get("/me/{role_id}")
def get_my_gap_analysis(
    role_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = get_user_from_authorization(authorization)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to view your readiness against this role.",
        )
    try:
        report = GapAnalyzer().compute_gap(user_id=user["id"], role_id=role_id)
    except GapAnalysisError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return report.to_dict()


@router.get("/{user_id}/{role_id}")
def get_gap_analysis(
    user_id: str,
    role_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    require_matching_user(user_id, authorization)
    try:
        report = GapAnalyzer().compute_gap(user_id=user_id, role_id=role_id)
    except GapAnalysisError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return report.to_dict()


__all__ = ["router"]
