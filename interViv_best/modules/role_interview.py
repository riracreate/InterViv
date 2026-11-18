"""Role-only targets and role interviews. Off unless ROLE_ONLY_TARGETS is set.

A role target is one of the starter blueprints plus a level. It is stored in
the existing ``target_contexts.role_id`` column as ``blueprint:<id>:<level>``
with no company, so no migration is needed. Company consumers never see that
value (``backend.db.user_target.get_user_target`` hides it).

A role interview is a staged_v1 Quick or Full interview built from the
deterministic blueprint plan:

* the opener is scripted and unscored;
* core slots are served from bundles or the CSV bank for the planned skill
  and difficulty, exactly as a staged core round is. A core skill with
  neither becomes a scripted, unscored practice slot and says so; a core
  slot served from a bundle that is not reviewed gives feedback only;
* scenario and behavioural slots are scripted from the blueprint and
  unscored; scenario slots in business, product and design roles are
  labelled practice only;
* a Full interview keeps the blueprint's practical track (coding or SQL).

No model calls. Resume skills only steer the plan and never reach a score.
"""
from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable

from modules.role_blueprints import LEVELS, get_blueprint
from modules.role_planner import PlanError, PlanSlot, plan_role

ROLE_TARGET_PREFIX = "blueprint"
SCRIPT_SOURCE = "role_script"
LENGTHS = ("quick", "full")

_LINK = re.compile(r"\(?\[[^\]]*\]\([^)]*\)?\)?")
_URL = re.compile(r"https?://\S+")
_PROJECT_LIMIT = 80


SCORED_CONTENT = frozenset({"bank", "reviewed_bundle"})


class RoleInterviewError(ValueError):
    """A role target or role interview request that cannot be satisfied."""


@dataclass(frozen=True)
class InterviewSlot:
    """One planned turn of a role interview, as served."""

    kind: str
    competency_id: str
    name: str
    skill: str
    difficulty: str
    reason: str
    practice_only: bool
    scored: bool
    stage: str
    # Core slots: reviewed_bundle | auto_checked_bundle | generated_bundle | bank | none.
    content: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def role_only_targets_enabled() -> bool:
    return os.getenv("ROLE_ONLY_TARGETS", "0").strip().lower() in {"1", "true", "yes", "on"}


# ── stored role target ───────────────────────────────────────────────────────


def encode_role_target(role_id: str, level: str) -> str:
    doc = get_blueprint(role_id)
    if doc is None:
        raise RoleInterviewError(f"Unknown role '{role_id}'.")
    clean_level = str(level or "").strip().lower()
    if clean_level not in LEVELS:
        raise RoleInterviewError("level must be intern, junior, or mid.")
    return f"{ROLE_TARGET_PREFIX}:{doc['id']}:{clean_level}"


def decode_role_target(value: Any) -> dict[str, str] | None:
    """``{"role_id", "level"}`` for a stored role target, else None."""
    if not isinstance(value, str):
        return None
    parts = value.split(":")
    if len(parts) != 3 or parts[0] != ROLE_TARGET_PREFIX:
        return None
    role_id, level = parts[1].strip(), parts[2].strip()
    if not role_id or level not in LEVELS:
        return None
    return {"role_id": role_id, "level": level}


def role_target_view(value: Any) -> dict[str, Any] | None:
    """Public view of a stored role target, or None when it is not one."""
    decoded = decode_role_target(value)
    if decoded is None:
        return None
    doc = get_blueprint(decoded["role_id"])
    if doc is None:
        return None
    return {
        "role_id": doc["id"],
        "level": decoded["level"],
        "title": doc["title"],
        "family": doc["family"],
        "practical_track": doc.get("practical_track") or "none",
    }


# ── resume used for planning only ────────────────────────────────────────────


def resume_for_planning(candidate: dict | None, blueprint: dict) -> dict | None:
    """Planner resume from a stored candidate: skills only, no free text.

    Skills found in experience or project sections count as claimed with
    evidence, other listed skills as listed only, and the blueprint's
    technical skills that the resume does not list as missing.
    """
    if not candidate:
        return None
    listed = [str(s).strip() for s in candidate.get("resume_skills") or [] if str(s).strip()]
    snapshot = candidate.get("ats_snapshot") or {}
    evidence = {str(s).casefold() for s in snapshot.get("evidence_skills") or [] if str(s).strip()}
    if not listed:
        return None
    skills: dict[str, str] = {}
    for name in listed:
        skills[name] = "claimed_with_evidence" if name.casefold() in evidence else "listed_only"
    known = {name.casefold() for name in skills}
    for item in blueprint.get("competencies") or []:
        if item.get("type") != "technical":
            continue
        for skill in item.get("skills") or []:
            if str(skill).casefold() not in known:
                skills[str(skill)] = "missing"
    return {"skills": skills}


# ── scripted questions ───────────────────────────────────────────────────────


def _clean_topic(text: str) -> str:
    clean = _URL.sub("", _LINK.sub("", str(text or "")))
    clean = clean.split(";")[0]
    clean = " ".join(clean.replace("(", " ").replace(")", " ").split()).strip(" ,.:")
    if clean and clean[0].isupper() and not clean[:2].isupper():
        clean = clean[0].lower() + clean[1:]
    return clean


def opener_question(blueprint: dict, resume: dict | None = None) -> str:
    projects = (resume or {}).get("projects") or []
    if projects:
        project = " ".join(str(projects[0]).split())[:_PROJECT_LIMIT]
        return f"Walk me through {project}: what you built, what was hard, and what you would change."
    title = str(blueprint.get("title") or "this")
    return f"Tell me a little about yourself and what draws you to the {title} role."


def scenario_question(item: dict) -> str:
    name = str(item.get("name") or "this area")
    topics = [t for t in (item.get("scenario_topics") or []) if str(t).strip()]
    topic = _clean_topic(topics[0]) if topics else ""
    if topic:
        return f"Practice scenario on {name}: {topic}. How would you approach it, step by step?"
    return f"Practice scenario on {name}. How would you approach a realistic case, step by step?"


def core_practice_question(skill: str) -> str:
    return (
        f"Practice question on {skill}: explain one idea from {skill} you would rely on in this role, "
        "and walk through an example of using it."
    )


def core_content(skill: str, difficulty: str) -> str:
    """Where a core round for this skill would be served from right now."""
    try:
        from modules.bundle_selector import (
            reviewed_available_count,
            reviewed_bundles_only,
            select_bundle_question,
        )

        if reviewed_bundles_only():
            found = reviewed_available_count(skill=skill, difficulty=difficulty, topic=None)
            return "reviewed_bundle" if found > 0 else "none"
        payload = select_bundle_question(skill=skill, difficulty=difficulty, asked=[], topic=None)
        if payload:
            label = str(payload.get("source") or "")
            return label if label.endswith("_bundle") else "unknown_bundle"
    except Exception:
        pass
    try:
        from modules.question_runtime import eligible_offline_questions

        if eligible_offline_questions(skill):
            return "bank"
    except Exception:
        pass
    return "none"


def behavioural_question(item: dict) -> str:
    name = str(item.get("name") or "teamwork")
    return (
        f"Tell me about a time that called for {name.lower()}. "
        "What was the situation, what did you do, and what was the result?"
    )


# ── interview plan ───────────────────────────────────────────────────────────


def _competency(blueprint: dict, competency_id: str) -> dict | None:
    for item in blueprint.get("competencies") or []:
        if item.get("id") == competency_id:
            return item
    return None


def _apply_core_choice(blueprint: dict, slots: list[PlanSlot], chosen: list[str]) -> list[PlanSlot]:
    cores = [index for index, slot in enumerate(slots) if slot.kind == "core"]
    ids = [str(item).strip() for item in chosen]
    if len(ids) != len(cores):
        raise RoleInterviewError(f"core_competencies must list {len(cores)} technical competencies.")
    if len(set(ids)) != len(ids):
        raise RoleInterviewError("core_competencies must not repeat a competency.")
    out = list(slots)
    for index, competency_id in zip(cores, ids):
        item = _competency(blueprint, competency_id)
        if item is None or item.get("type") != "technical":
            raise RoleInterviewError(f"'{competency_id}' is not a technical competency of this role.")
        current = out[index]
        if item["id"] == current.competency_id:
            continue
        skill = (item.get("skills") or [item["name"]])[0]
        out[index] = replace(
            current, competency_id=item["id"], name=item["name"], skill=str(skill),
            reason=f"{skill}: swapped in",
        )
    return out


def interview_slots(
    blueprint: dict,
    *,
    level: str,
    length: str,
    resume: dict | None = None,
    jd_skills: list[str] | None = None,
    core_competencies: list[str] | None = None,
    content_of: Callable[[str, str], str] | None = core_content,
) -> list[InterviewSlot]:
    """The planner's slots, with the interview rules applied.

    The opener is always scripted and unscored. Scenario and behavioural
    slots are scripted and unscored. A core slot keeps the planner's skill
    and difficulty; it counts toward the score only when its content is the
    CSV bank or a reviewed bundle, and becomes a labelled practice slot when
    there is no content at all. Practical slots are unchanged.
    """
    try:
        planned = plan_role(blueprint, level=level, length=length, resume=resume, jd_skills=jd_skills)
    except PlanError as exc:
        raise RoleInterviewError(str(exc)) from exc
    if core_competencies:
        planned = _apply_core_choice(blueprint, planned, core_competencies)
    out: list[InterviewSlot] = []
    for slot in planned:
        base = dict(
            kind=slot.kind, competency_id=slot.competency_id, name=slot.name, skill=slot.skill,
            difficulty=slot.difficulty, reason=slot.reason, practice_only=slot.practice_only,
        )
        if slot.kind == "opener":
            if slot.name == "Resume opener":
                out.append(InterviewSlot(**base, scored=False, stage="warm_up"))
            else:
                out.append(InterviewSlot(
                    "opener", "", "Role opener", str(blueprint["title"]), "easy",
                    opener_question(blueprint), False, False, "warm_up",
                ))
        elif slot.kind == "core":
            content = content_of(slot.skill, slot.difficulty) if content_of else None
            if content == "none":
                out.append(InterviewSlot(**{
                    **base,
                    "reason": f"{slot.skill}: no question bank for this skill yet, practice only",
                    "practice_only": True,
                }, scored=False, stage="practice", content=content))
            else:
                scored = content is None or content in SCORED_CONTENT
                out.append(InterviewSlot(**base, scored=scored, stage="core", content=content))
        elif slot.kind == "scenario":
            out.append(InterviewSlot(**base, scored=False, stage="practice"))
        elif slot.kind == "behavioural":
            out.append(InterviewSlot(**base, scored=False, stage="behavioural"))
        else:
            out.append(InterviewSlot(**base, scored=True, stage="practical"))
    return out


def slot_payloads(slots: list[InterviewSlot]) -> list[dict[str, Any]]:
    return [slot.as_dict() for slot in slots]


def _practical_block(track: str) -> dict[str, Any]:
    from modules.staged_flow import _practical_block_for_track

    return _practical_block_for_track(track)


def build_role_blocks(
    blueprint: dict,
    slots: list[InterviewSlot],
    *,
    preset: str,
    level: str,
    resume: dict | None = None,
    used_resume: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    """Raw staged blocks, staged_v1 metadata, and scripted texts by block id."""
    from modules.staged_flow import STAGED_FLOW_VERSION, estimate_minutes

    if preset not in LENGTHS:
        raise RoleInterviewError("preset must be quick or full.")
    cores = [slot for slot in slots if slot.kind == "core"]
    if not cores:
        raise RoleInterviewError("This role has no technical competencies to ask.")
    opener_skill = cores[0].skill
    interview = {"round_type": "technical_short_answer", "category": "interview", "count": 1}
    blocks: list[dict[str, Any]] = []
    scripts: dict[str, str] = {}
    stages: list[str] = []
    planned: list[dict[str, Any]] = []
    practical_track: str | None = None
    core_index = 0
    for slot in slots:
        if slot.kind == "opener":
            block_id = "role-opener"
            blocks.append({**interview, "id": block_id, "stage": slot.stage, "skills": [opener_skill],
                           "difficulty": "easy", "allow_optional_follow_ups": False})
            scripts[block_id] = slot.reason if slot.name == "Role opener" else opener_question(blueprint, resume)
        elif slot.kind == "core":
            core_index += 1
            block_id = f"role-core-{core_index}"
            block = {**interview, "id": block_id, "stage": slot.stage, "skills": [slot.skill],
                     "difficulty": slot.difficulty}
            if slot.stage == "practice":
                block["allow_optional_follow_ups"] = False
                scripts[block_id] = core_practice_question(slot.skill)
            blocks.append(block)
        elif slot.kind == "scenario":
            block_id = "role-scenario"
            item = _competency(blueprint, slot.competency_id) or {"name": slot.name}
            blocks.append({**interview, "id": block_id, "stage": slot.stage, "skills": [slot.name],
                           "difficulty": slot.difficulty, "allow_optional_follow_ups": False})
            scripts[block_id] = scenario_question(item)
        elif slot.kind == "behavioural":
            block_id = "role-behavioural"
            item = _competency(blueprint, slot.competency_id) or {"name": slot.name}
            blocks.append({**interview, "id": block_id, "stage": slot.stage, "skills": ["HR"],
                           "difficulty": "medium", "allow_optional_follow_ups": False})
            scripts[block_id] = behavioural_question(item)
        else:
            block_id = "role-practical"
            practical_track = str(slot.skill)
            blocks.append({**_practical_block(practical_track), "id": block_id})
        if slot.stage not in stages:
            stages.append(slot.stage)
        planned.append({**slot.as_dict(), "block_id": block_id})
    has_behavioural = any(slot.kind == "behavioural" for slot in slots)
    meta = {
        "version": STAGED_FLOW_VERSION,
        "preset": preset,
        "deferred_feedback": True,
        "stages_scheduled": stages,
        "core_count": len(cores),
        "practical_track": practical_track,
        "practical_skipped": practical_track is None,
        "practical_skipped_reason": None if practical_track else (
            "quick_preset" if preset == "quick" else "no_practical_track"
        ),
        "behavioural_count": 1 if has_behavioural else 0,
        "behavioural_skipped": not has_behavioural,
        "behavioural_skipped_reason": None if has_behavioural else (
            "quick_preset" if preset == "quick" else "no_behavioural_competency"
        ),
        "estimated_minutes": estimate_minutes(preset, include_practical=practical_track is not None),
        "role_interview": {
            "role_id": blueprint["id"],
            "title": blueprint["title"],
            "family": blueprint["family"],
            "level": level,
            "length": preset,
            "used_resume": bool(used_resume),
            "slots": planned,
        },
    }
    return blocks, meta, scripts


def public_role_interview(meta: dict | None) -> dict[str, Any] | None:
    """What clients see about a role interview (no slot reasons or resume data)."""
    info = (meta or {}).get("role_interview")
    if not isinstance(info, dict):
        return None
    return {
        "role_id": info.get("role_id"),
        "title": info.get("title"),
        "level": info.get("level"),
        "length": info.get("length"),
    }
