"""Company Hiring Graph loader.

DISCLAIMER (load-bearing):
    Company hiring profiles are curated from publicly available job descriptions,
    observed placement patterns, and industry references. These are reference
    profiles for practice preparation, not exact hiring criteria. The required
    levels and importance weights are interViv's curation, not the companies'
    stated rubric.

This module reads data/company_hiring_graphs.yaml at startup and exposes a
read-only API:

    graph = get_company_graph()
    graph.list_companies() -> List[Company]
    graph.get_company(company_id) -> Company | None
    graph.get_role(company_id, role_id) -> Role | None
    graph.get_required_skills(role_id) -> List[SkillRequirement]
    graph.disclaimer -> str

The loader is module-level cached; tests can call ``reload_company_graph(path)``
to force a re-read.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from backend.config import get_settings


DEFAULT_RELATIVE_PATH = Path("data") / "company_hiring_graphs.yaml"

DEFAULT_DISCLAIMER = (
    "Company hiring profiles are curated from publicly available job "
    "descriptions, observed placement patterns, and industry references. "
    "These are reference profiles for practice preparation, not exact hiring "
    "criteria."
)


@dataclass(frozen=True)
class SkillRequirement:
    skill: str
    required_level: float
    importance_weight: float
    display_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "display_name": self.display_name or self.skill,
            "required_level": self.required_level,
            "importance_weight": self.importance_weight,
        }


@dataclass(frozen=True)
class Role:
    id: str
    title: str
    level: str | None
    skill_requirements: list[SkillRequirement] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "level": self.level,
            "skill_requirements": [req.to_dict() for req in self.skill_requirements],
        }


@dataclass(frozen=True)
class Company:
    id: str
    name: str
    logo_url: str | None
    public_info: dict[str, Any] = field(default_factory=dict)
    roles: list[Role] = field(default_factory=list)

    def to_dict(self, include_roles: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "logo_url": self.logo_url,
            "public_info": self.public_info,
        }
        if include_roles:
            payload["roles"] = [role.to_dict() for role in self.roles]
        return payload


class CompanyGraphError(RuntimeError):
    pass


class CompanyHiringGraph:
    """In-memory, read-only company hiring graph."""

    def __init__(
        self,
        companies: list[Company],
        disclaimer: str,
        source_path: Path | None = None,
    ) -> None:
        self._companies = companies
        self._by_id = {c.id: c for c in companies}
        self._role_index: dict[str, tuple[Company, Role]] = {}
        for company in companies:
            for role in company.roles:
                self._role_index[role.id] = (company, role)
        self._disclaimer = disclaimer
        self._source_path = source_path

    @property
    def disclaimer(self) -> str:
        return self._disclaimer

    @property
    def source_path(self) -> Path | None:
        return self._source_path

    def list_companies(self) -> list[Company]:
        return list(self._companies)

    def get_company(self, company_id: str) -> Company | None:
        return self._by_id.get(company_id)

    def get_role(self, company_id: str, role_id: str) -> Role | None:
        entry = self._role_index.get(role_id)
        if entry is None:
            return None
        company, role = entry
        if company.id != company_id:
            return None
        return role

    def find_role(self, role_id: str) -> tuple[Company, Role] | None:
        return self._role_index.get(role_id)

    def get_required_skills(self, role_id: str) -> list[SkillRequirement]:
        entry = self._role_index.get(role_id)
        if entry is None:
            return []
        _, role = entry
        return list(role.skill_requirements)


def _coerce_requirement(raw: dict[str, Any]) -> SkillRequirement:
    if "skill" not in raw:
        raise CompanyGraphError(f"skill_requirements entry missing 'skill': {raw!r}")
    if "required_level" not in raw:
        raise CompanyGraphError(f"skill_requirements entry missing 'required_level': {raw!r}")
    if "importance_weight" not in raw:
        raise CompanyGraphError(f"skill_requirements entry missing 'importance_weight': {raw!r}")
    return SkillRequirement(
        skill=str(raw["skill"]).strip(),
        required_level=float(raw["required_level"]),
        importance_weight=float(raw["importance_weight"]),
        display_name=(raw.get("display_name") or None),
    )


def _coerce_role(raw: dict[str, Any]) -> Role:
    if "id" not in raw or "title" not in raw:
        raise CompanyGraphError(f"role missing id/title: {raw!r}")
    reqs_raw = raw.get("skill_requirements") or []
    reqs = [_coerce_requirement(r) for r in reqs_raw]
    weight_sum = sum(r.importance_weight for r in reqs)
    if reqs and abs(weight_sum - 1.0) > 0.05:
        raise CompanyGraphError(
            f"role {raw['id']!r} weights sum to {weight_sum:.3f}, expected ~1.0"
        )
    return Role(
        id=str(raw["id"]).strip(),
        title=str(raw["title"]).strip(),
        level=(str(raw["level"]).strip() if raw.get("level") else None),
        skill_requirements=reqs,
    )


def _coerce_company(raw: dict[str, Any]) -> Company:
    if "id" not in raw or "name" not in raw:
        raise CompanyGraphError(f"company missing id/name: {raw!r}")
    roles_raw = raw.get("roles") or []
    return Company(
        id=str(raw["id"]).strip(),
        name=str(raw["name"]).strip(),
        logo_url=(str(raw["logo_url"]).strip() if raw.get("logo_url") else None),
        public_info=dict(raw.get("public_info") or {}),
        roles=[_coerce_role(r) for r in roles_raw],
    )


def load_company_graph(path: Path | None = None) -> CompanyHiringGraph:
    settings = get_settings()
    candidate = path or (settings.project_root / DEFAULT_RELATIVE_PATH)
    if not candidate.exists():
        raise CompanyGraphError(f"company hiring graph not found: {candidate}")

    with candidate.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    if not isinstance(raw, dict):
        raise CompanyGraphError("company hiring graph root must be a mapping")

    disclaimer = str(raw.get("disclaimer") or DEFAULT_DISCLAIMER).strip()
    companies_raw = raw.get("companies") or []
    if not isinstance(companies_raw, list):
        raise CompanyGraphError("'companies' must be a list")

    companies = [_coerce_company(c) for c in companies_raw]
    return CompanyHiringGraph(companies=companies, disclaimer=disclaimer, source_path=candidate)


_CACHED_GRAPH: CompanyHiringGraph | None = None


def get_company_graph() -> CompanyHiringGraph:
    global _CACHED_GRAPH
    if _CACHED_GRAPH is None:
        _CACHED_GRAPH = load_company_graph()
    return _CACHED_GRAPH


def reload_company_graph(path: Path | None = None) -> CompanyHiringGraph:
    global _CACHED_GRAPH
    _CACHED_GRAPH = load_company_graph(path)
    return _CACHED_GRAPH


__all__ = [
    "Company",
    "CompanyGraphError",
    "CompanyHiringGraph",
    "DEFAULT_DISCLAIMER",
    "Role",
    "SkillRequirement",
    "get_company_graph",
    "load_company_graph",
    "reload_company_graph",
]
