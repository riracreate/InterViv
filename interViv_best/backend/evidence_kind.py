"""Evidence population labels for scored rounds.

Self-reported results (structured self-assessment) must stay in their own
population: visible and labeled, never mixed into measured mastery,
readiness, gap analysis, or retry seeding.
"""

from __future__ import annotations

from typing import Any

from backend.execution import get_execution_status

EVIDENCE_MEASURED = "measured"
EVIDENCE_SELF_REPORTED = "self_reported"
EVIDENCE_PRACTICE_REVIEW = "practice_review"
SELF_ASSESSMENT_MODE = "structured_self_assessment"

# Scoring-mode labels persisted on each scored attempt at write time.
# Pre-G.0 rows without this field must surface as unknown — never guessed.
SCORING_MODE_FULL = "full"
SCORING_MODE_DEGRADED = "lexical_fallback_degraded"
SCORING_MODE_SELF_REPORTED = "self_reported"
SCORING_MODE_UNKNOWN = "unknown"


def scoring_mode_at_write(
    *,
    self_reported: bool,
    scoring_breakdown: dict[str, Any] | None = None,
    scoring_result: dict[str, Any] | None = None,
) -> str:
    """Canonical scoring mode for the attempt being persisted now."""
    if self_reported:
        return SCORING_MODE_SELF_REPORTED
    bd = scoring_breakdown or {}
    result = scoring_result or {}
    if (
        bd.get("semantic_component_source") == "lexical_fallback"
        or bd.get("semantic_scoring_available") is False
        or result.get("semantic_scoring_available") is False
    ):
        return SCORING_MODE_DEGRADED
    return SCORING_MODE_FULL


def scoring_mode_for_round(round_doc: dict[str, Any] | None) -> str:
    """Read persisted mode; never invent one for historical rows.

    Prefer the top-level field when present. SQLAlchemy round rows only
    keep known columns, so G.0 also stores ``scoring_mode`` inside
    ``scoring_breakdown`` (JSON) — read that second. Rows with neither
    are ``unknown``.
    """
    if not isinstance(round_doc, dict):
        return SCORING_MODE_UNKNOWN
    allowed = {
        SCORING_MODE_FULL,
        SCORING_MODE_DEGRADED,
        SCORING_MODE_SELF_REPORTED,
        SCORING_MODE_UNKNOWN,
    }
    mode = round_doc.get("scoring_mode")
    if mode in allowed:
        return str(mode)
    breakdown = round_doc.get("scoring_breakdown") or {}
    if isinstance(breakdown, dict):
        nested = breakdown.get("scoring_mode")
        if nested in allowed:
            return str(nested)
    return SCORING_MODE_UNKNOWN


def scoring_mode_label_for_display(mode: str) -> str:
    if mode == SCORING_MODE_DEGRADED:
        return "Lexical fallback (semantic scorer unavailable)"
    if mode == SCORING_MODE_SELF_REPORTED:
        return "Self-reported (not measured)"
    if mode == SCORING_MODE_FULL:
        return "Full semantic scoring"
    return "Scoring mode unknown"


def is_self_reported_round(round_doc: dict[str, Any] | None) -> bool:
    if not isinstance(round_doc, dict):
        return False
    if str(round_doc.get("round_type") or "") == "system_design":
        return True
    mode = round_doc.get("evaluation_mode")
    if mode == SELF_ASSESSMENT_MODE:
        return True
    artifact = round_doc.get("artifact_json") or {}
    if isinstance(artifact, dict) and artifact.get("evaluation_mode") == SELF_ASSESSMENT_MODE:
        return True
    return round_doc.get("evidence_kind") == EVIDENCE_SELF_REPORTED


def is_practice_review_round(round_doc: dict[str, Any] | None) -> bool:
    """Spaced-review practice: scored for scheduling only, never measured."""
    if not isinstance(round_doc, dict):
        return False
    return round_doc.get("evidence_kind") == EVIDENCE_PRACTICE_REVIEW


def evidence_kind_for_round(
    *,
    round_type: str | None = None,
    evaluation_mode: str | None = None,
) -> str:
    if round_type == "system_design" or evaluation_mode == SELF_ASSESSMENT_MODE:
        return EVIDENCE_SELF_REPORTED
    return EVIDENCE_MEASURED


def evaluation_unavailable(round_type: str | None) -> bool:
    """True when no evaluation service could score this round right now.

    Expiry mirrors the submit path: a submit that would 503 as
    unavailable must record as unscored on expiry, never a zero.
    Unknown round types default to False so existing behaviour holds
    for categories this predicate has never heard of.
    """
    if round_type == "ml_primitives":
        return True  # No evaluator exists; every submit 503s.
    if round_type == "coding":
        return not get_execution_status().get("available", False)
    return False


def measured_scores(rounds: list[dict[str, Any]]) -> list[float]:
    out: list[float] = []
    for item in rounds:
        if item.get("final_score") is None:
            continue
        if is_self_reported_round(item) or is_practice_review_round(item):
            continue
        out.append(float(item["final_score"]))
    return out
