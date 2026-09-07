"""
answer_v2.py — Drop-in replacement for backend/routes/answer.py

Core changes vs. the current version:
  • Uses _skill_for_round() to pick the correct skill for EACH round
  • Elo is updated on the skill THIS round was about (not always session["skill"])
  • Generates next question from the skill the NEXT round will use
  • Includes current_skill + total_rounds in response for the UI
  • Honors session["total_rounds"] (falls back to settings.max_rounds if unset)
"""
from __future__ import annotations

import re
import logging
from datetime import datetime, timezone

import json
from typing import Any
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, model_validator

from backend.config import get_settings
from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.integrations import IntegrationError
from backend.routes.auth import get_user_from_authorization, require_matching_user, require_user
from backend.routes.session import (
    _expanded_spec_for_round,
    _get_next_question,
    _skill_for_round,
    _sub_domain_for_skill,
    build_round_document,
)
from backend.serializers.round_serializer import sanitize_round_for_client, sanitize_sql_artifact_for_client
from modules import adaptive_question_selector
from modules.scoring import UnsupportedRoundTypeError, score_round
from modules.concept_mastery import ConceptMastery
from modules.skill_graph import StudentSkillGraph

router = APIRouter(prefix="/session", tags=["answer"])
logger = logging.getLogger(__name__)

DIFFICULTY_RATINGS = {"easy": 1000, "medium": 1500, "hard": 2000}
WORD_RE = re.compile(r"[A-Za-z0-9_+#.]+")


class MCQAnswerItem(BaseModel):
    question_id: str
    selected_option_ids: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _validate_fields(cls, values: Any) -> Any:
        if isinstance(values, dict):
            allowed = {"question_id", "selected_option_ids"}
            extra = set(values.keys()) - allowed
            if extra:
                raise ValueError(f"Unknown extra fields in MCQ answer item: {sorted(extra)}")
        return values


class SubmitAnswerRequest(BaseModel):
    session_id: str
    round: int
    answer_text: str | None = None
    answers: list[MCQAnswerItem] | None = None
    word_count: int = 0
    engagement_label: str | None = None
    engagement_confidence: float | None = None
    engagement_delta: int | None = None
    wpm: float | None = None
    pause_count: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _validate_fields(cls, values: Any) -> Any:
        if isinstance(values, dict):
            allowed = {
                "session_id",
                "round",
                "answer_text",
                "answers",
                "word_count",
                "engagement_label",
                "engagement_confidence",
                "engagement_delta",
                "wpm",
                "pause_count",
            }
            extra = set(values.keys()) - allowed
            if extra:
                raise ValueError(f"Unknown extra fields rejected: {sorted(extra)}")
        return values


def _difficulty_from_elo(elo: float) -> str:
    if elo < 1200:
        return "easy"
    if elo < 1700:
        return "medium"
    return "hard"


def _compute_elo_update(elo_before: float, difficulty: str, final_score: float) -> float:
    question_rating = DIFFICULTY_RATINGS.get(difficulty, 1500)
    expected = 1.0 / (1.0 + pow(10.0, (question_rating - elo_before) / 400.0))
    actual = final_score / 100.0
    updated = elo_before + 32 * (actual - expected)
    return round(max(600.0, min(2400.0, updated)), 2)


def _difficulty_delta(previous: str, current: str) -> str:
    order = {"easy": 0, "medium": 1, "hard": 2}
    if order.get(current, 1) > order.get(previous, 1):
        return "increase"
    if order.get(current, 1) < order.get(previous, 1):
        return "decrease"
    return "same"


def _total_rounds(session: dict, settings) -> int:
    """Prefer the explicit total from multi-skill start; fall back to legacy setting."""
    n = session.get("total_rounds")
    if isinstance(n, int) and n > 0:
        return n
    return int(settings.max_rounds)


def _server_word_count(answer_text: str) -> int:
    return len(WORD_RE.findall(answer_text or ""))


def _update_learning_state(
    *,
    session: dict,
    skill: str,
    final_score: float,
    difficulty: str,
    scoring_breakdown: dict,
    elo_before: float | None = None,
    elo_after: float | None = None,
    session_id: str | None = None,
) -> None:
    user_id = session.get("user_id")
    if not user_id:
        return
    try:
        StudentSkillGraph(str(user_id)).update_after_round(
            skill=skill,
            score=final_score,
            difficulty=difficulty,
        )
        ConceptMastery().update_from_round(
            user_id=str(user_id),
            skill=skill,
            covered_concepts=(
                (scoring_breakdown.get("concepts") or {}).get("covered")
                or scoring_breakdown.get("covered_concepts", [])
                or []
            ),
            missing_concepts=(
                (scoring_breakdown.get("concepts") or {}).get("missing")
                or scoring_breakdown.get("missing_concepts", [])
                or []
            ),
        )
        if elo_before is not None and elo_after is not None:
            from modules.learning_signals import record_elo_delta

            record_elo_delta(
                user_id=str(user_id),
                session_id=str(session_id or session.get("session_id") or ""),
                skill=skill,
                elo_before=float(elo_before),
                elo_after=float(elo_after),
            )
    except Exception:
        logger.warning("Failed to update Phase 2 learning state.", exc_info=True)


def _clear_answer_draft(db: Any, session_id: str, round_number: int) -> None:
    """Remove the saved draft for a submitted round (best effort)."""
    try:
        collection = db["answer_drafts"]
    except Exception:
        return
    try:
        if hasattr(collection, "delete_many"):
            collection.delete_many({"session_id": session_id, "round": int(round_number)})
        elif hasattr(collection, "delete_one"):
            collection.delete_one({"session_id": session_id, "round": int(round_number)})
    except Exception:
        # Memory-store fallback: rewrite without the matching draft.
        try:
            remaining = [doc for doc in collection.find({})
                         if not (doc.get("session_id") == session_id
                                 and int(doc.get("round") or 0) == int(round_number))]
            if hasattr(collection, "_docs"):
                collection._docs = remaining  # type: ignore[attr-defined]
        except Exception:
            pass


@router.post("/answer")
def submit_answer(
    request: SubmitAnswerRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    settings = get_settings()
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
    rounds = session.get("rounds", [])
    active_round = next((item for item in rounds if item.get("round") == request.round), None)
    if not active_round:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested round not found in session.",
        )

    round_type = active_round.get("round_type", "technical_short_answer")

    # Phase 2 MCQ & SQL sessions must require valid JWT principal; reject anonymous sessions
    if round_type in ("mcq", "sql"):
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
                    detail="You cannot access another user's data.",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Anonymous sessions are not permitted for this round type.",
            )
    elif session.get("user_id") and authorization:
        require_matching_user(str(session["user_id"]), authorization)

    # Strict round-type validation
    normalized_answers = None
    if round_type == "mcq":
        if request.answers is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="MCQ round requires structured 'answers' payload.",
            )
        if request.answer_text is not None and request.answer_text != "":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="MCQ round rejects 'answer_text'.",
            )
        normalized_answers = [
            item.model_dump() if hasattr(item, "model_dump") else dict(item)
            for item in request.answers
        ]
    else:
        if request.answer_text is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Round type '{round_type}' requires 'answer_text'.",
            )
        if request.answers is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Round type '{round_type}' rejects 'answers'.",
            )

    now = datetime.now(timezone.utc)

    # Deadline enforcement (no hidden grace period)
    expires_at = active_round.get("expires_at")
    if expires_at is not None:
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at)
            except Exception:
                expires_at = None
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and now > expires_at:
            active_round["status"] = "expired"
            active_round["final_score"] = 0.0
            db["sessions"].update_one(
                {"session_id": request.session_id},
                {"$set": {"rounds": rounds}},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Assessment deadline expired at {expires_at.isoformat()}.",
            )

    # Concurrency guard: atomic finalization check
    round_status = active_round.get("status")
    if (
        round_status in ("submitted", "finalizing", "expired")
        or active_round.get("answer_text")
        or active_round.get("final_score") is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This round has already been submitted or is finalizing.",
        )

    # Claim finalization
    active_round["status"] = "finalizing"
    db["sessions"].update_one(
        {"session_id": request.session_id},
        {"$set": {"rounds": rounds}},
    )

    # Which skill does THIS round belong to?
    current_skill = _skill_for_round(session, request.round)

    # Candidate baseline from prior rounds (unchanged behaviour)
    rounds_so_far = [item for item in rounds if item.get("final_score") is not None]
    candidate_baseline = None
    if len(rounds_so_far) >= 2:
        candidate_baseline = sum(
            float(item["final_score"]) for item in rounds_so_far
        ) / len(rounds_so_far)

    try:
        if round_type == "mcq":
            scoring_result = score_round(
                round_type="mcq",
                answers=normalized_answers,
                question_context=active_round.get("question_context", {}),
                config=active_round.get("config_json", {}),
            )
        else:
            scoring_result = score_round(
                round_type=round_type,
                answer_text=request.answer_text,
                word_count=_server_word_count(request.answer_text or ""),
                engagement_label=request.engagement_label,
                wpm=request.wpm,
                pause_count=request.pause_count,
                question_context=active_round.get("question_context", {}),
                difficulty=active_round.get("difficulty", "medium"),
                candidate_baseline=candidate_baseline,
            )
    except Exception as exc:
        # Rollback status on failure so round is not stuck in 'finalizing'
        active_round["status"] = "in_progress"
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {"$set": {"rounds": rounds}},
        )
        if isinstance(exc, (ValueError, UnsupportedRoundTypeError)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
        if isinstance(exc, IntegrationError):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise

    # Elo update against THIS round's skill
    elo_before = float(active_round.get("elo_before") or settings.initial_elo)
    elo_after = _compute_elo_update(
        elo_before=elo_before,
        difficulty=active_round.get("difficulty", "medium"),
        final_score=float(scoring_result["final_score"]),
    )
    next_difficulty = _difficulty_from_elo(elo_after)
    difficulty_change = _difficulty_delta(
        active_round.get("difficulty", "medium"), next_difficulty
    )

    persisted_answer = (
        request.answer_text
        if round_type != "mcq"
        else json.dumps(normalized_answers)
    )

    # Persist this round
    for index, round_document in enumerate(rounds):
        if round_document.get("round") != request.round:
            continue
        _bd = scoring_result.get("scoring_breakdown", {}) or {}
        rounds[index] = {
            **round_document,
            "skill": current_skill,
            "answer_text": persisted_answer,
            "status": "submitted",
            "submitted_at": now,
            "nlp_score": scoring_result.get("nlp_score"),
            "svm_label": scoring_result.get("svm_label"),
            "kg_score": scoring_result.get("kg_score"),
            "kg_label": _bd.get("kg_label", ""),
            "covered_concepts": _bd.get("covered_concepts", []),
            "missing_concepts": _bd.get("missing_concepts", []),
            "ner_entities": scoring_result.get("ner_entities", []),
            "final_score": scoring_result["final_score"],
            "difficulty_change": difficulty_change,
            "feedback": scoring_result["feedback"],
            "score_explanation": scoring_result.get("score_explanation", {}),
            "elo_before": elo_before,
            "elo_after": elo_after,
            "engagement_label": request.engagement_label,
            "engagement_confidence": request.engagement_confidence,
            "engagement_delta": request.engagement_delta,
            "scoring_breakdown": _bd,
            "artifact_json": scoring_result.get("artifact_json") or round_document.get("artifact_json", {}),
            "guard_applied": scoring_result.get("guard_applied"),
        }
        break

    total_rounds = _total_rounds(session, settings)

    next_question: str | None = None
    next_skill: str | None = None
    next_target: dict[str, object] | None = None
    response_next_difficulty = next_difficulty
    next_round_type: str | None = None
    next_question_context: dict[str, object] | None = None
    next_config_json: dict[str, object] | None = None
    next_expires_at: str | None = None
    next_block_id: str | None = None
    next_block_position: int | None = None
    next_block_category: str | None = None

    session_status = "completed" if request.round >= total_rounds else "active"
    completed_scores = [
        float(item.get("final_score"))
        for item in rounds
        if item.get("final_score") is not None
    ]
    session_update = {
        "rounds": rounds,
        "last_round": request.round,
        "current_difficulty": next_difficulty,
        "current_skill": next_skill or current_skill,
        "status": session_status,
    }
    if session_status == "completed":
        session_update["completed_at"] = datetime.now(timezone.utc)
        session_update["overall_readiness_score"] = (
            round(sum(completed_scores) / len(completed_scores), 2)
            if completed_scores
            else 0.0
        )

    try:
        # First persist the completed round and Elo. The adaptive selector
        # reads SkillGraph / ConceptMastery after this update, so it can
        # react to the answer that was just submitted.
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {"$set": session_update},
        )
        # Elo is stored per-skill — increment the skill THIS round was about
        db["candidates"].update_one(
            {"candidate_id": session["candidate_id"]},
            {"$set": {f"elo_ratings.{current_skill}": elo_after}},
        )
        _update_learning_state(
            session=session,
            skill=current_skill,
            final_score=float(scoring_result["final_score"]),
            difficulty=active_round.get("difficulty", "medium"),
            scoring_breakdown=scoring_result.get("scoring_breakdown", {}) or {},
            elo_before=elo_before,
            elo_after=elo_after,
            session_id=request.session_id,
        )

        # Clear the saved draft for the submitted round: submitted attempts
        # are immutable and drafts must not survive submission.
        try:
            _clear_answer_draft(db, request.session_id, request.round)
        except Exception:
            logger.warning("Failed to clear answer draft.", exc_info=True)

        # Queue the next round after recomputing the user's weakest skill
        # and concept from fresh learning state. Anonymous sessions keep the
        # existing rotation behavior. Block sessions honor the expanded plan
        # in requested order; legacy sessions honor round_plan.
        if request.round < total_rounds:
            next_round = request.round + 1
            # Idempotent progression: if the next round already exists (retry
            # after a lost response), reuse it instead of appending a duplicate.
            existing_next = next(
                (item for item in rounds if item.get("round") == next_round),
                None,
            )
            if existing_next is not None:
                sanitized_existing = sanitize_round_for_client(dict(existing_next))
                next_question = existing_next.get("question")
                next_skill = existing_next.get("skill") or _skill_for_round(session, next_round)
                next_round_type = existing_next.get("round_type")
                response_next_difficulty = existing_next.get("difficulty", next_difficulty)
                next_question_context = sanitized_existing.get("question_context") or {}
                next_config_json = dict(existing_next.get("config_json") or {})
                raw_expires = existing_next.get("expires_at")
                next_expires_at = (
                    raw_expires.isoformat()
                    if hasattr(raw_expires, "isoformat")
                    else (raw_expires if isinstance(raw_expires, str) else None)
                )
                next_block_id = existing_next.get("block_id")
                next_block_position = existing_next.get("block_position")
                next_block_category = existing_next.get("block_category")
                db["sessions"].update_one(
                    {"session_id": request.session_id},
                    {
                        "$set": {
                            "current_difficulty": response_next_difficulty,
                            "current_skill": next_skill,
                            "status": session_status,
                        }
                    },
                )
            else:
                plan = session.get("round_plan") or []
                planned_type = None
                if plan and next_round - 1 < len(plan):
                    planned_type = str(plan[next_round - 1])
                expanded_spec = _expanded_spec_for_round(session, next_round)
                if expanded_spec:
                    planned_type = str(expanded_spec.get("round_type") or planned_type)

                rotation_skill = _skill_for_round(session, next_round)
                candidate_doc = db["candidates"].find_one({"candidate_id": session["candidate_id"]})
                candidate_elos = (candidate_doc or {}).get("elo_ratings", {}) or {}
                rotation_elo = float(candidate_elos.get(rotation_skill, elo_after))
                rotation_difficulty = _difficulty_from_elo(rotation_elo)
                session_user_id = session.get("user_id")
                session_target_company = session.get("target_company_id")
                session_target_role = session.get("target_role_id")
                resume_skills = list((candidate_doc or {}).get("resume_skills") or session.get("skills") or [])
                session_skills = list(session.get("skills") or [session.get("skill") or "DBMS"])
                if expanded_spec:
                    spec_skills = [s for s in (expanded_spec.get("skills") or []) if s]
                    if spec_skills:
                        session_skills = spec_skills
                        rotation_skill = spec_skills[0]
                        rotation_elo = float(candidate_elos.get(rotation_skill, elo_after))
                        rotation_difficulty = (
                            str(expanded_spec.get("difficulty"))
                            if expanded_spec.get("difficulty")
                            else _difficulty_from_elo(rotation_elo)
                        )

                if planned_type in ("mcq", "sql"):
                    if expanded_spec:
                        spec_config: dict[str, Any] = {
                            "count": expanded_spec.get("count", 15),
                            "duration_minutes": expanded_spec.get("duration_minutes"),
                            "negative_marking": expanded_spec.get("negative_marking", 0.25),
                            "review_policy": expanded_spec.get("review_policy", "none"),
                            "difficulty": expanded_spec.get("difficulty"),
                            "question_ids": expanded_spec.get("question_ids") or None,
                            "problem_ids": expanded_spec.get("problem_ids") or None,
                            "problem_id": (expanded_spec.get("problem_ids") or [None])[0],
                        }
                        legacy_cfg = dict(session.get("round_config") or {})
                        for key in ("max_rows", "timeout_seconds"):
                            if key in legacy_cfg:
                                spec_config[key] = legacy_cfg[key]
                        if spec_config.get("duration_minutes") is None:
                            spec_config.pop("duration_minutes", None)
                        sql_index = 0
                    else:
                        sql_index = sum(
                            1 for i, t in enumerate(plan[: next_round - 1]) if t == "sql"
                        )
                        spec_config = dict(session.get("round_config") or {})
                    try:
                        next_doc = build_round_document(
                            round_number=next_round,
                            round_type=planned_type,
                            skills=session_skills,
                            elo_before=rotation_elo,
                            difficulty=rotation_difficulty,
                            sub_domain=_sub_domain_for_skill(candidate_doc, rotation_skill),
                            round_config=spec_config,
                            user_id=str(session_user_id) if session_user_id else None,
                            target_company_id=str(session_target_company) if session_target_company else None,
                            target_role_id=str(session_target_role) if session_target_role else None,
                            resume_skills=resume_skills,
                            asked=[item.get("question", "") for item in rounds],
                            sql_problem_index=sql_index,
                            block_id=(expanded_spec or {}).get("block_id"),
                            block_position=(expanded_spec or {}).get("block_position"),
                            block_category=(expanded_spec or {}).get("category"),
                            block_index=(expanded_spec or {}).get("block_index"),
                            block_total=(expanded_spec or {}).get("block_total"),
                            allow_unknown_fallback=bool(session.get("allow_unknown_topic_fallback")),
                        )
                    except ValueError as exc:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
                        ) from exc
                    except IntegrationError as exc:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
                        ) from exc
                    next_payload = next_doc.model_dump()
                    rounds.append(next_payload)
                    next_question = next_doc.question
                    next_skill = rotation_skill
                    next_round_type = planned_type
                    response_next_difficulty = next_doc.difficulty
                    sanitized = sanitize_round_for_client(next_payload)
                    next_question_context = sanitized.get("question_context") or {}
                    next_config_json = next_doc.config_json or {}
                    next_expires_at = (
                        next_doc.expires_at.isoformat() if next_doc.expires_at else None
                    )
                    next_block_id = next_doc.block_id
                    next_block_position = next_doc.block_position
                    next_block_category = next_doc.block_category
                    db["sessions"].update_one(
                        {"session_id": request.session_id},
                        {
                            "$set": {
                                "rounds": rounds,
                                "current_difficulty": response_next_difficulty,
                                "current_skill": next_skill,
                                "status": session_status,
                            }
                        },
                    )
                else:
                    # Block sessions constrain adaptation to the block's own
                    # skills; legacy sessions adapt across all session skills.
                    adaptive_skills = (
                        session_skills if expanded_spec
                        else (session.get("skills") or [session.get("skill")])
                    )
                    target = adaptive_question_selector.choose_adaptive_target(
                        user_id=str(session_user_id) if session_user_id else None,
                        fallback_skill=rotation_skill,
                        fallback_difficulty=rotation_difficulty,
                        session_skills=adaptive_skills,
                        target_role_id=str(session_target_role) if session_target_role else None,
                        candidate_elo_by_skill=candidate_elos,
                    )
                    next_skill = target.skill
                    if expanded_spec:
                        # Stay inside the requested block topics.
                        spec_skill_set = set(session_skills)
                        if next_skill not in spec_skill_set:
                            next_skill = rotation_skill
                    next_skill_elo = float(
                        target.current_elo
                        if target.current_elo is not None
                        else candidate_elos.get(next_skill, elo_after)
                    )
                    next_round_difficulty = (
                        str(expanded_spec.get("difficulty"))
                        if expanded_spec and expanded_spec.get("difficulty")
                        else target.difficulty
                    )
                    response_next_difficulty = next_round_difficulty
                    sub = _sub_domain_for_skill(candidate_doc, next_skill)
                    asked = [item.get("question", "") for item in rounds]
                    weak_context = list(target.target_concepts or [])
                    if target.source != "rotation" and target.skill:
                        weak_context.insert(0, target.skill)

                    try:
                        question_payload = _get_next_question(
                            skill=next_skill,
                            sub_domain=sub,
                            difficulty=next_round_difficulty,
                            asked=asked,
                            user_id=str(session_user_id) if session_user_id else None,
                            target_company_id=str(session_target_company) if session_target_company else None,
                            target_role_id=str(session_target_role) if session_target_role else None,
                            target_concepts=target.target_concepts,
                            resume_skills=resume_skills,
                            weak_skills=weak_context,
                        )
                    except IntegrationError as exc:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
                        ) from exc
                    question_payload["adaptive_target"] = target.to_dict()
                    next_target = target.to_dict()
                    next_round_type = "technical_short_answer"

                    next_expires_value = None
                    next_config_value: dict[str, Any] = {}
                    if expanded_spec and expanded_spec.get("duration_minutes"):
                        from datetime import timedelta as _timedelta
                        activated = datetime.now(timezone.utc)
                        next_expires_value = activated + _timedelta(
                            minutes=int(expanded_spec["duration_minutes"])
                        )
                        next_config_value = {
                            "duration_minutes": int(expanded_spec["duration_minutes"])
                        }
                        next_expires_at = next_expires_value.isoformat()
                    next_round_doc = {
                        "round": next_round,
                        "skill": next_skill,
                        "round_type": "technical_short_answer",
                        "artifact_json": {},
                        "config_json": next_config_value,
                        "question": question_payload["question"],
                        "answer_text": None,
                        "nlp_score": None,
                        "svm_label": None,
                        "kg_score": None,
                        "ner_entities": [],
                        "final_score": None,
                        "difficulty": next_round_difficulty,
                        "difficulty_change": None,
                        "feedback": {"content": [], "strengths": [], "next_step": ""},
                        "elo_before": next_skill_elo,
                        "elo_after": None,
                        "question_context": question_payload,
                        "started_at": datetime.now(timezone.utc),
                        "expires_at": next_expires_value,
                        "status": "in_progress",
                        "block_id": (expanded_spec or {}).get("block_id"),
                        "block_position": (expanded_spec or {}).get("block_position"),
                        "block_category": (expanded_spec or {}).get("category"),
                        "block_index": (expanded_spec or {}).get("block_index"),
                        "block_total": (expanded_spec or {}).get("block_total"),
                    }
                    rounds.append(next_round_doc)
                    next_question = question_payload["question"]
                    next_question_context = question_payload
                    next_config_json = next_config_value
                    next_block_id = (expanded_spec or {}).get("block_id")
                    next_block_position = (expanded_spec or {}).get("block_position")
                    next_block_category = (expanded_spec or {}).get("category")
                    db["sessions"].update_one(
                        {"session_id": request.session_id},
                        {
                            "$set": {
                                "rounds": rounds,
                                "current_difficulty": next_round_difficulty,
                                "current_skill": next_skill,
                                "status": session_status,
                            }
                        },
                    )
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except Exception as exc:
        if is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"MongoDB operation failed: {exc}",
            ) from exc
        raise

    resp_artifact = scoring_result.get("artifact_json")
    if round_type == "sql" and resp_artifact:
        resp_artifact = sanitize_sql_artifact_for_client(resp_artifact)

    return {
        "svm_label": scoring_result.get("svm_label"),
        "nlp_score": scoring_result.get("nlp_score"),
        "kg_score": scoring_result.get("kg_score"),
        "ner_entities": scoring_result.get("ner_entities", []),
        "final_score": scoring_result["final_score"],
        "feedback": scoring_result["feedback"],
        "score_explanation": scoring_result.get("score_explanation", {}),
        "scoring_schema_version": scoring_result.get("scoring_schema_version"),
        "rubric": scoring_result.get("rubric", {}),
        "concepts": scoring_result.get("concepts", {}),
        "guard": scoring_result.get("guard", {}),
        "scoring_breakdown": scoring_result.get("scoring_breakdown", {}),
        "artifact_json": resp_artifact,
        "guard_applied": scoring_result.get("guard_applied"),
        "next_question": next_question,
        "next_round_type": next_round_type or ("technical_short_answer" if next_question else None),
        "next_question_context": next_question_context,
        "next_config_json": next_config_json,
        "next_expires_at": next_expires_at,
        "next_difficulty": response_next_difficulty,
        "next_skill": next_skill,
        "next_block_id": next_block_id,
        "next_block_position": next_block_position,
        "next_block_category": next_block_category,
        "adaptive_target": next_target,
        "current_skill": current_skill,
        "elo_after": elo_after,
        "difficulty_change": difficulty_change,
        "total_rounds": total_rounds,
        "session_complete": request.round >= total_rounds,
    }
