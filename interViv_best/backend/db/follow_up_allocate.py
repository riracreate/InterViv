"""Store-level atomic follow-up allocation.

Closes the Phase 4B follow-up scheduling gap: caps were enforced only by
application-level checks under a process-local lock, so concurrent workers
could double-book a parent, overspend a block budget, or exceed session
capacity — and pending (scheduled-but-unmaterialized) follow-ups were
invisible to the caps entirely.

Protocol (SQLAlchemy): the store's shared optimistic-concurrency protocol
on ``sessions.revision``. Every attempt runs inside ONE transaction on ONE
connection:

  1. fresh-read the session document (rounds + expanded_plan + block_plan),
  2. re-validate parent/materialized+pending caps and mandatory reservation,
  3. narrow conditional write of ONLY ``expanded_plan`` / ``total_rounds``
     via ``sessions.update_one(..., expected_revision=...)`` — a
     ``SessionWriteConflict`` means another writer won and this attempt
     rolls back,
  4. insert the teaching exposure in the same transaction.

Conflicts (or lock/serialization errors) roll back and retry with a fresh
read, up to ``max_attempts``; definitive cap failures return their reason
immediately; exhaustion returns a retryable ``allocation_conflict``.

Submit and continue commits use the same protocol and only touch
``rounds`` + their scalars, so neither direction can clobber the other:
concurrent operations serialize into an order where every winner's effect
survives. The partial unique index on
``(session_id, follow_up_parent_round)`` remains as defense-in-depth at
materialization time.

Memory backend: the same read-validate-write runs inside the store-global
``atomic()`` lock, which is a true critical section for the process-local
store, so one attempt suffices.
"""

from __future__ import annotations

from typing import Any

MAX_ALLOCATION_ATTEMPTS = 5


def allocate_follow_up(
    db: Any,
    *,
    session_id: str,
    parent_round: int,
    plan_entry: dict[str, Any],
    max_attempts: int = MAX_ALLOCATION_ATTEMPTS,
) -> dict[str, Any]:
    """Atomically schedule one follow-up for a submitted parent round.

    Returns ``{"scheduled": True, "follow_up_identity": ..., "total_rounds":
    ..., "attempts": n}`` or ``{"scheduled": False, "reason": ...}``.
    Definitive reasons (``parent_follow_up_exists``, ``block_follow_up_cap``,
    ``no_capacity``, ``recursive_follow_up_forbidden``,
    ``assessment_follow_ups_disabled``, ``follow_ups_disabled_for_block``,
    ``parent_not_submitted``, ``parent_not_found``, ``session_not_found``)
    are final; ``allocation_conflict`` is transient and safe to retry.
    Unexpected errors propagate (the route maps database errors to 503);
    failed attempts leave no session changes and no teaching exposures.
    """
    from backend.db.memory import _MemoryDB
    from backend.db.sqlalchemy_store import SQLAlchemyDatabase

    if isinstance(db, SQLAlchemyDatabase):
        return _allocate_sql(
            db,
            session_id=session_id,
            parent_round=int(parent_round),
            plan_entry=plan_entry,
            max_attempts=max(1, int(max_attempts)),
        )
    if isinstance(db, _MemoryDB):
        return _allocate_memory(
            db,
            session_id=session_id,
            parent_round=int(parent_round),
            plan_entry=plan_entry,
        )
    raise TypeError(
        "allocate_follow_up supports the memory and SQLAlchemy backends, "
        f"not {type(db).__name__}."
    )


def _validate_fresh_doc(
    doc: dict[str, Any] | None,
    *,
    parent_round: int,
    plan_entry: dict[str, Any],
) -> dict[str, Any]:
    """Re-check everything on a fresh read; returns a result or plan."""
    from modules.follow_ups import can_schedule_follow_up, schedule_follow_up_in_session

    if not doc:
        return {"scheduled": False, "reason": "session_not_found"}
    rounds = list(doc.get("rounds") or [])
    parent = next(
        (r for r in rounds if int(r.get("round") or 0) == int(parent_round)),
        None,
    )
    if parent is None:
        return {"scheduled": False, "reason": "parent_not_found"}
    if parent.get("final_score") is None and str(parent.get("status") or "") != "submitted":
        return {"scheduled": False, "reason": "parent_not_submitted"}
    ok, reason = can_schedule_follow_up(session=doc, parent_round_doc=parent)
    if not ok:
        return {"scheduled": False, "reason": reason}
    result = schedule_follow_up_in_session(
        doc, parent_round_doc=parent, plan_entry=plan_entry
    )
    if not result.get("scheduled"):
        return {"scheduled": False, "reason": result.get("reason") or "not_scheduled"}
    return {
        "scheduled": True,
        "expanded_plan": result["expanded_plan"],
        "total_rounds": result["total_rounds"],
    }


def _is_transient_db_error(exc: Exception) -> bool:
    """True for lock/serialization failures that a retry may survive."""
    try:
        from sqlalchemy.exc import DBAPIError, OperationalError
    except ModuleNotFoundError:  # pragma: no cover
        return False
    if isinstance(exc, OperationalError):
        return True
    if isinstance(exc, DBAPIError):
        code = str(getattr(getattr(exc, "orig", None), "pgcode", "") or "")
        if code in ("40001", "40P01"):  # serialization failure / deadlock
            return True
        message = str(exc).lower()
        if "database is locked" in message or "deadlock" in message:
            return True
    return False


def _allocate_sql(
    db: Any,
    *,
    session_id: str,
    parent_round: int,
    plan_entry: dict[str, Any],
    max_attempts: int,
) -> dict[str, Any]:
    from backend.db.sqlalchemy_store import SessionWriteConflict, ambient_session
    from modules.teaching_exposures import record_teaching_exposure

    identity = str(plan_entry.get("follow_up_identity") or "")
    attempts = 0
    while attempts < max_attempts:
        attempts += 1
        try:
            with ambient_session():
                doc = db["sessions"].find_one({"session_id": session_id})
                checked = _validate_fresh_doc(
                    doc, parent_round=parent_round, plan_entry=plan_entry
                )
                if not checked.get("scheduled"):
                    return {**checked, "attempts": attempts}
                # Narrow conditional write through the shared store
                # protocol: the read above and this write share one
                # transaction, and a lost race raises SessionWriteConflict
                # with nothing persisted — not even the exposure below.
                db["sessions"].update_one(
                    {"session_id": session_id},
                    {
                        "$set": {
                            "expanded_plan": checked["expanded_plan"],
                            "total_rounds": int(checked["total_rounds"]),
                        }
                    },
                    expected_revision=(doc or {}).get("revision"),
                )
                rounds = list((doc or {}).get("rounds") or [])
                parent = next(
                    (r for r in rounds if int(r.get("round") or 0) == int(parent_round)),
                    {},
                )
                record_teaching_exposure(
                    db,
                    kind="follow_up_prompt",
                    item_type="follow_up",
                    item_id=identity,
                    session=doc,
                    user_id=(doc or {}).get("user_id"),
                    round_number=int(parent_round),
                    block_id=(parent or {}).get("block_id"),
                    content_fingerprint=identity,
                    also_legacy_assistance=False,
                )
                return {
                    "scheduled": True,
                    "reason": "",
                    "follow_up_identity": identity,
                    "total_rounds": int(checked["total_rounds"]),
                    "attempts": attempts,
                }
        except SessionWriteConflict:
            continue
        except Exception as exc:
            if _is_transient_db_error(exc) and attempts < max_attempts:
                continue
            raise
    return {
        "scheduled": False,
        "reason": "allocation_conflict",
        "retryable": True,
        "attempts": attempts,
    }


def _allocate_memory(
    db: Any,
    *,
    session_id: str,
    parent_round: int,
    plan_entry: dict[str, Any],
) -> dict[str, Any]:
    from backend.db.transactions import atomic
    from modules.teaching_exposures import record_teaching_exposure

    identity = str(plan_entry.get("follow_up_identity") or "")
    with atomic(db):
        doc = db["sessions"].find_one({"session_id": session_id})
        checked = _validate_fresh_doc(
            doc, parent_round=parent_round, plan_entry=plan_entry
        )
        if not checked.get("scheduled"):
            return {**checked, "attempts": 1}
        rounds = list((doc or {}).get("rounds") or [])
        parent = next(
            (r for r in rounds if int(r.get("round") or 0) == int(parent_round)),
            {},
        )
        db["sessions"].update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "expanded_plan": checked["expanded_plan"],
                    "total_rounds": int(checked["total_rounds"]),
                }
            },
        )
        record_teaching_exposure(
            db,
            kind="follow_up_prompt",
            item_type="follow_up",
            item_id=identity,
            session=doc,
            user_id=(doc or {}).get("user_id"),
            round_number=int(parent_round),
            block_id=(parent or {}).get("block_id"),
            content_fingerprint=identity,
            also_legacy_assistance=False,
        )
        return {
            "scheduled": True,
            "reason": "",
            "follow_up_identity": identity,
            "total_rounds": int(checked["total_rounds"]),
            "attempts": 1,
        }
