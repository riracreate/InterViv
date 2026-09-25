from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from backend.routes.auth import require_authenticated, require_matching_user, require_user
from modules.concept_mastery import ConceptMastery
from modules.learning_signals import (
    build_signals_payload,
    get_roadmap_completion,
    mark_roadmap_block_complete,
)
from modules.roadmap_generator import SUPPORTED_DAYS
from modules.skill_graph import StudentSkillGraph


router = APIRouter(tags=["learning"], dependencies=[Depends(require_authenticated)])


class RoadmapProgressRequest(BaseModel):
    role_id: str = Field(min_length=1)
    plan_days: int
    block_index: int = Field(ge=1)
    blocks_total: int = Field(ge=1)


def _with_assistance(payload: dict[str, Any], user_id: str) -> dict[str, Any]:
    """Attach the assisted/unassisted split next to unchanged figures.

    Mastery and skill-graph math are preserved exactly; this sibling key
    keeps the two populations from being silently mixed in any claim
    built on these endpoints.
    """
    from backend.routes.learning_hub import assistance_breakdown_for_user

    return {**payload, "assistance": assistance_breakdown_for_user(user_id)}


@router.get("/skill-graph/me")
def get_my_skill_graph(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    return _with_assistance(
        StudentSkillGraph(str(user["id"])).to_api_payload(), str(user["id"])
    )


@router.get("/skill-graph/{user_id}")
def get_skill_graph(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    if not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_id is required.",
        )
    require_matching_user(user_id, authorization)
    return _with_assistance(StudentSkillGraph(user_id).to_api_payload(), user_id)


@router.get("/mastery/me")
def get_my_mastery(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    return _with_assistance(
        ConceptMastery().to_api_payload(str(user["id"])), str(user["id"])
    )


@router.get("/mastery/{user_id}")
def get_mastery(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    if not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_id is required.",
        )
    require_matching_user(user_id, authorization)
    return _with_assistance(ConceptMastery().to_api_payload(user_id), user_id)


@router.get("/learning/signals/me")
def get_my_learning_signals(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    return build_signals_payload(str(user["id"]))


@router.get("/learning/signals/{user_id}")
def get_learning_signals(
    user_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    if not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_id is required.",
        )
    require_matching_user(user_id, authorization)
    return build_signals_payload(user_id)


@router.post("/learning/roadmap-progress")
def post_roadmap_progress(
    body: RoadmapProgressRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    if body.plan_days not in SUPPORTED_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"plan_days must be one of {SUPPORTED_DAYS}",
        )
    try:
        return mark_roadmap_block_complete(
            user_id=str(user["id"]),
            role_id=body.role_id.strip(),
            plan_days=body.plan_days,
            block_index=body.block_index,
            blocks_total=body.blocks_total,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get("/learning/roadmap-completion/me")
def get_my_roadmap_completion(
    role_id: str | None = None,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    return {
        "user_id": str(user["id"]),
        "roadmap_completion": get_roadmap_completion(str(user["id"]), role_id),
    }
