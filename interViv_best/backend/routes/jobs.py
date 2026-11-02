from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.db import get_database
from backend.routes.auth import require_authenticated, require_user
from backend.routes.session import StartSessionRequest, start_session
from modules.adzuna_client import AdzunaClientError, normalize_country, safe_redirect_url
from modules.greenhouse_client import safe_greenhouse_url
from modules.jobs_explorer import (
    PROVIDER_GREENHOUSE,
    build_practice_prepare_payload,
    build_practice_start_payload,
    get_job,
    missing_skills_for_job,
    rate_limit_ok,
    search_greenhouse_jobs,
    search_jobs,
    user_skills_for_overlay,
)


router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_authenticated)])


class PracticeConfirmRequest(BaseModel):
    confirm: bool = False
    skills: list[str] | None = None
    blocks: list[dict[str, Any]] | None = None
    company: str | None = None
    role: str | None = None
    full_jd: str | None = Field(default=None, max_length=8000)


def _http_for_adzuna(exc: AdzunaClientError) -> HTTPException:
    code = {
        "unsupported_country": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "config": status.HTTP_503_SERVICE_UNAVAILABLE,
        "auth": status.HTTP_502_BAD_GATEWAY,
        "rate_limit": status.HTTP_429_TOO_MANY_REQUESTS,
        "timeout": status.HTTP_504_GATEWAY_TIMEOUT,
        "provider": status.HTTP_502_BAD_GATEWAY,
    }.get(exc.kind, status.HTTP_502_BAD_GATEWAY)
    return HTTPException(
        status_code=code,
        detail={
            "error": exc.kind,
            "message": exc.message,
            "empty": False,
        },
    )


@router.get("")
def list_jobs(
    q: str = Query(default="software intern OR backend OR data"),
    where: str = Query(default=""),
    page: int = Query(default=1, ge=1, le=20),
    country: str = Query(default="in"),
    source: str = Query(default="adzuna"),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    if not rate_limit_ok(str(user["id"])):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Jobs search rate limit exceeded. Try again shortly.",
        )
    selected = (source or "adzuna").strip().lower()
    if selected not in {"adzuna", "greenhouse"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Job source must be adzuna or greenhouse.",
        )
    try:
        if selected == "greenhouse":
            return search_greenhouse_jobs(
                q=q,
                where=where,
                page=page,
                user_id=str(user["id"]),
            )
        normalize_country(country)
        return search_jobs(
            q=q,
            where=where,
            page=page,
            user_id=str(user["id"]),
            country=country,
        )
    except AdzunaClientError as exc:
        raise _http_for_adzuna(exc) from exc


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

    if job.get("provider") == PROVIDER_GREENHOUSE:
        redirect = safe_greenhouse_url(job.get("redirect_url"))
    else:
        redirect = safe_redirect_url(job.get("redirect_url"))
    return {
        "id": job["id"],
        "title": job["title"],
        "company": job["company"],
        "location": job["location"],
        "salary_min": job.get("salary_min"),
        "salary_max": job.get("salary_max"),
        "salary_is_predicted": job.get("salary_is_predicted"),
        "salary_currency": job.get("salary_currency"),
        "created": job.get("created"),
        "skills": job.get("skills") or [],
        "match_pct": match_pct(job.get("skills") or [], user_skills),
        "redirect_url": redirect,
        "snippet": job.get("snippet"),
        "missing_skills": missing_skills_for_job(job, user_skills),
        "snippet_is_incomplete": True,
    }


@router.post("/{job_id}/prepare")
def prepare_practice_for_job(
    job_id: str,
    body: PracticeConfirmRequest | None = None,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Return a confirmable practice draft — does not start a session."""
    user = require_user(authorization)
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    user_skills = user_skills_for_overlay(str(user["id"]))
    full_jd = body.full_jd if body else None
    draft = build_practice_prepare_payload(
        job=job, user_skills=user_skills, full_jd=full_jd
    )
    return draft


@router.post("/{job_id}/practice")
def practice_for_job(
    job_id: str,
    body: PracticeConfirmRequest | None = None,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Start practice only after explicit confirm with reviewed skills/blocks."""
    user = require_user(authorization)
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    req = body or PracticeConfirmRequest()
    if not req.confirm:
        # Back-compat: return prepare draft instead of silently starting.
        user_skills = user_skills_for_overlay(str(user["id"]))
        draft = build_practice_prepare_payload(
            job=job, user_skills=user_skills, full_jd=req.full_jd
        )
        return {**draft, "started": False}

    user_skills = user_skills_for_overlay(str(user["id"]))
    skills = [s for s in (req.skills or missing_skills_for_job(job, user_skills)) if s][:5]
    blocks = req.blocks

    db = get_database()
    candidate = db["candidates"].find_one({"user_id": user["id"]})
    candidate_id = str(candidate["candidate_id"]) if candidate else ""

    start_body = build_practice_start_payload(
        skills=skills,
        candidate_id=candidate_id or None,
        blocks=blocks,
    )
    # Optional company/role are session metadata only — never scoring inputs.
    if req.company:
        start_body["target_company_name"] = req.company[:200]
    if req.role:
        start_body["target_role_name"] = req.role[:200]

    request = StartSessionRequest(**{
        k: v for k, v in start_body.items()
        if k in StartSessionRequest.model_fields
    })
    session = start_session(request, authorization=authorization)
    return {
        **session,
        "started": True,
        "round_plan": start_body.get("round_plan"),
        "blocks": start_body.get("blocks"),
        "navigate": f"/interview/{session.get('session_id')}",
        "practice_href": "/practice",
        "job_id": job_id,
        "missing_skills": skills,
        "company": req.company or job.get("company"),
        "role": req.role or job.get("title"),
    }
