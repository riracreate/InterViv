"""Immutable per-attempt snapshots and deterministic rules-feedback replay.

Phase 3A: the attempt commit freezes an ``attempt_snapshot`` on the scored
round — the question served, the answer as scored, every score, the
breakdown, the feedback, Elo before/after, and the policy knobs in force.
Later writes (progression appends, expiry marks, future endpoints) carry
submitted rounds forward untouched; the snapshot's ``digest`` makes any
later mutation tamper-evident via :func:`verify_attempt_snapshot`.

:func:`regenerate_rules_feedback` replays the deterministic rules feedback
(``modules.c4_feedback`` plus the pipeline's fixed post-processing) purely
from snapshot inputs. It is byte-identical to the feedback stored at score
time for rules-scored rounds; type-specific scorers (MCQ/SQL/coding/...) do
not use the rules path and their snapshots replay to ``None``. The mirror
of the pipeline post-processing is enforced by test, not by discipline:
if the pipeline text changes, the equality test fails loudly.

Snapshots are server-side only: serializers strip ``attempt_snapshot``
before anything reaches a client.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

SNAPSHOT_VERSION = 1

# Only the pipeline/c4 path (technical short answer) feeds the rules
# feedback; every other round type is scored by its own module.
RULES_REPLAYABLE_ROUND_TYPES = frozenset({"technical_short_answer"})

# Verbatim mirror of the guard-message map in
# backend/scoring/pipeline.py ("Guard message into feedback"). Do not edit
# one without the other — the snapshot equality test pins both.
_GUARD_MESSAGES = {
    "empty": "Your answer looks incomplete or gibberish. Please write a meaningful explanation.",
    "gibberish": "Your answer looks incomplete or gibberish. Please write a meaningful explanation.",
    "repetition": "Your answer looks incomplete or gibberish. Please write a meaningful explanation.",
    "too_short": "Your answer looks incomplete or gibberish. Please write a meaningful explanation.",
    "keyword_stuffing": "Your answer appeared to stuff keywords without meaningful context.",
    "question_parroting": "Your answer mostly repeats the question. Explain the concept in your own words.",
    "low_density": "Your answer looks incomplete or gibberish. Please write a meaningful explanation.",
    "off_topic": "Your answer doesn't seem to address the question. Re-read the question and focus on its specific topic.",
}
_GUARD_MESSAGE_FALLBACK = "Your answer quality was flagged by the scoring guard."
_SOFTENED_MESSAGE = (
    "Your answer was brief, but the semantic match was strong, so only a small "
    "brevity penalty was applied."
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def snapshot_digest(core: dict[str, Any]) -> str:
    """Tamper-evidence digest over a snapshot core (the ``digest`` key excluded)."""
    return hashlib.sha256(_canonical_json(core).encode("utf-8")).hexdigest()


def freeze_attempt_snapshot(scored_round: dict[str, Any], scoring_result: dict[str, Any]) -> dict[str, Any]:
    """Freeze the scored round's inputs and outputs into an immutable snapshot.

    ``scored_round`` is the round dict as built for the attempt commit;
    ``scoring_result`` supplies the schema version. Pure: inputs are copied,
    never mutated.
    """
    breakdown = copy.deepcopy(scored_round.get("scoring_breakdown") or {})
    config = scored_round.get("config_json") or {}
    submitted_at = scored_round.get("submitted_at")
    if hasattr(submitted_at, "isoformat"):
        submitted_at = submitted_at.isoformat()
    round_type = scored_round.get("round_type") or "technical_short_answer"
    core = {
        "snapshot_version": SNAPSHOT_VERSION,
        "round": scored_round.get("round"),
        "round_type": round_type,
        "skill": scored_round.get("skill"),
        "question": scored_round.get("question"),
        "answer": scored_round.get("answer_text"),
        "scores": {
            "nlp_score": scored_round.get("nlp_score"),
            "svm_label": scored_round.get("svm_label"),
            "kg_score": scored_round.get("kg_score"),
            "ner_entities": copy.deepcopy(scored_round.get("ner_entities") or []),
            "final_score": scored_round.get("final_score"),
        },
        "guard_applied": breakdown.get("guard_applied", scored_round.get("guard_applied")),
        "guard_softened": breakdown.get("guard_softened"),
        "scoring_breakdown": breakdown,
        "scoring_schema_version": (
            scoring_result.get("scoring_schema_version")
            or breakdown.get("scoring_schema_version")
        ),
        "feedback": copy.deepcopy(scored_round.get("feedback") or {}),
        "elo_before": scored_round.get("elo_before"),
        "elo_after": scored_round.get("elo_after"),
        "difficulty": scored_round.get("difficulty"),
        "difficulty_change": scored_round.get("difficulty_change"),
        "evidence_kind": scored_round.get("evidence_kind"),
        "scoring_mode": scored_round.get("scoring_mode"),
        "evaluation_mode": scored_round.get("evaluation_mode"),
        "config": {
            "attempt_policy": (config or {}).get("attempt_policy"),
            "review_policy": (config or {}).get("review_policy"),
        },
        "submitted_at": submitted_at,
        "rules_replayable": round_type in RULES_REPLAYABLE_ROUND_TYPES,
    }
    return {**core, "digest": snapshot_digest(core)}


def verify_attempt_snapshot(snapshot: dict[str, Any] | None) -> bool:
    """Recompute the digest: True only for an unmodified frozen snapshot."""
    if not isinstance(snapshot, dict):
        return False
    digest = snapshot.get("digest")
    if not isinstance(digest, str) or not digest:
        return False
    core = {key: value for key, value in snapshot.items() if key != "digest"}
    return snapshot_digest(core) == digest


def regenerate_rules_feedback(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    """Replay deterministic rules feedback purely from snapshot inputs.

    Returns None for snapshots whose round type never used the rules path.
    For rules-scored rounds the result is byte-identical to the feedback
    stored at score time (guarantee enforced by test).
    """
    if not isinstance(snapshot, dict) or not snapshot.get("rules_replayable"):
        return None
    from backend.integrations import normalize_feedback
    from modules.c4_feedback import generate_feedback

    scores = snapshot.get("scores") or {}
    # Same pipeline as score time: rules, then the shared normalizer (which
    # reduces the payload to content/strengths/weakness/next_step), then the
    # deterministic guard-message prepends below.
    feedback = normalize_feedback(generate_feedback(
        answer_text=snapshot.get("answer"),
        svm_label=scores.get("svm_label"),
        ner_entities=list(scores.get("ner_entities") or []),
        guard_reason=snapshot.get("guard_applied"),
    ))
    # Deterministic post-processing, mirrored from the pipeline: a capping
    # guard prepends its message, else a softened brevity guard prepends its
    # own. Same inputs, same branch, same text — byte-identical by test.
    reason = snapshot.get("guard_applied")
    if reason is not None:
        msg = _GUARD_MESSAGES.get(reason, _GUARD_MESSAGE_FALLBACK)
        feedback.setdefault("content", []).insert(0, msg)
    elif snapshot.get("guard_softened"):
        feedback.setdefault("content", []).insert(0, _SOFTENED_MESSAGE)
    return feedback
