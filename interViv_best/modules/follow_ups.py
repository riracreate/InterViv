"""Bounded optional follow-up scheduling (Phase 4A).

Rules:
- At most one follow-up per parent; at most two per Interview block.
- Never recursively follow a follow-up.
- Reserve remaining mandatory rounds before allocating optional capacity
  against MAX_TOTAL_ROUNDS (50). Skip optional when no spare capacity.
- Do not renumber completed/assigned rounds; append with stable identity.
- Concurrent requests must not schedule duplicate follow-ups.

Two server-side initiators share these rules (``initiator`` and
``placement`` are internal keyword arguments, never request fields):

- ``candidate`` (default): the candidate's consented request. Appended
  after every assigned round (``placement="append"``), unchanged.
- ``system``: proposed during the parent's own attempt commit and
  inserted immediately after the parent (``placement="after_parent"``).
  Only plans whose mandatory specs all carry ``mandatory_index`` qualify,
  never after the final mandatory round, never ahead of a materialized
  round. The prompt is validated inside :func:`schedule_follow_up_in_session`.
"""

from __future__ import annotations

import copy
from typing import Any
from uuid import uuid4

from backend.models.blocks import MAX_TOTAL_ROUNDS

MAX_FOLLOWUPS_PER_PARENT = 1
MAX_FOLLOWUPS_PER_INTERVIEW_BLOCK = 2

INITIATOR_CANDIDATE = "candidate"
INITIATOR_SYSTEM = "system"
INITIATORS = frozenset({INITIATOR_CANDIDATE, INITIATOR_SYSTEM})
PLACEMENT_APPEND = "append"
PLACEMENT_AFTER_PARENT = "after_parent"
PLACEMENTS = frozenset({PLACEMENT_APPEND, PLACEMENT_AFTER_PARENT})
SYSTEM_FOLLOW_UP_DEFAULT_KIND = "clarification"


def block_follow_up_limit(block: dict[str, Any] | None) -> int:
    """Per-block follow-up cap: 2, or the lower configured ``max_follow_ups``."""
    if isinstance(block, dict):
        configured = block.get("max_follow_ups")
        if isinstance(configured, bool):
            pass
        elif isinstance(configured, int) and configured >= 0:
            return min(MAX_FOLLOWUPS_PER_INTERVIEW_BLOCK, configured)
    return MAX_FOLLOWUPS_PER_INTERVIEW_BLOCK


def block_allows_follow_ups(block: dict[str, Any] | None, session: dict[str, Any] | None = None) -> bool:
    if isinstance(block, dict) and block.get("allow_optional_follow_ups") is True:
        return True
    # Session-level opt-in used when block plan is absent.
    if isinstance(session, dict) and session.get("allow_optional_follow_ups") is True:
        return True
    return False


def session_practice_mode(session: dict[str, Any] | None) -> str:
    """assessment | coached_practice. Assessment defaults follow-ups off."""
    if not isinstance(session, dict):
        return "coached_practice"
    mode = str(session.get("practice_mode") or "").strip().lower()
    if mode in ("assessment", "coached_practice"):
        return mode
    # Infer: after_session review policy on any block ≈ assessment-like.
    plan = session.get("block_plan") or []
    if any(str(b.get("review_policy") or "") == "after_session" for b in plan if isinstance(b, dict)):
        return "assessment"
    return "coached_practice"


def _interview_block_ids(session: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for block in session.get("block_plan") or []:
        if not isinstance(block, dict):
            continue
        if str(block.get("category") or "") == "interview" or str(block.get("round_type") or "") == "technical_short_answer":
            if block.get("id"):
                out.add(str(block["id"]))
    return out


def _block_for_id(session: dict[str, Any], block_id: str | None) -> dict[str, Any] | None:
    if not block_id:
        return None
    for block in session.get("block_plan") or []:
        if isinstance(block, dict) and str(block.get("id")) == str(block_id):
            return block
    return None


def non_follow_up_rounds(rounds: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Rounds excluding follow-ups, order preserved (``is_follow_up`` detection)."""
    return [r for r in (rounds or []) if not (isinstance(r, dict) and r.get("is_follow_up"))]


def pending_follow_ups(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Scheduled-but-unmaterialized follow-up entries from ``expanded_plan``.

    A scheduled follow-up only becomes a round row when progression reaches
    it, so caps must count pending entries too — otherwise sequential or
    concurrent schedules double-book the same parent/block budget. An entry
    is pending while no materialized round carries its ``follow_up_identity``
    (answer progression copies the identity onto the round row).
    """
    rounds = session.get("rounds") or []
    materialized = {
        str(r.get("follow_up_identity") or "")
        for r in rounds
        if r.get("is_follow_up") and r.get("follow_up_identity")
    }
    pending = []
    for entry in session.get("expanded_plan") or []:
        if not isinstance(entry, dict) or not entry.get("is_follow_up"):
            continue
        if str(entry.get("follow_up_identity") or "") in materialized:
            continue
        pending.append(entry)
    return pending


def count_follow_ups_in_block(
    rounds: list[dict[str, Any]],
    block_id: str | None,
    *,
    pending: list[dict[str, Any]] | None = None,
) -> int:
    n = 0
    for r in list(rounds or []) + list(pending or []):
        if not r.get("is_follow_up"):
            continue
        if block_id is None or str(r.get("block_id") or "") == str(block_id):
            n += 1
    return n


def parent_already_has_follow_up(
    rounds: list[dict[str, Any]],
    parent_round: int,
    *,
    pending: list[dict[str, Any]] | None = None,
) -> bool:
    for r in list(rounds or []) + list(pending or []):
        if not r.get("is_follow_up"):
            continue
        if int(r.get("follow_up_parent_round") or -1) == int(parent_round):
            return True
        if str(r.get("follow_up_parent_identity") or "") == f"round:{parent_round}":
            return True
    return False


def mandatory_plan_specs(session: dict[str, Any]) -> list[dict[str, Any]]:
    """Mandatory ``expanded_plan`` entries (every non-follow-up entry)."""
    return [
        e
        for e in (session.get("expanded_plan") or [])
        if isinstance(e, dict) and not e.get("is_follow_up")
    ]


def follow_up_count(session: dict[str, Any]) -> int:
    """Distinct follow-ups, pending or materialized, each counted once.

    A materialized follow-up has both a plan entry and a round row carrying
    the same ``follow_up_identity``; identity de-duplicates the pair.
    Identity-less entries (legacy) count individually.
    """
    identities: set[str] = set()
    anonymous = 0
    for item in list(session.get("expanded_plan") or []) + list(session.get("rounds") or []):
        if not isinstance(item, dict) or not item.get("is_follow_up"):
            continue
        identity = str(item.get("follow_up_identity") or "")
        if identity:
            identities.add(identity)
        else:
            anonymous += 1
    return len(identities) + anonymous


def mandatory_total(session: dict[str, Any]) -> int:
    """Size of the mandatory plan: follow-ups never count."""
    specs = mandatory_plan_specs(session)
    if specs:
        return len(specs)
    return max(0, int(session.get("total_rounds") or 0) - follow_up_count(session))


def mandatory_remaining(session: dict[str, Any], current_round: int) -> int:
    """Rounds still required by the original mandatory plan (excluding follow-ups).

    Pending and materialized follow-ups are both excluded from the mandatory
    total, each once (see :func:`follow_up_count`).
    """
    rounds = session.get("rounds") or []
    # Rounds at or before current that are mandatory.
    mandatory_done = sum(
        1
        for r in rounds
        if not r.get("is_follow_up") and int(r.get("round") or 0) <= int(current_round)
    )
    return max(0, mandatory_total(session) - mandatory_done)


def remaining_questions(session: dict[str, Any], after_round: int) -> int:
    """Mandatory questions still to be asked after ``after_round``.

    Same follow-up filter as :func:`mandatory_remaining`. Plan-backed
    sessions count mandatory entries positioned after ``after_round``;
    entries without a ``round`` fall back to :func:`mandatory_remaining`.
    """
    specs = mandatory_plan_specs(session)
    if specs and all(_positive_int(s.get("round")) for s in specs):
        return sum(1 for s in specs if int(s["round"]) > int(after_round))
    return mandatory_remaining(session, after_round)


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def mandatory_indices_complete(session: dict[str, Any]) -> bool:
    """True when every mandatory spec carries a distinct ``mandatory_index``.

    Sessions created before indices were stamped (or without an expanded
    plan) return False and never receive a system insertion.
    """
    specs = mandatory_plan_specs(session)
    if not specs:
        return False
    indices = [s.get("mandatory_index") for s in specs]
    return all(_positive_int(i) for i in indices) and len(set(indices)) == len(indices)


def spare_capacity(session: dict[str, Any], current_round: int) -> int:
    """Optional slots remaining after reserving mandatory rounds under the 50 cap."""
    rounds = session.get("rounds") or []
    scheduled = max(len(rounds), int(session.get("total_rounds") or 0))
    remaining_mandatory = mandatory_remaining(session, current_round)
    # Capacity left in the hard cap after everything already scheduled.
    hard_left = max(0, MAX_TOTAL_ROUNDS - scheduled)
    # Must keep enough for remaining mandatory after any optional insert.
    return max(0, hard_left - remaining_mandatory)


def _placement_for(initiator: str, placement: str | None) -> str:
    if initiator not in INITIATORS:
        raise ValueError(f"Unknown follow-up initiator: {initiator!r}")
    if placement is None:
        return PLACEMENT_AFTER_PARENT if initiator == INITIATOR_SYSTEM else PLACEMENT_APPEND
    if placement not in PLACEMENTS:
        raise ValueError(f"Unknown follow-up placement: {placement!r}")
    return placement


def _after_parent_blocker(session: dict[str, Any], parent_round: int) -> str:
    """Reason an immediate-next insertion is unsafe, or ``""`` when safe."""
    if not mandatory_indices_complete(session):
        return "mandatory_indices_incomplete"
    if any(
        int(r.get("round") or 0) > int(parent_round)
        for r in (session.get("rounds") or [])
        if isinstance(r, dict)
    ):
        # A later round row already exists: inserting would renumber it.
        return "later_rounds_materialized"
    if remaining_questions(session, parent_round) < 1:
        # Never after the final mandatory round.
        return "no_mandatory_remaining"
    return ""


def can_schedule_follow_up(
    *,
    session: dict[str, Any],
    parent_round_doc: dict[str, Any],
    placement: str = PLACEMENT_APPEND,
) -> tuple[bool, str]:
    """Return (ok, reason_if_not).

    Shared by both initiators. ``placement="after_parent"`` adds the
    immediate-next safety checks on top of the shared caps.
    """
    if parent_round_doc.get("is_follow_up"):
        return False, "recursive_follow_up_forbidden"
    if placement == PLACEMENT_AFTER_PARENT:
        blocker = _after_parent_blocker(session, int(parent_round_doc.get("round") or 0))
        if blocker:
            return False, blocker
    parent_round = int(parent_round_doc.get("round") or 0)
    rounds = list(session.get("rounds") or [])
    pending = pending_follow_ups(session)
    if parent_already_has_follow_up(rounds, parent_round, pending=pending):
        return False, "parent_follow_up_exists"
    block_id = parent_round_doc.get("block_id")
    block = _block_for_id(session, block_id)
    mode = session_practice_mode(session)
    if mode == "assessment" and not block_allows_follow_ups(block, session):
        return False, "assessment_follow_ups_disabled"
    if not block_allows_follow_ups(block, session) and mode != "coached_practice":
        # Coached practice may still require explicit block opt-in when blocks exist.
        if session.get("block_plan"):
            return False, "follow_ups_disabled_for_block"
    if session.get("block_plan") and not block_allows_follow_ups(block, session):
        return False, "follow_ups_disabled_for_block"
    # Interview-block cap (pending entries count: they hold budget).
    limit = block_follow_up_limit(block)
    interview_ids = _interview_block_ids(session)
    if block_id and str(block_id) in interview_ids:
        if count_follow_ups_in_block(rounds, str(block_id), pending=pending) >= limit:
            return False, "block_follow_up_cap"
    elif block and str(block.get("category") or "") == "interview":
        if count_follow_ups_in_block(rounds, str(block_id), pending=pending) >= limit:
            return False, "block_follow_up_cap"
    if spare_capacity(session, parent_round) < 1:
        return False, "no_capacity"
    return True, ""


def build_follow_up_plan_entry(
    *,
    parent_round_doc: dict[str, Any],
    reviewed_bundle: dict[str, Any] | None,
    clarification_prompt: str | None = None,
) -> dict[str, Any]:
    """Build an expanded_plan entry for an optional follow-up.

    Reviewed bundle → numerically scored practice (still excluded from primary
    metrics). Otherwise → unscored clarification with null score policy.
    """
    parent_round = int(parent_round_doc.get("round") or 0)
    block_id = parent_round_doc.get("block_id")
    identity = f"followup:{parent_round}:{uuid4().hex[:8]}"
    if reviewed_bundle:
        return {
            "round_type": "technical_short_answer",
            "skill": parent_round_doc.get("skill"),
            "block_id": block_id,
            "block_position": parent_round_doc.get("block_position"),
            "block_category": parent_round_doc.get("block_category") or "interview",
            "is_follow_up": True,
            "follow_up_parent_round": parent_round,
            "follow_up_parent_identity": f"round:{parent_round}",
            "follow_up_identity": identity,
            "follow_up_scoring": "reviewed",
            "purpose": "follow_up",
            "bundle_id": reviewed_bundle.get("bundle_id"),
            "version": reviewed_bundle.get("version"),
            "review_policy": (parent_round_doc.get("config_json") or {}).get("review_policy", "none"),
        }
    prompt = (clarification_prompt or "").strip() or (
        "Clarify the key idea from the previous question in your own words."
    )
    return {
        "round_type": "technical_short_answer",
        "skill": parent_round_doc.get("skill"),
        "block_id": block_id,
        "block_position": parent_round_doc.get("block_position"),
        "block_category": parent_round_doc.get("block_category") or "interview",
        "is_follow_up": True,
        "follow_up_parent_round": parent_round,
        "follow_up_parent_identity": f"round:{parent_round}",
        "follow_up_identity": identity,
        "follow_up_scoring": "unreviewed",
        "purpose": "follow_up",
        "clarification_prompt": prompt,
        "review_policy": (parent_round_doc.get("config_json") or {}).get("review_policy", "none"),
    }


def build_system_follow_up_plan_entry(
    *,
    parent_round_doc: dict[str, Any],
    prompt: str,
    kind: str = SYSTEM_FOLLOW_UP_DEFAULT_KIND,
) -> dict[str, Any]:
    """Plan entry for a system-initiated, unscored follow-up.

    Built directly from the supplied prompt; materialization never consults
    the bank selector. The parent's skill is copied onto the spec (both
    ``skill`` and ``skills``) so round-to-skill resolution needs no index.
    No ``mandatory_index`` is stored: follow-ups are never mandatory.
    """
    parent_round = int(parent_round_doc.get("round") or 0)
    skill = parent_round_doc.get("skill")
    return {
        "round_type": "technical_short_answer",
        "skill": skill,
        "skills": [skill] if skill else [],
        "block_id": parent_round_doc.get("block_id"),
        "block_position": parent_round_doc.get("block_position"),
        "block_category": parent_round_doc.get("block_category") or "interview",
        "is_follow_up": True,
        "follow_up_parent_round": parent_round,
        "follow_up_parent_identity": f"round:{parent_round}",
        "follow_up_identity": f"followup:{parent_round}:{uuid4().hex[:8]}",
        "follow_up_scoring": "unreviewed",
        "follow_up_initiator": INITIATOR_SYSTEM,
        "follow_up_kind": str(kind or SYSTEM_FOLLOW_UP_DEFAULT_KIND),
        "purpose": "follow_up",
        "clarification_prompt": str(prompt or "").strip(),
        "review_policy": (parent_round_doc.get("config_json") or {}).get("review_policy", "none"),
    }


def is_system_follow_up(item: dict[str, Any] | None) -> bool:
    """True for a system-initiated follow-up spec or round."""
    if not isinstance(item, dict) or not item.get("is_follow_up"):
        return False
    initiator = item.get("follow_up_initiator") or (item.get("config_json") or {}).get(
        "follow_up_initiator"
    )
    return initiator == INITIATOR_SYSTEM


def build_system_follow_up_round(
    spec: dict[str, Any],
    *,
    parent_round_doc: dict[str, Any] | None,
    elo_before: float | None,
) -> dict[str, Any]:
    """Prepared (``ready``) round document for a system follow-up spec.

    The question is the spec's validated prompt; no bank selection happens,
    so a bank miss can never block it. Activation starts it like any round.
    """
    parent = parent_round_doc or {}
    prompt = str(spec.get("clarification_prompt") or "").strip()
    skill = spec.get("skill") or parent.get("skill")
    difficulty = parent.get("difficulty") or "medium"
    follow_up_keys = {
        "is_follow_up": True,
        "follow_up_parent_round": spec.get("follow_up_parent_round"),
        "follow_up_identity": spec.get("follow_up_identity"),
        "follow_up_scoring": spec.get("follow_up_scoring") or "unreviewed",
    }
    # Server-only (ROUND_PRIVATE_META_KEYS): persisted in private metadata,
    # stripped from every client payload; never placed in config_json.
    private_keys = {
        "follow_up_initiator": spec.get("follow_up_initiator") or INITIATOR_SYSTEM,
        "follow_up_kind": spec.get("follow_up_kind") or SYSTEM_FOLLOW_UP_DEFAULT_KIND,
    }
    return {
        "round": int(spec["round"]),
        "skill": skill,
        "round_type": "technical_short_answer",
        "artifact_json": {},
        "config_json": dict(follow_up_keys),
        "question": prompt,
        "answer_text": None,
        "nlp_score": None,
        "svm_label": None,
        "kg_score": None,
        "ner_entities": [],
        "final_score": None,
        "difficulty": difficulty,
        "difficulty_change": None,
        "feedback": {"content": [], "strengths": [], "next_step": ""},
        "elo_before": elo_before,
        "elo_after": None,
        "question_context": {
            "question": prompt,
            "skill": skill,
            "difficulty": difficulty,
            "source": "system_follow_up",
            "followups": [],
        },
        "started_at": None,
        "expires_at": None,
        "status": "ready",
        "block_id": spec.get("block_id"),
        "block_position": spec.get("block_position"),
        "block_category": spec.get("block_category") or "interview",
        "block_index": parent.get("block_index"),
        "block_total": parent.get("block_total"),
        "purpose": "follow_up",
        **follow_up_keys,
        **private_keys,
    }


def follow_up_scoring_of(round_doc: dict[str, Any] | None) -> str | None:
    """``follow_up_scoring`` from the round, or its legacy config copy."""
    if not isinstance(round_doc, dict):
        return None
    return round_doc.get("follow_up_scoring") or (round_doc.get("config_json") or {}).get(
        "follow_up_scoring"
    )


def is_system_or_unreviewed_follow_up(round_doc: dict[str, Any] | None) -> bool:
    """THE Slice 1 predicate for follow-ups that leave assessed presentation.

    True for a system-initiated follow-up, or any unreviewed (unscored)
    follow-up -- regardless of a stored numeric score. False for reviewed,
    scored candidate follow-ups, which keep today's behaviour everywhere.
    Used for report reveal exposures, rules-replay eligibility, and the
    server-derived report-section field.
    """
    if not isinstance(round_doc, dict):
        return False
    from modules.assistance_policy import is_follow_up_round

    if not is_follow_up_round(round_doc):
        return False
    return is_system_follow_up(round_doc) or follow_up_scoring_of(round_doc) == "unreviewed"


def report_exposure_exempt(round_doc: dict[str, Any] | None) -> bool:
    """Report reveals record no teaching exposure for this round.

    Only system-initiated or unreviewed follow-ups are exempt, even when a
    numeric score is present. Reviewed, scored candidate follow-ups keep
    today's reveal exposure.
    """
    return is_system_or_unreviewed_follow_up(round_doc)


def non_system_follow_up_rounds(rounds: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Rounds excluding SYSTEM follow-ups (order preserved).

    Selector isolation filter for asked-question lists and mandatory
    rounds' eligibility history. Candidate follow-ups stay in: a reviewed
    candidate follow-up serves a real bank question, which must stay in the
    asked list so it is never re-served.
    """
    return [r for r in (rounds or []) if not is_system_follow_up(r)]


def _insert_after_parent(
    session: dict[str, Any],
    *,
    parent_round: int,
    plan_entry: dict[str, Any],
) -> dict[str, Any]:
    """Place ``plan_entry`` at ``parent_round + 1``; shift only later entries.

    Callers have verified (``_after_parent_blocker``) that no round row
    exists after the parent, so every shifted entry is unmaterialized.
    ``mandatory_index`` values travel with their specs unchanged.
    """
    insert_round = int(parent_round) + 1
    new_total = int(session.get("total_rounds") or 0) + 1
    if new_total > MAX_TOTAL_ROUNDS:
        return {"scheduled": False, "reason": "no_capacity"}
    expanded: list[dict[str, Any]] = []
    position = None
    for entry in session.get("expanded_plan") or []:
        entry = copy.deepcopy(entry)
        round_number = int(entry.get("round") or 0) if isinstance(entry, dict) else 0
        if round_number >= insert_round:
            if position is None:
                position = len(expanded)
            entry["round"] = round_number + 1
        expanded.append(entry)
    new_entry = {**copy.deepcopy(plan_entry), "round": insert_round}
    expanded.insert(len(expanded) if position is None else position, new_entry)
    result: dict[str, Any] = {
        "scheduled": True,
        "reason": "",
        "expanded_plan": expanded,
        "total_rounds": new_total,
        "follow_up_identity": plan_entry.get("follow_up_identity"),
        "insert_at": insert_round,
    }
    round_plan = session.get("round_plan")
    if isinstance(round_plan, list):
        placeholder = list(round_plan)
        placeholder.insert(min(parent_round, len(placeholder)), plan_entry.get("round_type") or "technical_short_answer")
        result["round_plan"] = placeholder
    return result


def schedule_follow_up_in_session(
    session: dict[str, Any],
    *,
    parent_round_doc: dict[str, Any],
    plan_entry: dict[str, Any],
    initiator: str = INITIATOR_CANDIDATE,
    placement: str | None = None,
    parent_answer: str | None = None,
    question_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Schedule one follow-up. Returns updated fields to merge into the session.

    Caller must hold the session submit/schedule lock and persist atomically.
    The input session is not mutated.

    ``initiator`` and ``placement`` are server-side only. Candidate requests
    (the default) append after every assigned round exactly as before.
    System requests insert immediately after the parent and validate the
    prompt here, against the candidate's submitted ``parent_answer`` and the
    parent's ``question_context`` (rubric source); rejection changes nothing.
    """
    placement = _placement_for(initiator, placement)
    ok, reason = can_schedule_follow_up(
        session=session, parent_round_doc=parent_round_doc, placement=placement
    )
    if not ok:
        return {"scheduled": False, "reason": reason}
    if initiator == INITIATOR_SYSTEM:
        from modules.system_follow_ups import validate_system_prompt

        ok, reason = validate_system_prompt(
            plan_entry.get("clarification_prompt"),
            parent_answer=parent_answer,
            question_context=(
                question_context
                if question_context is not None
                else parent_round_doc.get("question_context") or {}
            ),
        )
        if not ok:
            return {"scheduled": False, "reason": reason}
    if placement == PLACEMENT_AFTER_PARENT:
        return _insert_after_parent(
            session,
            parent_round=int(parent_round_doc.get("round") or 0),
            plan_entry=plan_entry,
        )

    expanded = list(session.get("expanded_plan") or [])
    # Insert after the parent's plan index when possible; else append.
    parent_round = int(parent_round_doc.get("round") or 0)
    insert_at = min(parent_round, len(expanded))
    # Prefer appending after all currently assigned mandatory+optional so we
    # never renumber already materialized rounds.
    insert_at = len(expanded)
    new_total = max(int(session.get("total_rounds") or 0) + 1, len(expanded) + 1)
    if new_total > MAX_TOTAL_ROUNDS:
        return {"scheduled": False, "reason": "no_capacity"}
    # Progression finds a round's spec by its ``round`` number; without it
    # the follow-up was built as an ordinary question.
    expanded.append({**plan_entry, "round": new_total})
    return {
        "scheduled": True,
        "reason": "",
        "expanded_plan": expanded,
        "total_rounds": new_total,
        "follow_up_identity": plan_entry.get("follow_up_identity"),
        "insert_at": insert_at,
    }


# ── Client-facing derived fields (Checkpoint C) ──────────────────────
#
# Backward-compatible additions computed on the server from stored state.
# Mandatory fields are omitted whenever the plan lacks complete indices
# (legacy sessions), so legacy clients and payloads are unchanged.

SYSTEM_FOLLOW_UP_LABEL = "Follow-up (not scored)"
# Progress position of a candidate-requested follow-up. It always comes after
# every mandatory round, so it has no "n/N" position of its own; the existing
# eligibility and report labels of candidate follow-ups are unchanged.
CANDIDATE_FOLLOW_UP_PROGRESS_LABEL = "Optional follow-up"
REPORT_SECTION_FOLLOW_UPS = "follow_ups"
REPORT_SECTION_ROUNDS = "rounds"
_CLOSED_STATUSES = frozenset({"submitted", "expired"})


def _mandatory_spec_at(session: dict[str, Any], round_number: int) -> dict[str, Any] | None:
    return next(
        (s for s in mandatory_plan_specs(session) if int(s.get("round") or 0) == int(round_number)),
        None,
    )


def mandatory_index_for_round(session: dict[str, Any], round_doc: dict[str, Any] | None) -> int | None:
    """Mandatory position of a delivered round; a follow-up takes its parent's.

    Materialized rounds never shift, so the spec at a mandatory round's
    number is the one it was built from.
    """
    if not isinstance(round_doc, dict) or not mandatory_indices_complete(session):
        return None
    from modules.assistance_policy import is_follow_up_round

    number = round_doc.get("round")
    if is_follow_up_round(round_doc):
        number = round_doc.get("follow_up_parent_round") or (round_doc.get("config_json") or {}).get(
            "follow_up_parent_round"
        )
    if number is None:
        return None
    spec = _mandatory_spec_at(session, int(number))
    index = (spec or {}).get("mandatory_index")
    return index if _positive_int(index) else None


def mandatory_progress(session: dict[str, Any]) -> dict[str, int] | None:
    """``mandatory_total`` / ``mandatory_completed``, or None for legacy plans."""
    if not mandatory_indices_complete(session):
        return None
    from modules.assistance_policy import is_follow_up_round

    completed = sum(
        1
        for r in (session.get("rounds") or [])
        if isinstance(r, dict) and not is_follow_up_round(r)
        and str(r.get("status") or "") in _CLOSED_STATUSES
    )
    return {"mandatory_total": len(mandatory_plan_specs(session)), "mandatory_completed": completed}


def system_follow_up_scheduled_for(session: dict[str, Any], parent_round: int | None) -> bool:
    """A system follow-up (pending or materialized) exists for this parent."""
    if parent_round is None:
        return False
    for item in list(session.get("expanded_plan") or []) + list(session.get("rounds") or []):
        if is_system_follow_up(item) and int(item.get("follow_up_parent_round") or -1) == int(parent_round):
            return True
    return False


def progress_label_for(round_doc: dict[str, Any] | None) -> str | None:
    """``"Optional follow-up"`` for a candidate-requested follow-up, else None.

    Independent of mandatory indices, so index-less (legacy) plans get it too.
    """
    from modules.assistance_policy import is_follow_up_round

    if isinstance(round_doc, dict) and is_follow_up_round(round_doc) and not is_system_follow_up(round_doc):
        return CANDIDATE_FOLLOW_UP_PROGRESS_LABEL
    return None


def delivered_round_fields(session: dict[str, Any], round_doc: dict[str, Any] | None) -> dict[str, Any]:
    """Derived, client-safe fields for one delivered round.

    ``mandatory_index`` (omitted for legacy plans), ``follow_up_label`` for
    system follow-ups only (candidate follow-ups keep their existing
    labels), ``progress_label`` for candidate-requested follow-ups only, and
    ``system_follow_up_scheduled`` for non-follow-up rounds.
    """
    if not isinstance(round_doc, dict):
        return {}
    from modules.assistance_policy import is_follow_up_round

    out: dict[str, Any] = {}
    index = mandatory_index_for_round(session, round_doc)
    if index is not None:
        out["mandatory_index"] = index
    if is_system_follow_up(round_doc):
        out["follow_up_label"] = SYSTEM_FOLLOW_UP_LABEL
    progress_label = progress_label_for(round_doc)
    if progress_label:
        out["progress_label"] = progress_label
    if not is_follow_up_round(round_doc):
        out["system_follow_up_scheduled"] = system_follow_up_scheduled_for(session, round_doc.get("round"))
    return out


def report_section_for(round_doc: dict[str, Any] | None) -> str:
    """Server-derived report section (same predicate as every backend rule)."""
    return REPORT_SECTION_FOLLOW_UPS if is_system_or_unreviewed_follow_up(round_doc) else REPORT_SECTION_ROUNDS
