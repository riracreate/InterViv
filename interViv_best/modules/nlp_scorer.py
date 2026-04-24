"""
nlp_scorer_v11.py — 3-Layer Hybrid Scoring System for interViv
================================================================
Replaces v10's single-pass scorer with a multi-layer architecture:

  Layer 1 — Core Content Match     (55%)
    ├─ TF-IDF Cosine similarity     (25%)
    ├─ Keyword coverage             (15%)
    └─ Key concept coverage         (15%)

  Layer 2 — Answer Quality         (25%)
    ├─ Technical depth              (8%)
    ├─ Logical structure/coherence  (7%)
    ├─ Accuracy (anti-gaming)       (5%)
    └─ Clarity & conciseness        (5%)

  Layer 3 — ML Confidence Judge    (20%)
    └─ SVM/RF label → numeric adj.

Smart modifiers applied AFTER blending:
  • Difficulty multiplier
  • Personal baseline calibration (after round 2)
  • Filler / repetition penalty
  • Trade-off / example / edge-case bonus

Pipeline-compatible:  NLPScorer().compute_overall_score(**kwargs) → dict
                      NLPScorer().get_feature_scores(**kwargs)     → dict
"""

from __future__ import annotations

import math
import re
from collections import Counter
from functools import lru_cache
from typing import Any

# ── Optional ML model (loaded lazily) ─────────────────────────────────────────
try:
    import joblib as _joblib
    _JOBLIB_OK = True
except ImportError:
    _JOBLIB_OK = False

# ── Optional semantic scorer (lazy import to keep start-up fast) ──────────────
import logging as _logging
_sem_logger = _logging.getLogger(__name__)

_semantic_scorer = None
_semantic_scorer_tried = False


def _get_semantic_scorer():
    global _semantic_scorer, _semantic_scorer_tried
    if _semantic_scorer_tried:
        return _semantic_scorer
    _semantic_scorer_tried = True
    try:
        from pathlib import Path as _Path
        import importlib.util as _ilu
        _here = _Path(__file__).parent
        _spec = _ilu.spec_from_file_location("semantic_scorer", _here / "semantic_scorer.py")
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _semantic_scorer = _mod.SemanticScorer()
    except Exception as exc:
        _sem_logger.error("nlp_scorer: failed to load SemanticScorer — %s", exc)
        _semantic_scorer = None
    return _semantic_scorer

# ── Stop words ────────────────────────────────────────────────────────────────
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "because", "but", "and", "or", "if", "while", "about", "up", "it",
    "its", "this", "that", "these", "those", "i", "me", "my", "we", "our",
    "you", "your", "he", "him", "his", "she", "her", "they", "them",
    "their", "what", "which", "who", "whom",
})

# Words that signal analytical/high-quality reasoning
_DEPTH_SIGNALS: frozenset[str] = frozenset({
    "because", "therefore", "however", "although", "whereas",
    "for example", "for instance", "specifically", "in particular",
    "trade-off", "tradeoff", "trade off", "alternatively",
    "on the other hand", "in contrast", "as a result",
    "this means", "which means", "the reason",
    "edge case", "edge-case", "corner case",
    "in practice", "real-world", "in production",
})

# Filler phrases that indicate vague / padded answers
_FILLER_PHRASES: list[str] = [
    "basically", "essentially", "kind of", "sort of", "you know",
    "i think", "i believe", "i guess", "i mean", "like i said",
    "as i mentioned", "as mentioned", "in general", "generally speaking",
    "it depends", "there are many", "there are various", "many ways",
    "different things", "different aspects", "lots of things",
]

# Difficulty → score multiplier table
_DIFFICULTY_MULTIPLIER: dict[str, float] = {
    "easy":   1.00,
    "medium": 1.05,
    "hard":   1.12,
}

# ML label → numeric adjustment (on 0-100 scale, applied at 20% weight)
_ML_LABEL_MAP: dict[str, float] = {
    "Good":    75.0,   # converts to positive influence
    "Average": 50.0,
    "Poor":    25.0,
}


# ══════════════════════════════════════════════════════════════════════════════
# Low-level text utilities
# ══════════════════════════════════════════════════════════════════════════════

def _tokenize(text: str) -> list[str]:
    """Lowercase, keep alphanumeric+special tech chars, remove stop words."""
    tokens = re.findall(r"\b[a-z][a-z0-9_#+.]*\b", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def _term_frequencies(tokens: list[str]) -> dict[str, float]:
    counts = Counter(tokens)
    total = len(tokens) or 1
    return {w: c / total for w, c in counts.items()}


def _cosine_similarity(tf_a: dict[str, float], tf_b: dict[str, float]) -> float:
    """Standard cosine similarity on TF vectors."""
    all_terms = set(tf_a) | set(tf_b)
    if not all_terms:
        return 0.0
    dot = sum(tf_a.get(t, 0.0) * tf_b.get(t, 0.0) for t in all_terms)
    mag_a = math.sqrt(sum(v * v for v in tf_a.values()))
    mag_b = math.sqrt(sum(v * v for v in tf_b.values()))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _normalize_phrase(text: str) -> str:
    return " ".join(_tokenize(text))


def _ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — Core Content Match helpers
# ══════════════════════════════════════════════════════════════════════════════

def _l1_tfidf_cosine(answer_tokens: list[str], ideal_tokens: list[str]) -> float:
    """
    TF-IDF cosine between answer and ideal.
    Returns 0.0–1.0.
    """
    if not ideal_tokens:
        # No ideal answer: score on answer self-quality
        return min(len(answer_tokens) / 30, 1.0) * 0.6

    tf_ans = _term_frequencies(answer_tokens)
    tf_ideal = _term_frequencies(ideal_tokens)
    return _cosine_similarity(tf_ans, tf_ideal)


def _l1_keyword_coverage(
    answer_text: str,
    answer_token_set: set[str],
    keywords_str: str,
) -> float:
    """
    Weighted keyword coverage: phrase-level (0.7) + token-level (0.3).
    Returns 0.0–1.0.
    """
    if not keywords_str or not keywords_str.strip():
        return 0.5

    phrases = [p.strip() for p in keywords_str.split(",") if p.strip()]
    if not phrases:
        return 0.5

    normalized_answer = _normalize_phrase(answer_text)
    phrase_hits = token_hits = token_total = 0

    for phrase in phrases:
        norm_phrase = _normalize_phrase(phrase)
        if norm_phrase and norm_phrase in normalized_answer:
            phrase_hits += 1
        phrase_toks = set(_tokenize(phrase))
        token_total += len(phrase_toks)
        token_hits += len(answer_token_set & phrase_toks)

    phrase_score = phrase_hits / len(phrases)
    token_score = token_hits / token_total if token_total else 0.5
    return min(0.7 * phrase_score + 0.3 * token_score, 1.0)


def _l1_key_concept_coverage(
    answer_tokens: list[str],
    ideal_tokens: list[str],
) -> float:
    """
    Checks bigram/trigram concept overlap between answer and ideal.
    Rewards answers that capture multi-word technical concepts.
    Returns 0.0–1.0.
    """
    if not ideal_tokens or len(ideal_tokens) < 2:
        return 0.5

    # Build concept candidates from ideal (bigrams + trigrams)
    ideal_bigrams  = set(_ngrams(ideal_tokens, 2))
    ideal_trigrams = set(_ngrams(ideal_tokens, 3))
    ans_bigrams    = set(_ngrams(answer_tokens, 2))
    ans_trigrams   = set(_ngrams(answer_tokens, 3))

    bi_hit = len(ideal_bigrams & ans_bigrams) / max(len(ideal_bigrams), 1)
    tri_hit = (
        len(ideal_trigrams & ans_trigrams) / max(len(ideal_trigrams), 1)
        if ideal_trigrams else 0.0
    )

    # Weight bigrams more; trigrams are bonus signal
    return min(0.65 * bi_hit + 0.35 * tri_hit, 1.0)


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — Answer Quality & Structure helpers
# ══════════════════════════════════════════════════════════════════════════════

def _l2_technical_depth(text: str, answer_tokens: list[str]) -> float:
    """
    Evaluates analytical depth:
    - Presence of reasoning / contrast / example signal phrases
    - Lexical richness (unique tokens / total)
    - Sentence count
    Returns 0.0–1.0.
    """
    text_lower = text.lower()

    # Signal phrase hits
    signal_hits = sum(1 for sig in _DEPTH_SIGNALS if sig in text_lower)
    signal_score = min(signal_hits / 4, 1.0)  # 4 signals = full

    # Lexical richness
    total_toks = len(answer_tokens) or 1
    unique_toks = len(set(answer_tokens))
    richness = min(unique_toks / total_toks * 2, 1.0)   # 0.5 ratio → 1.0

    # Sentence count (≥3 = full marks)
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    sentence_score = min(len(sentences) / 3, 1.0)

    return 0.45 * signal_score + 0.30 * richness + 0.25 * sentence_score


def _l2_logical_structure(text: str) -> float:
    """
    Detects logical connectives and answer organisation.
    Returns 0.0–1.0.
    """
    connectives = [
        "first", "second", "third", "finally", "lastly",
        "additionally", "furthermore", "moreover", "next",
        "initially", "subsequently", "consequently",
        "in summary", "to summarise", "in conclusion",
        "overall", "therefore", "thus", "hence",
    ]
    text_lower = text.lower()
    hits = sum(1 for c in connectives if c in text_lower)
    structure_score = min(hits / 3, 1.0)

    # Paragraph / sentence length variance (consistent = structured)
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    if len(sentences) >= 2:
        lengths = [len(s.split()) for s in sentences]
        avg = sum(lengths) / len(lengths)
        variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
        # Low variance ≈ rambling; moderate variance ≈ structured prose
        variance_score = min(math.sqrt(variance) / 10, 1.0)
    else:
        variance_score = 0.3

    return 0.60 * structure_score + 0.40 * variance_score


def _l2_accuracy_penalty(
    answer_tokens: list[str],
    ideal_tokens: list[str],
    answer_text: str,
) -> float:
    """
    Anti-gaming & accuracy checks:
    - Penalises excessive repetition (same content token > 3×)
    - Penalises filler phrase density
    - Rewards overlap with ideal's important (high-freq) terms
    Returns 0.0–1.0 (lower = worse).
    """
    # Repetition penalty
    if answer_tokens:
        counts = Counter(answer_tokens)
        total_toks = len(answer_tokens)
        repeated = sum(c for c in counts.values() if c > 3)
        rep_penalty = min(repeated / total_toks, 0.5)   # max 50% penalty
    else:
        rep_penalty = 0.0

    # Filler density
    text_lower = answer_text.lower()
    filler_hits = sum(1 for f in _FILLER_PHRASES if f in text_lower)
    filler_penalty = min(filler_hits * 0.08, 0.4)       # each filler = -8%

    # Ideal term overlap (rewards using the right vocabulary)
    if ideal_tokens:
        ideal_set = set(ideal_tokens)
        ans_set = set(answer_tokens)
        overlap = len(ideal_set & ans_set) / max(len(ideal_set), 1)
        vocab_bonus = min(overlap, 1.0)
    else:
        vocab_bonus = 0.5

    raw = vocab_bonus - rep_penalty - filler_penalty
    return max(0.0, min(raw, 1.0))


def _l2_clarity_conciseness(answer_tokens: list[str], ideal_tokens: list[str]) -> float:
    """
    Rewards answers that are appropriately concise:
    - 70%–160% of ideal length → full score
    - Too short OR excessively long → reduced score
    Returns 0.0–1.0.
    """
    ans_len = len(answer_tokens)
    ideal_len = len(ideal_tokens) or 50  # fallback

    ratio = ans_len / ideal_len
    if 0.70 <= ratio <= 1.60:
        return 1.0
    elif ratio < 0.70:
        return ratio / 0.70
    else:
        # Long answers: gentle penalty starting at 1.6×
        return max(0.4, 1.0 - (ratio - 1.60) * 0.25)


# ══════════════════════════════════════════════════════════════════════════════
# Smart modifier helpers
# ══════════════════════════════════════════════════════════════════════════════

def _bonus_advanced_signals(text: str) -> float:
    """
    Extra bonus (0.0–5.0 points) for:
    - Trade-off awareness
    - Real-world / production examples
    - Edge-case handling
    """
    text_lower = text.lower()
    bonus = 0.0
    if any(p in text_lower for p in ("trade-off", "tradeoff", "trade off", "pro and con")):
        bonus += 2.0
    if any(p in text_lower for p in ("in practice", "real-world", "in production", "deployed")):
        bonus += 1.5
    if any(p in text_lower for p in ("edge case", "edge-case", "corner case", "boundary")):
        bonus += 1.5
    return min(bonus, 5.0)


def _difficulty_multiplier(difficulty: str) -> float:
    return _DIFFICULTY_MULTIPLIER.get(difficulty.lower(), 1.0)


def _baseline_calibration(
    raw_score: float,
    baseline: float | None,
) -> float:
    """
    After the candidate's first 2 answers we have a personal baseline.
    Shift scores slightly toward baseline to reduce noise in early rounds.
    Weight: 15% baseline, 85% raw.
    """
    if baseline is None:
        return raw_score
    return 0.85 * raw_score + 0.15 * baseline


# ══════════════════════════════════════════════════════════════════════════════
# ML model integration
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def _load_ml_model(model_path: str) -> Any:
    """Load and cache SVM / RF model from disk."""
    if not _JOBLIB_OK:
        return None
    return _joblib.load(model_path)


def _ml_label_score(
    cos_sim: float,
    length_ratio: float,
    keyword_coverage: float,
    word_count: int,
    concept_coverage: float = 0.5,
    model_path: str | None = None,
) -> float:
    """
    Run the ML model and convert label to a numeric score (0–100).
    Falls back to 50 (neutral) if model unavailable.
    """
    if not model_path:
        return 50.0

    try:
        model = _load_ml_model(model_path)
        if model is None:
            return 50.0
        feature_count = int(getattr(model, "n_features_in_", 4) or 4)
        if feature_count >= 5:
            features = [[
                cos_sim,
                length_ratio,
                keyword_coverage,
                word_count,
                concept_coverage,
            ]]
        else:
            features = [[cos_sim, length_ratio, keyword_coverage, word_count]]
        label = str(model.predict(features)[0])
        return _ML_LABEL_MAP.get(label, 50.0)
    except Exception:   # noqa: BLE001  — never crash the scorer
        return 50.0


# ══════════════════════════════════════════════════════════════════════════════
# Main scorer class
# ══════════════════════════════════════════════════════════════════════════════

class NLPScorer:
    """
    3-Layer hybrid scorer for interViv.

    Parameters
    ----------
    model_path : str | None
        Absolute path to a joblib-serialised SVM or RF model.
        If None, Layer 3 is replaced by a neutral 50-point placeholder.
    """

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path

    # ── Public API ────────────────────────────────────────────────────────────

    def compute_overall_score(
        self,
        answer_text: str | None = None,
        answer: str | None = None,
        question: str | None = None,
        ideal_answer: str | None = None,
        reference_answer: str | None = None,
        ideal_keywords: str | None = None,
        expected_keywords: str | None = None,
        difficulty: str = "medium",
        candidate_baseline: float | None = None,
    ) -> dict[str, Any]:
        """
        Compute the final score.

        Returns
        -------
        dict with keys:
            overall_score       float 0–100  (primary output)
            layer1_score        float 0–100
            layer2_score        float 0–100
            layer3_score        float 0–100
            cosine_similarity   float 0–1
            keyword_coverage    float 0–1
            concept_coverage    float 0–1
            depth_score         float 0–1
            structure_score     float 0–1
            accuracy_score      float 0–1
            clarity_score       float 0–1
            difficulty_bonus    float
            advanced_bonus      float
            svm_label_score     float 0–100
        """
        features = self.get_feature_scores(
            answer_text=answer_text,
            answer=answer,
            question=question,
            ideal_answer=ideal_answer,
            reference_answer=reference_answer,
            ideal_keywords=ideal_keywords,
            expected_keywords=expected_keywords,
            difficulty=difficulty,
            candidate_baseline=candidate_baseline,
        )
        return features

    def get_feature_scores(
        self,
        answer_text: str | None = None,
        answer: str | None = None,
        question: str | None = None,
        ideal_answer: str | None = None,
        reference_answer: str | None = None,
        ideal_keywords: str | None = None,
        expected_keywords: str | None = None,
        difficulty: str = "medium",
        candidate_baseline: float | None = None,
    ) -> dict[str, Any]:
        """Return the full feature breakdown alongside the final score."""

        text   = answer_text or answer or ""
        ideal  = ideal_answer or reference_answer or ""
        kw_str = ideal_keywords or expected_keywords or ""

        # ── Early-exit for empty answers ─────────────────────────────────────
        if not text.strip():
            return self._zero_result()

        # ── Tokenise ─────────────────────────────────────────────────────────
        ans_tokens  = _tokenize(text)
        ideal_tokens = _tokenize(ideal)
        ans_token_set = set(ans_tokens)
        word_count  = len(text.split())

        # ══════════════════════════════════════════════════════════════════════
        # LAYER 1 — Core Content Match (55%)
        # ══════════════════════════════════════════════════════════════════════
        tfidf_cos     = _l1_tfidf_cosine(ans_tokens, ideal_tokens)
        kw_coverage   = _l1_keyword_coverage(text, ans_token_set, kw_str)
        concept_cov   = _l1_key_concept_coverage(ans_tokens, ideal_tokens)

        # Blend TF-IDF with semantic cosine (60% semantic, 40% TF-IDF).
        # Falls back to pure TF-IDF when semantic scorer is unavailable or ideal is empty.
        semantic_sim: float | None = None
        _sem = _get_semantic_scorer()
        if _sem is not None:
            semantic_sim = _sem.score(text, ideal)

        if semantic_sim is not None:
            cos_sim = 0.40 * tfidf_cos + 0.60 * semantic_sim
        else:
            cos_sim = tfidf_cos

        layer1_raw = (
            0.25 * cos_sim       # blended cosine (semantic+TF-IDF or pure TF-IDF)
            + 0.15 * kw_coverage   # keyword coverage
            + 0.15 * concept_cov   # bigram/trigram concept overlap
        ) / 0.55                  # normalise to [0, 1]

        layer1_score = min(layer1_raw * 100, 100.0)

        # ══════════════════════════════════════════════════════════════════════
        # LAYER 2 — Quality & Structure (25%)
        # ══════════════════════════════════════════════════════════════════════
        depth_score     = _l2_technical_depth(text, ans_tokens)
        structure_score = _l2_logical_structure(text)
        accuracy_score  = _l2_accuracy_penalty(ans_tokens, ideal_tokens, text)
        clarity_score   = _l2_clarity_conciseness(ans_tokens, ideal_tokens)

        layer2_raw = (
            0.08 * depth_score
            + 0.07 * structure_score
            + 0.05 * accuracy_score
            + 0.05 * clarity_score
        ) / 0.25                  # normalise to [0, 1]

        layer2_score = min(layer2_raw * 100, 100.0)

        # ══════════════════════════════════════════════════════════════════════
        # LAYER 3 — ML Confidence (20%)
        # ══════════════════════════════════════════════════════════════════════
        ideal_len    = len(ideal_tokens) or 50
        length_ratio = min(len(ans_tokens) / ideal_len, 3.0)

        svm_label_score = _ml_label_score(
            cos_sim=cos_sim,
            length_ratio=length_ratio,
            keyword_coverage=kw_coverage,
            word_count=word_count,
            concept_coverage=concept_cov,
            model_path=self.model_path,
        )
        layer3_score = svm_label_score  # already on 0–100 scale

        # ══════════════════════════════════════════════════════════════════════
        # Weighted blend
        # ══════════════════════════════════════════════════════════════════════
        blended = (
            0.55 * layer1_score
            + 0.25 * layer2_score
            + 0.20 * layer3_score
        )

        # ── Modifiers ────────────────────────────────────────────────────────
        diff_mult     = _difficulty_multiplier(difficulty)
        advanced_bonus = _bonus_advanced_signals(text)

        blended_with_mods = min(blended * diff_mult + advanced_bonus, 100.0)

        # ── Baseline calibration ─────────────────────────────────────────────
        final_score = _baseline_calibration(blended_with_mods, candidate_baseline)
        final_score = round(max(0.0, min(final_score, 100.0)), 2)

        return {
            # ── Primary output ───────────────────────────────────────────────
            "overall_score":    final_score,

            # ── Layer scores (0–100) ─────────────────────────────────────────
            "layer1_score":     round(layer1_score, 2),
            "layer2_score":     round(layer2_score, 2),
            "layer3_score":     round(layer3_score, 2),

            # ── Sub-feature scores (0–1) ─────────────────────────────────────
            "cosine_similarity":  round(cos_sim, 4),
            "tfidf_score":        round(tfidf_cos, 4),
            "semantic_score":     round(semantic_sim, 4) if semantic_sim is not None else None,
            "keyword_coverage":   round(kw_coverage, 4),
            "concept_coverage":   round(concept_cov, 4),
            "depth_score":        round(depth_score, 4),
            "structure_score":    round(structure_score, 4),
            "accuracy_score":     round(accuracy_score, 4),
            "clarity_score":      round(clarity_score, 4),

            # ── Modifiers ────────────────────────────────────────────────────
            "difficulty_bonus":   round(diff_mult - 1.0, 4),
            "advanced_bonus":     round(advanced_bonus, 2),
            "svm_label_score":    round(svm_label_score, 2),

            # ── Legacy keys (keeps pipeline.py happy) ────────────────────────
            "length_score":       round(clarity_score, 4),
            "depth_score_legacy": round(depth_score, 4),
        }

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _zero_result() -> dict[str, Any]:
        keys = [
            "overall_score", "layer1_score", "layer2_score", "layer3_score",
            "cosine_similarity", "tfidf_score", "keyword_coverage", "concept_coverage",
            "depth_score", "structure_score", "accuracy_score", "clarity_score",
            "difficulty_bonus", "advanced_bonus", "svm_label_score",
            "length_score", "depth_score_legacy",
        ]
        result = {k: 0.0 for k in keys}
        result["semantic_score"] = None
        return result
