"""Pure, in-sample answer-band classifier. No session/scoring integration."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from backend.config import (
    BAND_NONANSWER_MIN_WORDS, BAND_NONANSWER_MAX_SCORE,
    BAND_WRONG_MAX_SCORE, BAND_WRONG_MAX_CORRECTNESS,
    BAND_STRONG_MIN_SCORE, BAND_STRONG_MIN_CORRECTNESS, BAND_VAGUE_MAX_DEPTH,
)

NONANSWER_GUARDS = frozenset({
    "empty", "gibberish", "repetition", "too_short", "off_topic",
    "question_parroting", "low_density",
})
REFUSAL_PHRASES = frozenset({"i don't know", "i do not know", "no idea", "not sure", "skip", "pass"})
ANSWER_BANDS = frozenset({"nonanswer", "wrong", "vague", "adequate", "strong"})


def classify_answer_band(*, final_score: float, rubric: Mapping[str, float],
                         svm_label: str, guard_type: str | None, word_count: int,
                         answer_text: str, missed_concepts: Sequence[str]) -> str:
    """Total partition for finite inputs; invalid numeric inputs fail explicitly.

    `missed_concepts` is the existing binary diagnostic list. Confidence,
    generic filtering and probe availability are separate audit questions;
    this classifier does not select or authorize any concept probe.
    """
    correctness = float(rubric.get("correctness", 0.0))
    depth = float(rubric.get("depth", 0.0))
    if not all(math.isfinite(v) for v in (final_score, correctness, depth)):
        raise ValueError("Band inputs must be finite")
    if (guard_type in NONANSWER_GUARDS
        or answer_text.strip().lower().rstrip(".!?") in REFUSAL_PHRASES
        or (word_count < BAND_NONANSWER_MIN_WORDS and final_score < BAND_NONANSWER_MAX_SCORE
            and guard_type != "truncated_fragment")):
        return "nonanswer"
    if (final_score < BAND_WRONG_MAX_SCORE or correctness < BAND_WRONG_MAX_CORRECTNESS
        or svm_label == "Poor" or guard_type in {"entity_swap", "truncated_fragment"}):
        return "wrong"
    if (final_score >= BAND_STRONG_MIN_SCORE and correctness >= BAND_STRONG_MIN_CORRECTNESS
        and not guard_type):
        return "strong"
    if missed_concepts and (final_score < BAND_STRONG_MIN_SCORE or depth < BAND_VAGUE_MAX_DEPTH):
        return "vague"
    return "adequate"
