"""Continue a content_blocked session once matching inventory exists.

Ownership-checked. Does not rescore, does not re-apply Elo/learning, and
does not broaden an explicit topic pin. Concurrent continues share the
submit lock so only one next round is appended.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, status

from backend.config import get_settings
from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.db.transactions import atomic
from backend.integrations import IntegrationError
from backend.routes.answer import _difficulty_from_elo, _submit_locked, _total_rounds
from backend.routes.session import (
    _expanded_spec_for_round,
    _get_next_question,
    _skill_for_round,
    _sub_domain_for_skill,
    _verify_served_topic,
    build_round_document,
)
from backend.routes.session_access import assert_session_access
from backend.serializers.round_serializer import sanitize_round_for_client
from modules import adaptive_question_selector

router = APIRouter(prefix="/session", tags=["session-continue"])


def _asked_questions(rounds: list[dict]) -> list[str]:
    return [str(item.get("question") or "") for item in rounds if item.get("question")]


@router.post("/{session_id}/continue")
def continue_session(
    session_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    with _submit_locked(session_id):
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
        settings = get_settings()
        rounds = list(session.get("rounds") or [])
        total = _total_rounds(session, settings)

        # Idempotent: already has an open next round.
        open_round = next(
            (r for r in reversed(rounds) if r.get("status") == "in_progress"),
            None,
        )
        if open_round is not None and session.get("status") in ("active", "content_blocked"):
            if session.get("status") == "content_blocked":
                with atomic(db):
                    db["sessions"].update_one(
                        {"session_id": session_id},
                        {"$set": {
                            "status": "active",
                            "progression_blocked_reason": None,
                        }},
                    )
            sanitized = sanitize_round_for_client(dict(open_round))
            return {
                "session_id": session_id,
                "status": "active",
                "continued": True,
                "progression_blocked": False,
                "progression_blocked_reason": None,
                "round": open_round.get("round"),
                "question": open_round.get("question"),
                "round_type": open_round.get("round_type"),
                "difficulty": open_round.get("difficulty"),
                "question_context": sanitized.get("question_context") or {},
                "config_json": open_round.get("config_json") or {},
                "expires_at": (
                    open_round["expires_at"].isoformat()
                    if hasattr(open_round.get("expires_at"), "isoformat")
                    else open_round.get("expires_at")
                ),
                "block_id": open_round.get("block_id"),
                "block_position": open_round.get("block_position"),
                "block_category": open_round.get("block_category"),
                "current_skill": open_round.get("skill") or session.get("current_skill"),
                "total_rounds": total,
            }

        if session.get("status") != "content_blocked":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session is not waiting for content continuation.",
            )

        last_submitted = max(
            (int(r.get("round") or 0) for r in rounds if r.get("status") == "submitted"),
            default=0,
        )
        next_round = last_submitted + 1
        if next_round > total:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session has no remaining rounds to continue.",
            )
        if any(int(r.get("round") or 0) == next_round for r in rounds):
            # Should have been caught by open_round; treat as conflict.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Next round already exists.",
            )

        candidate_doc = db["candidates"].find_one(
            {"candidate_id": session.get("candidate_id")}
        ) or {}
        candidate_elos = dict(candidate_doc.get("elo_ratings") or {})
        expanded_spec = _expanded_spec_for_round(session, next_round)
        plan = session.get("round_plan") or []
        planned_type = None
        if plan and next_round - 1 < len(plan):
            planned_type = str(plan[next_round - 1])
        if expanded_spec:
            planned_type = str(expanded_spec.get("round_type") or planned_type)

        rotation_skill = _skill_for_round(session, next_round)
        session_skills = list(session.get("skills") or [session.get("skill") or "DBMS"])
        if expanded_spec:
            spec_skills = [s for s in (expanded_spec.get("skills") or []) if s]
            if spec_skills:
                session_skills = spec_skills
                rotation_skill = spec_skills[0]
        rotation_elo = float(candidate_elos.get(rotation_skill, settings.initial_elo))
        rotation_difficulty = (
            str(expanded_spec.get("difficulty"))
            if expanded_spec and expanded_spec.get("difficulty")
            else _difficulty_from_elo(rotation_elo)
        )

        blocked_reason: str | None = None
        next_payload: dict[str, Any] | None = None

        try:
            if planned_type in ("mcq", "sql", "coding", "system_design", "ml_primitives"):
                spec_config: dict[str, Any] = {
                    "count": (expanded_spec or {}).get("count", 15),
                    "duration_minutes": (expanded_spec or {}).get("duration_minutes"),
                    "negative_marking": (expanded_spec or {}).get("negative_marking", 0.25),
                    "review_policy": (expanded_spec or {}).get("review_policy", "none"),
                    "difficulty": (expanded_spec or {}).get("difficulty"),
                    "question_ids": (expanded_spec or {}).get("question_ids") or None,
                    "problem_ids": (expanded_spec or {}).get("problem_ids") or None,
                    "problem_id": ((expanded_spec or {}).get("problem_ids") or [None])[0],
                }
                if spec_config.get("duration_minutes") is None:
                    spec_config.pop("duration_minutes", None)
                next_doc = build_round_document(
                    round_number=next_round,
                    round_type=planned_type,
                    skills=session_skills,
                    elo_before=rotation_elo,
                    difficulty=rotation_difficulty,
                    sub_domain=(expanded_spec or {}).get("topic"),
                    round_config=spec_config,
                    user_id=session.get("user_id"),
                    target_company_id=session.get("target_company_id"),
                    target_role_id=session.get("target_role_id"),
                    resume_skills=list(candidate_doc.get("resume_skills") or session_skills),
                    asked=_asked_questions(rounds),
                    block_id=(expanded_spec or {}).get("block_id"),
                    block_position=(expanded_spec or {}).get("block_position"),
                    block_category=(expanded_spec or {}).get("category"),
                    block_index=(expanded_spec or {}).get("block_index"),
                    block_total=(expanded_spec or {}).get("block_total"),
                    allow_unknown_fallback=bool(
                        session.get("allow_unknown_topic_fallback")
                    ),
                )
                next_payload = next_doc.model_dump()
                next_payload["skill"] = rotation_skill
            else:
                # Technical short answer: keep explicit topic pin.
                adaptive_skills = (
                    session_skills if expanded_spec
                    else (session.get("skills") or [session.get("skill")])
                )
                target = adaptive_question_selector.choose_adaptive_target(
                    user_id=str(session["user_id"]) if session.get("user_id") else None,
                    fallback_skill=rotation_skill,
                    fallback_difficulty=rotation_difficulty,
                    session_skills=adaptive_skills,
                    target_role_id=(
                        str(session["target_role_id"])
                        if session.get("target_role_id") else None
                    ),
                    candidate_elo_by_skill=candidate_elos,
                )
                next_skill = target.skill
                if expanded_spec:
                    if next_skill not in set(session_skills):
                        next_skill = rotation_skill
                next_difficulty = (
                    str(expanded_spec.get("difficulty"))
                    if expanded_spec and expanded_spec.get("difficulty")
                    else target.difficulty
                )
                sub = (
                    (expanded_spec or {}).get("topic")
                    or _sub_domain_for_skill(candidate_doc, next_skill)
                )
                question_payload = _get_next_question(
                    skill=next_skill,
                    sub_domain=sub,
                    difficulty=next_difficulty,
                    asked=_asked_questions(rounds),
                    user_id=str(session["user_id"]) if session.get("user_id") else None,
                    target_company_id=(
                        str(session["target_company_id"])
                        if session.get("target_company_id") else None
                    ),
                    target_role_id=(
                        str(session["target_role_id"])
                        if session.get("target_role_id") else None
                    ),
                    target_concepts=list(target.target_concepts or []),
                    resume_skills=list(
                        candidate_doc.get("resume_skills") or session_skills
                    ),
                    weak_skills=list(target.target_concepts or []),
                )
                _verify_served_topic(
                    requested=(expanded_spec or {}).get("topic"),
                    served=question_payload.get("sub_domain"),
                    skill=next_skill,
                    difficulty=next_difficulty,
                )
                next_payload = {
                    "round": next_round,
                    "round_type": "technical_short_answer",
                    "skill": next_skill,
                    "question": question_payload["question"],
                    "answer_text": None,
                    "nlp_score": None,
                    "svm_label": None,
                    "kg_score": None,
                    "ner_entities": [],
                    "final_score": None,
                    "difficulty": next_difficulty,
                    "difficulty_change": None,
                    "feedback": {"content": [], "strengths": [], "next_step": ""},
                    "elo_before": float(
                        candidate_elos.get(next_skill, settings.initial_elo)
                    ),
                    "elo_after": None,
                    "question_context": question_payload,
                    "started_at": datetime.now(timezone.utc),
                    "expires_at": None,
                    "status": "in_progress",
                    "block_id": (expanded_spec or {}).get("block_id"),
                    "block_position": (expanded_spec or {}).get("block_position"),
                    "block_category": (expanded_spec or {}).get("category"),
                    "block_index": (expanded_spec or {}).get("block_index"),
                    "block_total": (expanded_spec or {}).get("block_total"),
                    "config_json": {},
                }
        except (ValueError, IntegrationError) as exc:
            blocked_reason = str(exc)
            next_payload = None

        if next_payload is None:
            reason = blocked_reason or session.get("progression_blocked_reason") or (
                "Matching practice content is still unavailable."
            )
            with atomic(db):
                db["sessions"].update_one(
                    {"session_id": session_id},
                    {"$set": {
                        "status": "content_blocked",
                        "progression_blocked_reason": reason,
                    }},
                )
            return {
                "session_id": session_id,
                "status": "content_blocked",
                "continued": False,
                "progression_blocked": True,
                "progression_blocked_reason": reason,
                "round": None,
                "question": None,
                "total_rounds": total,
                "preserved_last_round": last_submitted,
            }

        rounds.append(next_payload)
        with atomic(db):
            db["sessions"].update_one(
                {"session_id": session_id},
                {"$set": {
                    "rounds": rounds,
                    "status": "active",
                    "progression_blocked_reason": None,
                    "last_round": last_submitted,
                    "current_skill": next_payload.get("skill"),
                    "current_difficulty": next_payload.get("difficulty"),
                }},
            )

        sanitized = sanitize_round_for_client(dict(next_payload))
        return {
            "session_id": session_id,
            "status": "active",
            "continued": True,
            "progression_blocked": False,
            "progression_blocked_reason": None,
            "round": next_payload.get("round"),
            "question": next_payload.get("question"),
            "round_type": next_payload.get("round_type"),
            "difficulty": next_payload.get("difficulty"),
            "question_context": sanitized.get("question_context") or {},
            "config_json": next_payload.get("config_json") or {},
            "expires_at": (
                next_payload["expires_at"].isoformat()
                if hasattr(next_payload.get("expires_at"), "isoformat")
                else next_payload.get("expires_at")
            ),
            "block_id": next_payload.get("block_id"),
            "block_position": next_payload.get("block_position"),
            "block_category": next_payload.get("block_category"),
            "current_skill": next_payload.get("skill"),
            "total_rounds": total,
        }
