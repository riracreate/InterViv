from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, status

from backend.routes.auth import require_matching_user, require_user
from modules.concept_mastery import ConceptMastery
from modules.skill_graph import StudentSkillGraph


router = APIRouter(tags=["learning"])


@router.get("/skill-graph/me")
def get_my_skill_graph(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    return StudentSkillGraph(str(user["id"])).to_api_payload()


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
    return StudentSkillGraph(user_id).to_api_payload()


@router.get("/mastery/me")
def get_my_mastery(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    return ConceptMastery().to_api_payload(str(user["id"]))


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
    return ConceptMastery().to_api_payload(user_id)
