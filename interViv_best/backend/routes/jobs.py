from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, status

from backend.db import get_database
from backend.routes.auth import require_user
from backend.routes.session import StartSessionRequest, start_session
from modules.jobs_explorer import (
    build_practice_start_payload,
    get_job,
    missing_skills_for_job,
    rate_limit_ok,
    search_jobs,
    user_skills_for_overlay,
)


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(
    q: str = Query(default="software intern OR backend OR data"),
    where: str = Query(default=""),
    page: int = Query(default=1, ge=1, le=20),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    if not rate_limit_ok(str(user["id"])):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Jobs search rate limit exceeded. Try again shortly.",
        )
    return search_jobs(q=q, where=where, page=page, user_id=str(user["id"]))


@router.get("/{job_id}")
def get_job_detail(
    job_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    user_skills = user_skills_for_overlay(str(user["id"]))
    from modules.jobs_explorer import match_pct

    return {
        "id": job["id"],
        "title": job["title"],
        "company": job["company"],
        "location": job["location"],
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "created": job.get("created"),
        "skills": job.get("skills") or [],
        "match_pct": match_pct(job.get("skills") or [], user_skills),
        "redirect_url": job.get("redirect_url"),
        "snippet": job.get("snippet"),
        "missing_skills": missing_skills_for_job(job, user_skills),
    }


@router.post("/{job_id}/practice")
def practice_for_job(
    job_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    user_skills = user_skills_for_overlay(str(user["id"]))
    skills = missing_skills_for_job(job, user_skills)

    db = get_database()
    candidate = db["candidates"].find_one({"user_id": user["id"]})
    candidate_id = str(candidate["candidate_id"]) if candidate else ""

    start_body = build_practice_start_payload(skills=skills, candidate_id=candidate_id or None)
    request = StartSessionRequest(**start_body)
    session = start_session(request, authorization=authorization)
    return {
        **session,
        "round_plan": start_body.get("round_plan"),
        "navigate": f"/interview/{session.get('session_id')}",
        "job_id": job_id,
        "missing_skills": skills,
    }
