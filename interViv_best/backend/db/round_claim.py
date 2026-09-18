"""Store-level conditional claim for round submit finalization.

The per-session threading lock serializes one process. Independent workers
need a conditional status transition so two scorers cannot both finalize
the same round. Scope documented in Phase 4B policy:

* SQLAlchemy: ``UPDATE … WHERE status IN ('in_progress', …)`` rowcount==1
* Memory: compare-and-set under the collection lock (still single-process)
"""

from __future__ import annotations

from typing import Any


CLAIMABLE_STATUSES = ("in_progress",)
CLAIM_STATUS = "finalizing"


def claim_round_finalizing(
    db: Any,
    *,
    session_id: str,
    round_number: int,
    allow_stale_takeover: bool = False,
) -> str:
    """Claim a round for scoring.

    Returns:
        ``claimed`` — this caller owns finalization
        ``already_done`` — round already submitted/scored
        ``busy`` — another worker holds ``finalizing`` (no takeover)
        ``missing`` — session or round not found

    When ``allow_stale_takeover`` is True and status is ``finalizing`` without
    a score, returns ``claimed`` (single-process stale-holder recovery).
    """
    from backend.db.memory import _MemoryDB
    from backend.db.sqlalchemy_store import SQLAlchemyDatabase

    if isinstance(db, SQLAlchemyDatabase):
        return _claim_sql(
            session_id=session_id,
            round_number=round_number,
            allow_stale_takeover=allow_stale_takeover,
        )
    if isinstance(db, _MemoryDB):
        return _claim_memory(
            db,
            session_id=session_id,
            round_number=round_number,
            allow_stale_takeover=allow_stale_takeover,
        )
    # Unknown backend: fall back to document read (caller still holds lock).
    return _claim_memory(
        db,
        session_id=session_id,
        round_number=round_number,
        allow_stale_takeover=allow_stale_takeover,
    )


def _claim_sql(
    *,
    session_id: str,
    round_number: int,
    allow_stale_takeover: bool,
) -> str:
    from sqlalchemy import and_, or_, update

    from backend.db.sqlalchemy_models import RoundRow, SessionRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        row = (
            session.query(RoundRow)
            .join(SessionRow, RoundRow.session_id == SessionRow.id)
            .filter(SessionRow.id == session_id)
            .filter(RoundRow.round_number == int(round_number))
            .one_or_none()
        )
        if row is None:
            return "missing"
        status = str(row.status or "")
        scored = row.final_score is not None or bool(row.answer_text)
        if status in ("submitted", "expired") or (scored and status != CLAIM_STATUS):
            return "already_done"
        if status == CLAIM_STATUS:
            if allow_stale_takeover and not scored:
                return "claimed"
            if scored:
                return "already_done"
            return "busy"

        result = session.execute(
            update(RoundRow)
            .where(
                and_(
                    RoundRow.session_id == row.session_id,
                    RoundRow.round_number == int(round_number),
                    or_(
                        RoundRow.status.in_(CLAIMABLE_STATUSES),
                        RoundRow.status.is_(None),
                    ),
                )
            )
            .values(status=CLAIM_STATUS)
        )
        if int(result.rowcount or 0) == 1:
            session.flush()
            return "claimed"
        # Lost the race.
        session.refresh(row)
        status = str(row.status or "")
        scored = row.final_score is not None or bool(row.answer_text)
        if status in ("submitted", "expired") or scored:
            return "already_done"
        if status == CLAIM_STATUS and allow_stale_takeover and not scored:
            return "claimed"
        return "busy"


def _claim_memory(
    db: Any,
    *,
    session_id: str,
    round_number: int,
    allow_stale_takeover: bool,
) -> str:
    session_doc = db["sessions"].find_one({"session_id": session_id})
    if not session_doc:
        return "missing"
    rounds = list(session_doc.get("rounds") or [])
    active = next(
        (r for r in rounds if int(r.get("round") or 0) == int(round_number)),
        None,
    )
    if active is None:
        return "missing"
    status = str(active.get("status") or "")
    scored = bool(active.get("answer_text")) or active.get("final_score") is not None
    if status in ("submitted", "expired") or (scored and status != CLAIM_STATUS):
        return "already_done"
    if status == CLAIM_STATUS:
        if allow_stale_takeover and not scored:
            active["status"] = CLAIM_STATUS
            db["sessions"].update_one(
                {"session_id": session_id},
                {"$set": {"rounds": rounds}},
            )
            return "claimed"
        if scored:
            return "already_done"
        return "busy"
    if status not in CLAIMABLE_STATUSES and status not in ("", "None"):
        return "already_done"
    active["status"] = CLAIM_STATUS
    db["sessions"].update_one(
        {"session_id": session_id},
        {"$set": {"rounds": rounds}},
    )
    return "claimed"
