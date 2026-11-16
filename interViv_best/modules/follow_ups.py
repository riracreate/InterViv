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


def _extract_gap_concepts(parent_round_doc: dict[str, Any]) -> list[str]:
    """Extract concept IDs needing clarification, prioritized contradicted > missing > uncertain."""
    buckets: dict[str, list[str]] = {
        "contradicted": [],
        "missing": [],
        "uncertain": [],
    }
    seen: set[str] = set()

    def _add(bucket: str, val: Any) -> None:
        if isinstance(val, str):
            norm = val.strip().lower()
            if norm and norm not in seen:
                seen.add(norm)
                buckets[bucket].append(norm)
        elif isinstance(val, (list, tuple)):
            for item in val:
                _add(bucket, item)

    containers: list[dict[str, Any]] = []
    for cand in (
        parent_round_doc,
        parent_round_doc.get("round_meta"),
        parent_round_doc.get("scoring_breakdown"),
        parent_round_doc.get("evaluation"),
    ):
        if isinstance(cand, dict):
            containers.append(cand)
            for sub_key in ("concept_evaluation", "concept_eval", "v2"):
                sub = cand.get(sub_key)
                if isinstance(sub, dict):
                    containers.append(sub)

    for container in containers:
        _add("contradicted", container.get("contradicted"))
        _add("contradicted", container.get("contradicted_concepts"))
        _add("missing", container.get("missing"))
        _add("missing", container.get("missing_concepts"))
        _add("missing", container.get("concept_gaps"))
        _add("uncertain", container.get("uncertain"))
        _add("uncertain", container.get("uncertain_concepts"))
        concepts = container.get("concepts")
        if isinstance(concepts, list):
            for c in concepts:
                if not isinstance(c, dict):
                    continue
                state = str(c.get("state") or "").strip().lower()
                if state in buckets:
                    cid = c.get("concept_id") or c.get("id")
                    _add(state, cid)

    return buckets["contradicted"] + buckets["missing"] + buckets["uncertain"]


def select_follow_up_spec(
    parent_round_doc: dict[str, Any],
    followups: list[Any] | None,
) -> tuple[str | None, str | None]:
    """Select the follow-up (prompt, targets_concept) matching parent concept gaps."""
    candidates: list[dict[str, str | None]] = []
    for item in (followups or []):
        if isinstance(item, dict):
            prompt = str(item.get("prompt") or "").strip()
            target = str(item.get("targets_concept") or "").strip() or None
            if prompt:
                candidates.append({"prompt": prompt, "targets_concept": target})
        elif isinstance(item, str):
            prompt = item.strip()
            if prompt:
                candidates.append({"prompt": prompt, "targets_concept": None})
        elif item is not None:
            prompt = str(item).strip()
            if prompt:
                candidates.append({"prompt": prompt, "targets_concept": None})

    if not candidates:
        return None, None

    gaps = _extract_gap_concepts(parent_round_doc or {})
    for gap_id in gaps:
        for cand in candidates:
            target = (cand.get("targets_concept") or "").strip().lower()
            if target and target == gap_id:
                return cand["prompt"], cand["targets_concept"]

    return candidates[0]["prompt"], candidates[0]["targets_concept"]


def build_follow_up_plan_entry(
    *,
    parent_round_doc: dict[str, Any],
    reviewed_bundle: dict[str, Any] | None,
    clarification_prompt: str | None = None,
    targets_concept: str | None = None,
) -> dict[str, Any]:
    """Build an expanded_plan entry for an optional follow-up.

    Reviewed bundle → numerically scored practice (still excluded from primary
    metrics). Otherwise → unscored clarification with null score policy.
    """
    parent_round = int(parent_round_doc.get("round") or 0)
    block_id = parent_round_doc.get("block_id")
    identity = f"followup:{parent_round}:{uuid4().hex[:8]}"
    if reviewed_bundle:
        entry: dict[str, Any] = {
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
        if targets_concept:
            entry["targets_concept"] = targets_concept
        return entry
    prompt = (clarification_prompt or "").strip() or (
        "Clarify the key idea from the previous question in your own words."
    )
    entry = {
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
    if targets_concept:
        entry["targets_concept"] = targets_concept
    return entry


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


# ── Slice 1: Inline bundle follow-ups (staged flow) ──────────────────────────
import copy
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

_slice1_logger = logging.getLogger(__name__)
_DEFAULT_FOLLOWUP_AUDIT_PATH = (
    Path(__file__).resolve().parents[1] / "artifacts" / "followup_decisions_audit.jsonl"
)


def staged_inline_follow_ups_enabled() -> bool:
    """Return True when STAGED_INLINE_FOLLOW_UPS opt-in flag is active."""
    from backend.config import get_settings

    return bool(get_settings().staged_inline_follow_ups)


def resolve_followup_audit_path() -> Path:
    """Resolve JSONL path for Amendment A6 follow-up decision audit logs."""
    override = os.getenv("FOLLOWUP_DECISIONS_AUDIT_PATH", "").strip()
    if override:
        return Path(override)
    return _DEFAULT_FOLLOWUP_AUDIT_PATH


def log_follow_up_decision(decision_record: dict[str, Any] | None) -> None:
    """Record one committed inline follow-up decision (structured log + JSONL)."""
    if not isinstance(decision_record, dict) or not decision_record:
        return
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **decision_record,
    }
    _slice1_logger.info(
        "inline_follow_up_decision %s",
        json.dumps(record, ensure_ascii=True, sort_keys=True),
    )
    audit_path = resolve_followup_audit_path()
    try:
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
    except OSError:
        _slice1_logger.warning(
            "Unable to append follow-up decision audit entry to %s",
            audit_path,
            exc_info=True,
        )


def _concept_match_keys(text: Any) -> set[str]:
    """Return normalized match keys so IDs like ``hash_collisions`` match reliably."""
    raw = str(text or "").strip()
    if not raw:
        return set()
    from modules import question_concepts

    keys = {
        raw.casefold(),
        re.sub(r"[_\W]+", " ", raw.casefold()).strip(),
        question_concepts.normalize(raw),
        question_concepts.canonical(raw),
    }
    return {k for k in keys if k}


def _extract_concept_label(item: Any) -> str | None:
    if isinstance(item, dict):
        val = str(
            item.get("concept") or item.get("concept_id") or item.get("id") or ""
        ).strip()
    else:
        val = str(item or "").strip()
    return val or None


def _collect_concepts_from_containers(
    containers: list[Any], keys: tuple[str, ...]
) -> list[str]:
    found: list[str] = []
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in keys:
            raw_list = container.get(key)
            if not isinstance(raw_list, (list, tuple, set)):
                continue
            for item in raw_list:
                label = _extract_concept_label(item)
                if label:
                    found.append(label)
    return found


def extract_inline_concept_gaps(parent_round_doc: dict[str, Any]) -> list[tuple[str, str]]:
    """Return ordered ``(concept, gap_status)`` tuples with strict priority.

    Priority order:
      1. ``contradicted`` concepts first (never skipped for a mere missing concept).
      2. ``missing`` concepts next (``not_demonstrated`` / ``missed``).

    Concepts evaluated as ``uncertain`` (or ``supported`` / ``matched``) are
    explicitly excluded and never trigger a follow-up. When ``bundle_v2`` trace
    entries are present in ``concept_match_trace``, they are authoritative for
    missed concepts so legacy KG keyword noise does not trigger spurious gaps.
    """
    if not isinstance(parent_round_doc, dict):
        return []
    breakdown = parent_round_doc.get("scoring_breakdown") or {}
    if not isinstance(breakdown, dict):
        breakdown = {}
    concepts_dict = breakdown.get("concepts") or parent_round_doc.get("concepts") or {}
    if not isinstance(concepts_dict, dict):
        concepts_dict = {}
    round_meta = parent_round_doc.get("round_meta") or {}
    if not isinstance(round_meta, dict):
        round_meta = {}

    containers = [round_meta, concepts_dict, breakdown, parent_round_doc]
    statuses = concepts_dict.get("concept_statuses") or {}
    if not isinstance(statuses, dict):
        statuses = {}

    uncertain_keys: set[str] = set()
    supported_keys: set[str] = set()
    for label in _collect_concepts_from_containers(
        containers, ("uncertain", "uncertain_concepts")
    ):
        uncertain_keys.update(_concept_match_keys(label))
    for label in statuses.get("uncertain") or []:
        lbl = _extract_concept_label(label)
        if lbl:
            uncertain_keys.update(_concept_match_keys(lbl))
    for label in statuses.get("matched") or []:
        lbl = _extract_concept_label(label)
        if lbl:
            supported_keys.update(_concept_match_keys(lbl))

    raw_trace = concepts_dict.get("concept_match_trace") or []
    traces = [entry for entry in raw_trace if isinstance(entry, dict)]
    for entry in traces:
        label = _extract_concept_label(entry)
        if not label:
            continue
        method = str(entry.get("method") or "").strip().lower()
        status_val = str(entry.get("status") or "").strip().lower()
        if method == "uncertain" or status_val == "uncertain":
            uncertain_keys.update(_concept_match_keys(label))
        elif method == "supported" or status_val == "matched":
            supported_keys.update(_concept_match_keys(label))

    contradicted: list[str] = []
    missing: list[str] = []
    bundle_v2_traces = [t for t in traces if t.get("source") == "bundle_v2"]

    if bundle_v2_traces:
        for entry in bundle_v2_traces:
            label = _extract_concept_label(entry)
            if not label:
                continue
            method = str(entry.get("method") or "").strip().lower()
            status_val = str(entry.get("status") or "").strip().lower()
            if method == "contradicted":
                contradicted.append(label)
            elif (
                method == "uncertain"
                or status_val == "uncertain"
                or method == "supported"
                or status_val == "matched"
            ):
                continue
            elif method in {"not_demonstrated", "missing"} or status_val == "missed":
                missing.append(label)
        # Also allow explicit contradiction markers if recorded alongside trace.
        contradicted.extend(
            _collect_concepts_from_containers(
                containers, ("contradicted", "contradicted_concepts")
            )
        )
    else:
        for entry in traces:
            label = _extract_concept_label(entry)
            if not label:
                continue
            method = str(entry.get("method") or "").strip().lower()
            status_val = str(entry.get("status") or "").strip().lower()
            if method == "contradicted":
                contradicted.append(label)
            elif (
                method in {"not_demonstrated", "missing", "not_matched"}
                or (status_val == "missed" and method != "uncertain")
            ):
                missing.append(label)
        contradicted.extend(
            _collect_concepts_from_containers(
                containers, ("contradicted", "contradicted_concepts")
            )
        )
        missing.extend(
            _collect_concepts_from_containers(
                containers, ("missing", "missing_concepts", "missed", "missed_concepts")
            )
        )

    seen_keys: set[str] = set()
    ordered_gaps: list[tuple[str, str]] = []
    for label in contradicted:
        keys = _concept_match_keys(label)
        if not keys or (keys & seen_keys) or (keys & uncertain_keys):
            continue
        seen_keys.update(keys)
        ordered_gaps.append((label, "contradicted"))

    for label in missing:
        keys = _concept_match_keys(label)
        if (
            not keys
            or (keys & seen_keys)
            or (keys & uncertain_keys)
            or (keys & supported_keys)
        ):
            continue
        seen_keys.update(keys)
        ordered_gaps.append((label, "missing"))

    return ordered_gaps


def select_inline_follow_up_spec(
    followups: list[Any] | None,
    gaps: list[tuple[str, str]],
) -> dict[str, Any] | None:
    """Pick the bundle follow-up targeting the highest-priority concept gap.

    Iterates ``gaps`` in ``contradicted`` -> ``missing`` order so a
    ``contradicted`` gap always wins regardless of ``followups`` order. Never
    falls back to an untargeted item or ``followups[0]`` when nothing matches.
    """
    if not gaps or not followups:
        return None
    candidates: list[dict[str, Any]] = []
    for item in followups:
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt") or item.get("question") or "").strip()
        target = str(item.get("targets_concept") or "").strip()
        if not prompt or not target:
            continue
        target_keys = _concept_match_keys(target)
        if not target_keys:
            continue
        candidates.append(
            {
                "prompt": prompt,
                "targets_concept": target,
                "target_keys": target_keys,
            }
        )
    if not candidates:
        return None

    for gap_concept, gap_status in gaps:
        gap_keys = _concept_match_keys(gap_concept)
        if not gap_keys:
            continue
        for cand in candidates:
            if cand["target_keys"] & gap_keys:
                return {
                    "prompt": cand["prompt"],
                    "targets_concept": cand["targets_concept"],
                    "gap_concept": gap_concept,
                    "gap_status": gap_status,
                }
    return None


def can_schedule_inline_follow_up(
    session: dict[str, Any],
    parent_round_doc: dict[str, Any],
) -> tuple[bool, str | None]:
    """Validate Q2/A5 eligibility for inline bundle follow-up scheduling."""
    if session_practice_mode(session) != "coached_practice":
        return False, "practice_mode_assessment"
    if not isinstance(parent_round_doc, dict) or parent_round_doc.get("round") is None:
        return False, "missing_parent_round"
    if (
        parent_round_doc.get("is_follow_up")
        or parent_round_doc.get("follow_up_parent_round") is not None
        or (parent_round_doc.get("round_meta") or {}).get("purpose") == "follow_up"
        or parent_round_doc.get("purpose") == "follow_up"
    ):
        return False, "parent_is_follow_up"
    parent_type = str(parent_round_doc.get("round_type") or "").strip()
    if parent_type and parent_type != "technical_short_answer":
        return False, "non_technical_round"
    from modules.staged_flow import round_stage

    parent_stage = round_stage(parent_round_doc)
    if parent_stage is not None and parent_stage != "core":
        return False, "non_core_stage"
    if (parent_round_doc.get("round_meta") or {}).get("skipped"):
        return False, "parent_skipped"

    block = _block_for_id(session, parent_round_doc.get("block_id"))
    if block is not None:
        category = str(block.get("category") or "").strip().lower()
        if category and category != "interview":
            return False, "non_interview_block"
    limit = block_follow_up_limit(block)
    if limit <= 0:
        return False, "block_cap_reached"

    parent_round = int(parent_round_doc["round"])
    rounds = list(session.get("rounds") or [])
    pending = pending_follow_ups(session)
    if parent_already_has_follow_up(rounds, parent_round, pending=pending):
        return False, "already_has_follow_up"
    block_id = parent_round_doc.get("block_id")
    interview_ids = _interview_block_ids(session)
    if block_id and (
        str(block_id) in interview_ids
        or (block and str(block.get("category") or "") == "interview")
    ):
        if count_follow_ups_in_block(rounds, str(block_id), pending=pending) >= limit:
            return False, "block_cap_reached"
    elif block_id is None:
        if count_follow_ups_in_block(rounds, None, pending=pending) >= limit:
            return False, "block_cap_reached"

    if spare_capacity(session, parent_round) < 1:
        return False, "no_capacity"

    existing_round_nums = {
        int(r["round"])
        for r in rounds
        if isinstance(r, dict) and r.get("round") is not None
    }
    if any(rn >= parent_round + 1 for rn in existing_round_nums):
        return False, "next_round_already_prepared"

    return True, None


def decide_inline_bundle_follow_up(
    *,
    session: dict[str, Any],
    parent_round_doc: dict[str, Any],
) -> dict[str, Any]:
    """Decide whether an inline bundle follow-up triggers after a parent answer.

    Never makes live LLM calls. Rejects bundles with status ``generated`` or
    ``rejected`` (Amendment A4: floor is ``auto_checked`` in
    ``coached_practice``, or ``reviewed`` only when ``REVIEWED_BUNDLES_ONLY=true``).
    Never falls back to ``followups[0]`` when no gap/target matches (Q2).
    """
    from modules import bundle_store
    from modules.bundle_selector import reviewed_bundles_only

    parent_round_raw = parent_round_doc.get("round") if isinstance(parent_round_doc, dict) else None
    parent_round = int(parent_round_raw) if parent_round_raw is not None else None
    session_id = session.get("session_id") if isinstance(session, dict) else None
    practice_mode = session_practice_mode(session)
    qctx = (
        parent_round_doc.get("question_context")
        if isinstance(parent_round_doc, dict)
        and isinstance(parent_round_doc.get("question_context"), dict)
        else {}
    )
    bundle_id = qctx.get("bundle_id") or (
        parent_round_doc.get("bundle_id") if isinstance(parent_round_doc, dict) else None
    )
    raw_version = (
        qctx.get("version")
        if qctx.get("version") is not None
        else (
            parent_round_doc.get("version")
            if isinstance(parent_round_doc, dict)
            else None
        )
    )
    version = int(raw_version) if raw_version is not None else None
    content_hash = qctx.get("content_hash") or (
        parent_round_doc.get("content_hash")
        if isinstance(parent_round_doc, dict)
        else None
    )

    def _skip(
        reason: str,
        *,
        bundle_status: str | None = None,
        gap_concept: str | None = None,
        gap_status: str | None = None,
    ) -> dict[str, Any]:
        return {
            "decision": "skipped",
            "reason": reason,
            "session_id": session_id,
            "parent_round": parent_round,
            "practice_mode": practice_mode,
            "bundle_id": str(bundle_id) if bundle_id else None,
            "version": version,
            "bundle_status": bundle_status,
            "gap_concept": gap_concept,
            "gap_status": gap_status,
            "chosen_prompt": None,
            "targets_concept": None,
            "follow_up_scoring": None,
            "follow_up_round": None,
        }

    eligible, cap_reason = can_schedule_inline_follow_up(session, parent_round_doc)
    if not eligible:
        return _skip(str(cap_reason or "ineligible"))

    if not bundle_id or version is None:
        return _skip("no_pinned_bundle")

    try:
        bundle_doc = bundle_store.get_version(str(bundle_id), int(version))
    except Exception:
        return _skip("bundle_not_found")

    bundle_status = str(bundle_doc.get("status") or "").strip().lower()
    allowed_statuses = {"reviewed"} if reviewed_bundles_only() else {"reviewed", "auto_checked"}
    if bundle_status not in allowed_statuses:
        return _skip(
            f"disallowed_bundle_status:{bundle_status or 'unknown'}",
            bundle_status=bundle_status or None,
        )

    gaps = extract_inline_concept_gaps(parent_round_doc)
    if not gaps:
        return _skip("no_concept_gap", bundle_status=bundle_status)

    bundle_content = bundle_doc.get("content_json") or bundle_doc.get("content") or {}
    followups = bundle_content.get("followups") or []
    match = select_inline_follow_up_spec(followups, gaps)
    if match is None:
        top_concept, top_status = gaps[0]
        return _skip(
            "no_matching_followup_target",
            bundle_status=bundle_status,
            gap_concept=top_concept,
            gap_status=top_status,
        )

    follow_up_scoring = "reviewed" if bundle_status == "reviewed" else "auto_checked"
    return {
        "decision": "scheduled",
        "reason": f"gap_{match['gap_status']}",
        "session_id": session_id,
        "parent_round": parent_round,
        "practice_mode": practice_mode,
        "bundle_id": str(bundle_id),
        "version": int(version),
        "content_hash": content_hash or bundle_doc.get("content_hash"),
        "bundle_status": bundle_status,
        "gap_concept": match["gap_concept"],
        "gap_status": match["gap_status"],
        "chosen_prompt": match["prompt"],
        "targets_concept": match["targets_concept"],
        "follow_up_scoring": follow_up_scoring,
        "follow_up_round": int(parent_round) + 1 if parent_round is not None else None,
    }


def splice_inline_follow_up_in_session(
    *,
    session: dict[str, Any],
    parent_round_doc: dict[str, Any],
    decision_result: dict[str, Any],
    target_difficulty: str | None = None,
) -> dict[str, Any]:
    """Splice a decided inline bundle follow-up at ``parent + 1`` (Amendment A5).

    Shifts only unprepared subsequent ``expanded_plan`` entries by ``+1``,
    increments ``total_rounds``, and never renumbers any existing ``RoundRow``.
    """
    if str(decision_result.get("decision") or "") != "scheduled":
        return {
            "scheduled": False,
            "reason": str(decision_result.get("reason") or "not_scheduled"),
        }
    ok, reason = can_schedule_inline_follow_up(session, parent_round_doc)
    if not ok:
        return {"scheduled": False, "reason": str(reason or "ineligible")}

    parent_round = int(parent_round_doc["round"])
    insert_round = parent_round + 1
    rounds = list(session.get("rounds") or [])
    prepared_round_nums = {
        int(r["round"])
        for r in rounds
        if isinstance(r, dict) and r.get("round") is not None
    }
    if any(rn >= insert_round for rn in prepared_round_nums):
        return {"scheduled": False, "reason": "next_round_already_prepared"}

    raw_plan = [
        copy.deepcopy(entry)
        for entry in (session.get("expanded_plan") or [])
        if isinstance(entry, dict)
    ]
    old_total = int(session.get("total_rounds") or len(raw_plan) or len(rounds))
    new_total = max(old_total + 1, len(raw_plan) + 1)
    if new_total > MAX_TOTAL_ROUNDS:
        return {"scheduled": False, "reason": "no_capacity"}

    session_id = str(session.get("session_id") or "")
    follow_up_identity = f"inline:{session_id}:{parent_round}"
    qctx = (
        parent_round_doc.get("question_context")
        if isinstance(parent_round_doc.get("question_context"), dict)
        else {}
    )
    skill = str(
        parent_round_doc.get("skill")
        or session.get("current_skill")
        or session.get("skill")
        or "General"
    )
    difficulty = str(
        target_difficulty
        or parent_round_doc.get("difficulty")
        or session.get("current_difficulty")
        or "medium"
    )
    follow_up_entry: dict[str, Any] = {
        "round": insert_round,
        "skill": skill,
        "difficulty": difficulty,
        "topic": parent_round_doc.get("topic") or qctx.get("topic") or qctx.get("sub_domain"),
        "round_type": "technical_short_answer",
        "category": parent_round_doc.get("block_category") or "interview",
        "stage": "follow_up",
        "block_id": parent_round_doc.get("block_id"),
        "block_position": parent_round_doc.get("block_position"),
        "block_index": parent_round_doc.get("block_index"),
        "block_total": parent_round_doc.get("block_total"),
        "duration_minutes": None,
        "is_follow_up": True,
        "follow_up_parent_round": parent_round,
        "follow_up_identity": follow_up_identity,
        "purpose": "follow_up",
        "follow_up_scoring": decision_result["follow_up_scoring"],
        "bundle_id": decision_result["bundle_id"],
        "version": int(decision_result["version"]),
        "content_hash": decision_result.get("content_hash"),
        "bundle_status": decision_result.get("bundle_status"),
        "prompt": decision_result["chosen_prompt"],
        "targets_concept": decision_result["targets_concept"],
        "gap_concept": decision_result["gap_concept"],
        "gap_status": decision_result["gap_status"],
    }

    if raw_plan:
        new_plan: list[dict[str, Any]] = []
        for entry in raw_plan:
            entry_round = int(entry.get("round") or 0)
            if entry_round >= insert_round and entry_round not in prepared_round_nums:
                entry["round"] = entry_round + 1
            new_plan.append(entry)
        new_plan.append(follow_up_entry)
        new_plan.sort(key=lambda item: int(item.get("round") or 0))
    else:
        new_plan = [follow_up_entry]

    return {
        "scheduled": True,
        "reason": str(decision_result.get("reason") or "scheduled"),
        "follow_up_round": insert_round,
        "follow_up_identity": follow_up_identity,
        "entry": follow_up_entry,
        "expanded_plan": new_plan,
        "total_rounds": new_total,
    }


def is_inline_bundle_follow_up_spec(expanded_spec: dict[str, Any] | None) -> bool:
    """True when ``expanded_spec`` is a pinned bundle follow-up (Slice 1)."""
    if not isinstance(expanded_spec, dict) or not expanded_spec.get("is_follow_up"):
        return False
    return bool(
        expanded_spec.get("bundle_id")
        and expanded_spec.get("version") is not None
        and expanded_spec.get("follow_up_scoring") in {"reviewed", "auto_checked"}
        and str(expanded_spec.get("prompt") or "").strip()
    )


def build_bundle_follow_up_round_doc(
    *,
    expanded_spec: dict[str, Any],
    round_number: int,
    candidate_elos: dict[str, Any],
    initial_elo: float,
    ready_status: str,
) -> dict[str, Any]:
    """Construct a READY ``RoundRow`` document for a pinned bundle follow-up.

    Never invokes ``_get_next_question``; pins the clarification prompt and
    parent ``(bundle_id, version, content_hash)`` directly on the round so Scorer
    v3 grades against that bundle while ``is_follow_up=True`` keeps it excluded
    from ``assessment_eligible_scores`` and Elo.
    """
    skill = str(expanded_spec.get("skill") or "General")
    difficulty = str(expanded_spec.get("difficulty") or "medium")
    topic = expanded_spec.get("topic") or skill
    prompt = str(expanded_spec["prompt"])
    follow_up_scoring = str(expanded_spec["follow_up_scoring"])
    source = (
        "reviewed_bundle"
        if follow_up_scoring == "reviewed"
        else "auto_checked_bundle"
    )
    parent_round = expanded_spec.get("follow_up_parent_round")
    identity = expanded_spec.get("follow_up_identity")
    targets_concept = expanded_spec.get("targets_concept")
    stage = expanded_spec.get("stage") or "follow_up"

    cfg: dict[str, Any] = {
        "is_follow_up": True,
        "follow_up_parent_round": parent_round,
        "follow_up_identity": identity,
        "follow_up_scoring": follow_up_scoring,
        "targets_concept": targets_concept,
        "stage": stage,
    }
    if expanded_spec.get("duration_minutes") is not None:
        minutes = int(expanded_spec["duration_minutes"])
        cfg["duration_minutes"] = minutes
        cfg["duration_seconds"] = minutes * 60

    question_context: dict[str, Any] = {
        "question": prompt,
        "skill": skill,
        "topic": topic,
        "sub_domain": topic,
        "difficulty": difficulty,
        "source": source,
        "bundle_id": expanded_spec["bundle_id"],
        "version": int(expanded_spec["version"]),
        "content_hash": expanded_spec.get("content_hash"),
        "followups": [],
    }

    return {
        "round": int(round_number),
        "round_type": "technical_short_answer",
        "skill": skill,
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
        "elo_before": float(candidate_elos.get(skill, initial_elo)),
        "elo_after": None,
        "artifact_json": {},
        "config_json": cfg,
        "question_context": question_context,
        "started_at": None,
        "expires_at": None,
        "status": ready_status,
        "block_id": expanded_spec.get("block_id"),
        "block_position": expanded_spec.get("block_position"),
        "block_category": expanded_spec.get("category")
        or expanded_spec.get("block_category"),
        "block_index": expanded_spec.get("block_index"),
        "block_total": expanded_spec.get("block_total"),
        "is_follow_up": True,
        "follow_up_parent_round": parent_round,
        "follow_up_identity": identity,
        "follow_up_scoring": follow_up_scoring,
        "purpose": "follow_up",
        "targets_concept": targets_concept,
        "stage": stage,
    }


def is_inline_bundle_follow_up_round(round_doc: dict[str, Any] | None) -> bool:
    """True only for Slice 1 inline bundle follow-ups (manual/other rounds False)."""
    if not isinstance(round_doc, dict):
        return False
    cfg = round_doc.get("config_json") or {}
    if not isinstance(cfg, dict):
        cfg = {}
    is_fu = bool(
        round_doc.get("is_follow_up") is True
        or cfg.get("is_follow_up")
        or str(round_doc.get("purpose") or "").lower() == "follow_up"
    )
    if not is_fu:
        return False
    identity = str(
        round_doc.get("follow_up_identity")
        or cfg.get("follow_up_identity")
        or ""
    )
    stage = str(round_doc.get("stage") or cfg.get("stage") or "").strip().lower()
    return identity.startswith("inline:") or stage == "follow_up"


def _humanize_concept_label(targets_concept: str) -> str:
    clean = " ".join(str(targets_concept or "").replace("_", " ").replace("-", " ").split())
    return clean or "Targeted concept"


_PROMPT_ECHO_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "because", "by", "can", "could",
    "did", "do", "does", "during", "even", "follow", "followup", "for", "from",
    "how", "in", "into", "is", "it", "its", "of", "on", "or", "other", "should",
    "so", "still", "that", "the", "their", "them", "then", "there", "these",
    "they", "this", "to", "under", "up", "very", "what", "when", "where",
    "which", "while", "who", "why", "will", "with", "would", "yes", "no",
    "not", "never", "without", "cannot", "cant",
})


def _content_word_stems(text: str) -> set[str]:
    """Normalized non-stopword tokens for prompt-echo discounting (P1)."""
    out: set[str] = set()
    for raw in re.findall(r"[A-Za-z0-9]+", (text or "").casefold()):
        if len(raw) <= 2 or raw in _PROMPT_ECHO_STOPWORDS:
            continue
        stem = raw[:-1] if len(raw) > 4 and raw.endswith("s") and not raw.endswith("ss") else raw
        out.add(stem)
    return out


def _supported_with_novel_evidence(
    *,
    answer_text: str,
    prompt_text: str,
    matched_entry: dict[str, Any],
) -> bool:
    """True only when at least one supported proposition adds evidence beyond the prompt."""
    from modules.concept_evaluator_v2 import _proposition_support

    answer_stems = _content_word_stems(answer_text)
    prompt_stems = _content_word_stems(prompt_text)
    if not answer_stems:
        return False
    # Repeating prompt words alone (0 new content tokens outside prompt) never passes.
    if prompt_stems and not (answer_stems - prompt_stems):
        return False

    for raw_prop in matched_entry.get("expected_propositions") or []:
        prop = str(raw_prop or "").strip()
        if not prop:
            continue
        if _proposition_support(answer_text, prop) != "supported":
            continue
        prop_stems = _content_word_stems(prop)
        # Discount propositions whose entire content-word vocabulary was supplied by the prompt.
        if prop_stems and prompt_stems and prop_stems.issubset(prompt_stems):
            continue
        return True
    return False


def evaluate_inline_follow_up_outcome(
    *,
    active_round: dict[str, Any],
    scoring_question_context: dict[str, Any] | None,
    answer_text: str,
    scoring_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build concept-only 3-state outcome & feedback for an inline bundle follow-up (A8/P1).

    Maps ``concept_evaluator_v2`` states to three outcomes:
      - ``demonstrated`` (proposition supported with non-prompt evidence)
      - ``unclear`` (``uncertain`` — alias/mention without resolved proposition)
      - ``not_clearly_demonstrated`` (``not_demonstrated``, ``contradicted``,
        active misconception, or prompt-word repetition only)
    """
    cfg = active_round.get("config_json") or {}
    if not isinstance(cfg, dict):
        cfg = {}
    targets_concept = str(
        active_round.get("targets_concept")
        or cfg.get("targets_concept")
        or ""
    ).strip()

    qctx = dict(scoring_question_context or {})
    required_concepts = list(qctx.get("required_concepts") or [])
    target_keys = _concept_match_keys(targets_concept)

    matched_entry: dict[str, Any] | None = None
    concept_label = ""
    for raw_entry in required_concepts:
        if isinstance(raw_entry, dict):
            entry_id = str(raw_entry.get("id") or raw_entry.get("concept_id") or "").strip()
            entry_keys = _concept_match_keys(entry_id)
            if target_keys and (target_keys & entry_keys):
                matched_entry = raw_entry
                concept_label = str(
                    raw_entry.get("descriptor")
                    or raw_entry.get("label")
                    or raw_entry.get("name")
                    or entry_id
                ).strip()
                break
        elif isinstance(raw_entry, str) and target_keys and (target_keys & _concept_match_keys(raw_entry)):
            concept_label = raw_entry.strip()
            break

    if not concept_label:
        concept_label = _humanize_concept_label(targets_concept)

    prompt_text = str(active_round.get("question") or (scoring_question_context or {}).get("question") or "")
    answer_stems = _content_word_stems(answer_text or "")
    prompt_stems = _content_word_stems(prompt_text)
    is_pure_prompt_echo = bool(prompt_stems) and (not answer_stems or not (answer_stems - prompt_stems))

    eval_state: str | None = None

    if matched_entry is not None and matched_entry.get("expected_propositions"):
        from modules.concept_evaluator_v2 import evaluate_answer

        evidence = evaluate_answer(
            answer_text=answer_text or "",
            bundle_content={
                "required_concepts": [matched_entry],
                "misconceptions": list(qctx.get("misconceptions") or []),
            },
        )
        items = evidence.get("concepts") or []
        raw_state = (
            str(items[0].get("state") or "not_demonstrated").strip().lower()
            if items
            else "not_demonstrated"
        )
        active_misconception = any(
            bool(m.get("matched")) and not bool(m.get("refuted"))
            for m in (evidence.get("misconceptions") or [])
            if isinstance(m, dict)
        )
        if raw_state == "contradicted" or active_misconception:
            eval_state = "contradicted"
        elif raw_state == "supported":
            if _supported_with_novel_evidence(
                answer_text=answer_text or "",
                prompt_text=prompt_text,
                matched_entry=matched_entry,
            ):
                eval_state = "supported"
            else:
                eval_state = "not_demonstrated"
        elif raw_state == "uncertain":
            eval_state = "not_demonstrated" if is_pure_prompt_echo else "uncertain"
        else:
            eval_state = "not_demonstrated"

    if eval_state is None:
        sr = dict(scoring_result or {})
        bd = sr.get("scoring_breakdown") if isinstance(sr.get("scoring_breakdown"), dict) else {}
        concepts_obj = sr.get("concepts") or (bd or {}).get("concepts") or {}
        if not isinstance(concepts_obj, dict):
            concepts_obj = {}
        trace = [
            entry
            for entry in (concepts_obj.get("concept_match_trace") or [])
            if isinstance(entry, dict)
        ]
        for entry in trace:
            label = _extract_concept_label(entry)
            if not label or (target_keys and not (target_keys & _concept_match_keys(label))):
                continue
            method = str(entry.get("method") or "").strip().lower()
            status_val = str(entry.get("status") or "").strip().lower()
            if method == "contradicted":
                eval_state = "contradicted"
            elif method == "uncertain" or status_val == "uncertain":
                eval_state = "not_demonstrated" if is_pure_prompt_echo else "uncertain"
            elif bool(entry.get("matched")) or method == "supported" or status_val == "matched":
                eval_state = "not_demonstrated" if is_pure_prompt_echo else "supported"
            else:
                eval_state = "not_demonstrated"
            break

        if eval_state is None:
            matched_list = (
                concepts_obj.get("matched_concepts")
                or concepts_obj.get("covered")
                or (bd or {}).get("covered_concepts")
                or []
            )
            for item in matched_list:
                lbl = _extract_concept_label(item)
                if lbl and target_keys and (target_keys & _concept_match_keys(lbl)):
                    eval_state = "not_demonstrated" if is_pure_prompt_echo else "supported"
                    break
            if eval_state is None:
                eval_state = "not_demonstrated"

    if eval_state == "supported":
        demonstrated = True
        status_label = "demonstrated"
        feedback = {
            "content": [f"{concept_label}: demonstrated in your follow-up answer."],
            "strengths": [f"Demonstrated {concept_label}."],
            "weakness": [],
            "next_step": "Continue with the remaining rounds.",
        }
    elif eval_state == "uncertain":
        demonstrated = False
        status_label = "unclear"
        feedback = {
            "content": [f"{concept_label}: unclear from your follow-up answer."],
            "strengths": [],
            "weakness": [f"{concept_label} was unclear in this follow-up."],
            "next_step": f"Clarify {concept_label} with concrete mechanism detail.",
        }
    else:
        demonstrated = False
        status_label = "not_clearly_demonstrated"
        qualifier = (
            "not clearly demonstrated (contradicted)"
            if eval_state == "contradicted"
            else "not clearly demonstrated"
        )
        feedback = {
            "content": [f"{concept_label}: {qualifier} in your follow-up answer."],
            "strengths": [],
            "weakness": [f"{concept_label} was {qualifier} in this follow-up."],
            "next_step": f"Review {concept_label} before your next session.",
        }

    return {
        "targets_concept": targets_concept,
        "concept_label": concept_label,
        "demonstrated": demonstrated,
        "status": status_label,
        "feedback": feedback,
    }


def maybe_apply_inline_bundle_follow_up(
    *,
    session: dict[str, Any],
    active_round: dict[str, Any],
    rounds: list[dict[str, Any]],
    total_rounds: int,
    target_difficulty: str | None = None,
) -> dict[str, Any]:
    """Run inline follow-up decision & splice on an attempt copy of ``session``.

    Called inside ``POST /session/answer`` before preparing ``next_round``. Does
    not write to the audit log file itself so retries under
    ``SessionWriteConflict`` never double-log; caller logs ``decision_record``
    once after the atomic commit succeeds.
    """
    session_view = {
        **session,
        "rounds": rounds,
        "total_rounds": total_rounds,
    }
    decision = decide_inline_bundle_follow_up(
        session=session_view,
        parent_round_doc=active_round,
    )
    if decision["decision"] == "scheduled":
        splice = splice_inline_follow_up_in_session(
            session=session_view,
            parent_round_doc=active_round,
            decision_result=decision,
            target_difficulty=target_difficulty,
        )
        if not splice.get("scheduled"):
            decision = {
                **decision,
                "decision": "skipped",
                "reason": str(splice.get("reason") or "splice_blocked"),
                "chosen_prompt": None,
                "targets_concept": None,
                "follow_up_scoring": None,
                "follow_up_round": None,
            }
        else:
            session["expanded_plan"] = splice["expanded_plan"]
            session["total_rounds"] = splice["total_rounds"]
            active_round["follow_up_decision"] = dict(decision)
            return {
                "scheduled": True,
                "decision_record": decision,
                "plan_update": {
                    "expanded_plan": splice["expanded_plan"],
                    "total_rounds": splice["total_rounds"],
                },
                "total_rounds": splice["total_rounds"],
                "follow_up_identity": splice["follow_up_identity"],
                "exposure_concept": decision.get("targets_concept")
                or decision.get("gap_concept"),
                "parent_round": int(active_round["round"]),
                "follow_up_round": splice["follow_up_round"],
            }

    active_round["follow_up_decision"] = dict(decision)
    return {
        "scheduled": False,
        "decision_record": decision,
        "plan_update": {},
        "total_rounds": total_rounds,
        "follow_up_identity": None,
        "exposure_concept": None,
        "parent_round": active_round.get("round"),
        "follow_up_round": None,
    }
