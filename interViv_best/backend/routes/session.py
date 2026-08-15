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

from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field, model_validator

from backend.config import get_settings
from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.integrations import IntegrationError
from backend.models.candidate import CandidateDocument
from backend.models.session import RoundDocument, SessionDocument
from backend.routes.auth import get_user_from_authorization
from modules.skill_graph import StudentSkillGraph

router = APIRouter(prefix="/session", tags=["session"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    candidate_id: str
    # Legacy single-skill field — still accepted
    skill: str | None = None
    # New: list of skills. 1 = single-skill session, N = rotate across N skills.
    skills: list[str] = Field(default_factory=list, description="List of skills for this session")
    sub_domain: str | None = None
    rounds_per_skill: int = Field(default=3, ge=1, le=10)
    target_company_id: str | None = None
    target_role_id: str | None = None

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
        return data


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
        first_question = _get_next_question(
            skill=first_skill, sub_domain=sub_domain,
            difficulty=difficulty, asked=[],
            user_id=str(user["id"]) if user else None,
            target_company_id=target_company_id,
            target_role_id=target_role_id,
            resume_skills=candidate.get("resume_skills") or request.skills,
        )
    except IntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=str(exc)) from exc

    # ── build session doc ───────────────────────────────────────────────────
    round_document = RoundDocument(
        round=1,
        question=first_question["question"],
        difficulty=difficulty,
        elo_before=elo_before,
        question_context=first_question,
    )
    session_id = str(uuid4())
    total_rounds = request.rounds_per_skill * len(request.skills)

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

    return {
        "session_id": session_id,
        "candidate_id": candidate_id,
        "user_id": user["id"] if user else candidate.get("user_id"),
        "question": first_question["question"],
        "difficulty": difficulty,
        "round": 1,
        "elo": elo_before,
        "total_rounds": total_rounds,
        "current_skill": first_skill,
        "skills": request.skills,
        "rounds_per_skill": request.rounds_per_skill,
    }
