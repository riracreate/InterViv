"""Idempotent seeder for the company hiring graph.

Reads modules/data/company_hiring_graphs.yaml via ``modules.company_graph`` and
upserts:

  - skills          (canonical_name unique)
  - companies       (name unique)
  - roles           (company_id + title + level unique)
  - company_role_requirements (role_id + skill_id unique)

The seeder is a no-op when DATABASE_URL is unset (in-memory mode). The
companies API still works in that case because the YAML loader is the source
of truth.

We also maintain two YAML-id -> DB-id maps in memory so route handlers can
translate the URL slugs the YAML uses (``amazon``, ``amazon_sde_intern``) to
the integer primary keys the SQL tables use.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.config import get_settings
from modules.company_graph import (
    CompanyHiringGraph,
    Role,
    SkillRequirement,
    get_company_graph,
)


LOGGER = logging.getLogger(__name__)


_COMPANY_SLUG_TO_DB_ID: dict[str, int] = {}
_ROLE_SLUG_TO_DB_ID: dict[str, int] = {}
_SKILL_NAME_TO_DB_ID: dict[str, int] = {}
_LOADED_FOR: str | None = None


def clear_slug_cache() -> None:
    """Drop the in-memory slug cache. The next lookup refills it from the database."""
    global _LOADED_FOR
    _COMPANY_SLUG_TO_DB_ID.clear()
    _ROLE_SLUG_TO_DB_ID.clear()
    _SKILL_NAME_TO_DB_ID.clear()
    _LOADED_FOR = None


def company_slug_to_db_id(slug: str) -> int | None:
    if not get_settings().database_url:
        return None
    _refill_slug_maps()
    return _COMPANY_SLUG_TO_DB_ID.get(slug)


def role_slug_to_db_id(slug: str) -> int | None:
    if not get_settings().database_url:
        return None
    _refill_slug_maps()
    return _ROLE_SLUG_TO_DB_ID.get(slug)


def company_db_id_to_slug(db_id: int | str | None) -> str | None:
    if db_id is None:
        return None
    try:
        target = int(db_id)
    except (TypeError, ValueError):
        return str(db_id)
    if get_settings().database_url:
        _refill_slug_maps()
    for slug, mapped_id in _COMPANY_SLUG_TO_DB_ID.items():
        if mapped_id == target:
            return slug
    return None


def role_db_id_to_slug(db_id: int | str | None) -> str | None:
    if db_id is None:
        return None
    try:
        target = int(db_id)
    except (TypeError, ValueError):
        return str(db_id)
    if get_settings().database_url:
        _refill_slug_maps()
    for slug, mapped_id in _ROLE_SLUG_TO_DB_ID.items():
        if mapped_id == target:
            return slug
    return None


def skill_name_to_db_id(name: str) -> int | None:
    return _SKILL_NAME_TO_DB_ID.get(name)


def seed_company_graph(graph: CompanyHiringGraph | None = None) -> dict[str, int]:
    """Seed companies, roles, skills, and requirements.

    Returns a counts dict (``{"companies": N, "roles": N, "skills": N,
    "requirements": N}``). Idempotent: re-running uses unique constraints
    plus per-row UPDATE-then-INSERT to avoid duplicates.

    No-op when DATABASE_URL is unset.
    """
    settings = get_settings()
    if not settings.database_url:
        LOGGER.info("DATABASE_URL unset; skipping company graph DB seed.")
        return {"companies": 0, "roles": 0, "skills": 0, "requirements": 0}

    from sqlalchemy import select

    from backend.db.sqlalchemy_models import (
        CompanyRoleRequirementRow,
        CompanyRow,
        RoleRow,
        SkillRow,
    )
    from backend.db.sqlalchemy_store import session_scope

    graph = graph or get_company_graph()

    counts = {"companies": 0, "roles": 0, "skills": 0, "requirements": 0}

    clear_slug_cache()

    with session_scope() as session:
        # Skills first (FK target for requirements)
        all_skills: set[str] = set()
        for company in graph.list_companies():
            for role in company.roles:
                for req in role.skill_requirements:
                    all_skills.add(req.skill)

        for skill_name in sorted(all_skills):
            existing = session.execute(
                select(SkillRow).where(SkillRow.canonical_name == skill_name)
            ).scalar_one_or_none()
            if existing is None:
                row = SkillRow(canonical_name=skill_name)
                session.add(row)
                session.flush()
                counts["skills"] += 1
                _SKILL_NAME_TO_DB_ID[skill_name] = row.id
            else:
                _SKILL_NAME_TO_DB_ID[skill_name] = existing.id

        # Companies + roles
        for company in graph.list_companies():
            db_company = session.execute(
                select(CompanyRow).where(CompanyRow.name == company.name)
            ).scalar_one_or_none()
            if db_company is None:
                db_company = CompanyRow(
                    name=company.name,
                    logo_url=company.logo_url,
                    public_info=_public_info_with_slug(company.id, company.public_info),
                )
                session.add(db_company)
                session.flush()
                counts["companies"] += 1
            else:
                db_company.logo_url = company.logo_url
                db_company.public_info = _public_info_with_slug(
                    company.id, company.public_info
                )
            _COMPANY_SLUG_TO_DB_ID[company.id] = db_company.id

            for role in company.roles:
                db_role = _upsert_role(session, db_company.id, role, counts)
                _ROLE_SLUG_TO_DB_ID[role.id] = db_role.id
                _upsert_role_requirements(session, db_role.id, role.skill_requirements, counts)

    global _LOADED_FOR
    _LOADED_FOR = settings.database_url
    LOGGER.info("Company graph seed counts: %s", counts)
    return counts


def _refill_slug_maps() -> None:
    """Load slug → id from companies.public_info and matching role rows.

    The in-memory maps are a cache. A new process, or a cleared cache, still
    resolves against rows the seeder already wrote. No-op without a database.
    """
    global _LOADED_FOR
    settings = get_settings()
    url = settings.database_url or ""
    if _LOADED_FOR == url:
        return
    _COMPANY_SLUG_TO_DB_ID.clear()
    _ROLE_SLUG_TO_DB_ID.clear()
    if not url:
        _LOADED_FOR = url
        return

    from sqlalchemy import select

    from backend.db.sqlalchemy_models import CompanyRow, RoleRow
    from backend.db.sqlalchemy_store import session_scope

    graph = get_company_graph()
    with session_scope() as session:
        company_rows = list(session.scalars(select(CompanyRow)))
        role_rows = list(session.scalars(select(RoleRow)))
    for row in company_rows:
        info = row.public_info if isinstance(row.public_info, dict) else {}
        slug = info.get("slug")
        if slug:
            _COMPANY_SLUG_TO_DB_ID[str(slug)] = row.id
    role_index = {(row.company_id, row.title, row.level): row.id for row in role_rows}
    for company in graph.list_companies():
        company_id = _COMPANY_SLUG_TO_DB_ID.get(company.id)
        if company_id is None:
            continue
        for role in company.roles:
            role_id = role_index.get((company_id, role.title, role.level))
            if role_id is not None:
                _ROLE_SLUG_TO_DB_ID[role.id] = role_id
    _LOADED_FOR = url


def _public_info_with_slug(slug: str, public_info: dict[str, Any]) -> dict[str, Any]:
    merged = dict(public_info or {})
    merged.setdefault("slug", slug)
    return merged


def _upsert_role(session, company_db_id: int, role: Role, counts: dict[str, int]):
    from sqlalchemy import select

    from backend.db.sqlalchemy_models import RoleRow

    existing = session.execute(
        select(RoleRow).where(
            RoleRow.company_id == company_db_id,
            RoleRow.title == role.title,
            RoleRow.level == role.level,
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = RoleRow(
            company_id=company_db_id,
            title=role.title,
            level=role.level,
        )
        session.add(existing)
        session.flush()
        counts["roles"] += 1
    return existing


def _upsert_role_requirements(
    session,
    role_db_id: int,
    requirements: list[SkillRequirement],
    counts: dict[str, int],
) -> None:
    from sqlalchemy import select

    from backend.db.sqlalchemy_models import CompanyRoleRequirementRow

    for req in requirements:
        skill_db_id = _SKILL_NAME_TO_DB_ID.get(req.skill)
        if skill_db_id is None:
            LOGGER.warning("Skill %r not seeded; skipping requirement.", req.skill)
            continue
        existing = session.execute(
            select(CompanyRoleRequirementRow).where(
                CompanyRoleRequirementRow.role_id == role_db_id,
                CompanyRoleRequirementRow.skill_id == skill_db_id,
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                CompanyRoleRequirementRow(
                    role_id=role_db_id,
                    skill_id=skill_db_id,
                    required_level=req.required_level,
                    importance_weight=req.importance_weight,
                )
            )
            counts["requirements"] += 1
        else:
            existing.required_level = req.required_level
            existing.importance_weight = req.importance_weight


__all__ = [
    "clear_slug_cache",
    "company_db_id_to_slug",
    "company_slug_to_db_id",
    "role_db_id_to_slug",
    "role_slug_to_db_id",
    "seed_company_graph",
    "skill_name_to_db_id",
]
