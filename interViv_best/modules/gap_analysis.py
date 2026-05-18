"""Gap Analysis engine.

Joins a student's persistent ``StudentSkillGraph`` against a company role's
``skill_requirements`` (sourced from the curated YAML) and produces a
``GapAnalysisReport``.

FORMULA (load-bearing — surfaced to UI and docs verbatim)
=========================================================

Per-skill readiness:

    per_skill_readiness = min(student_level / required_level, 1.0) * 100

Overall readiness (weighted average across **tested** required skills only):

    overall_readiness = sum_t(weight_t * per_skill_readiness_t) / sum_t(weight_t)

    where t iterates over the role's required skills that the student has
    actually practiced at least once. Untested required skills are surfaced
    in `per_skill_gap` as `tested=False` with `gap_severity="Untested"`, but
    do NOT contribute to the overall_readiness numerator or denominator.

    Rationale: we don't want to manufacture a fake level for untested
    skills. Excluding them keeps overall_readiness honest as "how strong is
    the candidate on the role skills they have actually demonstrated." The
    UI then highlights Untested skills prominently as "you haven't been
    tested on this yet — practice next."

Severity (over tested skills only):

    gap = required_level - student_level
    gap_severity = "High"   if gap > 25
                 = "Medium" if 10 < gap <= 25
                 = "Low"    if gap <= 10

    Untested skills are assigned severity "Untested".

Weak-area ranking:

    rank_score = importance_weight * gap_for_ranking
    gap_for_ranking = required_level if tested=False    # weight x required
                    = max(0, required_level - student_level)  # tested gap

    Sorted descending by rank_score. We use ``required_level`` for untested
    skills so high-importance untested entries surface near the top even
    though we don't yet have a student level.

The function ``compute_gap_for_levels`` is the pure, side-effect-free core
that callers can use directly with a ``{skill: student_level}`` dict (e.g.
for tests or "what-if" UI scenarios that don't write to the skill graph).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from modules.company_graph import (
    CompanyHiringGraph,
    Role,
    SkillRequirement,
    get_company_graph,
)
from modules.skill_graph import StudentSkillGraph


SEVERITY_HIGH_THRESHOLD = 25
SEVERITY_MEDIUM_THRESHOLD = 10


@dataclass(frozen=True)
class SkillGap:
    skill: str
    display_name: str
    student_level: float | None
    required_level: float
    gap_severity: str  # "High" | "Medium" | "Low" | "Untested"
    importance_weight: float
    per_skill_readiness: float  # 0-100, 0.0 for Untested
    attempts: int
    tested: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WeakArea:
    skill: str
    display_name: str
    gap_severity: str
    importance_weight: float
    student_level: float | None
    required_level: float
    rank_score: float
    tested: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GapAnalysisReport:
    user_id: str | None
    role_id: str
    role_title: str
    company_id: str
    company_name: str
    overall_readiness_percentage: float
    per_skill_gap: list[SkillGap] = field(default_factory=list)
    ranked_weak_areas: list[WeakArea] = field(default_factory=list)
    tested_skill_count: int = 0
    required_skill_count: int = 0
    disclaimer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "role_id": self.role_id,
            "role_title": self.role_title,
            "company_id": self.company_id,
            "company_name": self.company_name,
            "overall_readiness_percentage": self.overall_readiness_percentage,
            "tested_skill_count": self.tested_skill_count,
            "required_skill_count": self.required_skill_count,
            "per_skill_gap": [g.to_dict() for g in self.per_skill_gap],
            "ranked_weak_areas": [w.to_dict() for w in self.ranked_weak_areas],
            "disclaimer": self.disclaimer,
        }


def _severity_for_gap(gap: float) -> str:
    if gap > SEVERITY_HIGH_THRESHOLD:
        return "High"
    if gap > SEVERITY_MEDIUM_THRESHOLD:
        return "Medium"
    return "Low"


def _student_level_lookup(
    student_state: dict[str, Any],
    skill: str,
) -> tuple[float | None, int]:
    """Return (current_score, attempts) for a canonical skill name.

    Returns (None, 0) when the user has no skill_graph entry OR an entry
    with attempts == 0 (initialized from resume but never practiced).
    """
    node = student_state.get(skill)
    if node is None:
        return (None, 0)
    attempts = int(getattr(node, "attempts", 0))
    if attempts == 0:
        return (None, 0)
    return (float(getattr(node, "current_score", 0.0)), attempts)


def _build_skill_gap(req: SkillRequirement, student_level: float | None, attempts: int) -> SkillGap:
    if student_level is None:
        return SkillGap(
            skill=req.skill,
            display_name=req.display_name or req.skill,
            student_level=None,
            required_level=req.required_level,
            gap_severity="Untested",
            importance_weight=req.importance_weight,
            per_skill_readiness=0.0,
            attempts=0,
            tested=False,
        )

    if req.required_level <= 0:
        readiness = 100.0
        severity = "Low"
    else:
        readiness = min(student_level / req.required_level, 1.0) * 100.0
        severity = _severity_for_gap(req.required_level - student_level)

    return SkillGap(
        skill=req.skill,
        display_name=req.display_name or req.skill,
        student_level=round(float(student_level), 2),
        required_level=float(req.required_level),
        gap_severity=severity,
        importance_weight=float(req.importance_weight),
        per_skill_readiness=round(readiness, 2),
        attempts=int(attempts),
        tested=True,
    )


def _rank_weak_areas(gaps: list[SkillGap]) -> list[WeakArea]:
    weak: list[WeakArea] = []
    for g in gaps:
        if g.tested and g.gap_severity == "Low":
            continue
        if g.tested:
            gap_for_ranking = max(0.0, g.required_level - (g.student_level or 0.0))
        else:
            gap_for_ranking = g.required_level
        rank_score = g.importance_weight * gap_for_ranking
        weak.append(
            WeakArea(
                skill=g.skill,
                display_name=g.display_name,
                gap_severity=g.gap_severity,
                importance_weight=g.importance_weight,
                student_level=g.student_level,
                required_level=g.required_level,
                rank_score=round(rank_score, 2),
                tested=g.tested,
            )
        )
    weak.sort(key=lambda w: (-w.rank_score, w.skill))
    return weak


def compute_gap_for_levels(
    role: Role,
    student_levels: dict[str, tuple[float | None, int]],
    *,
    company_id: str = "",
    company_name: str = "",
    user_id: str | None = None,
    disclaimer: str = "",
) -> GapAnalysisReport:
    """Pure core: compute the report from an explicit ``{skill: (level, attempts)}`` dict.

    Used by the route handler (after fetching live skill graph state) and
    by unit tests (passing synthesized levels).
    """
    per_skill_gap: list[SkillGap] = []
    weighted_sum = 0.0
    weight_total = 0.0

    for req in role.skill_requirements:
        level, attempts = student_levels.get(req.skill, (None, 0))
        gap = _build_skill_gap(req, level, attempts)
        per_skill_gap.append(gap)
        if gap.tested:
            weighted_sum += gap.importance_weight * gap.per_skill_readiness
            weight_total += gap.importance_weight

    overall = round(weighted_sum / weight_total, 2) if weight_total > 0 else 0.0

    return GapAnalysisReport(
        user_id=user_id,
        role_id=role.id,
        role_title=role.title,
        company_id=company_id,
        company_name=company_name,
        overall_readiness_percentage=overall,
        per_skill_gap=per_skill_gap,
        ranked_weak_areas=_rank_weak_areas(per_skill_gap),
        tested_skill_count=sum(1 for g in per_skill_gap if g.tested),
        required_skill_count=len(per_skill_gap),
        disclaimer=disclaimer,
    )


class GapAnalysisError(RuntimeError):
    pass


class GapAnalyzer:
    """Live engine: pulls from StudentSkillGraph + the company hiring graph."""

    def __init__(self, graph: CompanyHiringGraph | None = None) -> None:
        self._graph = graph or get_company_graph()

    def compute_gap(self, user_id: str, role_id: str) -> GapAnalysisReport:
        entry = self._graph.find_role(role_id)
        if entry is None:
            raise GapAnalysisError(f"Unknown role '{role_id}'.")
        company, role = entry

        skill_graph = StudentSkillGraph(user_id)
        state = skill_graph.get_current_state()
        student_levels: dict[str, tuple[float | None, int]] = {}
        for req in role.skill_requirements:
            level, attempts = _student_level_lookup(state, req.skill)
            student_levels[req.skill] = (level, attempts)

        return compute_gap_for_levels(
            role,
            student_levels,
            company_id=company.id,
            company_name=company.name,
            user_id=user_id,
            disclaimer=self._graph.disclaimer,
        )


__all__ = [
    "GapAnalyzer",
    "GapAnalysisError",
    "GapAnalysisReport",
    "SkillGap",
    "WeakArea",
    "compute_gap_for_levels",
]
