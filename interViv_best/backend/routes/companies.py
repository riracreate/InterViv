"""Company hiring graph routes.

The disclaimer is surfaced in every list response and on the role detail
response. It is the single source of truth for the UI copy:

    "Company hiring profiles are curated from publicly available job
     descriptions, observed placement patterns, and industry references.
     These are reference profiles for practice preparation, not exact
     hiring criteria."
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from backend.config import get_settings
from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.db.transactions import atomic
from backend.db.company_seed import (
    company_slug_to_db_id,
    role_slug_to_db_id,
)
from backend.routes.auth import (
    _public_user,
    get_user_from_authorization,
    require_authenticated,
)
from modules.company_graph import (
    Company,
    CompanyHiringGraph,
    Role,
    get_company_graph,
)


router = APIRouter(tags=["companies"])


def _graph() -> CompanyHiringGraph:
    return get_company_graph()


def _company_payload(company: Company, include_roles: bool = True) -> dict[str, Any]:
    payload = company.to_dict(include_roles=include_roles)
    # Surface the DB id when available so clients that need to reference the
    # row directly can. In in-memory mode this stays null.
    payload["db_id"] = company_slug_to_db_id(company.id)
    return payload


def _role_payload(role: Role) -> dict[str, Any]:
    payload = role.to_dict()
    payload["db_id"] = role_slug_to_db_id(role.id)
    return payload


@router.get("/companies")
def list_companies() -> dict[str, Any]:
    graph = _graph()
    return {
        "disclaimer": graph.disclaimer,
        "companies": [_company_payload(c, include_roles=True) for c in graph.list_companies()],
    }


@router.get("/companies/{company_id}")
def get_company(company_id: str) -> dict[str, Any]:
    graph = _graph()
    company = graph.get_company(company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    return {
        "disclaimer": graph.disclaimer,
        "company": _company_payload(company),
    }


@router.get("/companies/{company_id}/roles")
def list_company_roles(company_id: str) -> dict[str, Any]:
    graph = _graph()
    company = graph.get_company(company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    return {
        "disclaimer": graph.disclaimer,
        "company": {"id": company.id, "name": company.name},
        "roles": [_role_payload(role) for role in company.roles],
    }


@router.get("/companies/{company_id}/roles/{role_id}")
def get_company_role(company_id: str, role_id: str) -> dict[str, Any]:
    graph = _graph()
    role = graph.get_role(company_id, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
    return {
        "disclaimer": graph.disclaimer,
        "company_id": company_id,
        "role": _role_payload(role),
    }


class TargetUpdate(BaseModel):
    target_company_id: str | None = None
    target_role_id: str | None = None


def _stored_target_id(slug: str, lookup, unknown: str) -> Any:
    if not get_settings().database_url:
        return slug
    resolved = lookup(slug)
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=unknown)
    return resolved


@router.patch("/auth/me/target", dependencies=[Depends(require_authenticated)])
def patch_my_target(
    request: TargetUpdate,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = get_user_from_authorization(authorization)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header.")

    graph = _graph()

    company_slug = request.target_company_id
    role_slug = request.target_role_id
    target_company_id_value: Any = None
    target_role_id_value: Any = None

    if company_slug is not None:
        company = graph.get_company(company_slug)
        if company is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown company '{company_slug}'."
            )
        target_company_id_value = _stored_target_id(company_slug, company_slug_to_db_id, "Unknown company")

        if role_slug is not None:
            role = graph.get_role(company_slug, role_slug)
            if role is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Role '{role_slug}' not found for company '{company_slug}'.",
                )
            target_role_id_value = _stored_target_id(role_slug, role_slug_to_db_id, "Unknown role")

    update_payload: dict[str, Any] = {
        "target_company_id": target_company_id_value,
        "target_role_id": target_role_id_value,
        "last_active_at": datetime.now(timezone.utc),
    }

    try:
        db = get_database()
        with atomic(db):
            users = db["users"]
            users.update_one({"id": user["id"]}, {"$set": update_payload})
            refreshed = users.find_one({"id": user["id"]}) or user
            current = db["target_contexts"].find_one({"user_id": user["id"]}) or {}
            merged = {
                "user_id": user["id"],
                "company_id": company_slug,
                "role_id": role_slug,
                "job_id": current.get("job_id"),
                "jd_source": current.get("jd_source"),
                "jd_text": current.get("jd_text"),
                "resume_ref": current.get("resume_ref"),
                "updated_at": datetime.now(timezone.utc),
            }
            if any(
                merged.get(key)
                for key in ("company_id", "role_id", "job_id", "jd_text", "resume_ref")
            ):
                db["target_contexts"].update_one(
                    {"user_id": user["id"]}, {"$set": merged}, upsert=True
                )
            else:
                db["target_contexts"].delete_one({"user_id": user["id"]})
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise

    return {
        "user": _public_user(refreshed),
        "target_company_slug": company_slug,
        "target_role_slug": role_slug,
        "disclaimer": graph.disclaimer,
    }


__all__ = ["router"]
