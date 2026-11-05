"""Phase B block contract: stable per-block identity, order and settings.

A ``round_plan`` array of type names cannot represent repeated blocks with
independent settings (two OA blocks with different topics). Blocks carry
their own identity, position, round type, category, topics, count, time
budget, difficulty policy, selected problem IDs and language.

This module is pure validation/normalization/expansion. Content selection
(DB + module banks) stays in ``backend.routes.session`` (existing engine).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

ALLOWED_ROUND_TYPES = (
    "technical_short_answer",
    "mcq",
    "sql",
    "coding",
    "system_design",
    "ml_primitives",
)
ALLOWED_CATEGORIES = (
    "verbal",
    "oa",
    "sql",
    "interview",
    "coding",
    "system_design",
    "ml_primitives",
)
ALLOWED_DIFFICULTIES = ("easy", "medium", "hard")
ALLOWED_REVIEW_POLICIES = ("none", "after_session")

VERBAL_SKILL = "Verbal Ability"
SYSTEM_DESIGN_SKILL = "System Design"

BLOCKS_VERSION = 1
PRESET_VERSION = 1
BUILDER_DRAFT_VERSION = 1

MAX_BLOCKS = 10
MAX_TOTAL_ROUNDS = 50
MAX_MCQ_COUNT = 30
MAX_SQL_PER_BLOCK = 5
MAX_CODING_PER_BLOCK = 5
MAX_INTERVIEW_PER_BLOCK = 10
MAX_SYSTEM_DESIGN_PER_BLOCK = 5
CODING_LANGUAGE = "python"


class BlockSpec(BaseModel):
    """One practice block. Server assigns stable ``id``/``position``."""

    id: str | None = None
    position: int | None = None
    round_type: str
    category: str | None = None
    skills: list[str] | None = None
    topics: list[str] | None = None
    topic: str | None = None
    count: int | None = None
    duration_minutes: int | None = None
    difficulty: str | None = None
    question_ids: list[str] | None = None
    problem_ids: list[str] | None = None
    problem_id: str | None = None
    language: str | None = None
    negative_marking: float | None = None
    review_policy: str | None = None
    # Phase 4A: optional follow-ups (Interview blocks; assessment defaults off).
    allow_optional_follow_ups: bool | None = None
    # Acceptance: lower per-block follow-up cap (default 2 when unset).
    max_follow_ups: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _strip_strings(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for key in ("id", "round_type", "category", "difficulty", "topic",
                        "problem_id", "language", "review_policy"):
                if isinstance(data.get(key), str):
                    data[key] = data[key].strip()
            for key in ("skills", "topics", "question_ids", "problem_ids"):
                values = data.get(key)
                if isinstance(values, list):
                    data[key] = [str(v).strip() for v in values
                                 if str(v).strip()]
        return data


def canonicalize_verbal_skills(skills: list[str] | None) -> list[str] | None:
    """Map whitespace/case variants of Verbal Ability to the exact name."""
    if not skills:
        return skills
    wanted = VERBAL_SKILL.lower()
    return [VERBAL_SKILL if s.strip().lower() == wanted else s
            for s in skills]


def _skills_for_block(raw: dict[str, Any]) -> list[str]:
    skills = list(raw.get("skills") or [])
    topics = list(raw.get("topics") or [])
    merged: list[str] = []
    for value in skills + topics:
        text = str(value).strip()
        if text and text not in merged:
            merged.append(text)
    return canonicalize_verbal_skills(merged) or []


def derive_category(round_type: str, skills: list[str]) -> str:
    if round_type == "mcq":
        return "verbal" if skills == [VERBAL_SKILL] else "oa"
    if round_type == "sql":
        return "sql"
    if round_type == "coding":
        return "coding"
    if round_type == "ml_primitives":
        return "ml_primitives"
    if round_type == "system_design":
        return "system_design"
    return "interview"


def normalize_blocks(raw_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate structure and assign stable ids/positions.

    Raises ValueError with a human-readable message. Content availability
    (bank counts) is checked separately at session start so presets and
    drafts can be stored without pinning bank sizes.
    """
    if not raw_blocks:
        raise ValueError("At least one block is required.")
    if len(raw_blocks) > MAX_BLOCKS:
        raise ValueError(f"At most {MAX_BLOCKS} blocks are allowed.")

    seen_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_blocks):
        if not isinstance(raw, dict):
            raise ValueError(f"Block {index + 1} must be an object.")
        try:
            spec = BlockSpec(**raw)
        except Exception as exc:
            raise ValueError(f"Block {index + 1} is invalid: {exc}") from exc

        round_type = (spec.round_type or "").strip()
        if round_type not in ALLOWED_ROUND_TYPES:
            raise ValueError(
                f"Block {index + 1}: unsupported round_type "
                f"'{spec.round_type}'. Allowed: {list(ALLOWED_ROUND_TYPES)}."
            )
        skills = _skills_for_block(raw)
        category = (spec.category or "").strip().lower() or None
        derived = derive_category(round_type, skills)
        if category is None:
            category = derived
        if category not in ALLOWED_CATEGORIES:
            raise ValueError(
                f"Block {index + 1}: unsupported category '{spec.category}'."
            )
        if category != derived:
            raise ValueError(
                f"Block {index + 1}: category '{category}' does not match "
                f"round_type '{round_type}' and skills {skills}."
            )
        if category == "verbal" and skills != [VERBAL_SKILL]:
            raise ValueError(
                f"Block {index + 1}: Verbal blocks must use skills "
                f"['{VERBAL_SKILL}']."
            )
        if category == "oa" and VERBAL_SKILL in skills:
            raise ValueError(
                f"Block {index + 1}: OA blocks must not include "
                f"'{VERBAL_SKILL}'; use a Verbal block."
            )
        if category in ("oa", "interview") and not skills:
            raise ValueError(
                f"Block {index + 1}: at least one skill/topic is required."
            )
        if category == "sql":
            skills = skills or ["SQL"]
        if category == "ml_primitives":
            skills = skills or ["ML primitives"]
        if category == "system_design":
            skills = skills or [SYSTEM_DESIGN_SKILL]
        if category == "coding" and VERBAL_SKILL in skills:
            raise ValueError(
                f"Block {index + 1}: coding topics must not include "
                f"'{VERBAL_SKILL}'."
            )

        difficulty = (spec.difficulty or "").strip().lower() or None
        if difficulty is not None and difficulty not in ALLOWED_DIFFICULTIES:
            raise ValueError(
                f"Block {index + 1}: unsupported difficulty '{spec.difficulty}'."
            )
        topic = (spec.topic or "").strip() or None
        if topic is not None and category != "interview":
            raise ValueError(
                f"Block {index + 1}: topic is only supported for "
                f"interview blocks."
            )
        if topic is not None and len(topic) > 120:
            raise ValueError(
                f"Block {index + 1}: topic must be at most 120 characters."
            )
        review_policy = (spec.review_policy or "").strip() or "none"
        if review_policy not in ALLOWED_REVIEW_POLICIES:
            raise ValueError(
                f"Block {index + 1}: unsupported review_policy "
                f"'{spec.review_policy}'."
            )
        language = (spec.language or "").strip().lower() or None
        if category == "sql":
            if language is not None and language != "sql":
                raise ValueError(
                    f"Block {index + 1}: SQL blocks use language 'sql'."
                )
            language = "sql"
        elif category == "coding":
            from backend.coding_languages import normalize_language
            language = normalize_language(language)
        elif category == "ml_primitives":
            if language is not None and language != CODING_LANGUAGE:
                raise ValueError(
                    f"Block {index + 1}: coding blocks use language "
                    f"'{CODING_LANGUAGE}'."
                )
            language = CODING_LANGUAGE
        elif language is not None:
            raise ValueError(
                f"Block {index + 1}: language is only supported for "
                f"SQL, coding and ML primitive blocks."
            )

        question_ids = [str(q).strip() for q in (spec.question_ids or [])
                        if str(q).strip()]
        problem_ids = [str(p).strip() for p in (spec.problem_ids or [])
                       if str(p).strip()]
        if spec.problem_id and str(spec.problem_id).strip():
            single = str(spec.problem_id).strip()
            if single not in problem_ids:
                problem_ids = problem_ids + [single]
        if question_ids and category not in ("oa", "verbal"):
            raise ValueError(
                f"Block {index + 1}: question_ids apply to MCQ blocks only."
            )
        if problem_ids and category not in ("sql", "coding", "system_design", "ml_primitives"):
            raise ValueError(
                f"Block {index + 1}: problem_ids apply to SQL, coding, and "
                f"system-design and ML primitive blocks only."
            )

        duration = spec.duration_minutes
        if duration is None:
            if category in ("oa", "verbal"):
                duration = 20
            elif category in ("coding", "ml_primitives"):
                duration = 30
            else:
                duration = 25
        try:
            duration = int(duration)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Block {index + 1}: duration_minutes must be an integer."
            ) from exc
        if category == "interview" and spec.duration_minutes is None:
            # Untimed legacy behavior: interview blocks without an
            # explicit budget stay untimed (no server deadline).
            duration_value: int | None = None
        else:
            if duration < 1 or duration > 180:
                raise ValueError(
                    f"Block {index + 1}: duration_minutes must be 1-180."
                )
            duration_value = duration

        count = spec.count
        if category in ("oa", "verbal"):
            if question_ids:
                if count is not None and int(count) != len(question_ids):
                    raise ValueError(
                        f"Block {index + 1}: count must match "
                        f"question_ids length ({len(question_ids)})."
                    )
                count_value = len(question_ids)
            else:
                count_value = int(count) if count is not None else 15
            if count_value < 1 or count_value > MAX_MCQ_COUNT:
                raise ValueError(
                    f"Block {index + 1}: count must be 1-{MAX_MCQ_COUNT}."
                )
        elif category in ("sql", "coding", "ml_primitives"):
            limit = (MAX_CODING_PER_BLOCK if category in ("coding", "ml_primitives")
                     else MAX_SQL_PER_BLOCK)
            if problem_ids:
                if count is not None and int(count) != len(problem_ids):
                    raise ValueError(
                        f"Block {index + 1}: count must match problem_ids "
                        f"length ({len(problem_ids)})."
                    )
                count_value = len(problem_ids)
            else:
                count_value = int(count) if count is not None else 1
            if count_value < 1 or count_value > limit:
                raise ValueError(
                    f"Block {index + 1}: count must be 1-{limit}."
                )
        elif category == "system_design":
            if problem_ids:
                if count is not None and int(count) != len(problem_ids):
                    raise ValueError(
                        f"Block {index + 1}: count must match problem_ids "
                        f"length ({len(problem_ids)})."
                    )
                count_value = len(problem_ids)
            else:
                count_value = int(count) if count is not None else 1
            if count_value < 1 or count_value > MAX_SYSTEM_DESIGN_PER_BLOCK:
                raise ValueError(
                    f"Block {index + 1}: count must be "
                    f"1-{MAX_SYSTEM_DESIGN_PER_BLOCK}."
                )
        else:
            count_value = int(count) if count is not None else 3
            if count_value < 1 or count_value > MAX_INTERVIEW_PER_BLOCK:
                raise ValueError(
                    f"Block {index + 1}: count must be "
                    f"1-{MAX_INTERVIEW_PER_BLOCK}."
                )

        negative_marking = (0.25 if category in ("oa", "verbal")
                            else 0.0)
        if spec.negative_marking is not None:
            try:
                negative_marking = float(spec.negative_marking)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Block {index + 1}: negative_marking must be a number."
                ) from exc
            if negative_marking < 0 or negative_marking > 1:
                raise ValueError(
                    f"Block {index + 1}: negative_marking must be 0-1."
                )

        block_id = (spec.id or "").strip() or str(uuid4())
        if block_id in seen_ids:
            raise ValueError(
                f"Block {index + 1}: duplicate block id '{block_id}'."
            )
        seen_ids.add(block_id)

        normalized.append({
            "id": block_id,
            "position": index + 1,
            "round_type": round_type,
            "category": category,
            "skills": skills,
            "topic": topic,
            "count": count_value,
            "duration_minutes": duration_value,
            "difficulty": difficulty,
            "question_ids": question_ids,
            "problem_ids": problem_ids,
            "language": language,
            "negative_marking": negative_marking,
            "review_policy": review_policy,
            "allow_optional_follow_ups": bool(spec.allow_optional_follow_ups)
            if category == "interview"
            else False,
            "max_follow_ups": spec.max_follow_ups
            if category == "interview"
            else None,
        })

    total = sum(b["count"] if b["category"] in (
                    "sql", "coding", "interview", "system_design", "ml_primitives")
                else 1 for b in normalized)
    if total > MAX_TOTAL_ROUNDS:
        raise ValueError(
            f"Too many rounds requested ({total}); "
            f"maximum is {MAX_TOTAL_ROUNDS}."
        )
    return normalized


def legacy_to_blocks(
    *,
    skills: list[str],
    rounds_per_skill: int = 3,
    round_type: str = "technical_short_answer",
    round_config: dict[str, Any] | None = None,
    round_plan: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Convert a legacy launch payload into blocks (order preserved)."""
    cfg = dict(round_config or {})
    skills = canonicalize_verbal_skills(
        [str(s).strip() for s in (skills or []) if str(s).strip()]
    ) or []
    if round_plan:
        plan = [str(t).strip() for t in round_plan if str(t).strip()]
        blocks: list[dict[str, Any]] = []
        sql_seen = 0
        problem_ids = [str(p).strip() for p in (cfg.get("problem_ids") or [])
                       if str(p).strip()]
        if cfg.get("problem_id") and str(cfg["problem_id"]).strip():
            single = str(cfg["problem_id"]).strip()
            if single not in problem_ids:
                problem_ids.append(single)
        coding_seen = 0
        coding_ids = [str(p).strip()
                      for p in (cfg.get("coding_problem_ids") or [])
                      if str(p).strip()]
        for entry in plan:
            if entry == "mcq":
                blocks.append({
                    "round_type": "mcq",
                    "skills": skills,
                    "count": int(cfg.get("count", 15)),
                    "duration_minutes": int(cfg.get("duration_minutes", 20)),
                    "difficulty": cfg.get("difficulty"),
                    "question_ids": cfg.get("question_ids"),
                    "negative_marking": cfg.get("negative_marking", 0.25),
                    "review_policy": cfg.get("review_policy", "none"),
                })
            elif entry == "sql":
                selected: list[str] = []
                if sql_seen < len(problem_ids):
                    selected = [problem_ids[sql_seen]]
                sql_seen += 1
                item: dict[str, Any] = {
                    "round_type": "sql",
                    "skills": skills or ["SQL"],
                    "duration_minutes": int(cfg.get("duration_minutes", 25)),
                    "difficulty": cfg.get("difficulty"),
                    "review_policy": cfg.get("review_policy", "none"),
                }
                if selected:
                    item["problem_ids"] = selected
                blocks.append(item)
            elif entry == "coding":
                selected_coding: list[str] = []
                if coding_seen < len(coding_ids):
                    selected_coding = [coding_ids[coding_seen]]
                coding_seen += 1
                coding_item: dict[str, Any] = {
                    "round_type": "coding",
                    # Legacy launches carry interview skills, not coding
                    # topics; like SQL, legacy coding auto-select ignores
                    # them. Blocks-API topics filter strictly.
                    "skills": [],
                    "duration_minutes": int(cfg.get("duration_minutes", 30)),
                    "difficulty": cfg.get("difficulty"),
                    "review_policy": cfg.get("review_policy", "none"),
                }
                if selected_coding:
                    coding_item["problem_ids"] = selected_coding
                blocks.append(coding_item)
            else:
                blocks.append({
                    "round_type": "technical_short_answer",
                    "skills": skills,
                    "count": 1,
                    "duration_minutes": cfg.get("duration_minutes"),
                    "difficulty": cfg.get("difficulty"),
                })
        return normalize_blocks(blocks)

    if round_type in ("mcq", "sql", "coding"):
        defaults = {"mcq": 20, "sql": 25, "coding": 30}
        item = {
            "round_type": round_type,
            "skills": [] if round_type == "coding" else skills,
            "count": int(cfg.get("count", 15)) if round_type == "mcq" else 1,
            "duration_minutes": int(cfg.get("duration_minutes",
                                            defaults[round_type])),
            "difficulty": cfg.get("difficulty"),
            "question_ids": cfg.get("question_ids"),
            "problem_ids": cfg.get("problem_ids"),
            "problem_id": cfg.get("problem_id"),
            "negative_marking": cfg.get("negative_marking", 0.25),
            "review_policy": cfg.get("review_policy", "none"),
        }
        return normalize_blocks([item])

    per = max(1, int(rounds_per_skill or 3))
    grouped: list[dict[str, Any]] = []
    for skill in skills or ["System Design"]:
        grouped.append({
            "round_type": "technical_short_answer",
            "skills": [skill],
            "count": per,
        })
    return normalize_blocks(grouped)


def expand_blocks(block_plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand blocks into per-round specs in requested order.

    MCQ blocks stay one round with N questions. SQL, coding, and
    Interview blocks expand into N rounds (one problem/question each)
    sharing the block id.
    """
    expanded: list[dict[str, Any]] = []
    round_number = 0
    for block in block_plan:
        category = block.get("category")
        if category in ("oa", "verbal"):
            round_number += 1
            expanded.append({
                "round": round_number,
                "block_id": block["id"],
                "block_position": block["position"],
                "block_index": 1,
                "block_total": 1,
                "round_type": block["round_type"],
                "category": category,
                "skills": list(block.get("skills") or []),
                "topic": block.get("topic"),
                "count": int(block.get("count") or 15),
                "duration_minutes": block.get("duration_minutes"),
                "difficulty": block.get("difficulty"),
                "question_ids": list(block.get("question_ids") or []),
                "problem_ids": [],
                "language": block.get("language"),
                "negative_marking": float(block.get("negative_marking", 0.25)),
                "review_policy": block.get("review_policy", "none"),
            })
        elif category in ("sql", "coding", "ml_primitives"):
            problem_ids = list(block.get("problem_ids") or [])
            total = len(problem_ids) if problem_ids else int(block.get("count") or 1)
            default_skills = ["SQL"] if category == "sql" else []
            default_language = "sql" if category == "sql" else CODING_LANGUAGE
            for item_index in range(total):
                round_number += 1
                selected = ([problem_ids[item_index]]
                            if item_index < len(problem_ids) else [])
                expanded.append({
                    "round": round_number,
                    "block_id": block["id"],
                    "block_position": block["position"],
                    "block_index": item_index + 1,
                    "block_total": total,
                    "round_type": block["round_type"],
                    "category": category,
                    "skills": list(block.get("skills") or default_skills),
                    "topic": block.get("topic"),
                    "count": 1,
                    "duration_minutes": block.get("duration_minutes"),
                    "difficulty": block.get("difficulty"),
                    "question_ids": [],
                    "problem_ids": selected,
                    "language": block.get("language") or default_language,
                    "negative_marking": 0.0,
                    "review_policy": block.get("review_policy", "none"),
                })
        elif category == "system_design":
            prompt_ids = list(block.get("problem_ids") or [])
            total = len(prompt_ids) if prompt_ids else int(block.get("count") or 1)
            for item_index in range(total):
                round_number += 1
                selected = ([prompt_ids[item_index]]
                            if item_index < len(prompt_ids) else [])
                expanded.append({
                    "round": round_number,
                    "block_id": block["id"],
                    "block_position": block["position"],
                    "block_index": item_index + 1,
                    "block_total": total,
                    "round_type": "system_design",
                    "category": "system_design",
                    "skills": list(block.get("skills") or [SYSTEM_DESIGN_SKILL]),
                    "topic": block.get("topic"),
                    "count": 1,
                    "duration_minutes": block.get("duration_minutes"),
                    "difficulty": block.get("difficulty"),
                    "question_ids": [],
                    "problem_ids": selected,
                    "language": None,
                    "negative_marking": 0.0,
                    "review_policy": block.get("review_policy", "none"),
                })
        else:
            total = int(block.get("count") or 3)
            for item_index in range(total):
                round_number += 1
                expanded.append({
                    "round": round_number,
                    "block_id": block["id"],
                    "block_position": block["position"],
                    "block_index": item_index + 1,
                    "block_total": total,
                    "round_type": "technical_short_answer",
                    "category": "interview",
                    "skills": list(block.get("skills") or []),
                    "topic": block.get("topic"),
                    "count": 1,
                    "duration_minutes": block.get("duration_minutes"),
                    "difficulty": block.get("difficulty"),
                    "question_ids": [],
                    "problem_ids": [],
                    "language": None,
                    "negative_marking": 0.0,
                    "review_policy": block.get("review_policy", "none"),
                })
    # Every expanded spec is mandatory. Its index is fixed at creation and
    # survives later follow-up insertions that shift ``round``.
    for spec in expanded:
        spec["mandatory_index"] = spec["round"]
    return expanded


def block_label(block: dict[str, Any]) -> str:
    """Human label such as 'OA · 12 questions' (never raw type names)."""
    category = (block.get("category") or "").lower()
    count = int(block.get("count") or 1)
    if category == "verbal":
        noun = "question" if count == 1 else "questions"
        return f"Verbal · {count} {noun}"
    if category == "oa":
        noun = "question" if count == 1 else "questions"
        return f"OA · {count} {noun}"
    if category == "sql":
        noun = "problem" if count == 1 else "problems"
        return f"SQL · {count} {noun}"
    if category == "coding":
        noun = "problem" if count == 1 else "problems"
        return f"Coding · {count} {noun}"
    if category == "ml_primitives":
        noun = "problem" if count == 1 else "problems"
        return f"ML primitives · {count} {noun} (ungraded)"
    if category == "system_design":
        noun = "prompt" if count == 1 else "prompts"
        return f"System design · {count} {noun}"
    noun = "question" if count == 1 else "questions"
    return f"Interview · {count} {noun}"


def total_time_summary(block_plan: list[dict[str, Any]]) -> dict[str, Any]:
    """Total timed minutes; untimed interview blocks are listed separately."""
    timed = sum(int(b.get("duration_minutes") or 0)
                for b in block_plan if b.get("duration_minutes"))
    untimed = sum(1 for b in block_plan if not b.get("duration_minutes"))
    return {"timed_minutes": timed, "untimed_blocks": untimed,
            "block_count": len(block_plan)}
