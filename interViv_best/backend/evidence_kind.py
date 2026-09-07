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
