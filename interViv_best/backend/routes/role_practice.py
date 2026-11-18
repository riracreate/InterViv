"""Practice for a role. Off unless ROLE_PRACTICE_ENABLED is set."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.routes.auth import require_authenticated
from modules.role_blueprints import load_blueprints
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
    if not role_practice_enabled():
        raise HTTPException(status_code=404, detail="Role practice is off.")


class PlanRequest(BaseModel):
    role_id: str
    level: str = "junior"
    length: str = "quick"
    jd_skills: list[str] = Field(default_factory=list)
    resume: dict | None = None
    extra_easy_skills: list[str] = Field(default_factory=list)


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
def plan(body: PlanRequest) -> dict:
    _require_enabled()
    doc = next((item for item in load_blueprints() if item["id"] == body.role_id), None)
    if doc is None:
        raise HTTPException(status_code=404, detail="Role blueprint not found.")
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
