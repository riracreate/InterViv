from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from backend.db import get_database
from backend.routes.auth import require_user
from backend.routes.session import StartSessionRequest, start_session
from modules.guidance_coach import (
    MAX_INPUT_CHARS,
    build_coach_plan,
    cap_practice_skills,
)
from modules.jobs_explorer import build_practice_start_payload


router = APIRouter(prefix="/coach", tags=["coach"])


class CoachPlanRequest(BaseModel):
    jd_text: str | None = None
    goal_text: str | None = None
    include_dashboard: bool = True
    role_id: str | None = None

    @model_validator(mode="after")
    def require_one_field(self) -> "CoachPlanRequest":
        jd = (self.jd_text or "").strip()
        goal = (self.goal_text or "").strip()
        if not jd and not goal:
            raise ValueError("Provide jd_text and/or goal_text.")
        if len(jd) > MAX_INPUT_CHARS or len(goal) > MAX_INPUT_CHARS:
            raise ValueError(f"Input exceeds {MAX_INPUT_CHARS} characters.")
        return self


class CoachStartPracticeRequest(BaseModel):
    skills: list[str] = Field(default_factory=list)
    round_plan: list[str] | None = None


@router.post("/plan")
def coach_plan(
    body: CoachPlanRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    role_id = body.role_id
    if not role_id:
        db = get_database()
        candidate = db["candidates"].find_one({"user_id": user["id"]})
        if candidate:
            role_id = candidate.get("target_role_id") or candidate.get("role_id")
        role_id = role_id or user.get("target_role_id")

    return build_coach_plan(
        jd_text=body.jd_text,
        goal_text=body.goal_text,
        user_id=str(user["id"]),
        role_id=str(role_id) if role_id else None,
        include_dashboard=bool(body.include_dashboard),
    )


@router.post("/start-practice")
def coach_start_practice(
    body: CoachStartPracticeRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    skills = cap_practice_skills(body.skills)
    if not skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No recognizable skills to practice.",
        )

    db = get_database()
    candidate = db["candidates"].find_one({"user_id": user["id"]})
    candidate_id = str(candidate["candidate_id"]) if candidate else ""

    start_body = build_practice_start_payload(skills=skills, candidate_id=candidate_id or None)
    if body.round_plan:
        cleaned = [r for r in body.round_plan if r in {"technical_short_answer", "mcq", "sql"}]
        if cleaned:
            start_body["round_plan"] = cleaned[:8]
            start_body["round_type"] = cleaned[0]

    request = StartSessionRequest(**start_body)
    session = start_session(request, authorization=authorization)
    return {
        **session,
        "round_plan": start_body.get("round_plan"),
        "navigate": f"/interview/{session.get('session_id')}",
        "skills": skills,
    }
