"""Target company and role as slugs outside the database.

``target_contexts`` stores the slugs. The integer columns on ``users`` (and
session rows) exist only so SQL can enforce foreign keys.
"""

from __future__ import annotations

from typing import Any

from backend.config import get_settings
from backend.db.company_seed import company_db_id_to_slug, company_slug_to_db_id, role_db_id_to_slug, role_slug_to_db_id


def get_user_target(user: dict | None) -> dict[str, str | None]:
    """Company and role slugs for this user, or None when unset."""
    if not user or not user.get("id"):
        return {"company_id": None, "role_id": None}
    from backend.db import get_database

    context = get_database()["target_contexts"].find_one({"user_id": str(user["id"])}) or {}
    company = context.get("company_id")
    role = context.get("role_id")
    if company or role:
        return {
            "company_id": str(company) if company else None,
            "role_id": str(role) if role else None,
        }
    company = user.get("target_company_id")
    role = user.get("target_role_id")
    if get_settings().database_url:
        company = company_db_id_to_slug(company) if company is not None else None
        role = role_db_id_to_slug(role) if role is not None else None
    return {
        "company_id": str(company) if company else None,
        "role_id": str(role) if role else None,
    }


def storage_target_id(slug: str | None, kind: str) -> Any:
    """Value to write into an integer foreign-key column, or the slug in memory mode."""
    if slug is None:
        return None
    if not get_settings().database_url:
        return slug
    resolved = company_slug_to_db_id(slug) if kind == "company" else role_slug_to_db_id(slug)
    return resolved
