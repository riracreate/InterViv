"""System-design evaluation: structured self-assessment only.

Does not judge diagrams, component lists, or keyword presence for
correctness. The candidate supplies per-criterion ratings; this module
aggregates them and labels the evaluation mode honestly.

Calibration (advisory): after a complete self-assessment, the design notes are
checked for concepts a design for that prompt usually mentions, per rubric
criterion. The result sits beside the self-rating so a candidate can see where
"I'd give myself 5" is not yet backed by what they wrote. It is a mention
check, not a correctness verdict, and it never changes the score.
"""

from __future__ import annotations

import re
from typing import Any

from backend.db.phase_e_system_design_bank import SYSTEM_DESIGN_EVIDENCE, SYSTEM_DESIGN_RUBRIC

EVALUATION_MODE = "structured_self_assessment"
ALLOWED_RATINGS = frozenset({1, 2, 3, 4, 5})
EVIDENCE_TARGET = 3          # concepts mentioned per criterion for a full 5
EVIDENCE_MIN_WORDS = 20      # below this the notes are too thin to compare
CALIBRATION_ALERT_GAP = 1.5


def evidence_coverage(answer_text: str | None, prompt_id: str | None) -> dict[str, Any]:
    """Per-criterion concept mentions in the design notes (advisory)."""
    concepts = SYSTEM_DESIGN_EVIDENCE.get(str(prompt_id or ""))
    if not concepts:
        return {"available": False, "reason": "No concept checklist for this prompt."}
    text = (answer_text or "").lower()
    if len(re.findall(r"[a-z0-9]+", text)) < EVIDENCE_MIN_WORDS:
        return {"available": False, "reason": "Design notes are too short to compare with your ratings."}
    criteria: dict[str, dict[str, Any]] = {}
    for cid, items in concepts.items():
        matched = [label for label, patterns in items if any(re.search(p, text) for p in patterns)]
        missing = [label for label, _ in items if label not in matched]
        level = 1.0 + 4.0 * min(1.0, len(matched) / EVIDENCE_TARGET)
        criteria[cid] = {"evidence_level": round(level, 1), "mentioned": matched, "not_mentioned": missing}
    return {"available": True, "criteria": criteria}


def _calibration(answer: str | None, question_context: dict[str, Any], ratings: dict[str, int]) -> dict[str, Any]:
    coverage = evidence_coverage(answer, (question_context or {}).get("id"))
    if not coverage.get("available"):
        return coverage
    rows = []
    for c in SYSTEM_DESIGN_RUBRIC:
        evidence = coverage["criteria"].get(c["id"])
        if evidence is None:
            continue
        gap = round(ratings[c["id"]] - evidence["evidence_level"], 1)
        rows.append({
            "id": c["id"],
            "name": c["name"],
            "self_rating": ratings[c["id"]],
            **evidence,
            "gap": gap,
            "overconfident": gap >= CALIBRATION_ALERT_GAP,
        })
    return {
        "available": True,
        "criteria": rows,
        "note": "Mention check against a per-prompt concept list. Advisory; not part of the score.",
    }


def score_system_design_round(
    *,
    answer: str | None = None,
    rubric_ratings: dict[str, Any] | None = None,
    question_context: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Aggregate self-ratings. Missing/invalid ratings yield no score."""
    _ = kwargs  # text is stored and mention-checked for calibration; never scored
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

    calibration = _calibration(answer, question_context or {}, normalized)
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
            "calibration": calibration,
        },
        "feedback": (
            "Self-assessment recorded. Review the named criteria; "
            "diagrams were not auto-scored."
        ),
    }
