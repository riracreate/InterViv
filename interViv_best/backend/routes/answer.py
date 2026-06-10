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

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.config import get_settings
from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.integrations import IntegrationError
from backend.routes.session import (
    _get_next_question,
    _skill_for_round,
    _sub_domain_for_skill,
)
from backend.scoring.pipeline import run_scoring_pipeline
from modules import adaptive_question_selector
from modules.concept_mastery import ConceptMastery
from modules.skill_graph import StudentSkillGraph

router = APIRouter(prefix="/session", tags=["answer"])
logger = logging.getLogger(__name__)

DIFFICULTY_RATINGS = {"easy": 1000, "medium": 1500, "hard": 2000}
WORD_RE = re.compile(r"[A-Za-z0-9_+#.]+")


class SubmitAnswerRequest(BaseModel):
    session_id: str
    round: int
    answer_text: str
    word_count: int = 0
    engagement_label: str | None = None
    engagement_confidence: float | None = None
    engagement_delta: int | None = None
    wpm: float | None = None
    pause_count: int | None = None


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
    except Exception:
        logger.warning("Failed to update Phase 2 learning state.", exc_info=True)


@router.post("/answer")
def submit_answer(request: SubmitAnswerRequest) -> dict[str, object]:
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
    if active_round.get("answer_text"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This round has already been submitted.",
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
        scoring_result = run_scoring_pipeline(
            answer_text=request.answer_text,
            word_count=_server_word_count(request.answer_text),
            engagement_label=request.engagement_label,
            wpm=request.wpm,
            pause_count=request.pause_count,
            question_context=active_round.get("question_context", {}),
            difficulty=active_round.get("difficulty", "medium"),
            candidate_baseline=candidate_baseline,
        )
    except IntegrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

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

    # Persist this round
    for index, round_document in enumerate(rounds):
        if round_document.get("round") != request.round:
            continue
        _bd = scoring_result.get("scoring_breakdown", {}) or {}
        rounds[index] = {
            **round_document,
            "skill": current_skill,
            "answer_text": request.answer_text,
            "nlp_score": scoring_result["nlp_score"],
            "svm_label": scoring_result["svm_label"],
            "kg_score": scoring_result["kg_score"],
            "kg_label": _bd.get("kg_label", ""),
            "covered_concepts": _bd.get("covered_concepts", []),
            "missing_concepts": _bd.get("missing_concepts", []),
            "ner_entities": scoring_result["ner_entities"],
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
            "guard_applied": scoring_result.get("guard_applied"),
        }
        break

    total_rounds = _total_rounds(session, settings)

    next_question: str | None = None
    next_skill: str | None = None
    next_target: dict[str, object] | None = None
    response_next_difficulty = next_difficulty

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
        )

        # Queue the next round after recomputing the user's weakest skill
        # and concept from fresh learning state. Anonymous sessions keep the
        # existing rotation behavior.
        if request.round < total_rounds:
            next_round = request.round + 1
            rotation_skill = _skill_for_round(session, next_round)
            candidate_doc = db["candidates"].find_one({"candidate_id": session["candidate_id"]})
            candidate_elos = (candidate_doc or {}).get("elo_ratings", {}) or {}
            rotation_elo = float(candidate_elos.get(rotation_skill, elo_after))
            rotation_difficulty = _difficulty_from_elo(rotation_elo)
            session_user_id = session.get("user_id")
            session_target_company = session.get("target_company_id")
            session_target_role = session.get("target_role_id")
            resume_skills = list((candidate_doc or {}).get("resume_skills") or session.get("skills") or [])

            target = adaptive_question_selector.choose_adaptive_target(
                user_id=str(session_user_id) if session_user_id else None,
                fallback_skill=rotation_skill,
                fallback_difficulty=rotation_difficulty,
                session_skills=session.get("skills") or [session.get("skill")],
                target_role_id=str(session_target_role) if session_target_role else None,
                candidate_elo_by_skill=candidate_elos,
            )
            next_skill = target.skill
            next_skill_elo = float(
                target.current_elo
                if target.current_elo is not None
                else candidate_elos.get(next_skill, elo_after)
            )
            next_round_difficulty = target.difficulty
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

            rounds.append(
                {
                    "round": next_round,
                    "skill": next_skill,
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
                }
            )
            next_question = question_payload["question"]
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

    return {
        "svm_label": scoring_result["svm_label"],
        "nlp_score": scoring_result["nlp_score"],
        "kg_score": scoring_result["kg_score"],
        "ner_entities": scoring_result["ner_entities"],
        "final_score": scoring_result["final_score"],
        "feedback": scoring_result["feedback"],
        "score_explanation": scoring_result.get("score_explanation", {}),
        "scoring_schema_version": scoring_result.get("scoring_schema_version"),
        "rubric": scoring_result.get("rubric", {}),
        "concepts": scoring_result.get("concepts", {}),
        "guard": scoring_result.get("guard", {}),
        "scoring_breakdown": scoring_result.get("scoring_breakdown", {}),
        "guard_applied": scoring_result.get("guard_applied"),
        "next_question": next_question,
        "next_difficulty": response_next_difficulty,
        "next_skill": next_skill,
        "adaptive_target": next_target,
        "current_skill": current_skill,
        "elo_after": elo_after,
        "difficulty_change": difficulty_change,
        "total_rounds": total_rounds,
        "session_complete": request.round >= total_rounds,
    }
