from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from modules.concept_mastery import ConceptMastery
from modules.skill_graph import StudentSkillGraph


router = APIRouter(tags=["learning"])


@router.get("/skill-graph/{user_id}")
def get_skill_graph(user_id: str) -> dict[str, Any]:
    if not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_id is required.",
        )
    return StudentSkillGraph(user_id).to_api_payload()


@router.get("/mastery/{user_id}")
def get_mastery(user_id: str) -> dict[str, Any]:
    if not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_id is required.",
        )
    return ConceptMastery().to_api_payload(user_id)
