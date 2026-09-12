from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, status

from backend.routes.auth import require_user
from modules.learning_resources import list_resources


router = APIRouter(tags=["resources"])


@router.get("/resources")
def get_resources(
    skill_id: str | None = Query(default=None),
    question_id: str | None = Query(default=None),
    limit_per_level: int = Query(default=3, ge=1, le=100),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Curated lecture/solution links. Auth matches practice-bank (student JWT)."""
    require_user(authorization)
    if not skill_id and not question_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide skill_id or question_id.",
        )
    return list_resources(
        skill_id=skill_id, question_id=question_id, limit_per_level=limit_per_level
    )
