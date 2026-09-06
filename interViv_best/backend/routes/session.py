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
from backend.integrations import IntegrationError
from backend.models.candidate import CandidateDocument
from backend.models.session import RoundDocument, SessionDocument
from backend.routes.auth import get_user_from_authorization, require_matching_user, require_user
from backend.serializers.round_serializer import sanitize_round_for_client
from modules.skill_graph import StudentSkillGraph

router = APIRouter(prefix="/session", tags=["session"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_ROUND_TYPES = ("technical_short_answer", "mcq", "sql")


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

    @model_validator(mode="before")
    @classmethod
    def _ensure_at_least_one(cls, data):  # noqa: N805
        if isinstance(data, dict):
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


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _elo_to_difficulty(elo: float) -> str:
    if elo < 1200:
        return "easy"
    if elo < 1700:
        return "medium"
    return "hard"


def _skill_for_round(session: dict, round_number: int) -> str:
    """Return the skill to ask in the given (1-based) round.

    Rotation strategy:
        skills = [A, B, C], rounds_per_skill = 3 → A A A B B B C C C
    This is predictable for the UI (progress pills) and gives each skill a
    fair chance to adapt difficulty before switching.
    """
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


def _filter_mcq_items(
    items: list[dict[str, Any]],
    *,
    skills: list[str] | None = None,
    count: int = 15,
    question_ids: list[str] | None = None,
    difficulty: str | None = None,
) -> list[dict[str, Any]]:
    if question_ids:
        wanted = {str(qid) for qid in question_ids}
        ordered = [q for q in items if str(q.get("id")) in wanted]
        # Preserve request order when possible
        by_id = {str(q.get("id")): q for q in ordered}
        items = [by_id[qid] for qid in question_ids if qid in by_id]
    else:
        if difficulty:
            items = [q for q in items if str(q.get("difficulty", "")).lower() == difficulty.lower()]
        if skills:
            matched = [q for q in items if q.get("skill") in skills]
            rest = [q for q in items if q.get("skill") not in skills]
            items = matched + rest
    return items[:count]


def _select_mcq_questions(
    skills: list[str] | None = None,
    count: int = 15,
    question_ids: list[str] | None = None,
    difficulty: str | None = None,
) -> list[dict[str, Any]]:
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
                if rows:
                    items = []
                    for q_row, skill_name in rows:
                        items.append({
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
                    return _filter_mcq_items(
                        items,
                        skills=skills,
                        count=count,
                        question_ids=question_ids,
                        difficulty=difficulty,
                    )
    except Exception:
        pass

    from backend.db.phase2_content_bank import PHASE2_MCQ_BANK
    items = [dict(q) for q in PHASE2_MCQ_BANK]
    return _filter_mcq_items(
        items,
        skills=skills,
        count=count,
        question_ids=question_ids,
        difficulty=difficulty,
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
) -> RoundDocument:
    """Build a RoundDocument for technical / MCQ / SQL (shared by start + answer)."""
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
        )
        if not assigned:
            raise IntegrationError("No MCQ questions available for the requested filters.")
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
    return RoundDocument(
        round=round_number,
        round_type="technical_short_answer",
        question=first_question["question"],
        difficulty=difficulty,
        elo_before=elo_before,
        question_context=first_question,
        started_at=now,
        status="in_progress",
    )


def list_practice_bank_items() -> dict[str, Any]:
    """Public catalog of existing MCQ + SQL banks (no answers / reference SQL)."""
    from backend.db.phase2_content_bank import PHASE2_MCQ_BANK, PHASE2_SQL_BANK

    mcq = [
        {
            "id": q["id"],
            "type": "mcq",
            "skill": q.get("skill"),
            "sub_domain": q.get("sub_domain"),
            "difficulty": q.get("difficulty"),
            "stem": q.get("stem"),
        }
        for q in PHASE2_MCQ_BANK
    ]
    sql = []
    for p in PHASE2_SQL_BANK:
        prompt = str(p.get("prompt") or "")
        title = prompt.split("\n", 1)[0].lstrip("# ").strip() or p["id"]
        sql.append(
            {
                "id": p["id"],
                "type": "sql",
                "skill": "SQL",
                "difficulty": p.get("difficulty"),
                "title": title,
            }
        )
    return {"mcq": mcq, "sql": sql, "counts": {"mcq": len(mcq), "sql": len(sql)}}


def _select_sql_problem(problem_id: str | None = None) -> dict[str, Any]:
    from backend.db.phase2_content_bank import PHASE2_SQL_BANK
    from backend.db.phase2a_fixtures import PHASE2A_SQL_FIXTURES
    target_id = problem_id or "sql_hr_high_earners"
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
    return dict(PHASE2A_SQL_FIXTURES[0])


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

    candidate_id = (request.candidate_id or "").strip()
    candidate = db["candidates"].find_one({"candidate_id": candidate_id}) if candidate_id else None
    user = get_user_from_authorization(authorization) if authorization else None

    plan = list(request.round_plan) if request.round_plan else None
    opening_type = (plan[0] if plan else request.round_type) or "technical_short_answer"
    needs_phase2_auth = opening_type in ("mcq", "sql") or any(
        t in ("mcq", "sql") for t in (plan or [])
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
            resume_skills=request.skills,
            sub_domain_profile={
                skill: request.sub_domain or "general" for skill in request.skills
            },
            elo_ratings={skill: settings.initial_elo for skill in request.skills},
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
    first_skill = request.skills[0]
    elo_before = float(candidate.get("elo_ratings", {}).get(first_skill, settings.initial_elo))
    difficulty = _elo_to_difficulty(elo_before)
    sub_domain = _sub_domain_for_skill(candidate, first_skill, request.sub_domain)

    try:
        round_document = build_round_document(
            round_number=1,
            round_type=opening_type,
            skills=request.skills,
            elo_before=elo_before,
            difficulty=difficulty,
            sub_domain=sub_domain,
            round_config=request.round_config,
            user_id=str(user["id"]) if user else None,
            target_company_id=target_company_id,
            target_role_id=target_role_id,
            resume_skills=candidate.get("resume_skills") or request.skills,
            asked=[],
            sql_problem_index=0,
        )
    except IntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=str(exc)) from exc

    session_id = str(uuid4())
    if plan:
        total_rounds = len(plan)
    else:
        total_rounds = request.rounds_per_skill * len(request.skills)
        # Single MCQ/SQL assessments are one round unless a plan was provided.
        if opening_type in ("mcq", "sql") and request.round_type in ("mcq", "sql"):
            total_rounds = 1

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
    session_dict["skills"] = request.skills
    session_dict["rounds_per_skill"] = request.rounds_per_skill
    session_dict["total_rounds"] = total_rounds
    session_dict["current_skill"] = first_skill
    session_dict["user_id"] = user["id"] if user else candidate.get("user_id")
    session_dict["target_company_id"] = target_company_id
    session_dict["target_role_id"] = target_role_id
    session_dict["round_config"] = request.round_config or {}
    if plan:
        session_dict["round_plan"] = plan

    try:
        db["sessions"].insert_one(session_dict)
        candidate_update = {
            "$addToSet": {
                "session_history": session_id,
                "resume_skills": {"$each": request.skills},
            },
            "$set": {},
        }
        # seed Elo for any skill the candidate hasn't been rated on
        for s in request.skills:
            existing_elo = candidate.get("elo_ratings", {}).get(s)
            if existing_elo is None:
                candidate_update["$set"][f"elo_ratings.{s}"] = settings.initial_elo
        if sub_domain:
            candidate_update["$set"][f"sub_domain_profile.{first_skill}"] = sub_domain
        if user:
            candidate_update["$set"]["user_id"] = user["id"]
        db["candidates"].update_one({"candidate_id": candidate_id}, candidate_update)
        if user:
            StudentSkillGraph(user["id"]).initialize_from_resume(request.skills)
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
        "skills": request.skills,
        "rounds_per_skill": request.rounds_per_skill,
        "round_plan": plan,
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
    has_phase2_round = any(r.get("round_type") in ("mcq", "sql") for r in rounds)
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
