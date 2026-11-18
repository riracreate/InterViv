"""Phase D shared target context.

One server-validated record per user carrying company, role, the
selected job or JD, and the relevant resume reference. Every hop in a
job-linked journey (jobs, coach, ATS, gap, roadmap, practice) reads
this instead of re-prompting.

Selecting a target is a statement of intent, not evidence of skill:
nothing here feeds mastery or readiness math. The company/role pair is
mirrored onto the users row (same conversion as the legacy target
endpoint) so existing readiness consumers keep working.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.db.transactions import atomic
from backend.db.company_seed import (
    company_slug_to_db_id,
    role_slug_to_db_id,
)
from backend.routes.auth import require_authenticated, require_user
from modules.company_graph import get_company_graph
from modules.guidance_coach import MAX_INPUT_CHARS
from modules.jobs_explorer import get_job
from modules.role_interview import (
    RoleInterviewError,
    decode_role_target,
    encode_role_target,
    role_only_targets_enabled,
    role_target_view,
)

router = APIRouter(
    prefix="/target-context",
    tags=["target-context"],
    dependencies=[Depends(require_authenticated)],
)

JD_SOURCES = ("job", "paste", "role")

_UNSET: Any = object()
_UNAVAILABLE = "Target context is temporarily unavailable."
LOGGER = logging.getLogger(__name__)


def _database_error(exc: Exception) -> HTTPException:
    LOGGER.exception("target context database error")
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_UNAVAILABLE)


def _stored_target_id(slug: str | None, kind: str) -> Any:
    """Memory mode stores the slug. SQL mode stores the integer foreign key."""
    if slug is None:
        return None
    if not get_settings().database_url:
        return slug
    resolved = company_slug_to_db_id(slug) if kind == "company" else role_slug_to_db_id(slug)
    if resolved is None:
        detail = "Unknown company" if kind == "company" else "Unknown role"
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    return resolved


class RoleTargetIn(BaseModel):
    """One of the starter role blueprints plus a level (ROLE_ONLY_TARGETS)."""

    role_id: str = Field(min_length=1, max_length=64)
    level: str = "junior"


class TargetContextUpdate(BaseModel):
    company_id: str | None = None
    role_id: str | None = None
    # Role-only target; null clears it. Rejected unless ROLE_ONLY_TARGETS is on.
    role_target: RoleTargetIn | None = None
    job_id: str | None = None
    jd_source: str | None = None
    jd_text: str | None = None
    resume_ref: str | None = None


def _context_or_none(db: Any, user_id: str) -> dict[str, Any] | None:
    try:
        return db["target_contexts"].find_one({"user_id": user_id})
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise _database_error(exc) from exc
        raise


def _resolve_context(context: dict[str, Any] | None, db: Any) -> dict[str, Any]:
    """Attach resolved names/skills so hops need no extra calls."""
    if not context:
        return {"target": None}
    if not any(
        context.get(key)
        for key in ("company_id", "role_id", "job_id", "jd_text", "resume_ref")
    ):
        return {"target": None}
    graph = get_company_graph()
    role_target = role_target_view(context.get("role_id"))
    company = graph.get_company(context.get("company_id") or "") if context.get("company_id") else None
    role = None
    if company and context.get("role_id") and role_target is None:
        role = graph.get_role(company.id, context["role_id"])
    required_skills = [r.skill for r in (role.skill_requirements if role else [])]
    job = get_job(context["job_id"]) if context.get("job_id") else None
    resume_skills: list[str] | None = None
    if context.get("resume_ref"):
        candidate = db["candidates"].find_one({"candidate_id": context["resume_ref"]})
        if candidate and str(candidate.get("user_id") or "") == str(context.get("user_id")):
            resume_skills = list(candidate.get("resume_skills") or [])
    return {
        "target": {
            "company_id": context.get("company_id"),
            "company_name": company.name if company else None,
            # A role-only target is never exposed as a company role.
            "role_id": None if role_target else context.get("role_id"),
            "role_title": role.title if role else None,
            **({"role_target": role_target} if role_target and role_only_targets_enabled() else {}),
            "required_skills": required_skills,
            "job_id": context.get("job_id"),
            "job_title": job.get("title") if job else None,
            "job_company": job.get("company") if job else None,
            "jd_source": context.get("jd_source"),
            "jd_text": context.get("jd_text"),
            "resume_ref": context.get("resume_ref"),
            "resume_skills": resume_skills,
            "updated_at": context.get("updated_at"),
        },
        "disclaimer": graph.disclaimer,
    }


@router.get("/me")
def get_my_target_context(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise _database_error(exc) from exc
    return _resolve_context(_context_or_none(db, str(user["id"])), db)


@router.put("/me")
def put_my_target_context(
    request: TargetContextUpdate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise _database_error(exc) from exc

    user_id = str(user["id"])
    payload = request.model_dump(exclude_unset=True)
    current = _context_or_none(db, user_id) or {}
    graph = get_company_graph()

    # Company/role validation mirrors the legacy target endpoint: slugs in,
    # graph-validated, db ids mirrored onto the users row.
    company_slug = payload.get("company_id", _UNSET)
    role_slug = payload.get("role_id", _UNSET)
    if "role_target" in payload:
        if not role_only_targets_enabled():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Role targets are off.",
            )
        if company_slug is not _UNSET or role_slug is not _UNSET:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Send role_target or company_id/role_id, not both.",
            )
        wanted = payload["role_target"]
        company_slug = None
        if wanted is None:
            role_slug = None if decode_role_target(current.get("role_id")) else current.get("role_id")
            company_slug = current.get("company_id") if role_slug is not None else None
        else:
            try:
                role_slug = encode_role_target(wanted["role_id"], wanted.get("level") or "junior")
            except RoleInterviewError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc),
                ) from exc
    if company_slug is _UNSET:
        company_slug = current.get("company_id")
    if role_slug is _UNSET:
        role_slug = current.get("role_id")
    role_only = decode_role_target(role_slug) is not None
    if role_only:
        company_slug = None
    if company_slug is not None:
        company = graph.get_company(company_slug)
        if company is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown company '{company_slug}'.",
            )
        if role_slug is not None and graph.get_role(company_slug, role_slug) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_slug}' not found for company '{company_slug}'.",
            )
    elif role_slug is not None and not role_only:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="role_id requires company_id.",
        )

    job_id = payload.get("job_id", _UNSET)
    if job_id is _UNSET:
        job_id = current.get("job_id")
    if job_id is not None and get_job(job_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found."
        )

    jd_source = payload.get("jd_source", _UNSET)
    if jd_source is _UNSET:
        jd_source = current.get("jd_source")
    if jd_source is not None and jd_source not in JD_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"jd_source must be one of {list(JD_SOURCES)}.",
        )
    jd_text = payload.get("jd_text", _UNSET)
    if jd_text is _UNSET:
        jd_text = current.get("jd_text")
    if jd_text is not None and len(jd_text) > MAX_INPUT_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"jd_text exceeds {MAX_INPUT_CHARS} characters.",
        )
    if jd_text is not None and jd_source is None:
        jd_source = "paste"
    if job_id is not None and jd_source is None:
        jd_source = "job"

    resume_ref = payload.get("resume_ref", _UNSET)
    if resume_ref is _UNSET:
        resume_ref = current.get("resume_ref")
    if resume_ref is not None:
        candidate = db["candidates"].find_one({"candidate_id": resume_ref})
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resume/candidate not found.",
            )
        if str(candidate.get("user_id") or "") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot target another user's resume.",
            )

    doc = {
        "user_id": user_id,
        "company_id": company_slug,
        "role_id": role_slug,
        "job_id": job_id,
        "jd_source": jd_source,
        "jd_text": jd_text,
        "resume_ref": resume_ref,
        "updated_at": datetime.now(timezone.utc),
    }
    try:
        with atomic(db):
            db["target_contexts"].update_one(
                {"user_id": user_id}, {"$set": doc}, upsert=True
            )
            db["users"].update_one(
                {"id": user_id},
                {
                    "$set": {
                        "target_company_id": _stored_target_id(company_slug, "company"),
                        # A role-only target has no company role row.
                        "target_role_id": None if role_only else _stored_target_id(role_slug, "role"),
                        "last_active_at": datetime.now(timezone.utc),
                    }
                },
            )
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise _database_error(exc) from exc
        raise
    return _resolve_context(_context_or_none(db, user_id), db)


@router.delete("/me")
def delete_my_target_context(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise _database_error(exc) from exc
    user_id = str(user["id"])
    try:
        with atomic(db):
            db["target_contexts"].delete_one({"user_id": user_id})
            db["users"].update_one(
                {"id": user_id},
                {
                    "$set": {
                        "target_company_id": None,
                        "target_role_id": None,
                        "last_active_at": datetime.now(timezone.utc),
                    }
                },
            )
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise _database_error(exc) from exc
        raise
    return {"target": None}
