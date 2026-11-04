"""Typed round scoring dispatch (Phase 1, Phase 2 & Phase C/E).

Routes an answered round to the scorer for its ``round_type``:
- ``technical_short_answer``: runs the existing 3-layer deterministic NLP pipeline.
- ``mcq``: exact-match multi-question deterministic aggregation.
- ``sql``: sandboxed multi-case SQLite evaluation.
- ``coding``: execution-outcome aggregation over visible/hidden pass rates.
- ``system_design``: structured self-assessment aggregation (no diagram judge).
- ``ml_primitives``: executed NumPy cases vs the pack oracle (v1-ml-primitives).

Deterministic like everything it calls: no LLM, no reviewer, no tie-breaker
(see AGENTS.md section 6). Unknown types raise; they never fall back.
"""

from __future__ import annotations

import json
from typing import Any

from backend.scoring.pipeline import run_scoring_pipeline

TECHNICAL_SHORT_ANSWER = "technical_short_answer"
MCQ = "mcq"
SQL = "sql"
CODING = "coding"
SYSTEM_DESIGN = "system_design"
ML_PRIMITIVES = "ml_primitives"


class UnsupportedRoundTypeError(ValueError):
    """Raised when a round names a type with no scoring arm."""


def score_round(
    *,
    round_type: str | None,
    answer_text: str | None = None,
    answers: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
    word_count: int = 0,
    engagement_label: str | None = None,
    wpm: float | None = None,
    pause_count: int | None = None,
    question_context: dict[str, Any] | None = None,
    difficulty: str = "medium",
    candidate_baseline: float | None = None,
    rubric_ratings: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Score one answered round with the scorer for its type."""
    if round_type is None:
        round_type = TECHNICAL_SHORT_ANSWER

    if round_type == TECHNICAL_SHORT_ANSWER:
        return run_scoring_pipeline(
            answer_text=answer_text or "",
            word_count=word_count,
            engagement_label=engagement_label,
            wpm=wpm,
            pause_count=pause_count,
            question_context=question_context or {},
            difficulty=difficulty,
            candidate_baseline=candidate_baseline,
        )

    if round_type == MCQ:
        from modules.scoring.mcq import score_mcq_round

        q_ctx = question_context or {}
        assigned = q_ctx.get("questions")
        if not assigned and "id" in q_ctx:
            # Single question context fallback
            assigned = [q_ctx]
        assigned = assigned or []

        # If answers is None but answer_text is provided, parse JSON list/dict
        if answers is None and answer_text:
            try:
                parsed = json.loads(answer_text)
                if isinstance(parsed, list):
                    answers = parsed
                elif isinstance(parsed, dict) and "answers" in parsed:
                    answers = parsed["answers"]
                elif isinstance(parsed, dict):
                    answers = [parsed]
            except Exception:
                answers = (
                    [{"question_id": assigned[0]["id"],
                      "selected_option_ids": [answer_text.strip()]}]
                    if assigned else []
                )

        return score_mcq_round(
            answers=answers or [],
            assigned_questions=assigned,
            config=config or q_ctx.get("config_json") or {},
        )

    if round_type == SQL:
        from modules.scoring.sql_round import score_sql_round

        return score_sql_round(
            candidate_query=answer_text or "",
            question_context=question_context or {},
            config=config or {},
            **kwargs,
        )

    if round_type == CODING:
        from modules.scoring.coding import score_coding_round

        return score_coding_round(
            candidate_source=answer_text or "",
            question_context=question_context or {},
            config=config or {},
            **kwargs,
        )

    if round_type == SYSTEM_DESIGN:
        from modules.scoring.system_design import (
            CONTENT_EVALUATION_MODE,
            score_system_design_content_v1,
            score_system_design_round,
        )

        # Rounds started as content-evaluated use the content estimate;
        # rounds started under self-assessment keep their original scorer.
        if (config or {}).get("evaluation_mode") == CONTENT_EVALUATION_MODE:
            return score_system_design_content_v1(
                answer=answer_text or "",
                rubric_ratings=rubric_ratings,
                question_context=question_context or {},
                **kwargs,
            )
        return score_system_design_round(
            answer=answer_text or "",
            rubric_ratings=rubric_ratings,
            question_context=question_context or {},
            config=config or {},
            **kwargs,
        )

    if round_type == ML_PRIMITIVES:
        from modules.scoring.ml_primitives import score_ml_primitives_round

        return score_ml_primitives_round(
            candidate_source=answer_text or "",
            config=config or {},
            **kwargs,
        )

    raise UnsupportedRoundTypeError(
        f"Unsupported round type: {round_type!r}. "
        "Add a scoring arm in modules/scoring instead of falling back."
    )
