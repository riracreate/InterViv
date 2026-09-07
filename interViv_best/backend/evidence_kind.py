"""Evidence population labels for scored rounds.

Self-reported results (structured self-assessment) must stay in their own
population: visible and labeled, never mixed into measured mastery,
readiness, gap analysis, or retry seeding.
"""

from __future__ import annotations

from typing import Any

EVIDENCE_MEASURED = "measured"
EVIDENCE_SELF_REPORTED = "self_reported"
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
    """Read persisted mode; never invent one for historical rows."""
    if not isinstance(round_doc, dict):
        return SCORING_MODE_UNKNOWN
    mode = round_doc.get("scoring_mode")
    if mode in {
        SCORING_MODE_FULL,
        SCORING_MODE_DEGRADED,
        SCORING_MODE_SELF_REPORTED,
        SCORING_MODE_UNKNOWN,
    }:
        return str(mode)
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


def evidence_kind_for_round(
    *,
    round_type: str | None = None,
    evaluation_mode: str | None = None,
) -> str:
    if round_type == "system_design" or evaluation_mode == SELF_ASSESSMENT_MODE:
        return EVIDENCE_SELF_REPORTED
    return EVIDENCE_MEASURED


def measured_scores(rounds: list[dict[str, Any]]) -> list[float]:
    out: list[float] = []
    for item in rounds:
        if item.get("final_score") is None:
            continue
        if is_self_reported_round(item):
            continue
        out.append(float(item["final_score"]))
    return out
