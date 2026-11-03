"""Policy-aware planning evidence for Gap/Roadmap/Coach (Phase 4B).

Does not change scoring formulas. Classifies existing round + graph evidence
into populations the deterministic planner may use:

* ``eligible`` — independently assessed (primary weaknesses)
* ``assisted_practice`` — practiced with help; practice recommendation only
* ``legacy_unknown`` — pre-policy or incomplete history; not independent mastery
* ``unassessed`` — role-required or goal skill with no attempts
* ``planning_context`` — resume/JD/interests (never demonstrated proficiency)
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from backend.evidence_kind import (
    assessment_eligible_rounds,
    is_practice_review_round,
    is_self_reported_round,
)
from modules.assistance_policy import read_persisted_eligibility

_log = logging.getLogger(__name__)


POP_ELIGIBLE = "eligible"
POP_ASSISTED = "assisted_practice"
POP_LEGACY = "legacy_unknown"
POP_UNASSESSED = "unassessed"
POP_CONTEXT = "planning_context"

EVIDENCE_SCHEMA_VERSION = "planning_evidence_v1"


@dataclass
class SkillEvidence:
    skill: str
    population: str
    attempts: int = 0
    mean_score: float | None = None
    current_score: float | None = None
    rationale: str = ""
    source_round_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlanningEvidence:
    user_id: str
    role_id: str | None
    schema_version: str = EVIDENCE_SCHEMA_VERSION
    evidence_digest: str = ""
    has_eligible_assessment: bool = False
    eligible: list[SkillEvidence] = field(default_factory=list)
    assisted_practice: list[SkillEvidence] = field(default_factory=list)
    legacy_unknown: list[SkillEvidence] = field(default_factory=list)
    unassessed: list[SkillEvidence] = field(default_factory=list)
    planning_context_skills: list[str] = field(default_factory=list)
    confirmed_goal: str | None = None
    hours_per_week: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "role_id": self.role_id,
            "schema_version": self.schema_version,
            "evidence_digest": self.evidence_digest,
            "has_eligible_assessment": self.has_eligible_assessment,
            "eligible": [s.to_dict() for s in self.eligible],
            "assisted_practice": [s.to_dict() for s in self.assisted_practice],
            "legacy_unknown": [s.to_dict() for s in self.legacy_unknown],
            "unassessed": [s.to_dict() for s in self.unassessed],
            "planning_context_skills": list(self.planning_context_skills),
            "confirmed_goal": self.confirmed_goal,
            "hours_per_week": self.hours_per_week,
        }


def _skill_key(skill: str) -> str:
    return str(skill or "").strip() or "General"


def _mean(scores: list[float]) -> float | None:
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def _bucket_rounds(rounds: list[dict[str, Any]]) -> dict[str, dict[str, list]]:
    """skill -> population -> list of scores / round keys."""
    out: dict[str, dict[str, list]] = {}
    for item in rounds:
        if item.get("final_score") is None:
            continue
        if is_self_reported_round(item) or is_practice_review_round(item):
            continue
        skill = _skill_key(str(item.get("skill") or "General"))
        info = read_persisted_eligibility(item)
        pop = POP_ELIGIBLE
        if info.get("legacy"):
            if item.get("assisted") or item.get("is_follow_up"):
                pop = POP_ASSISTED
            else:
                pop = POP_LEGACY
        else:
            decision = str(info.get("decision") or "")
            if decision == "eligible":
                pop = POP_ELIGIBLE
            elif decision in ("excluded", "unknown"):
                pop = POP_ASSISTED if decision == "excluded" else POP_LEGACY
            elif decision == "legacy_unknown":
                pop = POP_LEGACY
            else:
                pop = POP_LEGACY
        slot = out.setdefault(skill, {})
        bucket = slot.setdefault(pop, {"scores": [], "ids": []})
        bucket["scores"].append(float(item["final_score"]))
        bucket["ids"].append(
            f"{item.get('session_id') or ''}:{item.get('round')}"
        )
    return out


def collect_planning_evidence(
    *,
    user_id: str,
    role_id: str | None = None,
    confirmed_goal: str | None = None,
    hours_per_week: int | None = None,
    planning_context_skills: list[str] | None = None,
    db: Any | None = None,
) -> PlanningEvidence:
    """Build a read-only evidence view for deterministic planning."""
    from backend.db import get_database
    from modules.company_graph import get_company_graph
    from modules.skill_graph import StudentSkillGraph

    user_id = str(user_id or "").strip()
    role_id = str(role_id).strip() if role_id else None
    db = db or get_database()
    sessions = list(db["sessions"].find({"user_id": user_id}) or [])
    rounds: list[dict[str, Any]] = []
    for session in sessions:
        sid = session.get("session_id")
        for item in session.get("rounds") or []:
            row = dict(item)
            row.setdefault("session_id", sid)
            rounds.append(row)

    buckets = _bucket_rounds(rounds)
    graph_state = StudentSkillGraph(user_id).get_current_state()

    eligible: list[SkillEvidence] = []
    assisted: list[SkillEvidence] = []
    legacy: list[SkillEvidence] = []

    for skill, pops in sorted(buckets.items()):
        graph_score = None
        graph_attempts = 0
        node = graph_state.get(skill)
        if node is not None:
            graph_score = float(node.current_score)
            graph_attempts = int(node.attempts or 0)

        if POP_ELIGIBLE in pops:
            scores = pops[POP_ELIGIBLE]["scores"]
            eligible.append(
                SkillEvidence(
                    skill=skill,
                    population=POP_ELIGIBLE,
                    attempts=len(scores),
                    mean_score=_mean(scores),
                    current_score=graph_score if graph_attempts else _mean(scores),
                    rationale=(
                        f"Eligible assessment mean {_mean(scores)} "
                        f"across {len(scores)} attempt(s)."
                    ),
                    source_round_ids=list(pops[POP_ELIGIBLE]["ids"]),
                )
            )
        if POP_ASSISTED in pops:
            scores = pops[POP_ASSISTED]["scores"]
            assisted.append(
                SkillEvidence(
                    skill=skill,
                    population=POP_ASSISTED,
                    attempts=len(scores),
                    mean_score=_mean(scores),
                    current_score=None,
                    rationale=(
                        "Assistance-only practice — recommend independent "
                        "assessment before treating as mastery."
                    ),
                    source_round_ids=list(pops[POP_ASSISTED]["ids"]),
                )
            )
        if POP_LEGACY in pops and POP_ELIGIBLE not in pops:
            scores = pops[POP_LEGACY]["scores"]
            legacy.append(
                SkillEvidence(
                    skill=skill,
                    population=POP_LEGACY,
                    attempts=len(scores),
                    mean_score=_mean(scores),
                    current_score=None,
                    rationale=(
                        "Legacy or incomplete assistance coverage — not "
                        "treated as independently assessed."
                    ),
                    source_round_ids=list(pops[POP_LEGACY]["ids"]),
                )
            )

    assessed_skills = {s.skill for s in eligible} | {s.skill for s in assisted} | {
        s.skill for s in legacy
    }
    unassessed: list[SkillEvidence] = []
    if role_id:
        # find_role resolves a role id without its company; get_role needs both.
        role = None
        try:
            match = get_company_graph().find_role(role_id)
        except Exception:  # graph load failure must not break planning
            _log.warning("planning_evidence: company graph unavailable", exc_info=True)
        else:
            if match is None:
                _log.info("planning_evidence: unknown role_id %r", role_id)
            else:
                role = match[1]
        if role is not None:
            for req in role.skill_requirements:
                skill = _skill_key(req.skill)
                if skill in assessed_skills:
                    continue
                node = graph_state.get(skill)
                if node is not None and int(node.attempts or 0) > 0:
                    continue
                unassessed.append(
                    SkillEvidence(
                        skill=skill,
                        population=POP_UNASSESSED,
                        attempts=0,
                        rationale=f"Required for {role.title}; not yet assessed.",
                    )
                )

    context = [
        _skill_key(s)
        for s in (planning_context_skills or [])
        if _skill_key(s)
    ]
    evidence = PlanningEvidence(
        user_id=user_id,
        role_id=role_id,
        has_eligible_assessment=bool(eligible),
        eligible=eligible,
        assisted_practice=assisted,
        legacy_unknown=legacy,
        unassessed=unassessed,
        planning_context_skills=context,
        confirmed_goal=(confirmed_goal or "").strip() or None,
        hours_per_week=hours_per_week,
    )
    digest_src = (
        f"{EVIDENCE_SCHEMA_VERSION}|{user_id}|{role_id}|"
        f"{sorted((s.skill, s.population, s.attempts, s.mean_score) for s in eligible)}|"
        f"{sorted((s.skill, s.attempts) for s in assisted)}|"
        f"{sorted(s.skill for s in unassessed)}|"
        f"{context}|{evidence.confirmed_goal}|{hours_per_week}"
    )
    evidence.evidence_digest = hashlib.sha256(digest_src.encode("utf-8")).hexdigest()[:24]
    return evidence


def weak_eligible_skills(evidence: PlanningEvidence, *, limit: int = 5) -> list[SkillEvidence]:
    """Eligible skills ordered weakest-first for assessed recommendations."""
    ranked = sorted(
        evidence.eligible,
        key=lambda s: (
            float(s.current_score if s.current_score is not None else s.mean_score or 0.0),
            -s.attempts,
            s.skill.lower(),
        ),
    )
    return ranked[:limit]
