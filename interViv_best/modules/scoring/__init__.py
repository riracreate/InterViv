"""Typed round scoring dispatch (Phase 1).

Routes an answered round to the scorer for its ``round_type``. Phase 1 ships
one arm only: ``technical_short_answer`` runs the existing deterministic
pipeline. Phase 2 adds new arms (e.g. MCQ) here, without reopening the
answer route.

Deterministic like everything it calls: no LLM, no reviewer, no tie-breaker
(see AGENTS.md section 6). Unknown types raise; they never fall back.
"""

from __future__ import annotations

from typing import Any

from backend.scoring.pipeline import run_scoring_pipeline

TECHNICAL_SHORT_ANSWER = "technical_short_answer"


class UnsupportedRoundTypeError(ValueError):
    """Raised when a round names a type with no scoring arm."""


def score_round(
    *,
    round_type: str | None,
    answer_text: str,
    word_count: int = 0,
    engagement_label: str | None = None,
    wpm: float | None = None,
    pause_count: int | None = None,
    question_context: dict[str, Any] | None = None,
    difficulty: str = "medium",
    candidate_baseline: float | None = None,
) -> dict[str, Any]:
    """Score one answered round with the scorer for its type."""
    # Only in-memory shim documents predate round_type: after the Phase 1
    # backfill, round_type is never null in Postgres, so the None arm below
    # exists solely for those shims. Do not extend it into a general
    # fallback: unknown non-null types must raise (fail loudly).
    if round_type is None:
        round_type = TECHNICAL_SHORT_ANSWER
    if round_type == TECHNICAL_SHORT_ANSWER:
        return run_scoring_pipeline(
            answer_text=answer_text,
            word_count=word_count,
            engagement_label=engagement_label,
            wpm=wpm,
            pause_count=pause_count,
            question_context=question_context,
            difficulty=difficulty,
            candidate_baseline=candidate_baseline,
        )
    raise UnsupportedRoundTypeError(
        f"Unsupported round type: {round_type!r}. "
        "Add a scoring arm in modules/scoring instead of falling back."
    )
