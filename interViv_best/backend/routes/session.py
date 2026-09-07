"""
session_v2.py — Drop-in replacement for backend/routes/session.py

Core changes vs. the current version:
  • StartSessionRequest accepts `skills: List[str]` (1-5 skills) instead of `skill: str`
  • Backwards compat: accepts `skill: str` too and wraps it in a list
  • Stores `skills` + `rounds_per_skill` + `total_rounds` on the session doc
  • First round uses skills[0]; subsequent rounds rotate via _skill_for_round()
  • The helper `_skill_for_round(session, round_number)` is exported for answer.py

Helper export:
  from backend.routes.session import _skill_for_round, _sub_domain_for_skill
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from backend.config import get_settings
from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.execution import ExecutionUnavailableError, execute_python_tests
from backend.integrations import IntegrationError
from backend.models.blocks import (
    VERBAL_SKILL,
    canonicalize_verbal_skills,
    expand_blocks,
    legacy_to_blocks,
    normalize_blocks,
)
from backend.models.candidate import CandidateDocument
from backend.models.session import RoundDocument, SessionDocument
from backend.routes.auth import get_user_from_authorization, require_matching_user, require_user
from backend.serializers.round_serializer import sanitize_round_for_client
from modules.skill_graph import StudentSkillGraph

router = APIRouter(prefix="/session", tags=["session"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_ROUND_TYPES = (
    "technical_short_answer",
    "mcq",
    "sql",
    "coding",
    "system_design",
)


class StartSessionRequest(BaseModel):
    candidate_id: str = ""
    # Legacy single-skill field — still accepted
    skill: str | None = None
    # New: list of skills. 1 = single-skill session, N = rotate across N skills.
    skills: list[str] = Field(default_factory=list, description="List of skills for this session")
    sub_domain: str | None = None
    rounds_per_skill: int = Field(default=3, ge=1, le=10)
    target_company_id: str | None = None
    target_role_id: str | None = None
    round_type: str = "technical_short_answer"
    round_config: dict[str, Any] | None = None
    # Ticket A: ordered mix of real round types (e.g. ["mcq", "sql"]).
    # When set, total_rounds = len(round_plan) and answer.py queues by plan.
    round_plan: list[str] | None = None
    # Phase B: per-block plan with independent settings. When set, blocks
    # drive the session; legacy skills/round_plan are derived for storage.
    blocks: list[dict[str, Any]] | None = None

    @model_validator(mode="before")
    @classmethod
    def _ensure_at_least_one(cls, data):  # noqa: N805
        if isinstance(data, dict):
            if data.get("blocks") is not None:
                raw_blocks = data.get("blocks")
                if not isinstance(raw_blocks, list) or not raw_blocks:
                    raise ValueError("blocks must be a non-empty array.")
                # Detailed block validation happens in start_session so
                # errors return 422 with per-block messages. Top-level
                # skills are optional when blocks carry their own topics.
                skills = data.get("skills")
                skill = data.get("skill")
                if skills:
                    data["skills"] = [s.strip() for s in skills if s and str(s).strip()]
                elif skill and str(skill).strip():
                    data["skills"] = [str(skill).strip()]
                else:
                    data["skills"] = []
                return data
            skills = data.get("skills")
            skill = data.get("skill")
            if skills:
                data["skills"] = [s.strip() for s in skills if s and str(s).strip()]
            elif skill and str(skill).strip():
                data["skills"] = [str(skill).strip()]
            else:
                raise ValueError("At least one skill is required (skills=[...] or skill='...')")
            plan = data.get("round_plan")
            if plan is not None:
                cleaned = [str(t).strip() for t in plan if str(t).strip()]
                if not cleaned:
                    raise ValueError("round_plan must contain at least one round type")
                bad = [t for t in cleaned if t not in ALLOWED_ROUND_TYPES]
                if bad:
                    raise ValueError(
                        f"Unsupported round_plan types: {bad}. "
                        f"Allowed: {list(ALLOWED_ROUND_TYPES)}"
                    )
                data["round_plan"] = cleaned
                # First plan entry drives the opening round when round_type omitted/default.
                if not data.get("round_type") or data.get("round_type") == "technical_short_answer":
                    if cleaned[0] != "technical_short_answer":
                        data["round_type"] = cleaned[0]
        return data


class RunSQLPreviewRequest(BaseModel):
    session_id: str
    round: int
    query: str


class RunCodingPreviewRequest(BaseModel):
    session_id: str
    round: int
    source: str


class SaveAnswerDraftRequest(BaseModel):
    round: int
    answer_text: str | None = None
    answers: list[dict[str, Any]] | None = None
    rubric_ratings: dict[str, Any] | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _elo_to_difficulty(elo: float) -> str:
    if elo < 1200:
        return "easy"
    if elo < 1700:
        return "medium"
    return "hard"


def _expanded_spec_for_round(session: dict, round_number: int) -> dict[str, Any] | None:
    """Return the expanded block spec for a 1-based round, if present."""
    expanded = session.get("expanded_plan") or []
    for spec in expanded:
        if int(spec.get("round") or 0) == int(round_number):
            return spec
    return None


def _skill_for_round(session: dict, round_number: int) -> str:
    """Return the skill to ask in the given (1-based) round.

    Block sessions use the expanded plan's per-round skills (requested
    order). Legacy sessions rotate:

        skills = [A, B, C], rounds_per_skill = 3 → A A A B B B C C C
    """
    spec = _expanded_spec_for_round(session, round_number)
    if spec:
        skills = [s for s in (spec.get("skills") or []) if s]
        if skills:
            return skills[0]
    skills = session.get("skills") or [session.get("skill")]
    skills = [s for s in skills if s]
    if not skills:
        return session.get("skill") or "System Design"

    per = int(session.get("rounds_per_skill", 3))
    per = max(1, per)
    idx = (int(round_number) - 1) // per
    if idx >= len(skills):
        idx = len(skills) - 1
    return skills[idx]


def _sub_domain_for_skill(candidate: dict | None, skill: str,
                          override: str | None = None) -> str | None:
    if override:
        return override
    if not candidate:
        return None
    return (candidate.get("sub_domain_profile") or {}).get(skill)


def _normalize_question_payload(payload: object, *, skill: str,
                                sub_domain: str | None,
                                difficulty: str | None = None) -> dict:
    if isinstance(payload, str):
        return {
            "question": payload, "ideal_answer": "", "ideal_keywords": "",
            "skill": skill, "sub_domain": sub_domain,
            "difficulty": difficulty, "source": "legacy",
        }
    if isinstance(payload, dict):
        question_text = (payload.get("question") or payload.get("prompt")
                         or payload.get("text") or payload.get("query"))
        if not question_text:
            raise IntegrationError("question_bank returned a payload with no question text.")
        raw_keywords = (
            payload.get("ideal_keywords")
            or payload.get("keywords")
            or payload.get("expected_keywords")
            or ""
        )
        if isinstance(raw_keywords, list):
            ideal_keywords = ", ".join(str(item) for item in raw_keywords if str(item).strip())
            ideal_keywords_list = [str(item) for item in raw_keywords if str(item).strip()]
        else:
            ideal_keywords = str(raw_keywords)
            ideal_keywords_list = [item.strip() for item in ideal_keywords.split(",") if item.strip()]
        return {
            "question": str(question_text),
            "ideal_answer": str(payload.get("ideal_answer")
                                or payload.get("reference_answer")
                                or payload.get("answer") or ""),
            "ideal_keywords": ideal_keywords,
            "ideal_keywords_list": ideal_keywords_list,
            "skill": str(payload.get("skill") or skill),
            "sub_domain": payload.get("sub_domain") or sub_domain,
            "topic": payload.get("topic") or payload.get("sub_domain") or sub_domain,
            "difficulty": str(payload.get("difficulty") or difficulty or ""),
            "question_type": payload.get("question_type") or "conceptual",
            "company": payload.get("company") or "",
            "role": payload.get("role") or "",
            "followups": list(payload.get("followups") or []),
            "source": str(payload.get("source") or "unknown"),
            "llm_provider": payload.get("llm_provider"),
            "llm_model": payload.get("llm_model"),
            # Phase 2 Task 7 — adaptive selector metadata
            "target_concepts": list(payload.get("target_concepts") or []),
            "adaptive_selected": bool(payload.get("adaptive_selected") or False),
        }
    raise IntegrationError("question_bank returned an unsupported question format.")


def _get_next_question(
    *,
    skill: str,
    sub_domain: str | None,
    difficulty: str,
    asked: list[str],
    user_id: str | None = None,
    target_company_id: str | None = None,
    target_role_id: str | None = None,
    target_concepts: list[str] | None = None,
    resume_skills: list[str] | None = None,
    weak_skills: list[str] | None = None,
) -> dict:
    """Return the next question payload.

    When ``user_id`` is provided we route through the Phase 2 adaptive
    selector (``modules.adaptive_question_selector``), which prepends
    targeting hints for the user's weakest concepts in the skill. The
    selector itself falls back to ``question_bank.get_next_question``
    when no target concepts are available or the LLM call fails, so
    anonymous and first-session flows are unaffected.
    """
    if user_id:
        from modules import adaptive_question_selector

        try:
            payload = adaptive_question_selector.select_next_question(
                user_id=user_id,
                skill=skill,
                sub_domain=sub_domain,
                difficulty=difficulty,
                asked=asked,
                target_company_id=target_company_id,
                target_role_id=target_role_id,
                target_concepts=target_concepts,
                resume_skills=resume_skills,
                weak_skills=weak_skills,
            )
        except Exception as exc:
            raise IntegrationError(str(exc)) from exc
        return _normalize_question_payload(
            payload, skill=skill, sub_domain=sub_domain, difficulty=difficulty
        )

    try:
        from modules.question_runtime import MarketQuestionContext, generate_question

        payload = generate_question(
            skill,
            sub_domain,
            difficulty,
            asked,
            market_context=MarketQuestionContext(
                company_id=target_company_id,
                role_id=target_role_id,
                resume_skills=tuple(resume_skills or ()),
                weak_skills=tuple(weak_skills or target_concepts or ()),
            ),
        )
    except Exception as exc:
        raise IntegrationError(str(exc)) from exc
    return _normalize_question_payload(
        payload, skill=skill, sub_domain=sub_domain, difficulty=difficulty
    )


def _module_mcq_pool(*, verbal_only: bool) -> list[dict[str, Any]]:
    """In-memory fallback pool for one category, filtered before use."""
    if verbal_only:
        from backend.db.phase21_verbal_bank import PHASE21_VERBAL_BANK
        return [dict(q) for q in PHASE21_VERBAL_BANK]
    from backend.db.phase2_content_bank import PHASE2_MCQ_BANK
    return [dict(q) for q in PHASE2_MCQ_BANK]


def _filter_mcq_items(
    items: list[dict[str, Any]],
    *,
    skills: list[str] | None = None,
    count: int = 15,
    question_ids: list[str] | None = None,
    difficulty: str | None = None,
    allow_unknown_fallback: bool = False,
) -> list[dict[str, Any]]:
    """Strict topic filtering: never fill from other subjects.

    Raises ValueError with the available count when the request cannot be
    satisfied. Callers convert this to HTTP 422. Legacy launches without
    blocks keep the historical fallback for fully unknown topics (zero
    strict matches): the general pool is used, preserving demo behavior.
    New block requests are always strict.
    """
    skills = canonicalize_verbal_skills(
        [str(s).strip() for s in (skills or []) if str(s).strip()]
    ) or []
    pool = list(items)
    if difficulty:
        wanted_diff = str(difficulty).strip().lower()
        pool = [q for q in pool
                if str(q.get("difficulty", "")).lower() == wanted_diff]
    if question_ids:
        wanted = [str(qid).strip() for qid in question_ids if str(qid).strip()]
        by_id = {str(q.get("id")): q for q in pool}
        missing = [qid for qid in wanted if qid not in by_id]
        if missing:
            raise ValueError(
                f"Unknown question IDs for this category: {missing}."
            )
        selected = [by_id[qid] for qid in wanted]
        if skills:
            mismatched = [q["id"] for q in selected
                          if q.get("skill") not in skills]
            if mismatched:
                raise ValueError(
                    f"Question IDs {mismatched} do not match requested "
                    f"topics {skills}."
                )
        return selected
    if skills:
        strict_pool = [q for q in pool if q.get("skill") in skills]
        if not strict_pool and allow_unknown_fallback:
            # Historical legacy behavior for unknown topics only.
            return pool[:count]
        pool = strict_pool
    if len(pool) < count:
        label = ", ".join(skills) if skills else "MCQ"
        diff_note = f" ({difficulty})" if difficulty else ""
        raise ValueError(
            f"Not enough {label} MCQ questions available{diff_note}: "
            f"found {len(pool)}, need {count}. "
            f"Adjust count or topics."
        )
    return pool[:count]


def _select_mcq_questions(
    skills: list[str] | None = None,
    count: int = 15,
    question_ids: list[str] | None = None,
    difficulty: str | None = None,
    allow_unknown_fallback: bool = False,
) -> list[dict[str, Any]]:
    """Select `count` questions from exactly one category (strict).

    Verbal: zero eligible DB rows use the module fallback; enough DB rows
    are used as-is; a partial seed raises ValueError instead of mixing
    categories, supplementing silently, or shortening the round. Technical
    keeps the base behavior (DB rows when any exist, else module fallback)
    but now enforces exact-topic filtering and available-count errors.
    """
    skills = canonicalize_verbal_skills(
        [str(s).strip() for s in (skills or []) if str(s).strip()]
    ) or []
    verbal_only = bool(skills) and skills == [VERBAL_SKILL]

    db_pool: list[dict[str, Any]] = []
    try:
        from backend.config import get_settings
        if get_settings().database_url:
            from backend.db.sqlalchemy_store import session_scope
            from backend.db.sqlalchemy_models import MCQQuestionRow, SkillRow
            from sqlalchemy import select
            with session_scope() as session:
                stmt = select(MCQQuestionRow, SkillRow.canonical_name).join(
                    SkillRow, MCQQuestionRow.skill_id == SkillRow.id
                )
                rows = session.execute(stmt).all()
                for q_row, skill_name in rows:
                    if (skill_name == VERBAL_SKILL) != verbal_only:
                        continue
                    db_pool.append({
                        "id": q_row.id,
                        "skill": skill_name,
                        "sub_domain": q_row.sub_domain,
                        "difficulty": q_row.difficulty,
                        "stem": q_row.stem,
                        "options_json": q_row.options_json,
                        "correct_option_ids": q_row.correct_option_ids,
                        "explanation": q_row.explanation,
                        "negative_marking": float(q_row.negative_marking),
                    })
    except ValueError:
        raise
    except Exception:
        db_pool = []

    if verbal_only:
        if question_ids:
            # Explicit IDs: check DB first, then module fallback for missing.
            module_pool = _module_mcq_pool(verbal_only=True)
            combined = {q["id"]: q for q in module_pool}
            for q in db_pool:
                combined[q["id"]] = q
            return _filter_mcq_items(
                list(combined.values()),
                skills=skills,
                count=count,
                question_ids=question_ids,
                difficulty=difficulty,
            )
        if not db_pool:
            pool = _module_mcq_pool(verbal_only=True)
        elif len(db_pool) >= count:
            pool = db_pool
        else:
            # Partial seed: do not supplement or shorten.
            raise ValueError(
                f"Not enough {VERBAL_SKILL} MCQ questions available: "
                f"found {len(db_pool)}, need {count}."
            )
        return _filter_mcq_items(
            pool, skills=skills, count=count, difficulty=difficulty,
        )

    pool = db_pool if db_pool else _module_mcq_pool(verbal_only=False)
    return _filter_mcq_items(
        pool,
        skills=skills,
        count=count,
        question_ids=question_ids,
        difficulty=difficulty,
        allow_unknown_fallback=allow_unknown_fallback,
    )


def build_round_document(
    *,
    round_number: int,
    round_type: str,
    skills: list[str],
    elo_before: float,
    difficulty: str,
    sub_domain: str | None,
    round_config: dict[str, Any] | None,
    user_id: str | None = None,
    target_company_id: str | None = None,
    target_role_id: str | None = None,
    resume_skills: list[str] | None = None,
    asked: list[str] | None = None,
    sql_problem_index: int = 0,
    block_id: str | None = None,
    block_position: int | None = None,
    block_category: str | None = None,
    block_index: int | None = None,
    block_total: int | None = None,
    allow_unknown_fallback: bool = False,
) -> RoundDocument:
    """Build a RoundDocument for technical / MCQ / SQL (shared by start + answer).

    Activation policy: a round activates when built (first round at session
    start, later rounds when the prior round is submitted). Timed rounds get
    ``expires_at = started_at + duration``; refresh never extends it.
    Raises ValueError (→ HTTP 422) for unsatisfiable content filters.
    """
    now = datetime.now(timezone.utc)
    cfg = dict(round_config or {})
    skill = skills[0] if skills else "DBMS"

    if round_type == "mcq":
        count = int(cfg.get("count", 15))
        duration_mins = int(cfg.get("duration_minutes", 20))
        neg_mark = float(cfg.get("negative_marking", 0.25))
        question_ids = cfg.get("question_ids")
        if question_ids is not None:
            question_ids = [str(x) for x in question_ids]
        assigned = _select_mcq_questions(
            skills=skills,
            count=count,
            question_ids=question_ids,
            difficulty=cfg.get("difficulty"),
            allow_unknown_fallback=allow_unknown_fallback,
        )
        expires_at = now + timedelta(minutes=duration_mins)
        return RoundDocument(
            round=round_number,
            round_type="mcq",
            question="Multiple Choice Assessment",
            difficulty=difficulty,
            elo_before=elo_before,
            config_json={
                "count": len(assigned),
                "duration_minutes": duration_mins,
                "negative_marking": neg_mark,
                "attempt_policy": "single_submission_final",
                "review_policy": cfg.get("review_policy", "none"),
            },
            question_context={"questions": assigned},
            started_at=now,
            expires_at=expires_at,
            status="in_progress",
            block_id=block_id,
            block_position=block_position,
            block_category=block_category,
            block_index=block_index,
            block_total=block_total,
        )

    if round_type == "sql":
        duration_mins = int(cfg.get("duration_minutes", 25))
        problem_ids = cfg.get("problem_ids") or []
        problem_id = cfg.get("problem_id")
        if problem_ids and sql_problem_index < len(problem_ids):
            problem_id = problem_ids[sql_problem_index]
        problem = _select_sql_problem(problem_id=problem_id)
        expires_at = now + timedelta(minutes=duration_mins)
        return RoundDocument(
            round=round_number,
            round_type="sql",
            question=problem["prompt"],
            difficulty=problem.get("difficulty", difficulty),
            elo_before=elo_before,
            config_json={
                "duration_minutes": duration_mins,
                "attempt_policy": "single_submission_final",
                "review_policy": cfg.get("review_policy", "none"),
                "max_rows": int(cfg.get("max_rows", 1000)),
                "timeout_seconds": float(cfg.get("timeout_seconds", 2.0)),
                "problem_id": problem.get("id"),
            },
            question_context=problem,
            started_at=now,
            expires_at=expires_at,
            status="in_progress",
            block_id=block_id,
            block_position=block_position,
            block_category=block_category,
            block_index=block_index,
            block_total=block_total,
        )

    if round_type == "coding":
        duration_mins = int(cfg.get("duration_minutes", 30))
        problem_ids = cfg.get("problem_ids") or []
        problem_id = cfg.get("problem_id")
        if problem_ids and sql_problem_index < len(problem_ids):
            problem_id = problem_ids[sql_problem_index]
        problem = _select_coding_problem(problem_id=problem_id)
        expires_at = now + timedelta(minutes=duration_mins)
        return RoundDocument(
            round=round_number,
            round_type="coding",
            question=str(problem.get("title") or problem.get("id")),
            difficulty=str(problem.get("difficulty") or difficulty),
            elo_before=elo_before,
            config_json={
                "duration_minutes": duration_mins,
                "attempt_policy": "single_submission_final",
                "review_policy": cfg.get("review_policy", "none"),
                "problem_id": problem.get("id"),
                "language": "python",
            },
            question_context=coding_problem_public_context(problem),
            started_at=now,
            expires_at=expires_at,
            status="in_progress",
            block_id=block_id,
            block_position=block_position,
            block_category=block_category,
            block_index=block_index,
            block_total=block_total,
        )

    if round_type == "system_design":
        duration_mins = int(cfg.get("duration_minutes", 25))
        prompt_ids = cfg.get("problem_ids") or []
        prompt_id = cfg.get("problem_id")
        if prompt_ids and sql_problem_index < len(prompt_ids):
            prompt_id = prompt_ids[sql_problem_index]
        prompt = _select_system_design_prompt(prompt_id=prompt_id)
        expires_at = now + timedelta(minutes=duration_mins)
        public = public_system_design_prompt_context(prompt)
        return RoundDocument(
            round=round_number,
            round_type="system_design",
            question=str(prompt.get("title") or prompt.get("id")),
            difficulty=str(prompt.get("difficulty") or difficulty),
            elo_before=elo_before,
            config_json={
                "duration_minutes": duration_mins,
                "attempt_policy": "single_submission_final",
                "review_policy": cfg.get("review_policy", "none"),
                "problem_id": prompt.get("id"),
                "evaluation_mode": "structured_self_assessment",
            },
            question_context=public,
            started_at=now,
            expires_at=expires_at,
            status="in_progress",
            block_id=block_id,
            block_position=block_position,
            block_category=block_category or "system_design",
            block_index=block_index,
            block_total=block_total,
        )

    # technical_short_answer
    first_question = _get_next_question(
        skill=skill,
        sub_domain=sub_domain,
        difficulty=difficulty,
        asked=list(asked or []),
        user_id=user_id,
        target_company_id=target_company_id,
        target_role_id=target_role_id,
        resume_skills=resume_skills or skills,
    )
    duration_value = cfg.get("duration_minutes")
    expires_at = None
    if duration_value is not None:
        try:
            duration_mins = int(duration_value)
        except (TypeError, ValueError):
            duration_mins = 0
        if duration_mins > 0:
            expires_at = now + timedelta(minutes=duration_mins)
    return RoundDocument(
        round=round_number,
        round_type="technical_short_answer",
        question=first_question["question"],
        difficulty=difficulty,
        elo_before=elo_before,
        question_context=first_question,
        started_at=now,
        expires_at=expires_at,
        status="in_progress",
        block_id=block_id,
        block_position=block_position,
        block_category=block_category,
        block_index=block_index,
        block_total=block_total,
    )


def list_practice_bank_items() -> dict[str, Any]:
    """Candidate-safe catalog: OA MCQs, Verbal MCQs, SQL and coding problems.

    Exposes stems, SQL prompts/schemas, coding statements/starters and
    safe metadata only. Never exposes correct option IDs, explanations,
    reference queries/solutions, checks or hidden cases.
    """
    from backend.db.phase2_content_bank import PHASE2_MCQ_BANK, PHASE2_SQL_BANK
    from backend.db.phase21_verbal_bank import PHASE21_VERBAL_BANK
    from backend.db.phase_c_coding_bank import (
        CODING_PROBLEMS,
        public_coding_problem,
    )

    mcq = [
        {
            "id": q["id"],
            "type": "mcq",
            "category": "oa",
            "skill": q.get("skill"),
            "sub_domain": q.get("sub_domain"),
            "difficulty": q.get("difficulty"),
            "stem": q.get("stem"),
        }
        for q in PHASE2_MCQ_BANK
    ]
    verbal = [
        {
            "id": q["id"],
            "type": "mcq",
            "category": "verbal",
            "skill": q.get("skill"),
            "sub_domain": q.get("sub_domain"),
            "difficulty": q.get("difficulty"),
            "stem": q.get("stem"),
        }
        for q in PHASE21_VERBAL_BANK
    ]
    sql = []
    for p in PHASE2_SQL_BANK:
        prompt = str(p.get("prompt") or "")
        title = prompt.split("\n", 1)[0].lstrip("# ").strip() or p["id"]
        sql.append(
            {
                "id": p["id"],
                "type": "sql",
                "category": "sql",
                "skill": "SQL",
                "difficulty": p.get("difficulty"),
                "title": title,
                "prompt": prompt,
                "schema_ddl": p.get("schema_ddl") or "",
            }
        )
    coding = [public_coding_problem(p) for p in CODING_PROBLEMS]
    from backend.db.phase_e_system_design_bank import (
        SYSTEM_DESIGN_PROMPTS,
        public_system_design_prompt,
    )

    system_design = [public_system_design_prompt(p) for p in SYSTEM_DESIGN_PROMPTS]
    return {
        "mcq": mcq,
        "verbal": verbal,
        "sql": sql,
        "coding": coding,
        "system_design": system_design,
        "counts": {
            "mcq": len(mcq),
            "verbal": len(verbal),
            "sql": len(sql),
            "coding": len(coding),
            "system_design": len(system_design),
        },
    }


def _list_sql_problems(*, difficulty: str | None = None) -> list[dict[str, Any]]:
    """All SQL problems in deterministic order (for auto-select).

    The legacy default problem comes first, preserving single-problem
    auto-select behavior; the verified bank fills the remainder.
    """
    from backend.db.phase2_content_bank import PHASE2_SQL_BANK
    from backend.db.phase2a_fixtures import PHASE2A_SQL_FIXTURES
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    default_first = [p for p in PHASE2A_SQL_FIXTURES
                     if p.get("id") == "sql_hr_high_earners"]
    for source in (default_first, PHASE2_SQL_BANK):
        for problem in source:
            pid = str(problem.get("id"))
            if pid and pid not in seen:
                seen.add(pid)
                items.append(dict(problem))
    if difficulty:
        wanted = str(difficulty).strip().lower()
        items = [p for p in items
                 if str(p.get("difficulty", "")).lower() == wanted]
    return items


def _select_sql_problems(
    *,
    problem_ids: list[str] | None = None,
    count: int = 1,
    difficulty: str | None = None,
) -> list[dict[str, Any]]:
    """Validate explicit SQL IDs or auto-select `count` deterministically."""
    if problem_ids:
        wanted = [str(p).strip() for p in problem_ids if str(p).strip()]
        selected = [_select_sql_problem(problem_id=pid) for pid in wanted]
        if difficulty:
            mismatched = [p["id"] for p in selected
                          if str(p.get("difficulty", "")).lower()
                          != str(difficulty).strip().lower()]
            if mismatched:
                raise ValueError(
                    f"SQL problems {mismatched} do not match difficulty "
                    f"'{difficulty}'."
                )
        return selected
    pool = _list_sql_problems(difficulty=difficulty)
    if len(pool) < count:
        diff_note = f" ({difficulty})" if difficulty else ""
        raise ValueError(
            f"Not enough SQL problems available{diff_note}: "
            f"found {len(pool)}, need {count}. Adjust count or difficulty."
        )
    return pool[:count]


def _select_sql_problem(problem_id: str | None = None) -> dict[str, Any]:
    from backend.db.phase2_content_bank import PHASE2_SQL_BANK
    from backend.db.phase2a_fixtures import PHASE2A_SQL_FIXTURES
    target_id = (problem_id or "").strip() or "sql_hr_high_earners"
    explicit = bool((problem_id or "").strip())
    try:
        from backend.config import get_settings
        if get_settings().database_url:
            from backend.db.sqlalchemy_store import session_scope
            from backend.db.sqlalchemy_models import SQLProblemRow
            from sqlalchemy import select
            with session_scope() as session:
                stmt = select(SQLProblemRow).where(SQLProblemRow.id == target_id)
                p_row = session.execute(stmt).scalars().first()
                if p_row:
                    cases = [
                        {
                            "case_type": c.case_type,
                            "seed_data": c.seed_data,
                            "description": c.description,
                            "sort_order": c.sort_order,
                        }
                        for c in p_row.cases
                    ]
                    return {
                        "id": p_row.id,
                        "difficulty": p_row.difficulty,
                        "prompt": p_row.prompt,
                        "schema_ddl": p_row.schema_ddl,
                        "reference_query": p_row.reference_query,
                        "checks_json": p_row.checks_json,
                        "cases": cases,
                    }
    except Exception:
        pass

    for p in PHASE2_SQL_BANK:
        if p["id"] == target_id:
            return dict(p)
    for p in PHASE2A_SQL_FIXTURES:
        if p["id"] == target_id:
            return dict(p)
    if explicit:
        raise ValueError(f"Unknown SQL problem ID: '{target_id}'.")
    return dict(PHASE2A_SQL_FIXTURES[0])


def _list_coding_problems(
    *,
    topics: list[str] | None = None,
    difficulty: str | None = None,
) -> list[dict[str, Any]]:
    """Coding bank in stable order, filtered by exact topics/difficulty."""
    from backend.db.phase_c_coding_bank import CODING_PROBLEMS
    items = [dict(p) for p in CODING_PROBLEMS]
    if difficulty:
        wanted_diff = str(difficulty).strip().lower()
        items = [p for p in items
                 if str(p.get("difficulty", "")).lower() == wanted_diff]
    if topics:
        wanted = {str(t).strip().lower() for t in topics if str(t).strip()}
        items = [p for p in items
                 if wanted & {str(t).lower()
                              for t in (p.get("topics") or [])}]
    return items


def _select_coding_problem(problem_id: str | None = None) -> dict[str, Any]:
    """One coding problem by id (strict) or the deterministic default."""
    from backend.db.phase_c_coding_bank import (
        CODING_PROBLEMS,
        get_coding_problem,
    )
    target = (problem_id or "").strip()
    if target:
        problem = get_coding_problem(target)
        if problem is None:
            raise ValueError(f"Unknown coding problem ID: '{target}'.")
        return dict(problem)
    return dict(CODING_PROBLEMS[0])


def _select_coding_problems(
    *,
    problem_ids: list[str] | None = None,
    count: int = 1,
    topics: list[str] | None = None,
    difficulty: str | None = None,
) -> list[dict[str, Any]]:
    """Validate explicit coding IDs or auto-select `count` deterministically."""
    topics = [str(t).strip() for t in (topics or []) if str(t).strip()]
    if problem_ids:
        wanted = [str(p).strip() for p in problem_ids if str(p).strip()]
        selected = [_select_coding_problem(problem_id=pid) for pid in wanted]
        if topics:
            wanted_topics = {t.lower() for t in topics}
            mismatched = [p["id"] for p in selected
                          if not (wanted_topics & {str(t).lower()
                                                   for t in (p.get("topics") or [])})]
            if mismatched:
                raise ValueError(
                    f"Coding problems {mismatched} do not match topics "
                    f"{topics}."
                )
        if difficulty:
            mismatched_diff = [p["id"] for p in selected
                               if str(p.get("difficulty", "")).lower()
                               != str(difficulty).strip().lower()]
            if mismatched_diff:
                raise ValueError(
                    f"Coding problems {mismatched_diff} do not match "
                    f"difficulty '{difficulty}'."
                )
        return selected
    pool = _list_coding_problems(topics=topics or None, difficulty=difficulty)
    if len(pool) < count:
        label = ", ".join(topics) if topics else "coding"
        diff_note = f" ({difficulty})" if difficulty else ""
        raise ValueError(
            f"Not enough {label} coding problems available{diff_note}: "
            f"found {len(pool)}, need {count}. Adjust count or topics."
        )
    return pool[:count]


def coding_problem_public_context(problem: dict[str, Any]) -> dict[str, Any]:
    """Candidate-safe coding context: never hidden tests or solutions."""
    return {
        "problem_id": problem.get("id"),
        "title": problem.get("title"),
        "difficulty": problem.get("difficulty"),
        "topics": list(problem.get("topics") or []),
        "statement": problem.get("statement") or "",
        "constraints": list(problem.get("constraints") or []),
        "function": problem.get("function") or "",
        "starter_code": problem.get("starter_code") or "",
        "visible_tests": [
            {"input": dict(t.get("input") or {}),
             "expected": t.get("expected")}
            for t in (problem.get("visible_tests") or [])
        ],
        "language": "python",
    }


def _list_system_design_prompts(
    *,
    difficulty: str | None = None,
) -> list[dict[str, Any]]:
    from backend.db.phase_e_system_design_bank import list_system_design_prompts

    return list_system_design_prompts(difficulty=difficulty)


def _select_system_design_prompt(prompt_id: str | None = None) -> dict[str, Any]:
    from backend.db.phase_e_system_design_bank import (
        SYSTEM_DESIGN_PROMPTS,
        get_system_design_prompt,
    )

    target = (prompt_id or "").strip()
    if target:
        prompt = get_system_design_prompt(target)
        if not prompt:
            raise ValueError(f"Unknown system-design prompt ID: '{target}'.")
        return prompt
    return SYSTEM_DESIGN_PROMPTS[0]


def _select_system_design_prompts(
    *,
    count: int | None = None,
    prompt_ids: list[str] | None = None,
    difficulty: str | None = None,
) -> list[dict[str, Any]]:
    if prompt_ids:
        return [_select_system_design_prompt(prompt_id=pid) for pid in prompt_ids]
    wanted = int(count or 1)
    pool = _list_system_design_prompts(difficulty=difficulty)
    if len(pool) < wanted:
        diff_note = f" at difficulty '{difficulty}'" if difficulty else ""
        raise ValueError(
            f"Not enough system-design prompts available{diff_note}: "
            f"need {wanted}, have {len(pool)}."
        )
    return pool[:wanted]


def public_system_design_prompt_context(prompt: dict[str, Any]) -> dict[str, Any]:
    from backend.db.phase_e_system_design_bank import public_system_design_prompt

    return public_system_design_prompt(prompt)


def _validate_block_content(
    block_plan: list[dict[str, Any]],
    expanded: list[dict[str, Any]],
    allow_unknown_fallback: bool = False,
) -> None:
    """Check every block's content limits upfront (no writes).

    Fills auto-selected SQL problem IDs into the expanded plan so later
    rounds use the same stable assignment. Raises ValueError with the
    available count when a block cannot be satisfied.
    """
    by_block: dict[str, list[dict[str, Any]]] = {}
    for spec in expanded:
        by_block.setdefault(str(spec.get("block_id")), []).append(spec)
    for block in block_plan:
        category = block.get("category")
        if category in ("oa", "verbal"):
            _select_mcq_questions(
                skills=list(block.get("skills") or []),
                count=int(block.get("count") or 15),
                question_ids=list(block.get("question_ids") or []) or None,
                difficulty=block.get("difficulty"),
                allow_unknown_fallback=allow_unknown_fallback,
            )
        elif category == "sql":
            problem_ids = list(block.get("problem_ids") or [])
            if problem_ids:
                _select_sql_problems(
                    problem_ids=problem_ids,
                    difficulty=block.get("difficulty"),
                )
            else:
                count = int(block.get("count") or 1)
                selected = _select_sql_problems(
                    count=count,
                    difficulty=block.get("difficulty"),
                )
                specs = by_block.get(str(block.get("id")), [])
                for spec, problem in zip(specs, selected):
                    spec["problem_ids"] = [problem["id"]]
                block["problem_ids"] = [p["id"] for p in selected]
        elif category == "coding":
            problem_ids = list(block.get("problem_ids") or [])
            # "DSA" / "coding" are skill-category labels on coding blocks, not
            # bank topic tags (arrays, strings, …). Filtering by them yields
            # found 0 and silently breaks Standalone Coding / builder starts.
            _coding_skill_labels = {"dsa", "coding"}
            topics = [
                str(t).strip()
                for t in (block.get("skills") or [])
                if str(t).strip()
                and str(t).strip().lower() not in _coding_skill_labels
            ]
            if problem_ids:
                _select_coding_problems(
                    problem_ids=problem_ids,
                    topics=topics or None,
                    difficulty=block.get("difficulty"),
                )
            else:
                count = int(block.get("count") or 1)
                selected = _select_coding_problems(
                    count=count,
                    topics=topics or None,
                    difficulty=block.get("difficulty"),
                )
                specs = by_block.get(str(block.get("id")), [])
                for spec, problem in zip(specs, selected):
                    spec["problem_ids"] = [problem["id"]]
                block["problem_ids"] = [p["id"] for p in selected]
        elif category == "system_design":
            prompt_ids = list(block.get("problem_ids") or [])
            if prompt_ids:
                _select_system_design_prompts(prompt_ids=prompt_ids)
            else:
                count = int(block.get("count") or 1)
                selected = _select_system_design_prompts(
                    count=count,
                    difficulty=block.get("difficulty"),
                )
                specs = by_block.get(str(block.get("id")), [])
                for spec, prompt in zip(specs, selected):
                    spec["problem_ids"] = [prompt["id"]]
                block["problem_ids"] = [p["id"] for p in selected]


# ─────────────────────────────────────────────────────────────────────────────
# POST /session/start
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/start")
def start_session(
    request: StartSessionRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    settings = get_settings()
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=str(exc)) from exc

    # ── Normalize legacy and builder payloads into one block plan ──────────
    if request.blocks is not None:
        try:
            block_plan = normalize_blocks(request.blocks)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
    else:
        legacy_skills = canonicalize_verbal_skills(list(request.skills)) or []
        # Preserve valid legacy standalone Verbal requests; composition
        # with other skills requires the new blocks flow.
        if VERBAL_SKILL in legacy_skills:
            legacy_plan = list(request.round_plan) if request.round_plan else None
            is_standalone = (
                legacy_skills == [VERBAL_SKILL]
                and request.round_type == "mcq"
                and request.rounds_per_skill == 1
                and (legacy_plan is None or legacy_plan == ["mcq"])
            )
            if not is_standalone:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "Verbal Ability practice cannot be combined with other "
                        "skills via legacy fields; use blocks for composition."
                    ),
                )
        try:
            block_plan = legacy_to_blocks(
                skills=list(request.skills),
                rounds_per_skill=request.rounds_per_skill,
                round_type=request.round_type,
                round_config=request.round_config,
                round_plan=list(request.round_plan) if request.round_plan else None,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
    expanded = expand_blocks(block_plan)
    plan = [spec["round_type"] for spec in expanded]
    opening_type = plan[0] if plan else "technical_short_answer"
    opening_spec = expanded[0]
    # Legacy launches keep the unknown-topic fallback; blocks are strict.
    allow_unknown_fallback = request.blocks is None

    # Validate all blocks' content before any writes: no session, no silent
    # reductions, no mid-run failures after retries.
    try:
        _validate_block_content(block_plan, expanded,
                                allow_unknown_fallback=allow_unknown_fallback)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Union of block skills in first-seen order (for Elo seeding/history).
    session_skills: list[str] = []
    for block in block_plan:
        for skill in block.get("skills") or []:
            if skill not in session_skills:
                session_skills.append(skill)

    candidate_id = (request.candidate_id or "").strip()
    candidate = db["candidates"].find_one({"candidate_id": candidate_id}) if candidate_id else None
    user = get_user_from_authorization(authorization) if authorization else None

    needs_phase2_auth = any(
        t in ("mcq", "sql", "coding", "system_design") for t in plan
    )
    if needs_phase2_auth:
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication is required for this session.",
            )
        user = require_user(authorization)
        if candidate_id:
            if not candidate or str(candidate.get("user_id")) != str(user["id"]):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You cannot start a session for another user's candidate.",
                )
        else:
            existing_candidate = db["candidates"].find_one({"user_id": user["id"]})
            if existing_candidate:
                candidate = existing_candidate
                candidate_id = str(existing_candidate["candidate_id"])
    else:
        if candidate and candidate.get("user_id"):
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication is required for this candidate.",
                )
            if str(candidate["user_id"]) != str(user["id"]):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You cannot start a session for another user's candidate.",
                )
    target_company_id = (
        str(user.get("target_company_id")) if user and user.get("target_company_id") else request.target_company_id
    )
    target_role_id = (
        str(user.get("target_role_id")) if user and user.get("target_role_id") else request.target_role_id
    )
    if not candidate:
        # Allow quick-start demo sessions without a resume upload. Resume uploads
        # still create richer candidate documents through /resume.
        candidate_id = candidate_id or str(uuid4())
        candidate_doc = CandidateDocument(
            candidate_id=candidate_id,
            resume_skills=session_skills,
            sub_domain_profile={
                skill: request.sub_domain or "general" for skill in session_skills
            },
            elo_ratings={skill: settings.initial_elo for skill in session_skills},
            session_history=[],
        )
        candidate = candidate_doc.to_mongo()
        if user:
            candidate["user_id"] = user["id"]
        try:
            db["candidates"].insert_one(candidate)
        except DatabaseConnectionError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail=str(exc)) from exc
        except Exception as exc:
            if is_database_exception(exc):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"MongoDB operation failed: {exc}",
                ) from exc
            raise

    # ── first-round skill ───────────────────────────────────────────────────
    first_skill = (opening_spec.get("skills") or session_skills or ["System Design"])[0]
    elo_before = float(candidate.get("elo_ratings", {}).get(first_skill, settings.initial_elo))
    difficulty = (opening_spec.get("difficulty")
                  or _elo_to_difficulty(elo_before))
    sub_domain = _sub_domain_for_skill(candidate, first_skill, request.sub_domain)
    opening_config: dict[str, Any] = {
        "count": opening_spec.get("count", 15),
        "duration_minutes": opening_spec.get("duration_minutes"),
        "negative_marking": opening_spec.get("negative_marking", 0.25),
        "review_policy": opening_spec.get("review_policy", "none"),
        "difficulty": opening_spec.get("difficulty"),
        "question_ids": opening_spec.get("question_ids") or None,
        "problem_ids": opening_spec.get("problem_ids") or None,
        "problem_id": (opening_spec.get("problem_ids") or [None])[0],
    }
    # Preserve legacy timeout/row knobs when the legacy payload set them.
    legacy_cfg = dict(request.round_config or {})
    for key in ("max_rows", "timeout_seconds"):
        if key in legacy_cfg:
            opening_config[key] = legacy_cfg[key]
    if opening_config.get("duration_minutes") is None:
        opening_config.pop("duration_minutes", None)

    try:
        round_document = build_round_document(
            round_number=1,
            round_type=opening_type,
            skills=list(opening_spec.get("skills") or session_skills),
            elo_before=elo_before,
            difficulty=difficulty,
            sub_domain=sub_domain,
            round_config=opening_config,
            user_id=str(user["id"]) if user else None,
            target_company_id=target_company_id,
            target_role_id=target_role_id,
            resume_skills=candidate.get("resume_skills") or session_skills,
            asked=[],
            sql_problem_index=0,
            block_id=opening_spec.get("block_id"),
            block_position=opening_spec.get("block_position"),
            block_category=opening_spec.get("category"),
            block_index=opening_spec.get("block_index"),
            block_total=opening_spec.get("block_total"),
            allow_unknown_fallback=allow_unknown_fallback,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except IntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=str(exc)) from exc

    session_id = str(uuid4())
    total_rounds = len(expanded)

    session = SessionDocument(
        session_id=session_id,
        candidate_id=candidate_id,
        skill=first_skill,                         # legacy field — first skill
        sub_domain=sub_domain,
        rounds=[round_document],
        current_difficulty=difficulty,
        last_round=1,
    )

    session_dict = session.to_mongo()
    # attach multi-skill fields that SessionDocument doesn't know about
    session_dict["skills"] = session_skills
    session_dict["rounds_per_skill"] = request.rounds_per_skill
    session_dict["total_rounds"] = total_rounds
    session_dict["current_skill"] = first_skill
    session_dict["user_id"] = user["id"] if user else candidate.get("user_id")
    session_dict["target_company_id"] = target_company_id
    session_dict["target_role_id"] = target_role_id
    session_dict["round_config"] = request.round_config or {}
    session_dict["round_plan"] = plan
    session_dict["block_plan"] = block_plan
    session_dict["expanded_plan"] = expanded
    session_dict["allow_unknown_topic_fallback"] = allow_unknown_fallback

    try:
        db["sessions"].insert_one(session_dict)
        candidate_update = {
            "$addToSet": {
                "session_history": session_id,
                "resume_skills": {"$each": session_skills},
            },
            "$set": {},
        }
        # seed Elo for any skill the candidate hasn't been rated on
        for s in session_skills:
            existing_elo = candidate.get("elo_ratings", {}).get(s)
            if existing_elo is None:
                candidate_update["$set"][f"elo_ratings.{s}"] = settings.initial_elo
        if sub_domain:
            candidate_update["$set"][f"sub_domain_profile.{first_skill}"] = sub_domain
        if user:
            candidate_update["$set"]["user_id"] = user["id"]
        db["candidates"].update_one({"candidate_id": candidate_id}, candidate_update)
        if user:
            StudentSkillGraph(user["id"]).initialize_from_resume(session_skills)
    except DatabaseConnectionError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=str(exc)) from exc
    except Exception as exc:
        if is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"MongoDB operation failed: {exc}",
            ) from exc
        raise

    response = {
        "session_id": session_id,
        "candidate_id": candidate_id,
        "user_id": user["id"] if user else candidate.get("user_id"),
        "question": round_document.question,
        "difficulty": difficulty,
        "round_type": round_document.round_type,
        "round": 1,
        "elo": elo_before,
        "total_rounds": total_rounds,
        "current_skill": first_skill,
        "skills": session_skills,
        "rounds_per_skill": request.rounds_per_skill,
        "round_plan": plan,
        "block_plan": block_plan,
        "block_id": round_document.block_id,
        "block_position": round_document.block_position,
        "block_category": round_document.block_category,
        "started_at": round_document.started_at.isoformat() if round_document.started_at else None,
        "expires_at": round_document.expires_at.isoformat() if round_document.expires_at else None,
        "config_json": round_document.config_json,
    }
    if round_document.round_type == "mcq":
        sanitized = sanitize_round_for_client(round_document.model_dump())
        response["question_context"] = sanitized["question_context"]
        response["questions"] = sanitized["question_context"]["questions"]
    elif round_document.round_type == "sql":
        sanitized = sanitize_round_for_client(round_document.model_dump())
        response["question_context"] = sanitized["question_context"]
        response["schema_ddl"] = sanitized["question_context"].get("schema_ddl")
        response["sample_cases"] = sanitized["question_context"].get("sample_cases", [])
    elif round_document.round_type == "coding":
        sanitized = sanitize_round_for_client(round_document.model_dump())
        response["question_context"] = sanitized["question_context"]
        response["starter_code"] = sanitized["question_context"].get("starter_code")
    elif round_document.round_type == "system_design":
        sanitized = sanitize_round_for_client(round_document.model_dump())
        response["question_context"] = sanitized["question_context"]
    return response


# ─────────────────────────────────────────────────────────────────────────────
# GET /session/practice-bank (MCQ + SQL catalog for Problem practice)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/practice-bank")
def get_practice_bank(
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    require_user(authorization)
    return list_practice_bank_items()


# ─────────────────────────────────────────────────────────────────────────────
# GET /session/{session_id} (resume / refresh)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{session_id}")
def get_session(
    session_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    session = db["sessions"].find_one({"session_id": session_id})
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
        )

    rounds = session.get("rounds", [])
    has_phase2_round = any(
        r.get("round_type") in ("mcq", "sql", "coding", "system_design")
        for r in rounds
    )
    if has_phase2_round or session.get("user_id"):
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication is required for this session.",
            )
        user = require_user(authorization)
        if session.get("user_id"):
            if str(session["user_id"]) != str(user["id"]):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You cannot access another user's session.",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Anonymous sessions are not permitted for this round type.",
            )

    active_round = next(
        (r for r in reversed(rounds) if r.get("status") == "in_progress"),
        rounds[-1] if rounds else None,
    )
    is_completed = session.get("status") == "completed"

    sanitized_active_round = (
        sanitize_round_for_client(active_round, is_session_completed=is_completed)
        if active_round
        else None
    )

    return {
        "session_id": session["session_id"],
        "candidate_id": session.get("candidate_id"),
        "user_id": session.get("user_id"),
        "status": session.get("status", "active"),
        "current_skill": session.get("current_skill", session.get("skill")),
        "current_difficulty": session.get("current_difficulty"),
        "last_round": session.get("last_round", 1),
        "total_rounds": session.get("total_rounds", len(rounds)),
        "skills": session.get("skills") or [session.get("skill") or "General"],
        "round_plan": session.get("round_plan"),
        "block_plan": session.get("block_plan"),
        "active_round": sanitized_active_round,
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /session/sql/run (interactive preview runner against visible sample)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/sql/run")
def run_sql_preview(
    request: RunSQLPreviewRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    session = db["sessions"].find_one({"session_id": request.session_id})
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
        )

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required for this session.",
        )
    user = require_user(authorization)
    if session.get("user_id"):
        if str(session["user_id"]) != str(user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot access another user's session.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Anonymous sessions are not permitted for this round type.",
        )

    rounds = session.get("rounds", [])
    target_round = next(
        (r for r in rounds if r.get("round") == request.round), None
    )
    if not target_round:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target round not found in session.",
        )

    if target_round.get("round_type") != "sql":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target round is not an SQL assessment round.",
        )

    # Non-mutating run against visible sample case ONLY
    q_ctx = target_round.get("question_context") or {}
    schema_ddl = q_ctx.get("schema_ddl") or ""
    cases = q_ctx.get("cases") or []
    sample_case = next((c for c in cases if c.get("case_type") in ("sample", "visible_sample", "visible")), cases[0] if cases else None)

    if not sample_case:
        return {
            "columns": [],
            "rows": [],
            "truncated": False,
            "execution_time_ms": 0.0,
            "error": "No visible sample case configured for this problem.",
        }

    import sqlite3
    from modules.scoring.sql_security import (
        SQLSecurityError,
        SQLSingleStatementError,
        SQLTimeoutError,
        execute_sandboxed_sql,
    )

    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(schema_ddl)
        if sample_case.get("seed_data"):
            conn.executescript(sample_case["seed_data"])

        columns, rows, truncated, elapsed_ms = execute_sandboxed_sql(
            conn=conn,
            query=request.query,
            timeout_seconds=2.0,
            max_rows=1000,
        )
        return {
            "success": True,
            "columns": columns,
            "rows": [list(r) for r in rows],
            "row_count": len(rows),
            "truncated": truncated,
            "execution_time_ms": elapsed_ms,
            "error": None,
        }
    except (SQLSecurityError, SQLTimeoutError, SQLSingleStatementError, sqlite3.DatabaseError) as exc:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "execution_time_ms": 0.0,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "execution_time_ms": 0.0,
            "error": f"Execution error: {exc}",
        }
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# POST /session/coding/run (visible-examples check; never final scoring)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/coding/run")
def run_coding_preview(
    request: RunCodingPreviewRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    session = db["sessions"].find_one({"session_id": request.session_id})
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
        )

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required for this session.",
        )
    user = require_user(authorization)
    if session.get("user_id"):
        if str(session["user_id"]) != str(user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot access another user's session.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Anonymous sessions are not permitted for this round type.",
        )

    rounds = session.get("rounds", [])
    target_round = next(
        (r for r in rounds if r.get("round") == request.round), None
    )
    if not target_round:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target round not found in session.",
        )
    if target_round.get("round_type") != "coding":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target round is not a coding round.",
        )
    if target_round.get("status") != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This round is no longer active.",
        )
    expires_at = target_round.get("expires_at")
    if expires_at is not None:
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at)
            except Exception:
                expires_at = None
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and datetime.now(timezone.utc) > expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Answer deadline has expired.",
            )

    # Non-mutating run against visible examples ONLY. Hidden tests are
    # never loaded here and no score is recorded.
    q_ctx = target_round.get("question_context") or {}
    problem_id = str(q_ctx.get("problem_id") or "")
    from backend.db.phase_c_coding_bank import get_coding_problem
    problem = get_coding_problem(problem_id) if problem_id else None
    if problem is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown coding problem: {problem_id!r}.",
        )
    try:
        result = execute_python_tests(
            source=request.source or "",
            function=str(problem.get("function") or ""),
            visible_tests=list(problem.get("visible_tests") or []),
            hidden_tests=[],
        )
    except ExecutionUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    visible = [
        {"passed": bool(o.get("passed")), "error": o.get("error"),
         "stdout": (o.get("stdout") or "")[:4000]}
        for o in ((result or {}).get("visible") or [])
    ]
    return {
        "success": True,
        "scored": False,
        "visible": visible,
        "visible_passed": sum(1 for v in visible if v["passed"]),
        "visible_total": len(visible),
    }


def _draft_round_or_error(
    session: dict[str, Any], round_number: int
) -> dict[str, Any]:
    rounds = session.get("rounds", [])
    target = next((r for r in rounds if r.get("round") == int(round_number)), None)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target round not found in session.",
        )
    if session.get("status") == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session is completed; drafts are no longer accepted.",
        )
    if (
        target.get("status") in ("submitted", "finalizing", "expired")
        or target.get("answer_text")
        or target.get("final_score") is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This round has already been submitted; drafts are immutable.",
        )
    expires_at = target.get("expires_at")
    if expires_at is not None:
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at)
            except Exception:
                expires_at = None
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and datetime.now(timezone.utc) > expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Answer deadline has expired; draft was not saved.",
            )
    return target


@router.put("/{session_id}/draft")
def save_answer_draft(
    session_id: str,
    request: SaveAnswerDraftRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    """Autosave an in-progress answer. Respects ownership and deadlines."""
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    session = db["sessions"].find_one({"session_id": session_id})
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
        )
    user = require_user(authorization)
    if session.get("user_id") and str(session["user_id"]) != str(user["id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access another user's session.",
        )
    if not session.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Answer drafts require an owned session.",
        )
    target = _draft_round_or_error(session, request.round)
    round_type = target.get("round_type", "technical_short_answer")
    draft: dict[str, Any] = {"round": int(request.round)}
    if round_type == "mcq":
        if request.answers is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="MCQ draft requires 'answers'.",
            )
        assigned = {str(q.get("id")) for q in
                    (target.get("question_context") or {}).get("questions", [])}
        cleaned_answers = []
        for item in request.answers:
            qid = str(item.get("question_id") or "").strip()
            if not qid or qid not in assigned:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Draft question ID not assigned: '{qid}'.",
                )
            selected = [str(o) for o in (item.get("selected_option_ids") or [])]
            cleaned_answers.append({"question_id": qid,
                                    "selected_option_ids": selected})
        draft["answers"] = cleaned_answers
    else:
        if request.answer_text is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Round type '{round_type}' draft requires 'answer_text'.",
            )
        draft["answer_text"] = str(request.answer_text or "")[:20000]
        if round_type == "system_design" and request.rubric_ratings is not None:
            draft["rubric_ratings"] = dict(request.rubric_ratings)
    now = datetime.now(timezone.utc)
    db["answer_drafts"].update_one(
        {"session_id": session_id, "round": int(request.round)},
        {"$set": {"session_id": session_id, "round": int(request.round),
                  "user_id": str(user["id"]), "draft": draft,
                  "updated_at": now}},
        upsert=True,
    )
    return {"session_id": session_id, "round": int(request.round),
            "updated_at": now.isoformat(), "draft": draft}


@router.get("/{session_id}/draft")
def get_answer_draft(
    session_id: str,
    round: int,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    """Fetch a saved answer draft for safe recovery."""
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    session = db["sessions"].find_one({"session_id": session_id})
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
        )
    user = require_user(authorization)
    if session.get("user_id") and str(session["user_id"]) != str(user["id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access another user's session.",
        )
    _draft_round_or_error(session, round)
    stored = db["answer_drafts"].find_one(
        {"session_id": session_id, "round": int(round)}
    )
    if not stored or str(stored.get("user_id")) != str(user["id"]):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No draft found."
        )
    return {"session_id": session_id, "round": int(round),
            "updated_at": stored.get("updated_at"),
            "draft": stored.get("draft") or {}}
