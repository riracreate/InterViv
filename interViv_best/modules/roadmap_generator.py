"""Personalized Roadmap Generator.

Pulls the user's gap analysis (Task 4) and concept-mastery data
(Phase 2 Task 2) and lays out a recommended study plan over 7, 14,
or 30 days. The plan is a recommendation — not a binding schedule
— and the UI reflects that.

DESIGN (load-bearing, mirrored in the docstring of ``generate``)
================================================================

1. Identify the top 3-5 weak areas from ``GapAnalyzer``. We include
   both tested-with-a-gap entries and Untested required skills,
   because both are concrete things the candidate should practice
   before the interview.
2. For each weak skill, fetch the concepts the user hasn't
   demonstrated:
      a. If the user has any ConceptMastery rows for the skill,
         take all concepts whose level is Weak or Untested.
      b. Otherwise, fall back to the skill's KnowledgeGraph nodes
         (the full curated concept list) — these are the foundations
         we'd ask about anyway.
3. Distribute weak skills + concepts into weekly blocks. Default
   labels (30-day = 4 weeks):
      Week 1 → Foundations         (focus on top weak skill)
      Week 2 → Intermediate depth  (top weak skill + #2)
      Week 3 → Application & build (round out the top 3)
      Week 4 → Mock interviews     (full role coverage + behavioural)
4. For 7-day plans, collapse to 1 week with 4 daily phases. For
   14-day, use 2 weeks of [Foundations+Intermediate] / [App+Mock].
5. Each weekly block carries ``focus_topics`` (a flat list of
   skill+concept pairs) and ``daily_practice_suggestions``
   (free-form text guidance — no calendaring magic).

The generator is read-only: it never writes to the skill graph or
concept mastery store. It also gracefully degrades:
    - No skill graph yet → roadmap built entirely from Untested
      required skills + KG concepts.
    - No company profile match → raises ``RoadmapGenerationError``
      with a clear message.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from modules.company_graph import CompanyHiringGraph, Role, get_company_graph
from modules.concept_mastery import ConceptMastery, MasteryLevel
from modules.gap_analysis import GapAnalyzer, GapAnalysisError, WeakArea


SUPPORTED_DAYS = (7, 14, 30)
MAX_FOCUS_SKILLS = 5
MIN_FOCUS_SKILLS = 3
CONCEPTS_PER_SKILL = 6  # surface the first N missing concepts


DEFAULT_DAILY_SUGGESTIONS: dict[str, list[str]] = {
    "Foundations": [
        "Read the foundational concepts for each focus topic.",
        "Solve 2-3 warm-up problems per topic.",
        "Practice explaining one concept aloud in plain English.",
    ],
    "Intermediate depth": [
        "Tackle medium-difficulty problems on each focus topic.",
        "Compare two approaches per problem and write down trade-offs.",
        "Run a self-quiz on edge cases.",
    ],
    "Application & build": [
        "Pick one mini-project that exercises the top weak skill.",
        "Combine 2-3 concepts in a single design exercise.",
        "Time-box yourself: 30 minutes per problem, then review.",
    ],
    "Mock interviews": [
        "Run a 45-minute mock interview on interViv covering all focus skills.",
        "Record one behavioural answer and review for STAR structure.",
        "Re-attempt any topic that triggered low or medium readiness.",
    ],
}


@dataclass(frozen=True)
class FocusTopic:
    skill: str
    display_name: str
    concept: str | None
    severity: str  # mirrors gap_analysis severities + "Untested"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WeeklyBlock:
    index: int  # 1-based
    label: str  # "Foundations", "Intermediate depth", "Application & build", "Mock interviews"
    day_range: str  # "Days 1-7", etc.
    focus_skills: list[str]  # canonical names — convenient subset of focus_topics
    focus_topics: list[FocusTopic] = field(default_factory=list)
    daily_practice_suggestions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["focus_topics"] = [t.to_dict() for t in self.focus_topics]
        return payload


@dataclass(frozen=True)
class Roadmap:
    user_id: str
    role_id: str
    role_title: str
    company_id: str
    company_name: str
    days: int
    overall_readiness_percentage: float
    focus_skills: list[str]
    focus_concepts: list[str]
    weekly_blocks: list[WeeklyBlock] = field(default_factory=list)
    disclaimer: str = ""
    plan_note: str = (
        "This roadmap is a recommended plan based on your current readiness "
        "against the target role. Treat it as guidance — adjust pacing to "
        "suit your schedule. It is not a binding schedule."
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "role_id": self.role_id,
            "role_title": self.role_title,
            "company_id": self.company_id,
            "company_name": self.company_name,
            "days": self.days,
            "overall_readiness_percentage": self.overall_readiness_percentage,
            "focus_skills": list(self.focus_skills),
            "focus_concepts": list(self.focus_concepts),
            "weekly_blocks": [b.to_dict() for b in self.weekly_blocks],
            "disclaimer": self.disclaimer,
            "plan_note": self.plan_note,
        }


class RoadmapGenerationError(RuntimeError):
    pass


def _coerce_days(days: int) -> int:
    if days not in SUPPORTED_DAYS:
        # Snap to the nearest supported value.
        return min(SUPPORTED_DAYS, key=lambda d: abs(d - int(days)))
    return int(days)


def _week_layout(days: int) -> list[tuple[str, str]]:
    """Return ``[(label, day_range), ...]`` for the requested duration."""
    if days == 7:
        return [
            ("Foundations", "Days 1-2"),
            ("Intermediate depth", "Days 3-4"),
            ("Application & build", "Days 5-6"),
            ("Mock interviews", "Day 7"),
        ]
    if days == 14:
        return [
            ("Foundations", "Days 1-4"),
            ("Intermediate depth", "Days 5-8"),
            ("Application & build", "Days 9-12"),
            ("Mock interviews", "Days 13-14"),
        ]
    return [
        ("Foundations", "Days 1-7"),
        ("Intermediate depth", "Days 8-14"),
        ("Application & build", "Days 15-21"),
        ("Mock interviews", "Days 22-30"),
    ]


def _display_concept(value: str) -> str:
    return str(value).replace("_", " ").strip()


def _kg_concepts_for_skill(skill: str) -> list[str]:
    try:
        from modules.knowledge_graph import KnowledgeGraphScorer

        graph = KnowledgeGraphScorer().graphs.get(skill)
        if not graph:
            return []
        return [_display_concept(node) for node in graph.nodes]
    except Exception:
        return []


def _missing_concepts_for_skill(
    skill: str,
    mastery_map: dict[str, dict[str, MasteryLevel]],
    limit: int,
) -> list[str]:
    """Top ``limit`` concepts the user hasn't demonstrated for this skill."""
    user_concepts = mastery_map.get(skill, {})
    if user_concepts:
        weak_levels = {MasteryLevel.WEAK, MasteryLevel.UNTESTED}
        missing = [c for c, lvl in user_concepts.items() if lvl in weak_levels]
        if missing:
            return missing[:limit]
    # Fall back to the KG curated list — these are the canonical concepts.
    return _kg_concepts_for_skill(skill)[:limit]


def _roadmap_priority(wa: WeakArea) -> tuple[int, float]:
    """Roadmap-specific ordering.

    Tested weak skills always come before untested ones — they're proven
    gaps the user can immediately work on. Within each bucket, sort by
    ``rank_score`` desc. This intentionally differs from the gap analysis
    dashboard ranking (which is purely importance x gap, mixing tested
    and untested) because for a study plan, "what you've shown you're
    weak at" is more actionable than "what you haven't been tested on."
    """
    bucket = 0 if wa.tested else 1
    return (bucket, -wa.rank_score)


def _pick_focus_weak_areas(weak_areas: list[WeakArea]) -> list[WeakArea]:
    """Trim to 3-5 weak areas using the roadmap-specific priority."""
    if not weak_areas:
        return []
    ordered = sorted(weak_areas, key=_roadmap_priority)
    return ordered[: max(MIN_FOCUS_SKILLS, min(MAX_FOCUS_SKILLS, len(ordered)))]


def _build_focus_topics(
    weak_areas: list[WeakArea],
    mastery_map: dict[str, dict[str, MasteryLevel]],
) -> tuple[list[FocusTopic], dict[str, list[str]]]:
    """Return all FocusTopic rows + a ``{skill: [concepts]}`` index."""
    topics: list[FocusTopic] = []
    by_skill: dict[str, list[str]] = {}
    for wa in weak_areas:
        concepts = _missing_concepts_for_skill(wa.skill, mastery_map, CONCEPTS_PER_SKILL)
        by_skill[wa.skill] = concepts
        if not concepts:
            topics.append(
                FocusTopic(
                    skill=wa.skill,
                    display_name=wa.display_name,
                    concept=None,
                    severity=wa.gap_severity,
                )
            )
            continue
        for concept in concepts:
            topics.append(
                FocusTopic(
                    skill=wa.skill,
                    display_name=wa.display_name,
                    concept=concept,
                    severity=wa.gap_severity,
                )
            )
    return topics, by_skill


def _allocate_week_skills(
    weak_areas: list[WeakArea],
    layout: list[tuple[str, str]],
) -> list[list[str]]:
    """Decide which focus skills land in which week.

    The schedule is intentionally simple and surfaced for QA:
        Week 1 (Foundations):        top 1 weak skill
        Week 2 (Intermediate):       top 2 weak skills
        Week 3 (Application):        top 3 weak skills
        Week 4 (Mock):               all focus skills + behavioural if present
    """
    focus_names = [wa.skill for wa in weak_areas]
    if not focus_names:
        return [[] for _ in layout]

    weeks: list[list[str]] = []
    for i, _ in enumerate(layout):
        if i == 0:
            weeks.append(focus_names[:1])
        elif i == 1:
            weeks.append(focus_names[:2])
        elif i == 2:
            weeks.append(focus_names[:3])
        else:
            weeks.append(list(focus_names))
            if "HR" not in weeks[-1]:
                # Always include behavioural prep in mock-interview week.
                weeks[-1].append("HR")
    return weeks


class RoadmapGenerator:
    def __init__(
        self,
        graph: CompanyHiringGraph | None = None,
        analyzer: GapAnalyzer | None = None,
        concept_mastery: ConceptMastery | None = None,
    ) -> None:
        self._graph = graph or get_company_graph()
        self._analyzer = analyzer or GapAnalyzer(self._graph)
        self._concept_mastery = concept_mastery or ConceptMastery()

    def generate(self, user_id: str, role_id: str, days: int = 30) -> Roadmap:
        """Generate a personalized roadmap.

        Args:
            user_id:  the user whose skill graph + concept mastery to read.
            role_id:  YAML role slug (e.g. "amazon_sde_intern").
            days:     plan duration; snapped to 7, 14, or 30.

        Raises:
            RoadmapGenerationError: if the role_id is unknown.
        """
        days = _coerce_days(days)

        try:
            report = self._analyzer.compute_gap(user_id=user_id, role_id=role_id)
        except GapAnalysisError as exc:
            raise RoadmapGenerationError(str(exc)) from exc

        entry = self._graph.find_role(role_id)
        if entry is None:
            raise RoadmapGenerationError(f"Unknown role '{role_id}'.")
        _, role = entry

        focus_weak_areas = _pick_focus_weak_areas(report.ranked_weak_areas)
        mastery_map = self._concept_mastery.get_mastery_map(user_id)
        focus_topics, concepts_by_skill = _build_focus_topics(focus_weak_areas, mastery_map)

        layout = _week_layout(days)
        per_week_skills = _allocate_week_skills(focus_weak_areas, layout)

        weekly_blocks: list[WeeklyBlock] = []
        for i, (label, day_range) in enumerate(layout):
            wk_skills = per_week_skills[i]
            wk_topics: list[FocusTopic] = []
            for skill in wk_skills:
                wk_topics.extend(t for t in focus_topics if t.skill == skill)
                if skill not in {t.skill for t in focus_topics}:
                    # HR injected in week 4 even when no gap data exists.
                    role_req = next(
                        (r for r in role.skill_requirements if r.skill == skill), None
                    )
                    wk_topics.append(
                        FocusTopic(
                            skill=skill,
                            display_name=(role_req.display_name if role_req else skill),
                            concept=None,
                            severity="Untested",
                        )
                    )
            weekly_blocks.append(
                WeeklyBlock(
                    index=i + 1,
                    label=label,
                    day_range=day_range,
                    focus_skills=list(wk_skills),
                    focus_topics=wk_topics,
                    daily_practice_suggestions=list(DEFAULT_DAILY_SUGGESTIONS.get(label, [])),
                )
            )

        focus_skill_names = [wa.skill for wa in focus_weak_areas]
        focus_concept_set: list[str] = []
        seen: set[str] = set()
        for skill in focus_skill_names:
            for c in concepts_by_skill.get(skill, []):
                if c not in seen:
                    focus_concept_set.append(c)
                    seen.add(c)

        return Roadmap(
            user_id=user_id,
            role_id=role.id,
            role_title=role.title,
            company_id=report.company_id,
            company_name=report.company_name,
            days=days,
            overall_readiness_percentage=report.overall_readiness_percentage,
            focus_skills=focus_skill_names,
            focus_concepts=focus_concept_set,
            weekly_blocks=weekly_blocks,
            disclaimer=report.disclaimer,
        )


__all__ = [
    "FocusTopic",
    "Roadmap",
    "RoadmapGenerator",
    "RoadmapGenerationError",
    "SUPPORTED_DAYS",
    "WeeklyBlock",
]
