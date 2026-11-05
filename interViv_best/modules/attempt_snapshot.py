"""Immutable per-attempt snapshots and deterministic rules-feedback replay.

Phase 3A: the attempt commit freezes an ``attempt_snapshot`` on the scored
round — the question served, the answer as scored, every score, the
breakdown, the feedback, Elo before/after, and the policy knobs in force.
Later writes (progression appends, expiry marks, future endpoints) carry
submitted rounds forward untouched; the snapshot's ``digest`` makes any
later mutation tamper-evident via :func:`verify_attempt_snapshot`.

Phase 3B: new freezes (``SNAPSHOT_VERSION`` 2) also record server-only
``reference`` identity/provenance and ``scorer_provenance``. Old v1
snapshots remain verifiable — digests cover only keys present in the
core, and historical rows are never rewritten.

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

SNAPSHOT_VERSION = 2

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


def _reference_from_context(question_context: dict[str, Any] | None) -> dict[str, Any]:
    """Server-only reference identity / provenance from the scored round context.

    Reviewed bundles: exact pin only (no invented fields).
    Legacy: source + optional LLM attribution, with ideal answer/keywords
    retained under ``reference`` so provenance is complete while serializers
    continue to strip snapshots from client payloads.
    """
    ctx = dict(question_context or {})
    source = str(ctx.get("source") or "").strip() or "unknown"
    if source == "reviewed_bundle" or (
        ctx.get("bundle_id") is not None and ctx.get("version") is not None
    ):
        ref: dict[str, Any] = {"source": "reviewed_bundle"}
        for key in ("bundle_id", "version", "content_hash"):
            if ctx.get(key) is not None:
                ref[key] = ctx[key]
        return ref
    ref = {"source": source}
    if ctx.get("llm_provider") is not None:
        ref["llm_provider"] = ctx.get("llm_provider")
    if ctx.get("llm_model") is not None:
        ref["llm_model"] = ctx.get("llm_model")
    if "ideal_answer" in ctx:
        ref["ideal_answer"] = ctx.get("ideal_answer")
    if "ideal_keywords" in ctx:
        ref["ideal_keywords"] = ctx.get("ideal_keywords")
    elif "ideal_keywords_list" in ctx:
        keywords = ctx.get("ideal_keywords_list")
        if isinstance(keywords, list):
            ref["ideal_keywords"] = ", ".join(str(item) for item in keywords if str(item).strip())
        else:
            ref["ideal_keywords"] = keywords
    return ref


def _scorer_provenance(
    scored_round: dict[str, Any],
    scoring_result: dict[str, Any],
    breakdown: dict[str, Any],
) -> dict[str, Any]:
    return {
        "scoring_schema_version": (
            scoring_result.get("scoring_schema_version")
            or breakdown.get("scoring_schema_version")
            or scored_round.get("scoring_schema_version")
        ),
        "evaluation_mode": (
            scored_round.get("evaluation_mode")
            or scoring_result.get("evaluation_mode")
            or breakdown.get("evaluation_mode")
        ),
        "scoring_mode": (
            scored_round.get("scoring_mode")
            or scoring_result.get("scoring_mode")
            or breakdown.get("scoring_mode")
        ),
        "evidence_kind": (
            scored_round.get("evidence_kind")
            or scoring_result.get("evidence_kind")
            or breakdown.get("evidence_kind")
        ),
    }


def _is_follow_up_round(round_doc: dict[str, Any]) -> bool:
    config = round_doc.get("config_json") or {}
    return bool(
        round_doc.get("is_follow_up") is True
        or round_doc.get("purpose") == "follow_up"
        or (isinstance(config, dict) and config.get("is_follow_up"))
    )


_FOLLOW_UP_REASONS = frozenset({"follow_up", "unreviewed_follow_up"})


def snapshot_has_follow_up_markers(snapshot: dict[str, Any] | None) -> bool:
    """Follow-up / unreviewed markers, including legacy nested ones.

    Snapshots frozen before Slice 1 have no top-level follow-up flag; their
    markers live in eligibility reasons and the scoring breakdown. This is
    a read-time check: stored snapshots and digests are never rewritten.
    """
    if not isinstance(snapshot, dict):
        return False
    if snapshot.get("is_follow_up") is True:
        return True
    reasons = set(snapshot.get("eligibility_exclusion_reasons") or [])
    breakdown = snapshot.get("scoring_breakdown") or {}
    if not isinstance(breakdown, dict):
        breakdown = {}
    eligibility = breakdown.get("assessment_eligibility") or {}
    if isinstance(eligibility, dict):
        reasons |= set(eligibility.get("exclusion_reasons") or [])
    reasons |= set(breakdown.get("eligibility_exclusion_reasons") or [])
    if reasons & _FOLLOW_UP_REASONS:
        return True
    if breakdown.get("follow_up_scoring") or breakdown.get("unscored_reason") == "unreviewed_follow_up":
        return True
    config = snapshot.get("config") or {}
    return isinstance(config, dict) and bool(config.get("is_follow_up") or config.get("follow_up_scoring"))


_REPLAY_REQUIRED_KEYS = ("round", "question", "answer", "scores", "guard_applied", "rules_replayable")


def replayable_snapshots(rounds: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Snapshots whose rules feedback may be replayed, in round order.

    Uses the shared follow-up filter (``non_follow_up_rounds``), then keeps
    only intact (digest-verified), rules-replayable snapshots with every
    replay input present, no follow-up markers, and the same round number
    and question as the round they are stored on.
    """
    from modules.follow_ups import non_follow_up_rounds

    out = []
    for round_doc in non_follow_up_rounds(list(rounds or [])):
        snapshot = round_doc.get("attempt_snapshot")
        if not isinstance(snapshot, dict) or not snapshot.get("rules_replayable"):
            continue
        if any(key not in snapshot for key in _REPLAY_REQUIRED_KEYS):
            continue
        if not isinstance(snapshot.get("scores"), dict):
            continue
        if snapshot.get("round") != round_doc.get("round"):
            continue
        if snapshot.get("question") != round_doc.get("question"):
            continue
        if snapshot_has_follow_up_markers(snapshot) or not verify_attempt_snapshot(snapshot):
            continue
        out.append(snapshot)
    return out


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
    question_context = scored_round.get("question_context") or {}
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
        "assessment_eligibility": scored_round.get("assessment_eligibility"),
        "eligibility_policy_version": scored_round.get("eligibility_policy_version"),
        "eligibility_exclusion_reasons": copy.deepcopy(
            scored_round.get("eligibility_exclusion_reasons") or []
        ),
        "config": {
            "attempt_policy": (config or {}).get("attempt_policy"),
            "review_policy": (config or {}).get("review_policy"),
        },
        "submitted_at": submitted_at,
        # Follow-ups never replay rules feedback (Slice 1); every other
        # round freezes exactly as before.
        "rules_replayable": (
            round_type in RULES_REPLAYABLE_ROUND_TYPES and not _is_follow_up_round(scored_round)
        ),
        "reference": _reference_from_context(question_context),
        "scorer_provenance": _scorer_provenance(scored_round, scoring_result, breakdown),
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


def narration_allowed_claims(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """Production-established claims suitable for narration grounding.

    Returns only signals the active scorer actually committed on the
    snapshot: ``final_score``, ``guard_applied``, feedback fields, and
    covered/missing concepts when present as evaluated breakdown signals.

    Semantic similarity / ``semantic_score`` is intentionally excluded —
    similarity is not a correctness claim and must not be narrated as proof
    that an answer is correct.
    """
    if not isinstance(snapshot, dict):
        return {}
    scores = snapshot.get("scores") or {}
    feedback = snapshot.get("feedback") or {}
    breakdown = snapshot.get("scoring_breakdown") or {}
    concepts = breakdown.get("concepts") if isinstance(breakdown.get("concepts"), dict) else {}
    covered = (
        breakdown.get("covered_concepts")
        or concepts.get("covered")
        or []
    )
    missing = (
        breakdown.get("missing_concepts")
        or concepts.get("missing")
        or []
    )
    return {
        "final_score": scores.get("final_score", snapshot.get("final_score")),
        "guard_applied": snapshot.get("guard_applied"),
        "feedback": {
            "content": list(feedback.get("content") or []),
            "strengths": list(feedback.get("strengths") or []),
            "weakness": list(
                feedback.get("weakness") or feedback.get("weaknesses") or []
            ),
            "next_step": feedback.get("next_step") or feedback.get("recommendation") or "",
        },
        "strengths": list(feedback.get("strengths") or []),
        "covered_concepts": [str(item) for item in covered if str(item).strip()],
        "missing_concepts": [str(item) for item in missing if str(item).strip()],
        # Empty unless the scorer recorded explicit evidence/criterion ids.
        "evidence_ids": [
            str(item) for item in (breakdown.get("evidence_ids") or []) if str(item).strip()
        ],
        "criterion_ids": [
            str(item) for item in (breakdown.get("criterion_ids") or []) if str(item).strip()
        ],
    }


def regenerate_rules_feedback(snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    """Replay deterministic rules feedback purely from snapshot inputs.

    Returns None for snapshots whose round type never used the rules path.
    For rules-scored rounds the result is byte-identical to the feedback
    stored at score time (guarantee enforced by test).
    """
    if not isinstance(snapshot, dict) or not snapshot.get("rules_replayable"):
        return None
    if snapshot_has_follow_up_markers(snapshot):
        # Read-time guard for legacy follow-up snapshots frozen with
        # rules_replayable=True; their digests are left untouched.
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
