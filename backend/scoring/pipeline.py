from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import joblib

from backend.integrations import (
    IntegrationError,
    call_with_supported_signature,
    load_module,
    locate_file,
    normalize_feedback,
)

# ── C1 Scoring weights ─────────────────────────────────────────
_C1_WEIGHTS = {
    "answer_quality": 0.30,
    "communication_quality": 0.25,
    "engagement_indicator": 0.20,
    "keyword_match": 0.15,
    "pace_filler_penalty": 0.10,
}

_ENGAGEMENT_SCORES: dict[str, float] = {
    "high engagement": 90.0,
    "medium engagement": 65.0,
    "low engagement": 30.0,
}

_FILLER_RE = re.compile(
    r"\b(um+|uh+|like|you know|basically|literally|sort of|kind of|actually|right|so|well)\b",
    re.IGNORECASE,
)


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@lru_cache(maxsize=1)
def _load_svm_model() -> Any:
    model_path = locate_file("svm_model.joblib", group="model")
    return joblib.load(model_path)


def _extract_score_value(payload: Any, keys: tuple[str, ...]) -> float | None:
    if isinstance(payload, dict):
        for key in keys:
            if key in payload:
                return _coerce_float(payload[key])
    elif payload is not None:
        return _coerce_float(payload)
    return None


def _run_nlp_score(answer_text: str, question_context: dict[str, Any]) -> tuple[float, Any]:
    module = load_module("nlp_scorer", "nlp_scorer.py")

    if hasattr(module, "NLPScorer"):
        scorer = module.NLPScorer()
        result = call_with_supported_signature(
            scorer.compute_overall_score,
            answer_text=answer_text,
            answer=answer_text,
            question=question_context.get("question"),
            ideal_answer=question_context.get("ideal_answer"),
            reference_answer=question_context.get("ideal_answer"),
            ideal_keywords=question_context.get("ideal_keywords", ""),
            expected_keywords=question_context.get("ideal_keywords", ""),
        )
    elif hasattr(module, "compute_score"):
        result = call_with_supported_signature(
            module.compute_score,
            answer=answer_text,
            answer_text=answer_text,
            ideal_keywords=question_context.get("ideal_keywords", ""),
            ideal_answer=question_context.get("ideal_answer"),
        )
    else:
        raise IntegrationError(
            "nlp_scorer.py does not expose a supported scoring interface."
        )

    score = _extract_score_value(result, ("overall_score", "final_score", "score", "nlp_score"))
    return _coerce_float(score), result


def _run_svm_label(
    cos_similarity: float,
    length_ratio: float,
    aligned_score: float,
    word_count: int,
) -> str:
    model = _load_svm_model()
    features = [[cos_similarity, length_ratio, aligned_score, word_count]]
    prediction = model.predict(features)
    if prediction is None or len(prediction) == 0:
        raise IntegrationError("SVM model returned no prediction.")
    return str(prediction[0])


def _run_knowledge_graph(
    answer_text: str, question_context: dict[str, Any]
) -> tuple[float, Any]:
    module = load_module("knowledge_graph", "knowledge_graph.py")
    if not hasattr(module, "KnowledgeGraphScorer"):
        raise IntegrationError(
            "knowledge_graph.py does not expose KnowledgeGraphScorer."
        )

    scorer = module.KnowledgeGraphScorer()
    result = call_with_supported_signature(
        scorer.score_answer,
        answer=answer_text,
        answer_text=answer_text,
        question=question_context.get("question"),
        ideal_answer=question_context.get("ideal_answer"),
        reference_answer=question_context.get("ideal_answer"),
        skill=question_context.get("skill"),
        sub_domain=question_context.get("sub_domain"),
    )

    score = _extract_score_value(result, ("kg_score", "score", "final_score"))
    return _coerce_float(score), result


def _run_ner(answer_text: str) -> list[dict[str, Any] | str]:
    module = load_module("ner_scorer", "ner_scorer.py")
    if not hasattr(module, "NERScorer"):
        raise IntegrationError("ner_scorer.py does not expose NERScorer.")

    scorer = module.NERScorer()
    entities = call_with_supported_signature(
        scorer.extract_entities,
        answer=answer_text,
        answer_text=answer_text,
    )
    if isinstance(entities, list):
        return entities
    if entities is None:
        return []
    return [entities]


def _run_feedback(
    answer_text: str,
    nlp_score: float,
    svm_label: str,
    kg_score: float,
    final_score: float,
    ner_entities: list[dict[str, Any] | str],
    question_context: dict[str, Any],
    word_count: int = 0,
    filler_count: int = 0,
    keyword_match_rate: float | None = None,
    missing_keywords: list[str] | None = None,
) -> dict[str, Any]:
    module = load_module("c4_feedback", "c4_feedback.py")
    if not hasattr(module, "generate_feedback"):
        raise IntegrationError("c4_feedback.py does not expose generate_feedback().")

    payload = call_with_supported_signature(
        module.generate_feedback,
        answer=answer_text,
        answer_text=answer_text,
        question=question_context.get("question"),
        ideal_answer=question_context.get("ideal_answer"),
        ideal_keywords=question_context.get("ideal_keywords", ""),
        skill=question_context.get("skill"),
        sub_domain=question_context.get("sub_domain"),
        nlp_score=nlp_score,
        svm_label=svm_label,
        kg_score=kg_score,
        final_score=final_score,
        ner_entities=ner_entities,
        word_count=word_count,
        filler_count=filler_count,
        keyword_match_rate=keyword_match_rate,
        missing_keywords=missing_keywords or [],
    )
    return normalize_feedback(payload)


# ── C1 Scoring formula helpers ─────────────────────────────────

def _compute_communication_quality(wpm: float | None, pause_count: int | None) -> float:
    """
    Map WPM and pause_count to a 0–100 Communication Quality score.
    Ideal interview pace: 120–150 WPM.
    """
    if wpm is None:
        base = 60.0  # neutral when voice data unavailable
    elif 120.0 <= wpm <= 150.0:
        base = 95.0
    elif 100.0 <= wpm < 120.0 or 150.0 < wpm <= 160.0:
        base = 80.0
    elif 80.0 <= wpm < 100.0 or 160.0 < wpm <= 180.0:
        base = 65.0
    else:
        base = 45.0

    # Penalise excessive pauses (each pause beyond 2 costs 5 points)
    if pause_count is not None and pause_count > 2:
        base = max(0.0, base - (pause_count - 2) * 5.0)

    return round(base, 2)


def _compute_engagement_score(
    engagement_label: str | None,
    engagement_baseline: float | None = None,
) -> float:
    """
    A1 Baseline Calibration: map engagement label to score, then adjust
    relative to the candidate's personal baseline.
    """
    label_key = (engagement_label or "").strip().lower()
    base = _ENGAGEMENT_SCORES.get(label_key, 60.0)  # neutral default

    if engagement_baseline is not None:
        # Score relative to personal baseline — reward above-baseline engagement
        deviation = base - engagement_baseline
        calibrated = base + deviation * 0.5  # amplify positive, soften negative
        return round(max(0.0, min(100.0, calibrated)), 2)

    return round(base, 2)


def _count_filler_words(text: str) -> int:
    return len(_FILLER_RE.findall(text))


def _compute_pace_filler_score(answer_text: str, wpm: float | None) -> tuple[float, int]:
    """
    Return (pace_filler_score 0–100, filler_count).
    Higher score = less penalty = better.
    Starts at 100 and deducts for each filler word beyond 3.
    """
    filler_count = _count_filler_words(answer_text)
    score = 100.0
    if filler_count > 3:
        score -= (filler_count - 3) * 10.0

    # Additional pace penalty when WPM is far outside ideal range
    if wpm is not None:
        if wpm < 80.0 or wpm > 200.0:
            score -= 15.0

    return round(max(0.0, min(100.0, score)), 2), filler_count


def _compute_c1_final_score(
    answer_quality: float,
    communication_quality: float,
    engagement_indicator: float,
    keyword_match: float,
    pace_filler_penalty: float,
) -> float:
    """
    C1 Formula:
    Final Score = 0.30 × Answer Quality
                + 0.25 × Communication Quality
                + 0.20 × Engagement Indicator
                + 0.15 × Keyword Match
                + 0.10 × Pace and Filler Penalty
    """
    score = (
        _C1_WEIGHTS["answer_quality"] * answer_quality
        + _C1_WEIGHTS["communication_quality"] * communication_quality
        + _C1_WEIGHTS["engagement_indicator"] * engagement_indicator
        + _C1_WEIGHTS["keyword_match"] * keyword_match
        + _C1_WEIGHTS["pace_filler_penalty"] * pace_filler_penalty
    )
    return round(max(0.0, min(100.0, score)), 2)


def run_scoring_pipeline(
    *,
    answer_text: str,
    cos_similarity: float,
    length_ratio: float,
    aligned_score: float,
    word_count: int,
    engagement_label: str | None = None,
    wpm: float | None = None,
    pause_count: int | None = None,
    question_context: dict[str, Any] | None = None,
    engagement_baseline: float | None = None,
) -> dict[str, Any]:
    question_context = question_context or {}

    nlp_score, nlp_payload = _run_nlp_score(answer_text, question_context)
    svm_label = _run_svm_label(cos_similarity, length_ratio, aligned_score, word_count)
    kg_score, kg_payload = _run_knowledge_graph(answer_text, question_context)
    ner_entities = _run_ner(answer_text)

    # ── Extract dual-signal NLP features (A3) ─────────────────
    keyword_match_rate: float | None = None
    missing_keywords: list[str] = []
    if isinstance(nlp_payload, dict):
        if "keyword_match_rate" in nlp_payload:
            keyword_match_rate = _coerce_float(nlp_payload["keyword_match_rate"])
        if "missing_keywords" in nlp_payload:
            missing_keywords = nlp_payload.get("missing_keywords") or []

    # ── C1 component scores ────────────────────────────────────
    comm_quality = _compute_communication_quality(wpm, pause_count)
    engagement = _compute_engagement_score(engagement_label, engagement_baseline)
    pace_filler_score, filler_count = _compute_pace_filler_score(answer_text, wpm)

    # Keyword match: prefer NLP scorer's rate; fall back to KG score
    if keyword_match_rate is not None:
        kw_match_score = keyword_match_rate * 100.0
    else:
        kw_match_score = _coerce_float(
            _extract_score_value(kg_payload, ("kg_score", "score", "final_score")), 0.0
        ) * 100.0

    # ── C1 Final Score ─────────────────────────────────────────
    final_score = _compute_c1_final_score(
        answer_quality=nlp_score,
        communication_quality=comm_quality,
        engagement_indicator=engagement,
        keyword_match=kw_match_score,
        pace_filler_penalty=pace_filler_score,
    )

    feedback = _run_feedback(
        answer_text=answer_text,
        nlp_score=nlp_score,
        svm_label=svm_label,
        kg_score=kg_score,
        final_score=final_score,
        ner_entities=ner_entities,
        question_context=question_context,
        word_count=word_count,
        filler_count=filler_count,
        keyword_match_rate=keyword_match_rate,
        missing_keywords=missing_keywords,
    )

    metadata = {
        "engagement_label": engagement_label,
        "wpm": _coerce_float(wpm, 0.0) if wpm is not None else None,
        "pause_count": int(pause_count) if pause_count is not None else None,
        "communication_quality": comm_quality,
        "engagement_score": engagement,
        "pace_filler_score": pace_filler_score,
        "filler_count": filler_count,
        "keyword_match_rate": keyword_match_rate,
    }

    return {
        "svm_label": svm_label,
        "nlp_score": round(nlp_score, 2),
        "kg_score": round(kg_score, 2),
        "ner_entities": ner_entities,
        "final_score": final_score,
        "feedback": feedback,
        "metadata": metadata,
    }

