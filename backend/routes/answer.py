from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.config import get_settings
from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.integrations import IntegrationError
from backend.routes.session import _get_next_question
from backend.scoring.pipeline import run_scoring_pipeline

router = APIRouter(prefix="/session", tags=["answer"])

DIFFICULTY_RATINGS = {"easy": 1000, "medium": 1500, "hard": 2000}
_LEVELS = ["easy", "medium", "hard"]

# A1: Engagement label → numeric score map
_ENGAGEMENT_LABEL_SCORES: dict[str, float] = {
    "high engagement": 90.0,
    "medium engagement": 65.0,
    "low engagement": 30.0,
}


class SubmitAnswerRequest(BaseModel):
    session_id: str
    round: int
    answer_text: str
    cos_similarity: float
    length_ratio: float
    aligned_score: float
    word_count: int
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


def _clamp_difficulty(from_level: str, to_level: str) -> str:
    """Clamp difficulty change to ±1 level (C2 requirement)."""
    from_idx = _LEVELS.index(from_level) if from_level in _LEVELS else 1
    to_idx = _LEVELS.index(to_level) if to_level in _LEVELS else 1
    clamped = max(from_idx - 1, min(from_idx + 1, to_idx))
    return _LEVELS[clamped]


def _moving_average_difficulty(
    current_difficulty: str,
    past_scores: list[float],
    current_score: float,
    window: int = 3,
) -> str:
    """
    C2: Compute moving average of the last `window` scores and suggest difficulty.
    Returns the difficulty suggested by the moving average.
    """
    recent = (past_scores + [current_score])[-window:]
    avg = sum(recent) / len(recent)

    idx = _LEVELS.index(current_difficulty) if current_difficulty in _LEVELS else 1
    if avg >= 70.0 and idx < 2:
        return _LEVELS[idx + 1]
    if avg <= 40.0 and idx > 0:
        return _LEVELS[idx - 1]
    return current_difficulty


def _combined_difficulty(
    current_difficulty: str,
    elo_difficulty: str,
    moving_avg_difficulty: str,
) -> str:
    """
    C2 + Elo: Run both engines in parallel.
    - Both agree  → use that direction (clamped to ±1)
    - They disagree → stay at current difficulty
    """
    if elo_difficulty == moving_avg_difficulty:
        return _clamp_difficulty(current_difficulty, elo_difficulty)
    # Conservative fallback when signals disagree
    return current_difficulty


def _compute_engagement_baseline(rounds: list[dict]) -> float | None:
    """
    A1 Baseline Calibration: average engagement score from completed rounds.
    Returns None if no past engagement data exists.
    """
    scores: list[float] = []
    for r in rounds:
        label = r.get("engagement_label") or (r.get("metadata") or {}).get("engagement_label")
        if label:
            score = _ENGAGEMENT_LABEL_SCORES.get(label.strip().lower())
            if score is not None:
                scores.append(score)
    return sum(scores) / len(scores) if scores else None


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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
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

    # A1: Compute engagement baseline from past completed rounds
    completed_rounds = [r for r in rounds if r.get("final_score") is not None]
    engagement_baseline = _compute_engagement_baseline(completed_rounds)

    try:
        scoring_result = run_scoring_pipeline(
            answer_text=request.answer_text,
            cos_similarity=request.cos_similarity,
            length_ratio=request.length_ratio,
            aligned_score=request.aligned_score,
            word_count=request.word_count,
            engagement_label=request.engagement_label,
            wpm=request.wpm,
            pause_count=request.pause_count,
            question_context=active_round.get("question_context", {}),
            engagement_baseline=engagement_baseline,
        )
    except IntegrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    elo_before = float(active_round.get("elo_before") or settings.initial_elo)
    elo_after = _compute_elo_update(
        elo_before=elo_before,
        difficulty=active_round.get("difficulty", "medium"),
        final_score=float(scoring_result["final_score"]),
    )

    # C2 + Elo: Run both engines in parallel and combine
    elo_difficulty = _difficulty_from_elo(elo_after)

    past_scores = [float(r["final_score"]) for r in completed_rounds]
    current_difficulty = active_round.get("difficulty", "medium")
    moving_avg_difficulty = _moving_average_difficulty(
        current_difficulty=current_difficulty,
        past_scores=past_scores,
        current_score=float(scoring_result["final_score"]),
    )

    next_difficulty = _combined_difficulty(
        current_difficulty=current_difficulty,
        elo_difficulty=elo_difficulty,
        moving_avg_difficulty=moving_avg_difficulty,
    )
    difficulty_change = _difficulty_delta(current_difficulty, next_difficulty)

    for index, round_document in enumerate(rounds):
        if round_document.get("round") != request.round:
            continue
        rounds[index] = {
            **round_document,
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
            "engagement_label": request.engagement_label,
        }
        break

    next_question: str | None = None
    if request.round < settings.max_rounds:
        asked = [item.get("question", "") for item in rounds]
        try:
            question_payload = _get_next_question(
                skill=session["skill"],
                sub_domain=session.get("sub_domain"),
                difficulty=next_difficulty,
                asked=asked,
            )
        except IntegrationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc

        rounds.append(
            {
                "round": request.round + 1,
                "question": question_payload["question"],
                "answer_text": None,
                "nlp_score": None,
                "svm_label": None,
                "kg_score": None,
                "ner_entities": [],
                "final_score": None,
                "difficulty": next_difficulty,
                "difficulty_change": None,
                "feedback": {"content": [], "strengths": [], "next_step": ""},
                "elo_before": elo_after,
                "elo_after": None,
                "question_context": question_payload,
                "engagement_label": None,
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
                    "status": "completed"
                    if request.round >= settings.max_rounds
                    else "active",
                }
            },
        )
        db["candidates"].update_one(
            {"candidate_id": session["candidate_id"]},
            {"$set": {f"elo_ratings.{session['skill']}": elo_after}},
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
        "next_question": next_question,
        "next_difficulty": next_difficulty,
        "elo_after": elo_after,
        "difficulty_change": difficulty_change,
    }

