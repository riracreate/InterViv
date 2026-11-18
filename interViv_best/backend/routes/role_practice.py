"""Practice for a role. Off unless ROLE_PRACTICE_ENABLED or ROLE_ONLY_TARGETS is set.

With ROLE_ONLY_TARGETS on, /plan returns the interview plan that
POST /session/start builds for ``role_interview``: scripted unscored opener,
scripted unscored scenario and behavioural slots, and an optional plan from
the candidate's stored resume skills.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.routes.auth import require_authenticated
from modules.role_blueprints import get_blueprint, load_blueprints
from modules.role_interview import (
    RoleInterviewError,
    interview_slots,
    resume_for_planning,
    role_only_targets_enabled,
    slot_payloads,
)
from modules.role_planner import plan_role
from modules.staged_flow import estimate_minutes

router = APIRouter(
    prefix="/role-practice",
    tags=["role-practice"],
    dependencies=[Depends(require_authenticated)],
)


def role_practice_enabled() -> bool:
    return os.getenv("ROLE_PRACTICE_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}


def _require_enabled() -> None:
    if not (role_practice_enabled() or role_only_targets_enabled()):
        raise HTTPException(status_code=404, detail="Role practice is off.")


class PlanRequest(BaseModel):
    role_id: str
    level: str = "junior"
    length: str = "quick"
    jd_skills: list[str] = Field(default_factory=list)
    resume: dict | None = None
    extra_easy_skills: list[str] = Field(default_factory=list)
    # ROLE_ONLY_TARGETS only: plan with this stored resume (ownership-checked)
    # and keep swapped core slots.
    candidate_id: str | None = None
    core_competencies: list[str] | None = Field(default=None, max_length=6)


def _owned_candidate(candidate_id: str, authorization: str | None) -> dict:
    from backend.db import get_database
    from backend.routes.auth import require_user

    user = require_user(authorization)
    candidate = get_database()["candidates"].find_one({"candidate_id": candidate_id})
    if not candidate:
        raise HTTPException(status_code=404, detail="Resume not found.")
    if str(candidate.get("user_id") or "") != str(user["id"]):
        raise HTTPException(status_code=403, detail="You cannot plan with another user's resume.")
    return candidate


def _interview_plan(doc: dict, body: "PlanRequest", authorization: str | None) -> dict:
    resume = None
    if body.candidate_id:
        resume = resume_for_planning(_owned_candidate(body.candidate_id, authorization), doc)
    try:
        slots = interview_slots(
            doc, level=body.level, length=body.length, resume=resume,
            jd_skills=body.jd_skills, core_competencies=body.core_competencies,
        )
    except RoleInterviewError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    used = {slot.competency_id for slot in slots}
    practical = any(slot.kind == "practical" for slot in slots)
    return {
        "role_id": doc["id"],
        "title": doc["title"],
        "level": body.level,
        "length": body.length,
        "used_resume": resume is not None,
        "estimated_minutes": estimate_minutes(body.length, include_practical=practical),
        "slots": slot_payloads(slots),
        "alternatives": [
            {"competency_id": item["id"], "name": item["name"], "skill": (item.get("skills") or [item["name"]])[0]}
            for item in doc["competencies"]
            if item["type"] == "technical" and item["id"] not in used
        ],
        "interview": True,
    }


@router.get("/catalog")
def catalog() -> dict:
    _require_enabled()
    roles = []
    for doc in load_blueprints():
        roles.append({
            "id": doc["id"],
            "title": doc["title"],
            "aliases": doc.get("aliases") or [],
            "family": doc["family"],
            "practical_track": doc["practical_track"],
        })
    return {"roles": roles}


@router.post("/plan")
def plan(body: PlanRequest, authorization: str | None = Header(default=None)) -> dict:
    _require_enabled()
    doc = get_blueprint(body.role_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Role blueprint not found.")
    if role_only_targets_enabled():
        return _interview_plan(doc, body, authorization)
    slots = plan_role(
        doc, level=body.level, length=body.length, resume=body.resume,
        jd_skills=body.jd_skills, extra_easy_skills=set(body.extra_easy_skills),
    )
    used = {slot.competency_id for slot in slots}
    alternatives = [
        {"competency_id": item["id"], "name": item["name"], "skill": (item.get("skills") or [item["name"]])[0]}
        for item in doc["competencies"]
        if item["type"] == "technical" and item["id"] not in used
    ]
    practical = doc.get("practical_track") not in {None, "none"}
    return {
        "role_id": doc["id"],
        "title": doc["title"],
        "estimated_minutes": estimate_minutes(body.length, include_practical=practical),
        "slots": [slot.as_dict() for slot in slots],
        "alternatives": alternatives,
    }
