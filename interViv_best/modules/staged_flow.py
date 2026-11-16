"""Slice 2: Staged interview flow presets, track selection, and bank helpers.

Implements the ``staged_v1`` session plan without any database schema changes
(Amendment A1):

1. ``warm_up``: 1 unscored ``easy`` prompt (allowed even when
   ``REVIEWED_BUNDLES_ONLY=true``; excluded from Elo & readiness).
2. ``core``: 2 (``Quick``) or 4 (``Full``) adaptive ``technical_short_answer``
   rounds (where inline follow-ups may attach under ``STAGED_INLINE_FOLLOW_UPS``).
3. ``follow_up``: inline answer-aware follow-ups scheduled inside
   ``POST /session/answer`` strictly on Core rounds (``Q2``).
4. ``practical``: optional stage in ``Full`` only (``coding`` | ``sql`` |
   ``system_design``), skipped when role/skills have no practical track (``A2``).
5. ``behavioural``: unscored question-text-only ``HR`` turns loaded strictly
   from the reviewed CSV bank (``data/behavioural_questions_v1.csv``); skipped
   cleanly when the reviewed bank is absent or empty.

All per-round scores and feedback are deferred server-side until completion
(``A7``) when ``flow_version == "staged_v1"``.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from modules.company_graph import get_company_graph

STAGED_FLOW_VERSION = "staged_v1"
VALID_PRESETS = ("quick", "full")

STAGE_WARM_UP = "warm_up"
STAGE_CORE = "core"
STAGE_FOLLOW_UP = "follow_up"
STAGE_PRACTICAL = "practical"
STAGE_BEHAVIOURAL = "behavioural"

STAGE_NAMES = (
    STAGE_WARM_UP,
    STAGE_CORE,
    STAGE_FOLLOW_UP,
    STAGE_PRACTICAL,
    STAGE_BEHAVIOURAL,
)

UNSCORED_STAGES = frozenset({STAGE_WARM_UP, STAGE_BEHAVIOURAL})

_PRESET_SPECS: dict[str, dict[str, Any]] = {
    "quick": {
        "core_count": 2,
        "include_practical": False,
        "behavioural_count": 1,
        "estimated_minutes": 15,
    },
    "full": {
        "core_count": 4,
        "include_practical": True,
        "behavioural_count": 2,
        "estimated_minutes": 48,
        "estimated_minutes_without_practical": 22,
    },
}

_CODING_SKILL_KEYS = frozenset({
    "dsa",
    "coding",
    "algorithms",
    "algorithm",
    "data structures",
    "data structure",
})
_SQL_SKILL_KEYS = frozenset({
    "sql",
    "dbms",
    "database",
    "databases",
    "postgresql",
    "postgres",
    "mysql",
    "sqlite",
})
_SYSTEM_DESIGN_SKILL_KEYS = frozenset({
    "system design",
    "system_design",
    "distributed systems",
    "architecture",
})

_KEEP_TRUE_VALUES = frozenset({"y", "yes", "true", "1"})

DEFAULT_BEHAVIOURAL_CSV_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "behavioural_questions_v1.csv"
)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def validate_staged_request(
    *,
    preset: str | None,
    flow_version: str | None,
    blocks: list[dict[str, Any]] | None = None,
    round_plan: list[str] | None = None,
) -> tuple[str, str] | None:
    """Validate optional ``staged_v1`` preset/flow_version inputs.

    Returns ``None`` for legacy / custom-block requests, or
    ``("staged_v1", "quick" | "full")`` for valid staged starts.
    Raises ``ValueError`` (surfaced as HTTP 422) on invalid combinations.
    """
    clean_version = _clean_text(flow_version).lower() or None
    clean_preset = _clean_text(preset).lower() or None

    if clean_version is None and clean_preset is None:
        return None

    if clean_version is not None and clean_version != STAGED_FLOW_VERSION:
        raise ValueError(
            f"Unsupported flow_version '{flow_version}'. "
            f"Expected '{STAGED_FLOW_VERSION}'."
        )
    if clean_preset is None:
        raise ValueError(
            "preset is required when flow_version is 'staged_v1' "
            "(allowed: Quick, Full)."
        )
    if clean_preset not in VALID_PRESETS:
        raise ValueError(
            f"Unsupported preset '{preset}'. Allowed presets: Quick, Full."
        )
    if blocks is not None:
        raise ValueError(
            "Custom blocks cannot be combined with staged_v1 preset."
        )
    if round_plan is not None:
        raise ValueError(
            "round_plan cannot be combined with staged_v1 preset."
        )
    return STAGED_FLOW_VERSION, clean_preset


def is_staged_v1_session(session: dict[str, Any] | None) -> bool:
    """Return True when the session was created under ``staged_v1``."""
    if not isinstance(session, dict):
        return False
    if _clean_text(session.get("flow_version")).lower() == STAGED_FLOW_VERSION:
        return True
    round_cfg = session.get("round_config") or {}
    if isinstance(round_cfg, dict):
        meta = round_cfg.get("staged_flow") or {}
        if isinstance(meta, dict):
            return (
                _clean_text(meta.get("version") or meta.get("flow_version")).lower()
                == STAGED_FLOW_VERSION
            )
    return False


def staged_flow_meta(session: dict[str, Any] | None) -> dict[str, Any]:
    """Return persisted ``staged_v1`` metadata dict, or empty dict."""
    if not isinstance(session, dict):
        return {}
    round_cfg = session.get("round_config") or {}
    if isinstance(round_cfg, dict):
        meta = round_cfg.get("staged_flow")
        if isinstance(meta, dict):
            return dict(meta)
    return {}


def round_stage(round_doc: dict[str, Any] | None) -> str | None:
    """Resolve stage label from round config, breakdown, or top-level field."""
    if not isinstance(round_doc, dict):
        return None
    cfg = round_doc.get("config_json") or {}
    breakdown = round_doc.get("scoring_breakdown") or {}
    raw = (
        (cfg.get("stage") if isinstance(cfg, dict) else None)
        or round_doc.get("stage")
        or (breakdown.get("stage") if isinstance(breakdown, dict) else None)
    )
    clean = _clean_text(raw).lower()
    return clean if clean in STAGE_NAMES else None


def _track_for_skill(skill: str) -> str | None:
    key = " ".join(_clean_text(skill).casefold().replace("-", " ").split())
    if key in _CODING_SKILL_KEYS:
        return "coding"
    if key in _SQL_SKILL_KEYS:
        return "sql"
    if key in _SYSTEM_DESIGN_SKILL_KEYS:
        return "system_design"
    return None


def resolve_role_skills(role_id: str | None) -> list[str]:
    """Return non-HR required skills from CompanyHiringGraph sorted by weight."""
    slug = _clean_text(role_id)
    if not slug:
        return []
    found = get_company_graph().find_role(slug)
    if not found:
        return []
    _, role = found
    reqs = sorted(
        enumerate(role.skill_requirements),
        key=lambda item: (-float(item[1].importance_weight), item[0]),
    )
    skills: list[str] = []
    for _, req in reqs:
        name = _clean_text(req.skill)
        if name and name.casefold() != "hr" and name not in skills:
            skills.append(name)
    return skills


def resolve_practical_track(
    *,
    role_id: str | None = None,
    session_skills: list[str] | None = None,
) -> str | None:
    """Pick at most one Stage-4 Practical track (``A2``) or ``None`` to skip.

    Rule:
    1. When ``role_id`` matches a role in ``CompanyHiringGraph``, inspect its
       ``skill_requirements`` ordered by descending ``importance_weight`` and
       select the first matching track (``DSA``/``Coding`` -> ``coding``,
       ``SQL``/``DBMS`` -> ``sql``, ``System Design`` -> ``system_design``).
       If that role defines no execution skill, return ``None`` (skip Stage 4).
    2. Otherwise (no known role in graph), inspect ``session_skills`` in caller
       order using the same mapping; return ``None`` when none match.
    """
    role_skills = resolve_role_skills(role_id)
    candidates = role_skills if role_skills else [s for s in (session_skills or []) if _clean_text(s)]
    for skill in candidates:
        track = _track_for_skill(skill)
        if track is not None:
            return track
    return None


def _practical_block_for_track(track: str) -> dict[str, Any]:
    if track == "coding":
        return {
            "round_type": "coding",
            "category": "coding",
            "stage": STAGE_PRACTICAL,
            "skills": ["DSA"],
            "count": 1,
            "duration_minutes": 30,
            "language": "python",
        }
    if track == "sql":
        return {
            "round_type": "sql",
            "category": "sql",
            "stage": STAGE_PRACTICAL,
            "skills": ["SQL"],
            "count": 1,
            "duration_minutes": 25,
            "language": "sql",
        }
    return {
        "round_type": "system_design",
        "category": "system_design",
        "stage": STAGE_PRACTICAL,
        "skills": ["System Design"],
        "count": 1,
        "duration_minutes": 25,
    }


def build_behavioural_questions_csv(
    reviewed_csv_path: Path | str,
    output_csv_path: Path | str,
) -> int:
    """Compile approved HR prompts (``keep == y``) into deduplicated CSV bank.

    Only question text, difficulty, sub_domain, and source are persisted;
    ideal answers and scoring keywords are stripped per Q4 (question-text only).
    """
    src = Path(reviewed_csv_path)
    dst = Path(output_csv_path)
    if not src.exists():
        raise FileNotFoundError(f"Reviewed HR CSV not found: {src}")

    rows_out: list[dict[str, str]] = []
    seen_questions: set[str] = set()
    with src.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            keep_flag = _clean_text(row.get("keep")).casefold()
            if keep_flag not in _KEEP_TRUE_VALUES:
                continue
            question = _clean_text(row.get("question"))
            if not question:
                continue
            norm = " ".join(question.casefold().split())
            if norm in seen_questions:
                continue
            seen_questions.add(norm)
            rows_out.append({
                "question": question,
                "difficulty": _clean_text(row.get("difficulty")).lower() or "medium",
                "sub_domain": _clean_text(row.get("sub_domain")) or "hr_behavioral",
                "source": "behavioural_bank",
            })

    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["question", "difficulty", "sub_domain", "source"],
        )
        writer.writeheader()
        writer.writerows(rows_out)
    return len(rows_out)


def load_behavioural_questions(
    csv_path: Path | str | None = None,
) -> list[dict[str, str]]:
    """Load confirmed question-text-only HR prompts; empty list if absent."""
    path = Path(csv_path) if csv_path is not None else DEFAULT_BEHAVIOURAL_CSV_PATH
    if not path.exists() or not path.is_file():
        return []
    questions: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            question = _clean_text(row.get("question"))
            if not question:
                continue
            norm = " ".join(question.casefold().split())
            if norm in seen:
                continue
            seen.add(norm)
            questions.append({
                "question": question,
                "difficulty": _clean_text(row.get("difficulty")).lower() or "medium",
                "sub_domain": _clean_text(row.get("sub_domain")) or "hr_behavioral",
                "source": _clean_text(row.get("source")) or "behavioural_bank",
            })
    return questions


def select_warm_up_question_payload(
    *,
    skill: str,
    asked: list[str] | None = None,
) -> dict[str, Any]:
    """Select an unscored ``easy`` Warm-up prompt without LLM or bundle gate.

    Uses local CSV / domain fallback / template prompts strictly offline so
    Warm-up succeeds at $0 even when ``REVIEWED_BUNDLES_ONLY=true`` (Q1) or
    when an LLM provider is configured while live calls are gated off.
    """
    from modules.question_bank import (
        _domain_fallback_question,
        _get_bank,
        _template_question,
        resolve_skill,
    )

    chosen_skill = _clean_text(skill) or "System Design"
    canonical_skill, _ = resolve_skill(chosen_skill)
    asked_list = list(asked or [])
    q = (
        _get_bank().pick(
            canonical_skill,
            None,
            "easy",
            asked_list,
        )
        or _domain_fallback_question(canonical_skill, None, asked_list)
        or _template_question(canonical_skill, None, "easy")
    )
    out = dict(q)
    out.setdefault("skill", chosen_skill)
    out.setdefault("sub_domain", "general")
    out["difficulty"] = "easy"
    out["ideal_answer"] = ""
    out["ideal_keywords"] = ""
    out["stage"] = STAGE_WARM_UP
    out["unscored"] = True
    out["followups"] = []
    out["source"] = str(out.get("source") or "warm_up_bank")
    return out


def select_behavioural_question_payload(
    *,
    asked: list[str] | None = None,
    csv_path: Path | str | None = None,
) -> dict[str, Any]:
    """Select next confirmed HR Behavioural question (question text only, Q4)."""
    pool = load_behavioural_questions(csv_path=csv_path)
    if not pool:
        raise ValueError(
            "Confirmed behavioural question bank is unavailable or empty."
        )
    asked_norm = {" ".join(_clean_text(item).casefold().split()) for item in (asked or []) if _clean_text(item)}
    chosen = next(
        (
            row
            for row in pool
            if " ".join(row["question"].casefold().split()) not in asked_norm
        ),
        pool[0],
    )
    return {
        "question": chosen["question"],
        "skill": "HR",
        "sub_domain": chosen["sub_domain"],
        "difficulty": chosen["difficulty"],
        "ideal_answer": "",
        "ideal_keywords": "",
        "followups": [],
        "source": chosen["source"],
        "stage": STAGE_BEHAVIOURAL,
        "unscored": True,
        "question_text_only": True,
    }


def select_non_core_stage_question(
    *,
    stage: str | None,
    skill: str,
    asked: list[str] | None = None,
) -> tuple[dict[str, Any], str, str] | None:
    """Resolve question payload, skill, and difficulty for Warm-up / Behavioural.

    Returns ``None`` for Core or unstaged interview rounds so normal adaptive
    selection runs unchanged.
    """
    clean_stage = _clean_text(stage).lower()
    if clean_stage == STAGE_WARM_UP:
        chosen_skill = _clean_text(skill) or "System Design"
        payload = select_warm_up_question_payload(
            skill=chosen_skill,
            asked=asked,
        )
        return payload, chosen_skill, "easy"
    if clean_stage == STAGE_BEHAVIOURAL:
        payload = select_behavioural_question_payload(asked=asked)
        return payload, "HR", str(payload.get("difficulty") or "medium")
    return None


def deferred_feedback_response(
    *,
    session_id: str,
    round_number: int,
    session_status: str | None,
) -> dict[str, Any]:
    """Server-enforced deferred response for ``GET /rounds/{n}/feedback`` (A7)."""
    return {
        "session_id": session_id,
        "round": int(round_number),
        "session_status": session_status,
        "deferred": True,
        "feedback": {"content": [], "strengths": [], "weakness": [], "next_step": ""},
        "final_score": None,
        "narration": {
            "status": "deferred",
            "source": None,
            "script": None,
            "label": None,
            "details": {},
        },
        "assessment_completed": False,
        "assessment_eligibility": None,
        "eligibility_exclusion_reasons": [],
    }


def apply_deferred_answer_mask(response_payload: dict[str, Any]) -> dict[str, Any]:
    """Hide per-round scores/feedback on ``POST /session/answer`` in ``staged_v1``."""
    masked = dict(response_payload)
    masked.pop("scoring_breakdown", None)
    masked.pop("follow_up_outcome", None)
    masked["final_score"] = None
    masked["nlp_score"] = None
    masked["kg_score"] = None
    masked["svm_label"] = None
    masked["ner_entities"] = []
    masked["feedback"] = {
        "content": [],
        "strengths": [],
        "weakness": [],
        "next_step": "",
    }
    masked["score_explanation"] = {}
    masked["rubric"] = {}
    masked["concepts"] = {}
    masked["guard"] = {}
    masked["artifact_json"] = {}
    masked["guard_applied"] = None
    masked["elo_after"] = None
    masked["difficulty_change"] = None
    masked["feedback_deferred"] = True
    masked["narration_status"] = "deferred"
    return masked


def build_staged_blocks(
    *,
    preset: str,
    skills: list[str],
    sub_domain: str | None = None,
    difficulty: str | None = None,
    role_id: str | None = None,
    behavioural_questions: list[dict[str, str]] | None = None,
    behavioural_csv_path: Path | str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build raw blocks (ready for ``normalize_blocks``) and metadata for ``staged_v1``."""
    preset_key = _clean_text(preset).lower()
    if preset_key not in _PRESET_SPECS:
        raise ValueError(
            f"Unsupported preset '{preset}'. Allowed presets: Quick, Full."
        )
    spec = _PRESET_SPECS[preset_key]

    technical_skills = [
        _clean_text(s)
        for s in skills
        if _clean_text(s) and _clean_text(s).casefold() != "hr"
    ]
    if not technical_skills and role_id:
        technical_skills = resolve_role_skills(role_id)
    if not technical_skills:
        raise ValueError(
            "At least one technical skill or a known target_role_id with "
            "skills is required for staged_v1."
        )

    clean_topic = _clean_text(sub_domain) or None
    if clean_topic and clean_topic.lower() == "general":
        clean_topic = None
    clean_diff = _clean_text(difficulty).lower() or None

    raw_blocks: list[dict[str, Any]] = []
    stages_scheduled: list[str] = []

    # Stage 1: Warm-up (1 unscored easy prompt on primary technical skill).
    raw_blocks.append({
        "round_type": "technical_short_answer",
        "category": "interview",
        "stage": STAGE_WARM_UP,
        "skills": [technical_skills[0]],
        "count": 1,
        "difficulty": "easy",
        "allow_optional_follow_ups": False,
    })
    stages_scheduled.append(STAGE_WARM_UP)

    # Stage 2: Core technical turns (Stage 3 follow-ups attach dynamically here).
    core_block: dict[str, Any] = {
        "round_type": "technical_short_answer",
        "category": "interview",
        "stage": STAGE_CORE,
        "skills": list(technical_skills),
        "count": int(spec["core_count"]),
    }
    if clean_topic:
        core_block["topic"] = clean_topic
    if clean_diff:
        core_block["difficulty"] = clean_diff
    raw_blocks.append(core_block)
    stages_scheduled.append(STAGE_CORE)

    # Stage 4: Optional Practical (Full preset only, when role/skills have track).
    practical_track: str | None = None
    practical_skipped = True
    practical_skipped_reason: str | None = "quick_preset"
    if spec["include_practical"]:
        practical_track = resolve_practical_track(
            role_id=role_id,
            session_skills=technical_skills,
        )
        if practical_track is not None:
            raw_blocks.append(_practical_block_for_track(practical_track))
            stages_scheduled.append(STAGE_PRACTICAL)
            practical_skipped = False
            practical_skipped_reason = None
        else:
            practical_skipped = True
            practical_skipped_reason = "no_practical_track"

    # Stage 5: Behavioural (only when confirmed bank exists and is non-empty).
    beh_pool = (
        list(behavioural_questions)
        if behavioural_questions is not None
        else load_behavioural_questions(csv_path=behavioural_csv_path)
    )
    desired_beh = int(spec["behavioural_count"])
    actual_beh = min(desired_beh, len(beh_pool)) if beh_pool else 0
    if actual_beh > 0:
        raw_blocks.append({
            "round_type": "technical_short_answer",
            "category": "interview",
            "stage": STAGE_BEHAVIOURAL,
            "skills": ["HR"],
            "count": actual_beh,
            "difficulty": "medium",
            "allow_optional_follow_ups": False,
        })
        stages_scheduled.append(STAGE_BEHAVIOURAL)
        behavioural_skipped = False
        behavioural_skipped_reason = None
    else:
        behavioural_skipped = True
        behavioural_skipped_reason = "behavioural_bank_missing_or_empty"

    if preset_key == "full" and practical_skipped:
        est_minutes = int(spec["estimated_minutes_without_practical"])
    else:
        est_minutes = int(spec["estimated_minutes"])

    meta = {
        "version": STAGED_FLOW_VERSION,
        "preset": preset_key,
        "deferred_feedback": True,
        "stages_scheduled": stages_scheduled,
        "core_count": int(spec["core_count"]),
        "practical_track": practical_track,
        "practical_skipped": practical_skipped,
        "practical_skipped_reason": practical_skipped_reason,
        "behavioural_count": actual_beh,
        "behavioural_skipped": behavioural_skipped,
        "behavioural_skipped_reason": behavioural_skipped_reason,
        "estimated_minutes": est_minutes,
    }
    return raw_blocks, meta
