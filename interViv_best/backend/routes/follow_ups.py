"""Optional follow-up scheduling (Phase 4A)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.db.follow_up_allocate import allocate_follow_up
from backend.routes.answer import _submit_locked
from backend.routes.auth import require_authenticated
from backend.routes.session_access import assert_session_access
from modules.follow_ups import build_follow_up_plan_entry

router = APIRouter(prefix="/session", tags=["follow-ups"])


class FollowUpRequest(BaseModel):
    parent_round: int = Field(..., ge=1)
    # Explicit confirmation that the candidate accepts exclusion from primary metrics.
    accept_eligibility_consequence: bool = False


@router.post("/{session_id}/follow-ups", dependencies=[Depends(require_authenticated)])
def request_follow_up(
    session_id: str,
    body: FollowUpRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Schedule at most one optional follow-up for a completed parent round."""
    if not body.accept_eligibility_consequence:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Optional follow-ups are practiced with help and excluded from "
                "primary assessment metrics. Set accept_eligibility_consequence=true "
                "to continue."
            ),
        )
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    with _submit_locked(session_id):
        try:
            session = db["sessions"].find_one({"session_id": session_id})
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
                )
            assert_session_access(session, authorization)
            rounds = list(session.get("rounds") or [])
            parent = next(
                (r for r in rounds if int(r.get("round") or 0) == int(body.parent_round)),
                None,
            )
            if parent is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parent round {body.parent_round} not found.",
                )
            if parent.get("final_score") is None and str(parent.get("status") or "") != "submitted":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Parent round must be submitted before a follow-up can be scheduled.",
                )
            # Never invent reviewed inventory. Prefer clarification unscored
            # when no reviewed bundle is available in the production path.
            reviewed = None
            clarification = None
            ctx = parent.get("question_context") or {}
            followups = ctx.get("followups") or []
            if isinstance(followups, list) and followups:
                first = followups[0]
                clarification = first if isinstance(first, str) else str(
                    (first or {}).get("prompt") or first or ""
                )
            plan_entry = build_follow_up_plan_entry(
                parent_round_doc=parent,
                reviewed_bundle=reviewed,
                clarification_prompt=clarification,
            )
            # Store-level atomic allocation: re-validates caps on a fresh
            # read inside one transaction (conditional revision write +
            # exposure insert), so concurrent workers cannot overspend
            # parent/block/session budgets.
            result = allocate_follow_up(
                db,
                session_id=session_id,
                parent_round=int(body.parent_round),
                plan_entry=plan_entry,
            )
            if not result.get("scheduled"):
                reason = result.get("reason") or "not_scheduled"
                if reason == "session_not_found":
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Session not found.",
                    )
                if reason == "parent_not_found":
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Parent round {body.parent_round} not found.",
                    )
                if reason == "parent_not_submitted":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Parent round must be submitted before a follow-up can be scheduled.",
                    )
                if reason == "allocation_conflict":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Follow-up allocation conflicted with a concurrent "
                            "request; retry."
                        ),
                    )
                return {
                    "scheduled": False,
                    "reason": reason,
                    "session_id": session_id,
                    "parent_round": body.parent_round,
                }

            return {
                "scheduled": True,
                "reason": "",
                "session_id": session_id,
                "parent_round": body.parent_round,
                "follow_up_identity": result.get("follow_up_identity"),
                "total_rounds": result["total_rounds"],
                "follow_up_scoring": plan_entry.get("follow_up_scoring"),
                "label": "Follow-up",
                "eligibility_note": (
                    "Follow-up attempts are Practiced with help and excluded "
                    "from primary assessment metrics."
                ),
            }
        except HTTPException:
            raise
        except Exception as exc:
            if is_database_exception(exc) or isinstance(exc, DatabaseConnectionError):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
                ) from exc
            raise
