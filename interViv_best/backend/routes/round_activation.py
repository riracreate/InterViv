"""POST /session/{session_id}/rounds/{round_number}/activate.

Opens a prepared (``ready``) round: sets ``started_at`` and, for timed
rounds, ``expires_at`` exactly once. Repeated calls, retries and refreshes
return the same round and deadline. Ownership-checked; serialized with
submission through the per-session submit lock and, on SQL stores, the
session revision.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status

from backend.config import get_settings
from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.round_lifecycle import OPEN_STATUSES, ROUND_STATUS_ACTIVE, activate_round
from backend.routes.answer import _submit_locked, _total_rounds
from backend.routes.auth import require_authenticated
from backend.routes.session_access import (
    assert_session_access,
    session_assessment_completed,
)
from backend.serializers.round_serializer import sanitize_round_for_client

router = APIRouter(prefix="/session", tags=["session-rounds"])

MAX_ACTIVATE_ATTEMPTS = 3


def activation_payload(session: dict[str, Any], round_doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session["session_id"],
        "session_status": session.get("status", "active"),
        "total_rounds": _total_rounds(session, get_settings()),
        "active_round": sanitize_round_for_client(
            dict(round_doc),
            is_session_completed=session_assessment_completed(session),
        ),
    }


@router.post(
    "/{session_id}/rounds/{round_number}/activate",
    dependencies=[Depends(require_authenticated)],
)
def activate_session_round(
    session_id: str,
    round_number: int,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    from backend.db.sqlalchemy_store import SessionWriteConflict

    with _submit_locked(session_id):
        for _attempt in range(MAX_ACTIVATE_ATTEMPTS):
            try:
                session = db["sessions"].find_one({"session_id": session_id})
            except Exception as exc:
                if is_database_exception(exc):
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
                    ) from exc
                raise
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
                )
            assert_session_access(session, authorization)

            rounds = list(session.get("rounds") or [])
            target = next(
                (r for r in rounds if int(r.get("round") or 0) == int(round_number)),
                None,
            )
            if target is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Requested round not found in session.",
                )
            current = target.get("status")
            if current == ROUND_STATUS_ACTIVE:
                # Idempotent: never restart or extend a running clock.
                return activation_payload(session, target)
            if current not in OPEN_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "round_closed",
                        "round": round_number,
                        "status": current,
                        "message": "This question has already been answered.",
                    },
                )
            earlier_open = [
                r for r in rounds
                if int(r.get("round") or 0) < int(round_number)
                and r.get("status") in OPEN_STATUSES | {"finalizing"}
            ]
            if earlier_open:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "previous_round_open",
                        "round": earlier_open[0].get("round"),
                        "message": "Finish the current question first.",
                    },
                )

            activate_round(target, datetime.now(timezone.utc))
            try:
                db["sessions"].update_one(
                    {"session_id": session_id},
                    {"$set": {"rounds": rounds}},
                    expected_revision=session.get("revision"),
                )
            except SessionWriteConflict:
                # Another worker wrote first: reload and re-decide. If it
                # activated this round, the next pass returns that deadline.
                continue
            except Exception as exc:
                if is_database_exception(exc):
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
                    ) from exc
                raise
            return activation_payload(session, target)

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Concurrent session update; retry opening the question.",
    )
