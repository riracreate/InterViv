"""Phase I spaced-review schedule: fixed interval ladder over notebook misses.

Rule (reproducible from stored fields alone)
------------------------------------------
Ladder days: ``INTERVAL_LADDER = (1, 3, 7, 16, 35)``.

- New schedule rows start at index 0 (1 day) and are **due now**
  (``due_at = created_at``). Pre-feature notebook misses are not guessed into
  a historical timeline — they enter as due-now.
- Outcome ``correct``: ``interval_index = min(index + 1, len-1)``;
  ``interval_days = INTERVAL_LADDER[index]``; ``due_at = now + interval_days``.
- Outcome ``incorrect``: ``interval_index = 0``; ``interval_days = 1``;
  ``due_at = now + 1 day``.

Reviews never update measured mastery/readiness (see answer.py). Coding items
may be scheduled as ``review_available=False`` and never produce an outcome.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

INTERVAL_LADDER: tuple[int, ...] = (1, 3, 7, 16, 35)
OUTCOME_CORRECT = "correct"
OUTCOME_INCORRECT = "incorrect"
VALID_OUTCOMES = frozenset({OUTCOME_CORRECT, OUTCOME_INCORRECT})


def ladder_days_at(index: int) -> int:
    if index < 0:
        index = 0
    if index >= len(INTERVAL_LADDER):
        index = len(INTERVAL_LADDER) - 1
    return INTERVAL_LADDER[index]


def advance_after_outcome(
    *,
    interval_index: int,
    outcome: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return the next schedule fields after a review outcome."""
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(VALID_OUTCOMES)}")
    when = now or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if outcome == OUTCOME_CORRECT:
        next_index = min(int(interval_index) + 1, len(INTERVAL_LADDER) - 1)
    else:
        next_index = 0
    days = ladder_days_at(next_index)
    return {
        "interval_index": next_index,
        "interval_days": days,
        "due_at": when + timedelta(days=days),
        "last_reviewed_at": when,
        "last_outcome": outcome,
    }


def is_due(doc: dict[str, Any], *, now: datetime | None = None) -> bool:
    when = now or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    due = doc.get("due_at")
    if due is None:
        return False
    if isinstance(due, str):
        due = datetime.fromisoformat(due.replace("Z", "+00:00"))
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    return due <= when


def review_correct_for_round(round_doc: dict[str, Any]) -> bool | None:
    """Interpret a scored review round as correct/incorrect for scheduling.

    Returns None when the round cannot yield a scheduling outcome (e.g. coding
    unavailable, unscored).
    """
    if not isinstance(round_doc, dict):
        return None
    if round_doc.get("round_type") == "coding":
        return None
    if round_doc.get("final_score") is None:
        return None
    round_type = round_doc.get("round_type")
    if round_type == "mcq":
        artifact = round_doc.get("artifact_json") or {}
        results = artifact.get("results") or artifact.get("questions") or []
        if not results and isinstance(artifact.get("per_question"), list):
            results = artifact["per_question"]
        # Prefer explicit per-question correctness when present.
        flags = []
        for item in results:
            if isinstance(item, dict) and "is_correct" in item:
                flags.append(bool(item.get("is_correct")))
        if flags:
            return all(flags)
        return float(round_doc["final_score"]) >= 99.0
    if round_type == "sql":
        artifact = round_doc.get("artifact_json") or {}
        passed = artifact.get("cases_passed")
        total = artifact.get("cases_total")
        if isinstance(passed, (int, float)) and isinstance(total, (int, float)) and total:
            return int(passed) >= int(total)
        return float(round_doc["final_score"]) >= 99.0
    # Interview-style: treat >= 61 as "correct enough" to lengthen — same cutoff
    # the notebook uses for a miss. Reviews of interview_miss are rare (no item_id).
    return float(round_doc["final_score"]) >= 61.0
