"""Bounded optional follow-up scheduling (Phase 4A).

Rules:
- At most one follow-up per parent; at most two per Interview block.
- Never recursively follow a follow-up.
- Reserve remaining mandatory rounds before allocating optional capacity
  against MAX_TOTAL_ROUNDS (50). Skip optional when no spare capacity.
- Do not renumber completed/assigned rounds; append with stable identity.
- Concurrent requests must not schedule duplicate follow-ups.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.models.blocks import MAX_TOTAL_ROUNDS

MAX_FOLLOWUPS_PER_PARENT = 1
MAX_FOLLOWUPS_PER_INTERVIEW_BLOCK = 2


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


def count_follow_ups_in_block(rounds: list[dict[str, Any]], block_id: str | None) -> int:
    n = 0
    for r in rounds:
        if not r.get("is_follow_up"):
            continue
        if block_id is None or str(r.get("block_id") or "") == str(block_id):
            n += 1
    return n


def parent_already_has_follow_up(rounds: list[dict[str, Any]], parent_round: int) -> bool:
    for r in rounds:
        if not r.get("is_follow_up"):
            continue
        if int(r.get("follow_up_parent_round") or -1) == int(parent_round):
            return True
        if str(r.get("follow_up_parent_identity") or "") == f"round:{parent_round}":
            return True
    return False


def mandatory_remaining(session: dict[str, Any], current_round: int) -> int:
    """Rounds still required by the original mandatory plan (excluding follow-ups)."""
    total = int(session.get("total_rounds") or 0)
    # Count already-scheduled follow-ups so we can separate mandatory capacity.
    rounds = session.get("rounds") or []
    follow_ups_scheduled = sum(1 for r in rounds if r.get("is_follow_up"))
    expanded = session.get("expanded_plan") or []
    mandatory_total = max(0, len(expanded) - follow_ups_scheduled) if expanded else max(0, total - follow_ups_scheduled)
    # Rounds at or before current that are mandatory.
    mandatory_done = sum(
        1
        for r in rounds
        if not r.get("is_follow_up") and int(r.get("round") or 0) <= int(current_round)
    )
    return max(0, mandatory_total - mandatory_done)


def spare_capacity(session: dict[str, Any], current_round: int) -> int:
    """Optional slots remaining after reserving mandatory rounds under the 50 cap."""
    rounds = session.get("rounds") or []
    scheduled = max(len(rounds), int(session.get("total_rounds") or 0))
    remaining_mandatory = mandatory_remaining(session, current_round)
    # Capacity left in the hard cap after everything already scheduled.
    hard_left = max(0, MAX_TOTAL_ROUNDS - scheduled)
    # Must keep enough for remaining mandatory after any optional insert.
    return max(0, hard_left - remaining_mandatory)


def can_schedule_follow_up(
    *,
    session: dict[str, Any],
    parent_round_doc: dict[str, Any],
) -> tuple[bool, str]:
    """Return (ok, reason_if_not)."""
    if parent_round_doc.get("is_follow_up"):
        return False, "recursive_follow_up_forbidden"
    parent_round = int(parent_round_doc.get("round") or 0)
    rounds = list(session.get("rounds") or [])
    if parent_already_has_follow_up(rounds, parent_round):
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
    # Interview-block cap.
    interview_ids = _interview_block_ids(session)
    if block_id and str(block_id) in interview_ids:
        if count_follow_ups_in_block(rounds, str(block_id)) >= MAX_FOLLOWUPS_PER_INTERVIEW_BLOCK:
            return False, "block_follow_up_cap"
    elif block and str(block.get("category") or "") == "interview":
        if count_follow_ups_in_block(rounds, str(block_id)) >= MAX_FOLLOWUPS_PER_INTERVIEW_BLOCK:
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


def schedule_follow_up_in_session(
    session: dict[str, Any],
    *,
    parent_round_doc: dict[str, Any],
    plan_entry: dict[str, Any],
) -> dict[str, Any]:
    """Append follow-up to expanded_plan and bump total_rounds. Mutates session copy fields.

    Caller must hold the session submit/schedule lock and persist atomically.
    Returns updated fields to merge into the session document.
    """
    ok, reason = can_schedule_follow_up(session=session, parent_round_doc=parent_round_doc)
    if not ok:
        return {"scheduled": False, "reason": reason}

    expanded = list(session.get("expanded_plan") or [])
    # Insert after the parent's plan index when possible; else append.
    parent_round = int(parent_round_doc.get("round") or 0)
    insert_at = min(parent_round, len(expanded))
    # Prefer appending after all currently assigned mandatory+optional so we
    # never renumber already materialized rounds.
    insert_at = len(expanded)
    expanded.append(plan_entry)
    new_total = max(int(session.get("total_rounds") or 0) + 1, len(expanded))
    if new_total > MAX_TOTAL_ROUNDS:
        return {"scheduled": False, "reason": "no_capacity"}
    return {
        "scheduled": True,
        "reason": "",
        "expanded_plan": expanded,
        "total_rounds": new_total,
        "follow_up_identity": plan_entry.get("follow_up_identity"),
        "insert_at": insert_at,
    }
