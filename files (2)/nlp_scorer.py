"""
nlp_scorer.py — A3 Dual Signal NLP Scoring Module
Uses TF-IDF similarity AND semantic similarity (sentence-transformers) as
separate features to catch synonyms.  Semantic similarity falls back
gracefully when sentence-transformers is not available.
"""
from __future__ import annotations

import math
import re
from typing import Any


# ── Pure-Python TF-IDF helpers ─────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-z]+\b", text.lower())


def _tf(tokens: list[str]) -> dict[str, float]:
    freq: dict[str, int] = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    n = len(tokens) or 1
    return {t: c / n for t, c in freq.items()}


def _cosine_tfidf(text_a: str, text_b: str) -> float:
    """Return cosine similarity between two texts using simple TF vectors."""
    tf_a = _tf(_tokenize(text_a))
    tf_b = _tf(_tokenize(text_b))
    vocab = set(tf_a) | set(tf_b)
    dot = sum(tf_a.get(w, 0.0) * tf_b.get(w, 0.0) for w in vocab)
    mag_a = math.sqrt(sum(v ** 2 for v in tf_a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in tf_b.values()))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def _keyword_match_rate(answer: str, keywords: str) -> float:
    """Return fraction of expected keywords present in the answer (0.0–1.0)."""
    if not keywords:
        return 0.0
    kw_list = [k.strip().lower() for k in re.split(r"[,\s]+", keywords) if k.strip()]
    if not kw_list:
        return 0.0
    ans_lower = answer.lower()
    matched = sum(1 for kw in kw_list if kw in ans_lower)
    return matched / len(kw_list)


def _extract_missing_keywords(answer: str, keywords: str) -> list[str]:
    """Return the list of keywords absent from the answer."""
    if not keywords:
        return []
    kw_list = [k.strip() for k in re.split(r"[,\s]+", keywords) if k.strip()]
    ans_lower = answer.lower()
    return [kw for kw in kw_list if kw.lower() not in ans_lower]


# ── NLPScorer ──────────────────────────────────────────────────

class NLPScorer:
    """
    A3 Dual Signal Scorer:
    - Signal 1: TF-IDF cosine similarity (pure Python, always available)
    - Signal 2: Semantic similarity via sentence-transformers all-MiniLM-L6-v2
                (optional — silently falls back to TF-IDF when unavailable)
    """

    def __init__(self) -> None:
        self._semantic_model: Any = None
        self._semantic_available: bool | None = None

    def _try_load_semantic_model(self) -> bool:
        if self._semantic_available is not None:
            return self._semantic_available
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._semantic_model = SentenceTransformer("all-MiniLM-L6-v2")
            self._semantic_available = True
        except Exception:
            self._semantic_available = False
        return self._semantic_available  # type: ignore[return-value]

    def _semantic_similarity(self, text_a: str, text_b: str) -> float | None:
        """Return cosine similarity in [0, 1] or None if unavailable."""
        if not self._try_load_semantic_model():
            return None
        try:
            import numpy as np  # type: ignore
            emb_a, emb_b = self._semantic_model.encode([text_a, text_b])
            dot = float(np.dot(emb_a, emb_b))
            mag = float(np.linalg.norm(emb_a) * np.linalg.norm(emb_b))
            return dot / mag if mag > 0.0 else 0.0
        except Exception:
            return None

    def compute_overall_score(
        self,
        answer_text: str | None = None,
        answer: str | None = None,
        question: str | None = None,
        ideal_answer: str | None = None,
        reference_answer: str | None = None,
        ideal_keywords: str | None = None,
        expected_keywords: str | None = None,
    ) -> dict[str, Any]:
        text = answer_text or answer or ""
        reference = ideal_answer or reference_answer or ""
        keywords = ideal_keywords or expected_keywords or ""

        if not text.strip():
            return {
                "overall_score": 0.0,
                "tfidf_score": 0.0,
                "semantic_score": 0.0,
                "keyword_match_rate": 0.0,
                "missing_keywords": _extract_missing_keywords(text, keywords),
            }

        # Signal 1: TF-IDF similarity
        tfidf_sim = _cosine_tfidf(text, reference) if reference else 0.0

        # Signal 2: Semantic similarity (A3 — catches synonyms)
        semantic_sim = self._semantic_similarity(text, reference) if reference else None

        # Blend: equal weight when both available; fall back to TF-IDF alone
        if semantic_sim is not None:
            combined_sim = 0.5 * tfidf_sim + 0.5 * semantic_sim
            effective_semantic = semantic_sim
        else:
            combined_sim = tfidf_sim
            effective_semantic = tfidf_sim  # proxy when model unavailable

        kw_rate = _keyword_match_rate(text, keywords)
        missing = _extract_missing_keywords(text, keywords)

        # overall_score: 70% similarity + 30% keyword coverage, scaled 0–100
        overall_score = min(100.0, (0.70 * combined_sim + 0.30 * kw_rate) * 100.0)

        return {
            "overall_score": round(overall_score, 2),
            "tfidf_score": round(tfidf_sim, 4),
            "semantic_score": round(effective_semantic, 4),
            "keyword_match_rate": round(kw_rate, 4),
            "missing_keywords": missing,
        }
