"""Shared scoring schema for deterministic interViv answer scoring.

This module names the scoring contract used by the Python pipeline. It does
not call an LLM and does not replace the calibrated final-score formula.
"""

from __future__ import annotations

import os
from typing import Any

SCORING_SCHEMA_VERSION = "rubric_v1"

# Scorer version flag. v3 stays the default; v4 is explicit opt-in only.
SCORER_VERSION_ENV = "SCORER_VERSION"
SUPPORTED_SCORER_VERSIONS = ("v3", "v4")


def current_scorer_version() -> str:
    """Resolved scorer version for this process (``v3`` unless opted in)."""
    raw = (os.getenv(SCORER_VERSION_ENV) or "v3").strip().lower()
    return raw if raw in SUPPORTED_SCORER_VERSIONS else "v3"
RUBRIC_SCALE = "0-10"

RUBRIC_WEIGHTS: dict[str, float] = {
    "correctness": 0.35,
    "coverage": 0.25,
    "depth": 0.20,
    "clarity": 0.20,
}

FINAL_SCORE_WEIGHTS: dict[str, float] = {
    "semantic_or_lexical": 0.45,
    "classifier": 0.25,
    "keyword": 0.20,
    "tfidf": 0.10,
}

# v4 keeps the v3 slot weights; the keyword slot carries strict concept
# coverage when a bundle supplies required_concepts, otherwise its weight
# is renormalized across the remaining terms (see pipeline v4).
FINAL_SCORE_WEIGHTS_V4: dict[str, float] = {
    "semantic_or_lexical": 0.45,
    "model": 0.25,
    "keyword": 0.20,
    "tfidf": 0.10,
}

KG_BONUS_MAX = 4.0
NER_BONUS_PER_ENTITY = 0.4
NER_BONUS_MAX_ENTITIES = 5.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(float(value), high))


def _to_unit(value: Any, default: float = 0.0) -> float:
    """Normalize either a 0-1 signal or a 0-100 signal into 0-1."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if numeric > 1.0:
        numeric = numeric / 100.0
    return _clamp(numeric)


def _length_fit(length_ratio: Any) -> float:
    """Score how close answer length is to the reference length.

    A ratio near 1 is best. Very short or very long answers are still allowed
    to score, but they contribute less to the clarity dimension.
    """
    try:
        ratio = float(length_ratio)
    except (TypeError, ValueError):
        return 0.6

    if ratio <= 0:
        return 0.0
    if 0.5 <= ratio <= 1.6:
        return 1.0
    if ratio < 0.5:
        return _clamp(ratio / 0.5)
    return _clamp(1.0 - min(ratio - 1.6, 2.0) * 0.25, 0.5, 1.0)


def _round_10(unit_value: float) -> float:
    return round(_clamp(unit_value) * 10.0, 2)


def _apply_guard_cap(scores: dict[str, float], score_cap: Any | None) -> tuple[dict[str, float], bool]:
    if score_cap is None:
        return scores, False
    try:
        max_dimension_score = _clamp(float(score_cap) / 100.0) * 10.0
    except (TypeError, ValueError):
        return scores, False
    return {
        key: round(min(value, max_dimension_score), 2)
        for key, value in scores.items()
    }, True


def build_rubric_scores(
    *,
    semantic_component: Any,
    classifier_component: Any,
    keyword_coverage: Any,
    concept_coverage: Any,
    kg_score: Any,
    depth_score: Any,
    structure_score: Any,
    clarity_score: Any,
    length_ratio: Any,
    score_cap: Any | None = None,
) -> dict[str, Any]:
    """Build named 0-10 rubric scores from existing deterministic signals."""
    semantic = _to_unit(semantic_component)
    classifier = _to_unit(classifier_component, default=0.5)
    keyword = _to_unit(keyword_coverage)
    concept = _to_unit(concept_coverage)
    kg = _to_unit(kg_score)
    depth_signal = _to_unit(depth_score)
    structure = _to_unit(structure_score)
    clarity = _to_unit(clarity_score)
    length = _length_fit(length_ratio)

    scores = {
        "correctness": _round_10((0.70 * semantic) + (0.30 * classifier)),
        "coverage": _round_10((0.45 * keyword) + (0.35 * concept) + (0.20 * kg)),
        "depth": _round_10((0.70 * depth_signal) + (0.30 * kg)),
        "clarity": _round_10((0.45 * structure) + (0.40 * clarity) + (0.15 * length)),
    }
    scores, guard_capped = _apply_guard_cap(scores, score_cap)
    weighted_score = round(
        sum(scores[name] * RUBRIC_WEIGHTS[name] for name in RUBRIC_WEIGHTS),
        2,
    )

    return {
        "version": SCORING_SCHEMA_VERSION,
        "scale": RUBRIC_SCALE,
        "weights": dict(RUBRIC_WEIGHTS),
        "correctness": scores["correctness"],
        "coverage": scores["coverage"],
        "depth": scores["depth"],
        "clarity": scores["clarity"],
        "weighted_score": weighted_score,
        "guard_capped": guard_capped,
    }


def build_concepts_summary(
    *,
    covered_concepts: list[str] | tuple[str, ...] | None,
    missing_concepts: list[str] | tuple[str, ...] | None,
    question_concepts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "covered": [str(item) for item in (covered_concepts or []) if str(item).strip()],
        "missing": [str(item) for item in (missing_concepts or []) if str(item).strip()],
        **(question_concepts or {}),
    }


def build_guard_summary(
    guard: dict[str, Any],
    effective_guard: dict[str, Any],
    *,
    softened: bool = False,
) -> dict[str, Any]:
    guards_fired = guard.get("guards_fired", []) or []
    score_caps = [
        item.get("score_cap")
        for item in guards_fired
        if isinstance(item, dict) and item.get("score_cap") is not None
    ]
    applied = bool(effective_guard.get("cap_required"))
    return {
        "applied": applied,
        "reason": effective_guard.get("reason") if applied else None,
        "raw_reason": guard.get("reason") or None,
        "score_cap": effective_guard.get("score_cap") if applied else None,
        "score_caps": score_caps,
        "guards_fired": guards_fired,
        "softened": bool(softened),
    }
