"""Versioned assessment-eligibility policy (Phase 4A).

Eligibility describes observed in-app evidence under a declared product
policy. It does not prove the candidate received no outside help.

Policy v1 (initial):
- Follow-ups and same-item retries are always excluded from primary metrics.
- Fresh related items use same-session exposure plus a 24h cross-session
  window (owned accounts). Guests are session-scoped only.
- Exact-item repetition is always repeated practice (window does not help).
- Incomplete history → unknown, never clean.
- Legacy rows without a persisted decision → legacy/unknown.
- A round served from a question bundle counts only when the bundle label
  frozen in its question_context at serve time is ``reviewed_bundle``.
  Auto-checked, generated, draft or unlabelled bundle rounds keep their
  feedback but are excluded (``unreviewed_content``). The served snapshot
  decides, never a live store lookup; persisted decisions on past rounds
  are never recomputed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

POLICY_VERSION = "assistance_v1"
CROSS_SESSION_WINDOW = timedelta(hours=24)

ELIGIBLE = "eligible"
EXCLUDED = "excluded"
UNKNOWN = "unknown"
LEGACY_UNKNOWN = "legacy_unknown"

# Exclusion / uncertainty reason codes persisted with the attempt.
REASON_FOLLOW_UP = "follow_up"
REASON_SAME_ITEM_RETRY = "same_item_retry"
REASON_TEACHING_EXPOSURE = "teaching_exposure"
REASON_RELATED_EXPOSURE = "related_topic_exposure"
REASON_INCOMPLETE_HISTORY = "incomplete_history"
REASON_COARSE_SCOPE = "coarse_topic_scope"
REASON_GUEST_SESSION_ONLY = "guest_session_scoped"
REASON_LEGACY_UNVERIFIABLE = "legacy_unverifiable"
REASON_UNSCORED_FOLLOW_UP = "unreviewed_follow_up"
REASON_UNREVIEWED_CONTENT = "unreviewed_content"

# Label written by question_bundles.candidate_payload only for a bundle
# version whose status was exactly "reviewed" when it was served.
REVIEWED_BUNDLE_SOURCE = "reviewed_bundle"

TEACHING_KINDS = frozenset({
    "hint",
    "explanation",
    "solution",
    "editorial",
    "reference",
    "answer_sketch",
    "named_gap",
    "follow_up_prompt",
    "feedback_reveal",
})


def _as_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def item_identity_for_round(round_doc: dict[str, Any]) -> tuple[str | None, str | None]:
    """Stable (item_type, item_id) for the round when available."""
    round_type = str(round_doc.get("round_type") or "")
    ctx = round_doc.get("question_context") or {}
    config = round_doc.get("config_json") or {}
    if round_type == "mcq":
        questions = ctx.get("questions") or []
        ids = [str(q.get("id")) for q in questions if isinstance(q, dict) and q.get("id")]
        if ids:
            return "mcq", ",".join(ids)
        return "mcq", None
    if round_type in ("sql", "coding", "system_design"):
        problem_id = config.get("problem_id") or ctx.get("problem_id")
        item_type = "system_design" if round_type == "system_design" else round_type
        return item_type, str(problem_id) if problem_id else None
    # Technical short answer: prefer reviewed pin, else question text hash key.
    bundle_id = ctx.get("bundle_id")
    version = ctx.get("version")
    if bundle_id is not None and version is not None:
        return "technical", f"{bundle_id}@{version}"
    qid = round_doc.get("question_id") or ctx.get("question_id")
    if qid:
        return "technical", str(qid)
    question = round_doc.get("question")
    if question:
        return "technical", f"qtext:{hash(str(question)) & 0xFFFFFFFF:08x}"
    return "technical", None


def topic_scope_for_round(round_doc: dict[str, Any], session: dict[str, Any] | None = None) -> dict[str, Any]:
    """Conservative topic/skill scope when concept mappings are incomplete."""
    ctx = round_doc.get("question_context") or {}
    skill = round_doc.get("skill") or (session or {}).get("skill")
    topic = (
        ctx.get("topic")
        or ctx.get("sub_topic")
        or ctx.get("sub_domain")
        or (session or {}).get("sub_domain")
    )
    concepts = ctx.get("concepts") or ctx.get("required_concepts") or []
    concept_ids = []
    if isinstance(concepts, list):
        for c in concepts:
            if isinstance(c, str) and c.strip():
                concept_ids.append(c.strip())
            elif isinstance(c, dict) and c.get("id"):
                concept_ids.append(str(c["id"]))
    return {
        "skill": str(skill) if skill else None,
        "topic": str(topic) if topic else None,
        "concept_ids": concept_ids,
        "scope_certainty": "concept" if concept_ids else ("topic" if topic or skill else "unknown"),
    }


def served_bundle_label(round_doc: dict[str, Any] | None) -> str | None:
    """Bundle trust label frozen in question_context when the question was served.

    ``None`` when the round was not served from a question bundle (bank,
    template, LLM, MCQ, SQL or coding items are not affected by this rule).
    A pinned bundle with no label reads as ``unknown_bundle``.
    """
    if not isinstance(round_doc, dict):
        return None
    ctx = round_doc.get("question_context") or {}
    if not isinstance(ctx, dict):
        return None
    source = str(ctx.get("source") or "").strip()
    if ctx.get("bundle_id") is None and not source.endswith("_bundle"):
        return None
    return source or "unknown_bundle"


def is_unreviewed_bundle_round(round_doc: dict[str, Any] | None) -> bool:
    """True when the round was served from a bundle not explicitly reviewed."""
    label = served_bundle_label(round_doc)
    return label is not None and label != REVIEWED_BUNDLE_SOURCE


def is_follow_up_round(round_doc: dict[str, Any] | None) -> bool:
    if not isinstance(round_doc, dict):
        return False
    if round_doc.get("is_follow_up") is True:
        return True
    purpose = str(round_doc.get("purpose") or "").lower()
    if purpose == "follow_up":
        return True
    config = round_doc.get("config_json") or {}
    if isinstance(config, dict) and config.get("is_follow_up"):
        return True
    return False


def read_persisted_eligibility(round_doc: dict[str, Any] | None) -> dict[str, Any]:
    """Read frozen eligibility from an attempt; never invent a clean history."""
    if not isinstance(round_doc, dict):
        return {
            "decision": LEGACY_UNKNOWN,
            "policy_version": None,
            "exclusion_reasons": [REASON_LEGACY_UNVERIFIABLE],
            "exposure_ids": [],
            "legacy": True,
        }
    decision = round_doc.get("assessment_eligibility")
    if decision is None:
        bd = round_doc.get("scoring_breakdown") or {}
        if isinstance(bd, dict):
            nested = bd.get("assessment_eligibility")
            if isinstance(nested, dict):
                return {
                    "decision": nested.get("decision") or LEGACY_UNKNOWN,
                    "policy_version": nested.get("policy_version"),
                    "exclusion_reasons": list(nested.get("exclusion_reasons") or []),
                    "exposure_ids": list(nested.get("exposure_ids") or []),
                    "legacy": bool(nested.get("legacy", False)),
                }
            decision = bd.get("assessment_eligibility_decision")
    if decision is None:
        # Pre-4A rows: assisted flag exists but no versioned decision.
        return {
            "decision": LEGACY_UNKNOWN,
            "policy_version": None,
            "exclusion_reasons": [REASON_LEGACY_UNVERIFIABLE],
            "exposure_ids": [],
            "legacy": True,
        }
    reasons = round_doc.get("eligibility_exclusion_reasons")
    if reasons is None:
        bd = round_doc.get("scoring_breakdown") or {}
        reasons = (bd or {}).get("eligibility_exclusion_reasons") if isinstance(bd, dict) else []
    exposures = round_doc.get("eligibility_exposure_ids")
    if exposures is None:
        bd = round_doc.get("scoring_breakdown") or {}
        exposures = (bd or {}).get("eligibility_exposure_ids") if isinstance(bd, dict) else []
    version = round_doc.get("eligibility_policy_version")
    if version is None:
        bd = round_doc.get("scoring_breakdown") or {}
        if isinstance(bd, dict):
            version = bd.get("eligibility_policy_version")
    return {
        "decision": str(decision),
        "policy_version": version,
        "exclusion_reasons": list(reasons or []),
        "exposure_ids": list(exposures or []),
        "legacy": str(decision) in (LEGACY_UNKNOWN, UNKNOWN),
    }


def is_assessment_eligible(round_doc: dict[str, Any] | None) -> bool:
    """True only when the attempt is frozen as independently assessed."""
    info = read_persisted_eligibility(round_doc)
    return info["decision"] == ELIGIBLE


def is_primary_metric_round(round_doc: dict[str, Any] | None) -> bool:
    """Eligible for block scores, Elo, mastery, readiness, skill means.

    Self-reported and spaced-review remain excluded via evidence_kind filters
    at call sites; this gate only covers assistance / repeat / follow-up.
    """
    if not isinstance(round_doc, dict):
        return False
    if round_doc.get("final_score") is None:
        return False
    return is_assessment_eligible(round_doc)


def _prior_same_item_attempts(
    *,
    prior_rounds: list[dict[str, Any]],
    item_type: str | None,
    item_id: str | None,
    current_round_number: int | None,
) -> list[dict[str, Any]]:
    if not item_type or not item_id:
        return []
    out = []
    for prior in prior_rounds:
        if current_round_number is not None and prior.get("round") == current_round_number:
            continue
        if prior.get("final_score") is None and str(prior.get("status") or "") != "submitted":
            continue
        p_type, p_id = item_identity_for_round(prior)
        if p_type == item_type and p_id == item_id:
            out.append(prior)
    return out


def _exposure_matches_item(
    exposure: dict[str, Any],
    *,
    item_type: str | None,
    item_id: str | None,
    scope: dict[str, Any],
) -> tuple[bool, str | None]:
    """Return (matches, reason) for a teaching exposure vs the current item."""
    if not exposure:
        return False, None
    exp_type = str(exposure.get("item_type") or "")
    exp_id = str(exposure.get("item_id") or "")
    if item_type and item_id and exp_type == item_type and exp_id == item_id:
        return True, REASON_TEACHING_EXPOSURE
    # Conservative related-item fallback via topic/skill when concepts missing.
    exp_scope = exposure.get("concept_topic_scope") or {}
    if not isinstance(exp_scope, dict):
        exp_scope = {}
    exp_concepts = set(exp_scope.get("concept_ids") or [])
    cur_concepts = set(scope.get("concept_ids") or [])
    if exp_concepts and cur_concepts and exp_concepts & cur_concepts:
        return True, REASON_RELATED_EXPOSURE
    if scope.get("scope_certainty") in ("topic", "unknown") or exp_scope.get("scope_certainty") in ("topic", "unknown"):
        # Coarse fallback: same skill+topic when concept ids unavailable.
        same_skill = (
            scope.get("skill")
            and exp_scope.get("skill")
            and str(scope["skill"]).lower() == str(exp_scope["skill"]).lower()
        )
        same_topic = (
            scope.get("topic")
            and exp_scope.get("topic")
            and str(scope["topic"]).lower() == str(exp_scope["topic"]).lower()
        )
        if same_skill and (same_topic or not scope.get("topic") or not exp_scope.get("topic")):
            return True, REASON_COARSE_SCOPE
    return False, None


def evaluate_eligibility(
    *,
    session: dict[str, Any],
    round_doc: dict[str, Any],
    exposures: list[dict[str, Any]],
    prior_rounds: list[dict[str, Any]] | None = None,
    now: datetime | None = None,
    history_complete: bool = True,
    policy_version: str = POLICY_VERSION,
) -> dict[str, Any]:
    """Freeze-time eligibility decision for an authoritative submission.

    ``exposures`` must be teaching deliveries observed *before* submission
    acceptance (server ordering). Feedback released after submission must not
    be included by the caller.
    """
    now = now or datetime.now(timezone.utc)
    prior_rounds = list(prior_rounds or [])
    reasons: list[str] = []
    exposure_ids: list[str] = []
    item_type, item_id = item_identity_for_round(round_doc)
    scope = topic_scope_for_round(round_doc, session)
    user_id = session.get("user_id")
    session_id = str(session.get("session_id") or "")

    if is_follow_up_round(round_doc):
        reasons.append(REASON_FOLLOW_UP)
        follow_up_scoring = round_doc.get("follow_up_scoring") or (
            round_doc.get("config_json") or {}
        ).get("follow_up_scoring")
        if follow_up_scoring == "unreviewed":
            reasons.append(REASON_UNSCORED_FOLLOW_UP)
    elif is_unreviewed_bundle_round(round_doc):
        # Follow-ups are already excluded; any other bundle round counts only
        # when it was served from an explicitly reviewed version.
        reasons.append(REASON_UNREVIEWED_CONTENT)

    retries = _prior_same_item_attempts(
        prior_rounds=prior_rounds,
        item_type=item_type,
        item_id=item_id,
        current_round_number=round_doc.get("round"),
    )
    if retries:
        reasons.append(REASON_SAME_ITEM_RETRY)

    if not history_complete:
        reasons.append(REASON_INCOMPLETE_HISTORY)

    if item_id is None:
        # Cannot verify exact-item novelty; treat as uncertain unless already excluded.
        if REASON_FOLLOW_UP not in reasons and REASON_SAME_ITEM_RETRY not in reasons:
            reasons.append(REASON_INCOMPLETE_HISTORY)

    window_start = now - CROSS_SESSION_WINDOW
    for exposure in exposures:
        created = _as_utc(exposure.get("delivered_at") or exposure.get("created_at"))
        if created is None:
            reasons.append(REASON_INCOMPLETE_HISTORY)
            continue
        exp_session = str(exposure.get("session_id") or "")
        same_session = bool(exp_session) and exp_session == session_id
        if not same_session:
            if not user_id:
                # Guest: cross-session exposures are out of scope; ignore them.
                continue
            if created < window_start:
                continue
        matches, reason = _exposure_matches_item(
            exposure,
            item_type=item_type,
            item_id=item_id,
            scope=scope,
        )
        if matches and reason:
            reasons.append(reason)
            eid = exposure.get("delivery_id") or exposure.get("id")
            if eid:
                exposure_ids.append(str(eid))
            if reason == REASON_COARSE_SCOPE and REASON_COARSE_SCOPE not in reasons:
                reasons.append(REASON_COARSE_SCOPE)

    # Deduplicate reasons while preserving order.
    seen: set[str] = set()
    ordered_reasons: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            ordered_reasons.append(reason)

    if not user_id and any(
        r in ordered_reasons
        for r in (REASON_TEACHING_EXPOSURE, REASON_RELATED_EXPOSURE, REASON_COARSE_SCOPE)
    ):
        if REASON_GUEST_SESSION_ONLY not in ordered_reasons:
            ordered_reasons.append(REASON_GUEST_SESSION_ONLY)

    if ordered_reasons:
        decision = UNKNOWN if REASON_INCOMPLETE_HISTORY in ordered_reasons and not any(
            r in ordered_reasons
            for r in (
                REASON_FOLLOW_UP,
                REASON_SAME_ITEM_RETRY,
                REASON_TEACHING_EXPOSURE,
                REASON_RELATED_EXPOSURE,
                REASON_COARSE_SCOPE,
            )
        ) else EXCLUDED
        # Incomplete alone → unknown; any concrete exclusion → excluded.
        if any(
            r in ordered_reasons
            for r in (
                REASON_FOLLOW_UP,
                REASON_SAME_ITEM_RETRY,
                REASON_TEACHING_EXPOSURE,
                REASON_RELATED_EXPOSURE,
                REASON_COARSE_SCOPE,
                REASON_UNSCORED_FOLLOW_UP,
                REASON_UNREVIEWED_CONTENT,
            )
        ):
            decision = EXCLUDED
        elif REASON_INCOMPLETE_HISTORY in ordered_reasons:
            decision = UNKNOWN
        else:
            decision = EXCLUDED
    else:
        decision = ELIGIBLE

    return {
        "decision": decision,
        "policy_version": policy_version,
        "exclusion_reasons": ordered_reasons,
        "exposure_ids": list(dict.fromkeys(exposure_ids)),
        "item_type": item_type,
        "item_id": item_id,
        "concept_topic_scope": scope,
        "cutoff_at": now.isoformat(),
        "legacy": False,
    }


def eligibility_label(decision: str | None) -> str:
    if decision == ELIGIBLE:
        return "Assessment"
    if decision == EXCLUDED:
        return "Practiced with help"
    if decision in (UNKNOWN, LEGACY_UNKNOWN):
        return "Unscored practice"
    return "Unscored practice"
