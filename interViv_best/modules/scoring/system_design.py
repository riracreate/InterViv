"""System-design evaluation: structured self-assessment only.

Does not judge diagrams, component lists, or keyword presence for
correctness. The candidate supplies per-criterion ratings; this module
aggregates them and labels the evaluation mode honestly.
"""

from __future__ import annotations

from typing import Any

from backend.db.phase_e_system_design_bank import SYSTEM_DESIGN_RUBRIC

EVALUATION_MODE = "structured_self_assessment"
ALLOWED_RATINGS = frozenset({1, 2, 3, 4, 5})


def score_system_design_round(
    *,
    answer: str | None = None,
    rubric_ratings: dict[str, Any] | None = None,
    question_context: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Aggregate self-ratings. Missing/invalid ratings yield no score."""
    _ = answer, question_context, kwargs  # text is stored, not auto-judged
    criteria_ids = [c["id"] for c in SYSTEM_DESIGN_RUBRIC]
    ratings_in = rubric_ratings or {}
    normalized: dict[str, int] = {}
    for cid in criteria_ids:
        raw = ratings_in.get(cid)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value in ALLOWED_RATINGS:
            normalized[cid] = value

    if len(normalized) != len(criteria_ids):
        return {
            "final_score": None,
            "evaluation_mode": EVALUATION_MODE,
            "rubric": [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "rating": normalized.get(c["id"]),
                }
                for c in SYSTEM_DESIGN_RUBRIC
            ],
            "incomplete": True,
            "boundary": (
                "No automatic diagram correctness. Incomplete self-assessment "
                "produces no score (not a zero)."
            ),
            "artifact_json": {
                "evaluation": "system_design",
                "evaluation_mode": EVALUATION_MODE,
                "incomplete": True,
            },
            "feedback": (
                "Complete every rubric rating (1–5) to record a "
                "self-assessment score. Diagrams are not auto-validated."
            ),
        }

    avg = sum(normalized.values()) / len(normalized)
    # Map 1–5 average onto 0–100 for session aggregates without claiming
    # external correctness.
    final = round((avg - 1.0) / 4.0 * 100.0, 2)
    return {
        "final_score": final,
        "evaluation_mode": EVALUATION_MODE,
        "rubric": [
            {"id": c["id"], "name": c["name"], "rating": normalized[c["id"]]}
            for c in SYSTEM_DESIGN_RUBRIC
        ],
        "incomplete": False,
        "boundary": (
            "Score reflects structured self-assessment only. "
            "No automatic diagram or architecture correctness verdict."
        ),
        "artifact_json": {
            "evaluation": "system_design",
            "evaluation_mode": EVALUATION_MODE,
            "rubric": normalized,
            "incomplete": False,
        },
        "feedback": (
            "Self-assessment recorded. Review the named criteria; "
            "diagrams were not auto-scored."
        ),
    }
