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

router = APIRouter(prefix="/session", tags=["answer"])

DIFFICULTY_RATINGS = {"easy": 1000, "medium": 1500, "hard": 2000}


class SubmitAnswerRequest(BaseModel):
    session_id: str
    round: int
    answer_text: str
    word_count: int = 0
    engagement_label: str | None = None
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
            word_count=request.word_count,
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
        rounds[index] = {
            **round_document,
            "skill": current_skill,
            "answer_text": request.answer_text,
            "nlp_score": scoring_result["nlp_score"],
            "svm_label": scoring_result["svm_label"],
            "kg_score": scoring_result["kg_score"],
            "ner_entities": scoring_result["ner_entities"],
            "final_score": scoring_result["final_score"],
            "difficulty_change": difficulty_change,
            "feedback": scoring_result["feedback"],
            "elo_before": elo_before,
            "elo_after": elo_after,
            "scoring_breakdown": scoring_result.get("scoring_breakdown", {}),
            "guard_applied": scoring_result.get("guard_applied"),
        }
        break

    total_rounds = _total_rounds(session, settings)

    # Queue up next round if any remain
    next_question: str | None = None
    next_skill: str | None = None
    if request.round < total_rounds:
        # The upcoming round might use a different skill
        next_round = request.round + 1
        next_skill = _skill_for_round(session, next_round)
        candidate_doc = db["candidates"].find_one({"candidate_id": session["candidate_id"]})

        # Use the candidate's Elo on the NEXT skill for difficulty calibration
        next_skill_elo = float(
            (candidate_doc or {}).get("elo_ratings", {}).get(next_skill, elo_after)
        )
        next_round_difficulty = _difficulty_from_elo(next_skill_elo)
        sub = _sub_domain_for_skill(candidate_doc, next_skill)

        asked = [item.get("question", "") for item in rounds]
        try:
            question_payload = _get_next_question(
                skill=next_skill,
                sub_domain=sub,
                difficulty=next_round_difficulty,
                asked=asked,
            )
        except IntegrationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc

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

    try:
        db["sessions"].update_one(
            {"session_id": request.session_id},
            {
                "$set": {
                    "rounds": rounds,
                    "last_round": request.round,
                    "current_difficulty": next_difficulty,
                    "current_skill": next_skill or current_skill,
                    "status": "completed" if request.round >= total_rounds else "active",
                }
            },
        )
        # Elo is stored per-skill — increment the skill THIS round was about
        db["candidates"].update_one(
            {"candidate_id": session["candidate_id"]},
            {"$set": {f"elo_ratings.{current_skill}": elo_after}},
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
        "scoring_breakdown": scoring_result.get("scoring_breakdown", {}),
        "guard_applied": scoring_result.get("guard_applied"),
        "next_question": next_question,
        "next_difficulty": next_difficulty,
        "next_skill": next_skill,
        "current_skill": current_skill,
        "elo_after": elo_after,
        "difficulty_change": difficulty_change,
        "total_rounds": total_rounds,
        "session_complete": request.round >= total_rounds,
    }
