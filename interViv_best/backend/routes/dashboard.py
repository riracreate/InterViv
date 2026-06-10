from __future__ import annotations

import statistics
from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.db import DatabaseConnectionError, get_database, is_database_exception

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# Confidence band constants (spec: "variance / 2, capped at 10")
CONFIDENCE_BAND_CAP = 10.0


def _score_bucket(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Average"
    return "Poor"


def compute_confidence_band(layer_scores: list[float | None]) -> float | None:
    """Confidence band per spec — Phase 2 Task 6b.

        variance        = stdev([layer1_score, layer2_score, layer3_score])
        confidence_band = variance / 2  (capped at 10)

    Returns ``None`` if we don't have at least two real layer scores
    (stdev requires >=2 inputs and produces a noisy result on a single
    point — better to surface the absence than fake a band).
    """
    usable = [float(s) for s in layer_scores if s is not None]
    if len(usable) < 2:
        return None
    variance = statistics.stdev(usable)
    band = variance / 2.0
    return round(min(band, CONFIDENCE_BAND_CAP), 2)


def _sanitize_rounds(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized = []
    for round_document in rounds:
        cleaned = dict(round_document)
        question_context = cleaned.get("question_context", {}) or {}
        cleaned["ideal_answer"] = question_context.get("ideal_answer", "")
        cleaned["ideal_keywords"] = question_context.get("ideal_keywords", "")
        cleaned["topic"] = question_context.get("topic") or question_context.get("sub_domain")
        cleaned["sub_domain"] = question_context.get("sub_domain") or cleaned.get("sub_domain")
        cleaned["question_type"] = question_context.get("question_type")
        cleaned["company"] = question_context.get("company")
        cleaned["role"] = question_context.get("role")
        cleaned["followups"] = question_context.get("followups") or []
        cleaned.pop("question_context", None)
        cleaned["performance_band"] = _score_bucket(cleaned.get("final_score"))

        breakdown = cleaned.get("scoring_breakdown") or {}
        layer_scores = [
            breakdown.get("layer1_score"),
            breakdown.get("layer2_score"),
            breakdown.get("layer3_score"),
        ]
        cleaned["confidence_band"] = compute_confidence_band(layer_scores)
        sanitized.append(cleaned)
    return sanitized


def _compute_topic_scores(session: dict[str, Any]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for round_document in session.get("rounds", []):
        score = round_document.get("final_score")
        if score is None:
            continue
        context = round_document.get("question_context", {}) or {}
        label = (
            context.get("topic")
            or context.get("sub_topic")
            or context.get("sub_domain")
            or session.get("skill")
            or "Overall"
        )
        buckets.setdefault(str(label), []).append(float(score))

    return {
        label: round(sum(values) / len(values), 2) for label, values in buckets.items()
    }


@router.get("/{session_id}")
def get_dashboard(session_id: str) -> dict[str, Any]:
    try:
        session = get_database()["sessions"].find_one(
            {"session_id": session_id}, {"_id": 0}
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
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    rounds = _sanitize_rounds(session.get("rounds", []))
    completed_rounds = [item for item in rounds if item.get("final_score") is not None]

    if completed_rounds:
        averages = {
            "final_score": round(
                sum(float(item.get("final_score", 0)) for item in completed_rounds)
                / len(completed_rounds),
                2,
            ),
            "nlp_score": round(
                sum(float(item.get("nlp_score", 0)) for item in completed_rounds)
                / len(completed_rounds),
                2,
            ),
            "kg_score": round(
                sum(float(item.get("kg_score", 0)) for item in completed_rounds)
                / len(completed_rounds),
                2,
            ),
        }
    else:
        averages = {"final_score": 0.0, "nlp_score": 0.0, "kg_score": 0.0}

    breakdown = {"Good": 0, "Average": 0, "Poor": 0}
    for item in completed_rounds:
        band = item.get("performance_band")
        if band in breakdown:
            breakdown[band] += 1

    last_feedback = completed_rounds[-1].get("feedback", {}) if completed_rounds else {}

    session["rounds"] = rounds
    session["averages"] = averages
    session["breakdown"] = breakdown
    session["elo_progression"] = [
        item.get("elo_after") for item in completed_rounds if item.get("elo_after") is not None
    ]
    session["difficulty_progression"] = [item.get("difficulty") for item in completed_rounds]
    session["topic_scores"] = _compute_topic_scores(session)
    session["next_step"] = last_feedback.get("next_step", "")
    return session
