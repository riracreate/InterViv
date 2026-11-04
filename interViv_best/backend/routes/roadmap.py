"""Personalized Roadmap route — live generator + versioned study plans.

  GET /roadmap/{user_id}/{role_id}?days=30   -> legacy Roadmap JSON
  GET /roadmap/me/{role_id}?days=30          -> auth-bound variant
  GET /roadmap/plans/me                      -> active versioned plan
  POST /roadmap/plans/me                     -> ensure / regenerate plan
  POST /roadmap/plans/me/tasks/{task_id}/complete
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.db.user_target import get_user_target
from backend.routes.auth import (
    get_user_from_authorization,
    require_authenticated,
    require_matching_user,
    require_user,
)
from modules.roadmap_generator import RoadmapGenerationError, RoadmapGenerator
from modules.roadmap_plans import (
    DEFAULT_HOURS_PER_WEEK,
    complete_task,
    ensure_plan,
    get_active_plan,
    list_plan_versions,
)


router = APIRouter(
    prefix="/roadmap",
    tags=["roadmap"],
    dependencies=[Depends(require_authenticated)],
)


class EnsurePlanRequest(BaseModel):
    role_id: str | None = None
    days: int = Field(default=30, ge=1, le=120)
    hours_per_week: int | None = Field(default=None, ge=1, le=40)
    confirmed_goal: str | None = None
    planning_context_skills: list[str] = Field(default_factory=list)
    regenerate: bool = False


class CompleteTaskRequest(BaseModel):
    role_id: str | None = None
    confirmed_goal: str | None = None
    completed: bool = True


@router.get("/plans/me")
def get_my_plan(
    role_id: str | None = Query(default=None),
    confirmed_goal: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    plan = get_active_plan(
        str(user["id"]),
        role_id=role_id or get_user_target(user)["role_id"],
        confirmed_goal=confirmed_goal,
    )
    if plan is None:
        return {
            "plan": None,
            "note": "No active plan yet. POST /roadmap/plans/me to create one.",
            "default_hours_per_week": DEFAULT_HOURS_PER_WEEK,
        }
    return {"plan": plan, "versions": list_plan_versions(
        str(user["id"]),
        role_id=role_id or get_user_target(user)["role_id"],
        confirmed_goal=confirmed_goal,
    )}


@router.post("/plans/me")
def ensure_my_plan(
    body: EnsurePlanRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    role_id = body.role_id or get_user_target(user)["role_id"]
    plan = ensure_plan(
        str(user["id"]),
        role_id=str(role_id) if role_id else None,
        days=body.days,
        hours_per_week=body.hours_per_week,
        confirmed_goal=body.confirmed_goal,
        planning_context_skills=body.planning_context_skills,
        regenerate=body.regenerate,
    )
    return {"plan": plan}


@router.post("/plans/me/tasks/{task_id}/complete")
def complete_my_task(
    task_id: str,
    body: CompleteTaskRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        plan = complete_task(
            str(user["id"]),
            task_id,
            role_id=body.role_id or get_user_target(user)["role_id"],
            confirmed_goal=body.confirmed_goal,
            completed=bool(body.completed),
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "plan": plan,
        "note": (
            "Task completion updates plan progress only. It does not change "
            "score, Elo, readiness, or assessed mastery."
        ),
    }


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
    payload = roadmap.to_dict()
    # Attach versioned plan (deterministic) without replacing the legacy DTO.
    plan = ensure_plan(
        str(user["id"]),
        role_id=role_id,
        days=days,
        confirmed_goal=None,
        regenerate=False,
    )
    payload["study_plan"] = plan
    if not plan.get("evidence_summary", {}).get("has_eligible_assessment"):
        payload["overall_readiness_percentage"] = None
        payload["readiness_note"] = (
            plan.get("meta", {}) or {}
        ).get("readiness_note")
        payload["disclaimer"] = (
            (payload.get("disclaimer") or "")
            + " Starter/no-history plans do not fabricate a readiness percentage."
        ).strip()
    return payload


@router.get("/{user_id}/{role_id}")
def get_roadmap(
    user_id: str,
    role_id: str,
    days: int = Query(default=30, ge=1, le=120),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    require_matching_user(user_id, authorization)
    try:
        roadmap = RoadmapGenerator().generate(user_id=user_id, role_id=role_id, days=days)
    except RoadmapGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    payload = roadmap.to_dict()
    plan = ensure_plan(user_id, role_id=role_id, days=days, regenerate=False)
    payload["study_plan"] = plan
    if not plan.get("evidence_summary", {}).get("has_eligible_assessment"):
        payload["overall_readiness_percentage"] = None
        payload["readiness_note"] = (plan.get("meta", {}) or {}).get("readiness_note")
    return payload


__all__ = ["router"]
