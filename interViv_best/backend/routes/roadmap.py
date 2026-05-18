"""Personalized Roadmap route.

  GET /roadmap/{user_id}/{role_id}?days=30   -> Roadmap as JSON
  GET /roadmap/me/{role_id}?days=30          -> auth-bound variant

``days`` is snapped to the nearest supported value (7, 14, 30) — see
modules.roadmap_generator.SUPPORTED_DAYS.

Mirrors the /gap-analysis routing convention: the literal /me/ route
is declared first so FastAPI doesn't bind user_id="me".
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, status

from backend.routes.auth import get_user_from_authorization
from modules.roadmap_generator import RoadmapGenerationError, RoadmapGenerator


router = APIRouter(prefix="/roadmap", tags=["roadmap"])


@router.get("/me/{role_id}")
def get_my_roadmap(
    role_id: str,
    days: int = Query(default=30, ge=1, le=120),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = get_user_from_authorization(authorization)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to view your personalized roadmap.",
        )
    try:
        roadmap = RoadmapGenerator().generate(user_id=user["id"], role_id=role_id, days=days)
    except RoadmapGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return roadmap.to_dict()


@router.get("/{user_id}/{role_id}")
def get_roadmap(
    user_id: str,
    role_id: str,
    days: int = Query(default=30, ge=1, le=120),
) -> dict[str, Any]:
    try:
        roadmap = RoadmapGenerator().generate(user_id=user_id, role_id=role_id, days=days)
    except RoadmapGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return roadmap.to_dict()


__all__ = ["router"]
