"""Shared scoring features for scorer v4 (training and serving).

One builder used by both ``scripts/train_scorer_v4.py`` and the v4 serving
path in ``backend/scoring/pipeline.py`` so train/serve cannot drift.

Features (all 0-1, no length or pinned-keyword signal by design):
- ``semantic_score``: MiniLM cosine(answer, reference); TF-IDF fallback.
- ``tfidf_score``: TF-IDF cosine(answer, reference).
- ``concept_coverage``: strict bundle concept coverage (proposition and
  semantic matches only) when required concepts are supplied, else the
  reference n-gram concept coverage.
- ``ideal_content_recall``: share of reference content tokens present.
- ``max_sentence_semantic_sim``: best sentence-level semantic match.
"""

from __future__ import annotations

import re
from typing import Any

FEATURE_NAMES: tuple[str, ...] = (
    "semantic_score",
    "tfidf_score",
    "concept_coverage",
    "ideal_content_recall",
    "max_sentence_semantic_sim",
)

_STOPWORDS = frozenset({
    "the", "is", "a", "an", "of", "to", "and", "or", "in", "on", "at",
    "what", "why", "how", "when", "where", "which", "who", "it", "are",
    "was", "were", "be", "can", "could", "do", "does", "would", "should",
    "for", "by", "as", "with", "that", "this", "from", "into",
})

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _clamp01(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _content_tokens(text: str) -> set[str]:
    toks = re.findall(r"[a-zA-Z]+", (text or "").lower())
    return {t for t in toks if t not in _STOPWORDS and len(t) > 2}


def strict_concept_coverage(
    answer_text: str,
    required_concepts: list[Any] | None,
) -> float | None:
    """Proposition+semantic supported share under evaluator strict mode.

    Returns None when no required concepts are supplied.
    """
    if not required_concepts:
        return None
    from modules.concept_evaluator_v3 import evaluate_answer

    result = evaluate_answer(
        answer_text=answer_text,
        bundle_content={"required_concepts": list(required_concepts)},
        strict=True,
    )
    coverage = result.get("coverage") or {}
    n_required = int(coverage.get("n_required") or 0)
    if n_required <= 0:
        return None
    return _clamp01(int(coverage.get("k_supported") or 0) / n_required)


def build_scoring_features(
    *,
    answer_text: str,
    ideal_answer: str,
    required_concepts: list[Any] | None = None,
    semantic_scorer: Any | None = None,
) -> dict[str, float]:
    """Build the five v4 features for one answer/reference pair."""
    from modules import nlp_scorer

    answer = answer_text or ""
    ideal = ideal_answer or ""
    ans_tokens = nlp_scorer._tokenize(answer)
    ideal_tokens = nlp_scorer._tokenize(ideal)

    tfidf_score = _clamp01(nlp_scorer._l1_tfidf_cosine(ans_tokens, ideal_tokens))

    scorer = semantic_scorer
    if scorer is None:
        scorer = nlp_scorer._get_semantic_scorer()

    semantic_score: float | None = None
    if scorer is not None and ideal.strip():
        try:
            semantic_score = scorer.score(answer, ideal)
        except Exception:
            semantic_score = None
    semantic_value = _clamp01(semantic_score) if semantic_score is not None else tfidf_score

    concept = strict_concept_coverage(answer, required_concepts)
    if concept is None:
        concept = _clamp01(nlp_scorer._l1_key_concept_coverage(ans_tokens, ideal_tokens))

    ideal_content = _content_tokens(ideal)
    if ideal_content:
        recall = len(_content_tokens(answer) & ideal_content) / len(ideal_content)
    else:
        recall = 0.0

    max_sent = tfidf_score
    if scorer is not None and ideal.strip():
        sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(answer) if s.strip()]
        best: float | None = None
        for sentence in sentences[:24]:
            try:
                sim = scorer.max_similarity(sentence, [ideal])
            except Exception:
                sim = None
            if sim is not None:
                best = float(sim) if best is None else max(best, float(sim))
        if best is not None:
            max_sent = _clamp01(best)

    return {
        "semantic_score": round(semantic_value, 4),
        "tfidf_score": round(tfidf_score, 4),
        "concept_coverage": round(_clamp01(concept), 4),
        "ideal_content_recall": round(_clamp01(recall), 4),
        "max_sentence_semantic_sim": round(max_sent, 4),
    }


def feature_vector(features: dict[str, float]) -> list[float]:
    """Ordered feature vector matching FEATURE_NAMES."""
    return [float(features[name]) for name in FEATURE_NAMES]
