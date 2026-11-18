"""Deterministic versioned study plans (Phase 4B).

Server selects structure, priorities, task IDs, resources, and schedule.
Completing a task updates plan progress only — never score, Elo, readiness,
or assessed mastery.
"""

from __future__ import annotations

import copy
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.config import get_settings
from modules.learning_resources import list_resources
from modules.planning_evidence import (
    POP_ASSISTED,
    POP_ELIGIBLE,
    POP_UNASSESSED,
    PlanningEvidence,
    collect_planning_evidence,
    weak_eligible_skills,
)
from modules.roadmap_generator import SUPPORTED_DAYS, _coerce_days, _week_layout

PLAN_SCHEMA_VERSION = "study_plan_v1"
DEFAULT_HOURS_PER_WEEK = 6
MAX_TASKS = 24

# (user_id, role_or_goal_key) -> list of plan docs (newest last)
_MEMORY_PLANS: dict[tuple[str, str], list[dict[str, Any]]] = {}


def reset_memory_store() -> None:
    _MEMORY_PLANS.clear()


def snapshot_memory_store() -> dict[str, Any]:
    return {"plans": copy.deepcopy(_MEMORY_PLANS)}


def restore_memory_store(snapshot: dict[str, Any] | None) -> None:
    if not snapshot:
        return
    _MEMORY_PLANS.clear()
    _MEMORY_PLANS.update(copy.deepcopy(snapshot.get("plans") or {}))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _using_sqlalchemy() -> bool:
    return bool(get_settings().database_url)


def _scope_key(user_id: str, role_id: str | None, goal: str | None) -> str:
    if role_id:
        return f"role:{role_id}"
    goal_slug = hashlib.sha256((goal or "general").encode("utf-8")).hexdigest()[:12]
    return f"goal:{goal_slug}"


def stable_task_id(
    *,
    role_or_scope: str,
    skill: str,
    kind: str,
    week_index: int,
    ordinal: int,
) -> str:
    raw = f"{role_or_scope}|{skill}|{kind}|{week_index}|{ordinal}"
    return "task_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _catalog_resource(skill: str) -> dict[str, Any] | None:
    try:
        payload = list_resources(skill_id=skill) or {}
        rows = list(payload.get("resources") or [])
    except Exception:
        rows = []
    if not rows:
        return None
    row = rows[0]
    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "url": row.get("url"),
        "source": row.get("source"),
        "skill": skill,
        "level": row.get("level"),
    }


def _build_tasks_from_evidence(
    evidence: PlanningEvidence,
    *,
    days: int,
    hours_per_week: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    layout = _week_layout(days)
    scope = _scope_key(evidence.user_id, evidence.role_id, evidence.confirmed_goal)
    tasks: list[dict[str, Any]] = []
    meta = {
        "plan_kind": "starter",
        "readiness_percentage": None,
        "readiness_note": (
            "No eligible assessment history yet. This starter plan uses your "
            "confirmed goal and role requirements only — it does not invent "
            "a readiness percentage or weakness ranking."
        ),
    }

    if evidence.has_eligible_assessment:
        weak = weak_eligible_skills(evidence, limit=5)
        meta["plan_kind"] = "assessed"
        # Honest readiness from eligible means only (never fabricate).
        scores = [
            float(s.current_score if s.current_score is not None else s.mean_score or 0.0)
            for s in evidence.eligible
        ]
        meta["readiness_percentage"] = round(sum(scores) / len(scores), 1) if scores else None
        meta["readiness_note"] = (
            "Readiness reflects eligible assessment evidence only."
        )
        focus = weak
        focus_pop = POP_ELIGIBLE
    elif evidence.assisted_practice:
        meta["plan_kind"] = "assisted_practice"
        meta["readiness_percentage"] = None
        meta["readiness_note"] = (
            "You have assistance-only practice. Recommendations stay labeled "
            "as practice; assess independently before claiming mastery."
        )
        focus = evidence.assisted_practice[:5]
        focus_pop = POP_ASSISTED
    else:
        focus = evidence.unassessed[:5]
        if not focus and not evidence.planning_context_skills and evidence.confirmed_goal:
            from modules.guidance_coach import map_phrase_to_skills

            extracted = list(dict.fromkeys(map_phrase_to_skills(evidence.confirmed_goal)))[:12]
            if extracted:
                evidence.planning_context_skills = extracted
        if not focus and evidence.planning_context_skills:
            from modules.planning_evidence import SkillEvidence

            focus = [
                SkillEvidence(
                    skill=s,
                    population=POP_UNASSESSED,
                    rationale="From your confirmed goal / interests (planning context).",
                )
                for s in evidence.planning_context_skills[:5]
            ]
        if not focus:
            meta["plan_kind"] = "needs_goal_skills"
            meta["needs_goal_skills"] = True
            meta["prompt"] = "needs_goal_skills"
            meta["readiness_percentage"] = None
            meta["readiness_note"] = (
                "Name the skills to plan for. No default skill is substituted."
            )
            meta["hours_per_week"] = hours_per_week
            meta["hours_per_week_default"] = DEFAULT_HOURS_PER_WEEK
            meta["hours_editable"] = True
            return [], meta
        focus_pop = POP_UNASSESSED

    ordinal = 0
    for week_i, (label, day_range) in enumerate(layout, start=1):
        skill_slice = focus[: max(1, min(len(focus), week_i))]
        for skill_ev in skill_slice:
            ordinal += 1
            if len(tasks) >= MAX_TASKS:
                break
            skill = skill_ev.skill
            kind = (
                "independent_assessment"
                if focus_pop == POP_ASSISTED
                else "practice"
            )
            if week_i == len(layout):
                kind = "mock_or_review"
            resource = _catalog_resource(skill)
            task_id = stable_task_id(
                role_or_scope=scope,
                skill=skill,
                kind=kind,
                week_index=week_i,
                ordinal=ordinal,
            )
            minutes = max(25, int((hours_per_week * 60) / max(4, len(layout) * 2)))
            rationale = skill_ev.rationale or (
                f"Recommended for {label.lower()} given current evidence."
            )
            tasks.append(
                {
                    "task_id": task_id,
                    "week_index": week_i,
                    "week_label": label,
                    "day_range": day_range,
                    "skill": skill,
                    "kind": kind,
                    "population": skill_ev.population,
                    "title": f"{label}: {skill}",
                    "rationale": rationale,
                    "suggested_minutes": minutes,
                    "resource": resource,
                    "practice_href": f"/practice?mode=full&skills={skill}",
                    "status": "pending",
                    "completed_at": None,
                }
            )
        if len(tasks) >= MAX_TASKS:
            break

    # Optional enrichment must not appear as a required deficiency.
    for task in tasks:
        if task.get("resource"):
            task["resource_optional"] = True
            task["resource_note"] = "Catalog enrichment — not a diagnosed deficiency."

    meta["hours_per_week"] = hours_per_week
    meta["hours_per_week_default"] = DEFAULT_HOURS_PER_WEEK
    meta["hours_editable"] = True
    return tasks, meta


def build_plan_document(
    *,
    user_id: str,
    role_id: str | None,
    days: int = 30,
    hours_per_week: int | None = None,
    confirmed_goal: str | None = None,
    planning_context_skills: list[str] | None = None,
    previous: dict[str, Any] | None = None,
    db: Any | None = None,
) -> dict[str, Any]:
    days = _coerce_days(days)
    hours = int(hours_per_week) if hours_per_week else DEFAULT_HOURS_PER_WEEK
    hours = max(1, min(40, hours))
    evidence = collect_planning_evidence(
        user_id=user_id,
        role_id=role_id,
        confirmed_goal=confirmed_goal,
        hours_per_week=hours,
        planning_context_skills=planning_context_skills,
        db=db,
    )
    tasks, meta = _build_tasks_from_evidence(evidence, days=days, hours_per_week=hours)

    # Preserve completion on regeneration when task_id matches.
    prior_done = {}
    if previous:
        for t in previous.get("tasks") or []:
            if t.get("status") == "completed" and t.get("task_id"):
                prior_done[t["task_id"]] = t.get("completed_at")
    for task in tasks:
        if task["task_id"] in prior_done:
            task["status"] = "completed"
            task["completed_at"] = prior_done[task["task_id"]]

    version = int((previous or {}).get("version") or 0) + 1
    plan_id = str((previous or {}).get("plan_id") or uuid.uuid4())
    now = _now().isoformat()
    completed = sum(1 for t in tasks if t.get("status") == "completed")
    return {
        "plan_id": plan_id,
        "schema_version": PLAN_SCHEMA_VERSION,
        "version": version,
        "user_id": user_id,
        "role_id": role_id,
        "days": days,
        "created_at": (previous or {}).get("created_at") or now,
        "updated_at": now,
        "evidence_digest": evidence.evidence_digest,
        "evidence_schema_version": evidence.schema_version,
        "evidence_summary": {
            "has_eligible_assessment": evidence.has_eligible_assessment,
            "eligible_skills": [s.skill for s in evidence.eligible],
            "assisted_skills": [s.skill for s in evidence.assisted_practice],
            "unassessed_skills": [s.skill for s in evidence.unassessed],
            "planning_context_skills": list(evidence.planning_context_skills),
            "confirmed_goal": evidence.confirmed_goal,
        },
        "meta": meta,
        "tasks": tasks,
        "task_completion_pct": (
            round(100.0 * completed / len(tasks), 1) if tasks else 0.0
        ),
        "history_note": (
            "Regeneration keeps prior plan versions and carries completion "
            "forward for stable task IDs. Task completion is not an assessment metric."
        ),
        "supersedes_version": (previous or {}).get("version"),
    }


def _memory_key(user_id: str, role_id: str | None, goal: str | None) -> tuple[str, str]:
    return (str(user_id), _scope_key(user_id, role_id, goal))


def get_active_plan(
    user_id: str,
    *,
    role_id: str | None = None,
    confirmed_goal: str | None = None,
) -> dict[str, Any] | None:
    if _using_sqlalchemy():
        return _get_sql_active(user_id, role_id=role_id, confirmed_goal=confirmed_goal)
    key = _memory_key(user_id, role_id, confirmed_goal)
    series = _MEMORY_PLANS.get(key) or []
    return copy.deepcopy(series[-1]) if series else None


def list_plan_versions(
    user_id: str,
    *,
    role_id: str | None = None,
    confirmed_goal: str | None = None,
) -> list[dict[str, Any]]:
    if _using_sqlalchemy():
        return _list_sql_versions(user_id, role_id=role_id, confirmed_goal=confirmed_goal)
    key = _memory_key(user_id, role_id, confirmed_goal)
    return copy.deepcopy(_MEMORY_PLANS.get(key) or [])


def ensure_plan(
    user_id: str,
    *,
    role_id: str | None = None,
    days: int = 30,
    hours_per_week: int | None = None,
    confirmed_goal: str | None = None,
    planning_context_skills: list[str] | None = None,
    regenerate: bool = False,
    db: Any | None = None,
) -> dict[str, Any]:
    current = get_active_plan(user_id, role_id=role_id, confirmed_goal=confirmed_goal)
    if current and not regenerate:
        # Same evidence + days + hours → return existing (stable IDs).
        evidence = collect_planning_evidence(
            user_id=user_id,
            role_id=role_id,
            confirmed_goal=confirmed_goal,
            hours_per_week=hours_per_week or current.get("meta", {}).get("hours_per_week"),
            planning_context_skills=planning_context_skills,
            db=db,
        )
        same = (
            current.get("evidence_digest") == evidence.evidence_digest
            and int(current.get("days") or 0) == _coerce_days(days)
            and (
                hours_per_week is None
                or int(current.get("meta", {}).get("hours_per_week") or 0) == int(hours_per_week)
            )
        )
        if same:
            return current

    plan = build_plan_document(
        user_id=user_id,
        role_id=role_id,
        days=days,
        hours_per_week=hours_per_week
        or (current or {}).get("meta", {}).get("hours_per_week")
        or DEFAULT_HOURS_PER_WEEK,
        confirmed_goal=confirmed_goal,
        planning_context_skills=planning_context_skills,
        previous=current if regenerate or current else None,
        db=db,
    )
    _persist_plan(plan, confirmed_goal=confirmed_goal)
    return plan


def complete_task(
    user_id: str,
    task_id: str,
    *,
    role_id: str | None = None,
    confirmed_goal: str | None = None,
    completed: bool = True,
) -> dict[str, Any]:
    plan = get_active_plan(user_id, role_id=role_id, confirmed_goal=confirmed_goal)
    if not plan:
        raise KeyError("No active plan.")
    found = False
    now = _now().isoformat()
    for task in plan.get("tasks") or []:
        if task.get("task_id") != task_id:
            continue
        found = True
        if completed:
            task["status"] = "completed"
            task["completed_at"] = task.get("completed_at") or now
        else:
            task["status"] = "pending"
            task["completed_at"] = None
        break
    if not found:
        raise KeyError(f"Unknown task_id: {task_id}")
    completed_n = sum(1 for t in plan["tasks"] if t.get("status") == "completed")
    plan["task_completion_pct"] = (
        round(100.0 * completed_n / len(plan["tasks"]), 1) if plan["tasks"] else 0.0
    )
    plan["updated_at"] = now
    # In-place update of active version (completion is not a new plan version).
    _persist_plan(plan, confirmed_goal=confirmed_goal, replace_active=True)
    return plan


def _persist_plan(
    plan: dict[str, Any],
    *,
    confirmed_goal: str | None = None,
    replace_active: bool = False,
) -> None:
    if _using_sqlalchemy():
        _persist_sql(plan, confirmed_goal=confirmed_goal, replace_active=replace_active)
        return
    key = _memory_key(plan["user_id"], plan.get("role_id"), confirmed_goal)
    series = _MEMORY_PLANS.setdefault(key, [])
    if replace_active and series and series[-1].get("plan_id") == plan.get("plan_id"):
        series[-1] = copy.deepcopy(plan)
    elif series and series[-1].get("version") == plan.get("version") and series[-1].get("plan_id") == plan.get("plan_id"):
        series[-1] = copy.deepcopy(plan)
    else:
        series.append(copy.deepcopy(plan))


def _persist_sql(
    plan: dict[str, Any],
    *,
    confirmed_goal: str | None,
    replace_active: bool,
) -> None:
    from backend.db.sqlalchemy_models import StudyPlanRow
    from backend.db.sqlalchemy_store import session_scope

    scope = _scope_key(plan["user_id"], plan.get("role_id"), confirmed_goal)
    with session_scope() as session:
        if replace_active:
            row = (
                session.query(StudyPlanRow)
                .filter_by(user_id=plan["user_id"], scope_key=scope, plan_id=plan["plan_id"])
                .order_by(StudyPlanRow.version.desc())
                .first()
            )
            if row is not None:
                row.plan_json = plan
                row.updated_at = _now()
                row.is_active = True
                return
        # Deactivate prior active rows for this scope when inserting a new version.
        for prior in (
            session.query(StudyPlanRow)
            .filter_by(user_id=plan["user_id"], scope_key=scope, is_active=True)
            .all()
        ):
            prior.is_active = False
        session.add(
            StudyPlanRow(
                id=str(uuid.uuid4()),
                plan_id=plan["plan_id"],
                user_id=plan["user_id"],
                scope_key=scope,
                role_id=plan.get("role_id"),
                version=int(plan["version"]),
                is_active=True,
                plan_json=plan,
                created_at=_now(),
                updated_at=_now(),
            )
        )


def _get_sql_active(
    user_id: str,
    *,
    role_id: str | None,
    confirmed_goal: str | None,
) -> dict[str, Any] | None:
    from backend.db.sqlalchemy_models import StudyPlanRow
    from backend.db.sqlalchemy_store import session_scope

    scope = _scope_key(user_id, role_id, confirmed_goal)
    with session_scope() as session:
        row = (
            session.query(StudyPlanRow)
            .filter_by(user_id=user_id, scope_key=scope, is_active=True)
            .order_by(StudyPlanRow.version.desc())
            .first()
        )
        return copy.deepcopy(row.plan_json) if row else None


def _list_sql_versions(
    user_id: str,
    *,
    role_id: str | None,
    confirmed_goal: str | None,
) -> list[dict[str, Any]]:
    from backend.db.sqlalchemy_models import StudyPlanRow
    from backend.db.sqlalchemy_store import session_scope

    scope = _scope_key(user_id, role_id, confirmed_goal)
    with session_scope() as session:
        rows = (
            session.query(StudyPlanRow)
            .filter_by(user_id=user_id, scope_key=scope)
            .order_by(StudyPlanRow.version.asc())
            .all()
        )
        return [copy.deepcopy(r.plan_json) for r in rows]
