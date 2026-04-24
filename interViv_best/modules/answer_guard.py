"""
answer_guard.py — Anti-gaming quality gate for interViv.

Runs BEFORE the NLP scorer. Returns a cap instruction that pipeline.py
applies to final_score after scoring. Detections are evaluated in order
and the first match wins.
"""

from __future__ import annotations

import re
from collections import Counter

_GIBBERISH_PATTERNS = re.compile(r"(asdf|qwer|jkl|zxcv|hjkl|bnm)")

_VOWELS = frozenset("aeiouAEIOU")


def _vowel_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c in _VOWELS) / len(letters)


def _word_tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def check_answer_quality(answer_text: str, ideal_keywords: str = "") -> dict:
    """
    Evaluate answer for anti-gaming signals.

    Returns
    -------
    dict with keys:
        cap_required  bool   — whether a score cap should be applied
        score_cap     int    — maximum allowed score (ignored if cap_required=False)
        reason        str    — human-readable slug for the triggered rule
    """
    text = (answer_text or "").strip()

    # ── Rule 1: Empty / too tiny ─────────────────────────────────────────────
    if len(text) < 5:
        return {"cap_required": True, "score_cap": 5, "reason": "empty"}

    # ── Rule 2: Gibberish ─────────────────────────────────────────────────────
    if _vowel_ratio(text) < 0.30 or _GIBBERISH_PATTERNS.search(text.lower()):
        return {"cap_required": True, "score_cap": 10, "reason": "gibberish"}

    # ── Rule 3: Repeated tokens ───────────────────────────────────────────────
    tokens = _word_tokens(text)
    if tokens:
        counts = Counter(tokens)
        most_common_count = counts.most_common(1)[0][1]
        if most_common_count / len(tokens) > 0.40:
            return {"cap_required": True, "score_cap": 15, "reason": "repetition"}

    # ── Rule 4: Too short ─────────────────────────────────────────────────────
    word_count = len(text.split())
    if word_count < 12:
        return {"cap_required": True, "score_cap": 20, "reason": "too_short"}

    # ── Rule 5: Keyword stuffing ──────────────────────────────────────────────
    if ideal_keywords and ideal_keywords.strip() and tokens:
        kw_tokens: set[str] = set()
        for kw in ideal_keywords.split(","):
            kw_tokens.update(_word_tokens(kw))
        if kw_tokens:
            stuffed = sum(1 for t in tokens if t in kw_tokens)
            kw_ratio = stuffed / len(tokens)
            # High keyword ratio with very few non-keyword tokens = stuffing
            non_kw_tokens = [t for t in tokens if t not in kw_tokens]
            if kw_ratio > 0.30 and len(non_kw_tokens) < 8:
                return {"cap_required": True, "score_cap": 35, "reason": "keyword_stuffing"}

    return {"cap_required": False, "score_cap": 100, "reason": ""}
