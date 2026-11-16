"""
answer_v2.py — Drop-in replacement for backend/routes/answer.py

Core changes vs. the current version:
  • Uses _skill_for_round() to pick the correct skill for EACH round
  • Elo is updated on the skill THIS round was about (not always session["skill"])
  • Generates next question from the skill the NEXT round will use
  • Includes current_skill + total_rounds in response for the UI
  • Honors session["total_rounds"] (falls back to settings.max_rounds if unset)
"""
from __future__ import annotations

import copy
import re
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import json
from typing import Any
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, model_validator

from backend.config import get_settings
from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.db.transactions import atomic
from backend.execution import (
    CodingRateLimitedError,
    ExecutionUnavailableError,
    assert_coding_exec_allowed,
)
from backend.integrations import IntegrationError
from backend.routes.auth import (
    get_user_from_authorization,
    require_authenticated,
    require_matching_user,
    require_user,
)
from backend.routes.session_access import assert_session_access
from backend.routes.session import (
    _expanded_spec_for_round,
    _get_next_question,
    _skill_for_round,
    _sub_domain_for_skill,
    _verify_served_topic,
    build_round_document,
)
from backend.serializers.round_serializer import sanitize_round_for_client, sanitize_sql_artifact_for_client
from backend.evidence_kind import (
    SCORING_MODE_PRACTICE_ESTIMATE,
    SYSTEM_DESIGN_CONTENT_MODE,
    scoring_mode_at_write,
    EVIDENCE_PRACTICE_REVIEW,
    EVIDENCE_SELF_REPORTED,
    evaluation_unavailable,
    evidence_kind_for_round,
    is_self_reported_round,
    assessment_eligible_scores,
)
from modules import adaptive_question_selector
from modules.attempt_snapshot import freeze_attempt_snapshot
from modules.narration_jobs import enqueue_narration_job
from backend.round_lifecycle import (
    DURATION_SECONDS_KEY,
    ROUND_STATUS_READY,
    is_ready,
    prepare_round,
    round_not_active_detail,
)
from modules.scoring import UnsupportedRoundTypeError, score_round
from modules.concept_mastery import ConceptMastery
from modules.skill_graph import StudentSkillGraph
from modules.assistance_policy import (
    ELIGIBLE,
    evaluate_eligibility,
    is_follow_up_round,
)
from modules.follow_ups import (
    build_bundle_follow_up_round_doc,
    evaluate_inline_follow_up_outcome,
    is_inline_bundle_follow_up_round,
    is_inline_bundle_follow_up_spec,
    log_follow_up_decision,
    maybe_apply_inline_bundle_follow_up,
)
from modules.teaching_exposures import (
    list_exposures_for_eligibility,
    record_teaching_exposure,
)

router = APIRouter(prefix="/session", tags=["answer"])
logger = logging.getLogger(__name__)

# Per-session submit locks. Scoring + progression is a read-modify-write
# sequence (guard, claim, score, persist, append next round) that spans
# several store transactions on every backend, so the old check-then-claim
# allowed two concurrent submits to both score. Serializing per session
# closes that window for a single-process server. Different sessions never
# block each other. Multi-worker deployments also use store-level conditional
# claims (see backend.db.round_claim); entries are intentionally never
# evicted so a waiter can never miss a lock its session still holds.
_session_submit_locks: dict[str, threading.Lock] = {}
_session_submit_locks_guard = threading.Lock()


def _get_submit_lock(session_id: str) -> threading.Lock:
    with _session_submit_locks_guard:
        return _session_submit_locks.setdefault(session_id, threading.Lock())


@contextmanager
def _submit_locked(session_id: str):
    lock = _get_submit_lock(session_id or "")
    lock.acquire()
    try:
        yield
    finally:
        lock.release()

DIFFICULTY_RATINGS = {"easy": 1000, "medium": 1500, "hard": 2000}
WORD_RE = re.compile(r"[A-Za-z0-9_+#.]+")


class MCQAnswerItem(BaseModel):
    question_id: str
    selected_option_ids: list[str] = []

    @model_validator(mode="before")
    @classmethod
    def _validate_fields(cls, values: Any) -> Any:
        if isinstance(values, dict):
            allowed = {"question_id", "selected_option_ids"}
            extra = set(values.keys()) - allowed
            if extra:
                raise ValueError(f"Unknown extra fields in MCQ answer item: {sorted(extra)}")
        return values


class SubmitAnswerRequest(BaseModel):
    session_id: str
    round: int
    answer_text: str | None = None
    answers: list[MCQAnswerItem] | None = None
    word_count: int = 0
    engagement_label: str | None = None
    engagement_confidence: float | None = None
    engagement_delta: int | None = None
    wpm: float | None = None
    pause_count: int | None = None
    rubric_ratings: dict[str, Any] | None = None
    language: str = "python"

    @model_validator(mode="before")
    @classmethod
    def _validate_fields(cls, values: Any) -> Any:
        if isinstance(values, dict):
            allowed = {
                "session_id",
                "round",
                "answer_text",
                "answers",
                "word_count",
                "engagement_label",
                "engagement_confidence",
                "engagement_delta",
                "wpm",
                "pause_count",
                "rubric_ratings",
                "language",
            }
            extra = set(values.keys()) - allowed
            if extra:
                raise ValueError(f"Unknown extra fields rejected: {sorted(extra)}")
        return values


def _difficulty_from_elo(elo: float) -> str:
    if elo < 1200:
        return "easy"
    if elo < 1700:
        return "medium"
    return "hard"


def _compute_elo_update(elo_before: float, difficulty: str, final_score: float) -> float:
    question_rating = DIFFICULTY_RATINGS.get(difficulty, 1500)
    expected = 1.0 / (1.0 + pow(10.0, (question_rating - elo_before) / 400.0))
    actual = final_score / 100.0
    updated = elo_before + 32 * (actual - expected)
    return round(max(600.0, min(2400.0, updated)), 2)


def _difficulty_delta(previous: str, current: str) -> str:
    order = {"easy": 0, "medium": 1, "hard": 2}
    if order.get(current, 1) > order.get(previous, 1):
        return "increase"
    if order.get(current, 1) < order.get(previous, 1):
        return "decrease"
    return "same"


def _total_rounds(session: dict, settings) -> int:
    """Prefer the explicit total from multi-skill start; fall back to legacy setting."""
    n = session.get("total_rounds")
    if isinstance(n, int) and n > 0:
        return n
    return int(settings.max_rounds)


def _server_word_count(answer_text: str) -> int:
    return len(WORD_RE.findall(answer_text or ""))


def _update_learning_state(
    *,
    session: dict,
    skill: str,
    final_score: float,
    difficulty: str,
    scoring_breakdown: dict,
    elo_before: float | None = None,
    elo_after: float | None = None,
    session_id: str | None = None,
    raise_on_error: bool = True,
) -> None:
    """Update skill graph / mastery / Elo-delta signals.

    When ``raise_on_error`` is True (default), failures propagate so the
    attempt ``atomic()`` block can roll back scored round + learning effects
    together. Callers that intentionally keep best-effort semantics may pass
    ``raise_on_error=False``.
    """
    user_id = session.get("user_id")
    if not user_id:
        return
    try:
        StudentSkillGraph(str(user_id)).update_after_round(
            skill=skill,
            score=final_score,
            difficulty=difficulty,
        )
        ConceptMastery().update_from_round(
            user_id=str(user_id),
            skill=skill,
            covered_concepts=(
                (scoring_breakdown.get("concepts") or {}).get("covered")
                or scoring_breakdown.get("covered_concepts", [])
                or []
            ),
            missing_concepts=(
                (scoring_breakdown.get("concepts") or {}).get("missing")
                or scoring_breakdown.get("missing_concepts", [])
                or []
            ),
        )
        if elo_before is not None and elo_after is not None:
            from modules.learning_signals import record_elo_delta

            record_elo_delta(
                user_id=str(user_id),
                session_id=str(session_id or session.get("session_id") or ""),
                skill=skill,
                elo_before=float(elo_before),
                elo_after=float(elo_after),
            )
    except Exception:
        logger.warning("Failed to update Phase 2 learning state.", exc_info=True)
        if raise_on_error:
            raise


def _assistance_for_round(
    db: Any,
    *,
    user_id: str | None,
    session_id: str | None,
    round_type: str,
    round_document: dict,
    now: datetime,
) -> tuple[bool, list[str]]:
    """Snapshot whether THIS attempt used assistance before submit.

    Only events for this session/round, or unscoped events inside this
    round's time window, count. A later review of the same item must not
    taint a future unassisted retry. Best effort: a lookup failure leaves
    the round unmarked rather than failing the submit.
    """
    if not user_id:
        return False, []
    try:
        if round_type == "mcq":
            questions = (round_document.get("question_context") or {}).get("questions") or []
            wanted = {("mcq", str(q.get("id"))) for q in questions if q.get("id")}
        elif round_type in ("sql", "coding", "system_design"):
            config = round_document.get("config_json") or {}
            problem_id = config.get("problem_id")
            item_type = (
                "system_design" if round_type == "system_design" else round_type
            )
            wanted = {(item_type, str(problem_id))} if problem_id else set()
        else:
            return False, []
        if not wanted:
            return False, []
        started = round_document.get("started_at")
        if isinstance(started, str):
            try:
                started = datetime.fromisoformat(started.replace("Z", "+00:00"))
            except ValueError:
                started = None
        if isinstance(started, datetime) and started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        round_number = round_document.get("round")
        kinds: list[str] = []
        for event in db["assistance_events"].find({"user_id": str(user_id)}):
            key = (str(event.get("item_type")), str(event.get("item_id")))
            if key not in wanted:
                continue
            event_session = event.get("session_id")
            if event_session and session_id and str(event_session) != str(session_id):
                continue
            event_round = event.get("round")
            if event_round is not None and round_number is not None:
                try:
                    if int(event_round) != int(round_number):
                        continue
                except (TypeError, ValueError):
                    continue
            created = event.get("created_at")
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except ValueError:
                    created = None
            if isinstance(created, datetime):
                moment = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
                if moment > now:
                    continue
                # Unscoped events (Learn-page views) only count inside
                # this attempt's window, not forever after.
                if not event_session and started is not None and moment < started:
                    continue
            kind = str(event.get("kind") or "")
            if kind and kind not in kinds:
                kinds.append(kind)
        return bool(kinds), kinds
    except Exception:
        logger.warning("Failed to mark round assistance.", exc_info=True)
        return False, []


def _settle_narration(db: Any, session_id: str, round_number: int) -> str | None:
    """Return the round's narration job status, rendering it now when possible.

    With live narration off, the worker's only output is the deterministic
    rules script, so it is rendered here (post-commit, no network) instead of
    leaving the job queued for a worker that the local app never runs. With
    live narration on, the job stays queued for the worker.
    """
    from modules.llm_outbound_gate import llm_live_fetch_enabled
    from modules.narration_jobs import narration_job_id, process_narration_job

    job_id = narration_job_id(session_id, round_number)
    try:
        if llm_live_fetch_enabled():
            job = db["narration_jobs"].find_one({"id": job_id})
        else:
            job = process_narration_job(db, job_id)
    except Exception:
        logger.warning("Narration settle failed for %s.", job_id, exc_info=True)
        return None
    return (job or {}).get("status")


def _release_claim_to_pre_submit(
    db: Any,
    session_id: str,
    rounds: list[dict[str, Any]],
    round_number: int,
    pre_submit_round: dict[str, Any],
    expected_revision: int | None = None,
) -> None:
    """Best-effort rollback of the finalizing claim to the pre-submit round.

    Used when scoring failed before an attempt commit, and on the
    store-up unavailable paths (ml_primitives 503) so the round stays
    openly resubmittable instead of stuck in ``finalizing``. When the
    next question cannot be supplied after a successful evaluation, the
    scored result is preserved instead (session ``content_blocked``) — do
    not call this helper for that path.

    On a revision conflict the session is reloaded: if our round is still
    an unscored ``finalizing`` claim the release is retried once against
    the fresh revision, otherwise the state moved on (another worker owns
    it now) and the release is correctly skipped. Never raises: if the
    store is down the caller is already raising, and stale-claim takeover
    covers retry.
    """
    from backend.db.sqlalchemy_store import SessionWriteConflict

    try:
        restored = [copy.deepcopy(pre_submit_round) if doc.get("round") == round_number else doc
                    for doc in rounds]
        try:
            db["sessions"].update_one(
                {"session_id": session_id},
                {"$set": {"rounds": restored}},
                expected_revision=expected_revision,
            )
            return
        except SessionWriteConflict:
            pass
        fresh = db["sessions"].find_one({"session_id": session_id}) or {}
        fresh_rounds = list(fresh.get("rounds") or [])
        live = next(
            (doc for doc in fresh_rounds if doc.get("round") == round_number),
            None,
        )
        if live is None:
            return
        if str(live.get("status") or "") != "finalizing":
            return
        if bool(live.get("answer_text")) or live.get("final_score") is not None:
            return
        restored = [copy.deepcopy(pre_submit_round) if doc.get("round") == round_number else doc
                    for doc in fresh_rounds]
        try:
            db["sessions"].update_one(
                {"session_id": session_id},
                {"$set": {"rounds": restored}},
                expected_revision=fresh.get("revision"),
            )
        except SessionWriteConflict:
            logger.warning(
                "Release of finalizing claim lost a second race; "
                "stale-claim takeover covers retry."
            )
    except Exception:
        logger.warning("Failed to release finalizing claim.", exc_info=True)


def _clear_answer_draft(db: Any, session_id: str, round_number: int) -> None:
    """Remove the saved draft for a submitted round (best effort)."""
    try:
        db["answer_drafts"].delete_one(
            {"session_id": session_id, "round": int(round_number)}
        )
    except Exception:
        pass


MAX_SUBMISSION_SOURCE_CHARS = 100_000

# Bounded retries for the submit commit: on a lost cross-worker write race
# the attempt rolls back, reloads the session, revalidates round ownership,
# and re-runs progression against the fresh read. Scoring is never re-run,
# so retries cannot duplicate scores, snapshots, Elo, narration, or
# learning effects. Exhaustion is a controlled 409, not a 500.
MAX_SUBMIT_COMMIT_ATTEMPTS = 3


def _record_coding_attempt(
    db: Any,
    *,
    user_id: str | None,
    session_id: str,
    round_number: int,
    problem_id: str,
    source: str,
    status: str,
    score: float | None = None,
    visible_passed: int | None = None,
    visible_total: int | None = None,
    hidden_passed: int | None = None,
    hidden_total: int | None = None,
    error: str | None = None,
    language: str = "python",
) -> None:
    """Persist one coding submit attempt (best effort, aggregates only).

    Attempt rows carry the candidate's own source plus outcome counts.
    Hidden inputs, expected outputs, reference solutions, and hidden
    stdout/stderr are never stored here.
    """
    if not user_id:
        return
    text = source or ""
    truncated = len(text) > MAX_SUBMISSION_SOURCE_CHARS
    if truncated:
        text = text[:MAX_SUBMISSION_SOURCE_CHARS]
    try:
        db["coding_submissions"].insert_one({
            "id": str(uuid4()),
            "user_id": str(user_id),
            "session_id": session_id,
            "round": int(round_number),
            "problem_id": problem_id,
            "language": language,
            "source": text,
            "truncated": truncated,
            "status": status,
            "score": score,
            "visible_passed": visible_passed,
            "visible_total": visible_total,
            "hidden_passed": hidden_passed,
            "hidden_total": hidden_total,
            "error": error,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        logger.warning("Failed to record coding attempt.", exc_info=True)


def _record_system_design_attempt(
    db: Any,
    *,
    user_id: str | None,
    session_id: str,
    round_number: int,
    prompt_id: str,
    answer_text: str,
    rubric_json: dict[str, Any] | None,
    evaluation_mode: str,
    status: str,
    score: float | None = None,
    incomplete: bool = False,
) -> None:
    """Persist one system-design attempt (self-assessment aggregates only)."""
    if not user_id:
        return
    try:
        db["system_design_attempts"].insert_one({
            "id": str(uuid4()),
            "user_id": str(user_id),
            "session_id": session_id,
            "round": int(round_number),
            "prompt_id": prompt_id,
            "answer_text": answer_text or "",
            "rubric_json": rubric_json or {},
            "evaluation_mode": evaluation_mode or "structured_self_assessment",
            "status": status,
            "score": score,
            "incomplete": bool(incomplete),
            "created_at": datetime.now(timezone.utc),
        })
    except Exception:
        logger.warning("Failed to record system-design attempt.", exc_info=True)


@router.post("/answer", dependencies=[Depends(require_authenticated)])
def submit_answer(
    request: SubmitAnswerRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    settings = get_settings()
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    with _submit_locked(request.session_id):
        session = db["sessions"].find_one({"session_id": request.session_id})
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
            )
        rounds = session.get("rounds", [])
        active_round = next((item for item in rounds if item.get("round") == request.round), None)
        if not active_round:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requested round not found in session.",
            )

        round_type = active_round.get("round_type", "technical_short_answer")

        # Same ownership gate as GET /session: owned or Phase-2 sessions
        # require the owning JWT. Legacy anonymous technical sessions stay
        # guest-submittable. Missing token on an owned session is 401, not a bypass.
        user = assert_session_access(
            session,
            authorization,
            foreign_detail="You cannot access another user's data.",
        )

        # Strict round-type validation
        normalized_answers = None
        if round_type == "mcq":
            if request.answers is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="MCQ round requires structured 'answers' payload.",
                )
            if request.answer_text is not None and request.answer_text != "":
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="MCQ round rejects 'answer_text'.",
                )
            normalized_answers = [
                item.model_dump() if hasattr(item, "model_dump") else dict(item)
                for item in request.answers
            ]
        else:
            if request.answer_text is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Round type '{round_type}' requires 'answer_text'.",
                )
            if request.answers is not None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Round type '{round_type}' rejects 'answers'.",
                )

        if is_ready(active_round):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=round_not_active_detail(active_round),
            )

        now = datetime.now(timezone.utc)

        # Deadline enforcement (no hidden grace period)
        expires_at = active_round.get("expires_at")
        if expires_at is not None:
            if isinstance(expires_at, str):
                try:
                    expires_at = datetime.fromisoformat(expires_at)
                except Exception:
                    expires_at = None
            if expires_at and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at and now > expires_at:
                from backend.db.sqlalchemy_store import SessionWriteConflict

                active_round["status"] = "expired"
                if not evaluation_unavailable(round_type):
                    active_round["final_score"] = 0.0
                try:
                    db["sessions"].update_one(
                        {"session_id": request.session_id},
                        {"$set": {"rounds": rounds}},
                        expected_revision=session.get("revision"),
                    )
                except SessionWriteConflict:
                    # Another worker committed since our read: reload and
                    # re-decide rather than clobber. A concurrently
                    # submitted round wins over the late expiry mark.
                    fresh = (
                        db["sessions"].find_one(
                            {"session_id": request.session_id}
                        )
                        or {}
                    )
                    fresh_rounds = list(fresh.get("rounds") or [])
                    live = next(
                        (
                            item
                            for item in fresh_rounds
                            if item.get("round") == request.round
                        ),
                        None,
                    )
                    if live is None:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="Requested round not found in session.",
                        ) from None
                    if str(live.get("status") or "") == "submitted" or (
                        live.get("final_score") is not None
                        and str(live.get("status") or "") != "expired"
                    ):
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="This round has already been submitted.",
                        ) from None
                    live["status"] = "expired"
                    if not evaluation_unavailable(round_type):
                        live["final_score"] = 0.0
                    try:
                        db["sessions"].update_one(
                            {"session_id": request.session_id},
                            {"$set": {"rounds": fresh_rounds}},
                            expected_revision=fresh.get("revision"),
                        )
                    except SessionWriteConflict:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=(
                                "Concurrent session update; retry the submission."
                            ),
                        ) from None
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Assessment deadline expired at {expires_at.isoformat()}.",
                )

        # Concurrency guard: store-level conditional claim (+ process lock).
        from backend.db.round_claim import claim_round_finalizing

        # Stale finalizing without a score: takeover is safe under the
        # per-session lock (single-process). Cross-worker races rely on the
        # SQL UPDATE rowcount instead.
        round_status = active_round.get("status")
        scored = bool(active_round.get("answer_text")) or active_round.get("final_score") is not None
        allow_takeover = round_status == "finalizing" and not scored
        if allow_takeover:
            logger.warning(
                "Taking over stale finalizing claim for session %s round %s.",
                request.session_id, request.round,
            )
        claim = claim_round_finalizing(
            db,
            session_id=request.session_id,
            round_number=request.round,
            allow_stale_takeover=allow_takeover,
        )
        if claim == "already_done":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This round has already been submitted or is finalizing.",
            )
        if claim == "busy":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This round has already been submitted or is finalizing.",
            )
        if claim == "missing":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Round not found.",
            )
        # Refresh local view after claim so status matches the store.
        session = db["sessions"].find_one({"session_id": request.session_id}) or session
        rounds = session.get("rounds", [])
        active_round = next(
            (item for item in rounds if item.get("round") == request.round),
            active_round,
        )
        active_round["status"] = "finalizing"

        # Pristine pre-submit copy: a failure before the attempt commit
        # (content errors building the next round) restores this, so the
        # retry is a clean resubmit rather than a 409 over half-scored data.
        pre_submit_round = copy.deepcopy(active_round)
        if pre_submit_round.get("status") == "finalizing":
            # Takeover path: release must undo the claim, not re-persist it.
            pre_submit_round["status"] = "in_progress"

        # Which skill does THIS round belong to?
        current_skill = _skill_for_round(session, request.round)

        # Candidate baseline from prior rounds (unchanged behaviour)
        rounds_so_far = [item for item in rounds if item.get("final_score") is not None]
        candidate_baseline = None
        if len(rounds_so_far) >= 2:
            candidate_baseline = sum(
                float(item["final_score"]) for item in rounds_so_far
            ) / len(rounds_so_far)

        from modules.staged_flow import (
            UNSCORED_STAGES,
            apply_deferred_answer_mask,
            is_staged_v1_session,
            round_stage,
            select_non_core_stage_question,
            unscored_stage_result,
        )

        active_stage = round_stage(active_round)
        scoring_question_context: dict[str, Any] = dict(active_round.get("question_context", {}) or {})
        try:
            follow_up_scoring_pre = (
                (active_round.get("config_json") or {}).get("follow_up_scoring")
                or active_round.get("follow_up_scoring")
            )
            if active_stage in UNSCORED_STAGES:
                # Warm-up and Behavioural share the same null-score mechanism.
                scoring_result = unscored_stage_result(
                    stage=active_stage, reason=f"{active_stage}_unscored"
                )
            elif is_follow_up_round(active_round) and follow_up_scoring_pre == "unreviewed":
                # Unreviewed follow-ups are explicitly unscored practice even
                # when REVIEWED_BUNDLES_ONLY is false. No numeric score.
                scoring_result = {
                    "final_score": None,
                    "nlp_score": None,
                    "svm_label": None,
                    "kg_score": None,
                    "ner_entities": [],
                    "feedback": {
                        "content": ["Unscored clarification follow-up."],
                        "strengths": [],
                        "weakness": [],
                        "next_step": "Continue with the remaining mandatory rounds.",
                    },
                    "scoring_breakdown": {
                        "follow_up_scoring": "unreviewed",
                        "unscored_reason": "unreviewed_follow_up",
                    },
                    "score_explanation": {},
                    "guard_applied": None,
                }
            elif round_type == "mcq":
                scoring_result = score_round(
                    round_type="mcq",
                    answers=normalized_answers,
                    question_context=active_round.get("question_context", {}),
                    config=active_round.get("config_json", {}),
                )
            elif round_type == "coding":
                from functools import partial
                from backend.coding_languages import normalize_language
                from backend.db.phase_c_coding_bank import get_coding_problem
                from backend.execution import execute_python_tests

                language = normalize_language(request.language)
                coding_config = dict(active_round.get("config_json") or {})
                problem = get_coding_problem(coding_config.get("problem_id"))
                if user is None:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication is required for coding rounds.",
                    )
                assert_coding_exec_allowed(str(user["id"]), active_round)
                scoring_result = score_round(
                    round_type="coding", answer_text=request.answer_text,
                    question_context=active_round.get("question_context", {}),
                    config=coding_config,
                    executor=partial(execute_python_tests, language=language, problem=problem),
                )
                active_round["config_json"] = {**coding_config, "language": language}
            elif round_type == "ml_primitives":
                if user is None:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication is required for ML primitives rounds.",
                    )
                from backend.ml_primitives.catalog import scoring_available as ml_available

                if not ml_available():
                    # No executor: nothing is run or scored; source is stored below.
                    raise ExecutionUnavailableError(
                        "ML execution is unavailable in this environment."
                    )
                # Same per-user and per-round execution quota as coding; an
                # infrastructure failure releases it with the claim below.
                assert_coding_exec_allowed(str(user["id"]), active_round)
                scoring_result = score_round(
                    round_type="ml_primitives",
                    answer_text=request.answer_text,
                    config=active_round.get("config_json", {}),
                )
            elif round_type == "system_design":
                scoring_result = score_round(
                    round_type="system_design",
                    answer_text=request.answer_text,
                    rubric_ratings=request.rubric_ratings,
                    question_context=active_round.get("question_context", {}),
                    config=active_round.get("config_json", {}),
                )
            else:
                from modules.bundle_scoring import (
                    BundleReferenceUnavailable,
                    scoring_context_from_round,
                )

                try:
                    scoring_question_context = scoring_context_from_round(
                        active_round.get("question_context", {})
                    )
                except BundleReferenceUnavailable as exc:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=str(exc),
                    ) from exc
                reference = str(
                    scoring_question_context.get("ideal_answer")
                    or scoring_question_context.get("reference_answer")
                    or ""
                ).strip()
                if (
                    is_staged_v1_session(session)
                    and active_stage == "core"
                    and not reference
                    and not scoring_question_context.get("required_concepts")
                ):
                    scoring_result = unscored_stage_result(
                        stage=active_stage, reason="no_reference_unscored"
                    )
                else:
                    scoring_result = score_round(
                        round_type=round_type,
                        answer_text=request.answer_text,
                        word_count=_server_word_count(request.answer_text or ""),
                        engagement_label=request.engagement_label,
                        wpm=request.wpm,
                        pause_count=request.pause_count,
                        question_context=scoring_question_context,
                        difficulty=active_round.get("difficulty", "medium"),
                        candidate_baseline=candidate_baseline,
                    )
        except Exception as exc:
            # Rollback status on failure so round is not stuck in 'finalizing'
            _release_claim_to_pre_submit(
                db,
                request.session_id,
                rounds,
                request.round,
                pre_submit_round,
                expected_revision=session.get("revision"),
            )
            if isinstance(exc, CodingRateLimitedError):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
                ) from exc
            if isinstance(exc, ExecutionUnavailableError):
                # The attempt is recorded as unevaluated history; the round
                # stays open, nothing is scored, and the retry is a plain
                # resubmit (not a 409).
                if round_type == "coding":
                    # Coding rounds always carry an owning user_id (auth is
                    # mandatory), so the session owner is authoritative here.
                    _record_coding_attempt(
                        db,
                        user_id=session.get("user_id"),
                        session_id=request.session_id,
                        round_number=request.round,
                        problem_id=str((active_round.get("config_json") or {}).get("problem_id") or ""),
                        source=request.answer_text or "",
                        status="unavailable",
                        error=str(exc),
                        language=request.language,
                    )
                if round_type == "ml_primitives":
                    from backend.routes.ml_primitives import store_unavailable_attempt

                    # Source stored as unevaluated history; the round stays
                    # open and the retry is a plain resubmit.
                    detail = store_unavailable_attempt(
                        db, session, active_round, request.answer_text
                    )
                    raise HTTPException(status_code=503, detail=detail) from exc
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
                ) from exc
            if isinstance(exc, (ValueError, UnsupportedRoundTypeError)):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
                ) from exc
            if isinstance(exc, IntegrationError):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
                ) from exc
            raise

        if round_type == "coding":
            # Authoritative evaluation happened; record the graded attempt
            # alongside the round persist below (aggregates only).
            explanation = scoring_result.get("score_explanation") or {}
            _record_coding_attempt(
                db,
                user_id=session.get("user_id"),
                session_id=request.session_id,
                round_number=request.round,
                problem_id=str((active_round.get("config_json") or {}).get("problem_id") or ""),
                source=request.answer_text or "",
                status="scored",
                language=request.language,
                score=scoring_result.get("final_score"),
                visible_passed=explanation.get("visible_passed"),
                visible_total=explanation.get("visible_total"),
                hidden_passed=explanation.get("hidden_passed"),
                hidden_total=explanation.get("hidden_total"),
                error=None,
            )

        if round_type == "ml_primitives":
            from backend.routes.ml_primitives import store_graded_attempt

            store_graded_attempt(db, session, active_round, request.answer_text, scoring_result)

        if round_type == "system_design":
            incomplete = bool(scoring_result.get("incomplete"))
            prompt_id = str(
                (active_round.get("config_json") or {}).get("problem_id") or ""
            )
            _record_system_design_attempt(
                db,
                user_id=session.get("user_id"),
                session_id=request.session_id,
                round_number=request.round,
                prompt_id=prompt_id,
                answer_text=request.answer_text or "",
                rubric_json={
                    "ratings": request.rubric_ratings or {},
                    "rubric": scoring_result.get("rubric") or [],
                    "boundary": scoring_result.get("boundary"),
                },
                evaluation_mode=str(
                    scoring_result.get("evaluation_mode")
                    or "structured_self_assessment"
                ),
                status="incomplete" if incomplete else "scored",
                score=scoring_result.get("final_score"),
                incomplete=incomplete,
            )
            if incomplete or scoring_result.get("final_score") is None:
                # Incomplete self-assessment: no score, round stays open.
                _release_claim_to_pre_submit(
                    db,
                    request.session_id,
                    rounds,
                    request.round,
                    pre_submit_round,
                    expected_revision=session.get("revision"),
                )
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        scoring_result.get("feedback")
                        or "Complete every rubric rating (1–5). "
                        "Incomplete self-assessment produces no score."
                    ),
                )

        # Elo / difficulty: self-reported, spaced-review, and non-eligible
        # assisted/repeated/follow-up attempts never move measured Elo.
        elo_before = float(active_round.get("elo_before") or settings.initial_elo)
        is_spaced_review = (
            (session.get("round_config") or {}).get("purpose") == "spaced_review"
        )
        evidence_kind = (
            EVIDENCE_PRACTICE_REVIEW
            if is_spaced_review
            else evidence_kind_for_round(
                round_type=round_type,
                evaluation_mode=scoring_result.get("evaluation_mode"),
            )
        )
        self_reported = evidence_kind == EVIDENCE_SELF_REPORTED
        # Self-reported and practice-review results (e.g. the system-design
        # content estimate) are shown but never move Elo or learning state.
        practice_only = self_reported or evidence_kind == EVIDENCE_PRACTICE_REVIEW

        # Freeze eligibility at submission acceptance using exposures at or
        # before this server cutoff. Feedback released after commit cannot
        # retroactively mark this attempt assisted.
        assisted, assistance_kinds = _assistance_for_round(
            db,
            user_id=session.get("user_id"),
            session_id=session.get("session_id"),
            round_type=round_type,
            round_document=active_round,
            now=now,
        )
        exposures = list_exposures_for_eligibility(
            db,
            session=session,
            user_id=session.get("user_id"),
            before=now,
        )
        # Carry follow-up flags from the active round / expanded plan.
        eligibility_round = dict(active_round)
        if is_follow_up_round(active_round):
            eligibility_round["is_follow_up"] = True
        eligibility = evaluate_eligibility(
            session=session,
            round_doc=eligibility_round,
            exposures=exposures,
            prior_rounds=rounds,
            now=now,
            history_complete=True,
        )
        # Phase D assisted flag stays for notebooks; eligibility is authoritative.
        if eligibility["decision"] != ELIGIBLE and not assisted:
            if any(
                r in eligibility["exclusion_reasons"]
                for r in (
                    "teaching_exposure",
                    "related_topic_exposure",
                    "coarse_topic_scope",
                )
            ):
                assisted = True
                assistance_kinds = list(
                    dict.fromkeys(
                        list(assistance_kinds)
                        + [
                            str(e.get("content_kind") or "hint")
                            for e in exposures
                            if e.get("delivery_id") in set(eligibility["exposure_ids"])
                        ]
                    )
                )

        assessment_eligible = eligibility["decision"] == ELIGIBLE
        if (
            practice_only
            or is_spaced_review
            or not assessment_eligible
            or scoring_result.get("final_score") is None
        ):
            elo_after = elo_before
            next_difficulty = active_round.get("difficulty", "medium")
            difficulty_change = "same"
        else:
            elo_after = _compute_elo_update(
                elo_before=elo_before,
                difficulty=active_round.get("difficulty", "medium"),
                final_score=float(scoring_result["final_score"]),
            )
            next_difficulty = _difficulty_from_elo(elo_after)
            difficulty_change = _difficulty_delta(
                active_round.get("difficulty", "medium"), next_difficulty
            )

        persisted_answer = (
            request.answer_text
            if round_type != "mcq"
            else json.dumps(normalized_answers)
        )

        # Unreviewed follow-ups are always null-scored practice even when
        # REVIEWED_BUNDLES_ONLY is false.
        follow_up_scoring = (
            (active_round.get("config_json") or {}).get("follow_up_scoring")
            or active_round.get("follow_up_scoring")
        )
        if is_follow_up_round(active_round) and follow_up_scoring == "unreviewed":
            scoring_result = {
                **scoring_result,
                "final_score": None,
                "feedback": scoring_result.get("feedback")
                or {
                    "content": ["Unscored clarification follow-up."],
                    "strengths": [],
                    "weakness": [],
                    "next_step": "Continue with the remaining mandatory rounds.",
                },
            }

        is_inline_follow_up = is_inline_bundle_follow_up_round(active_round)
        inline_follow_up_outcome: dict[str, Any] | None = None
        inline_client_feedback: dict[str, Any] | None = None

        # Persist this round (assisted already resolved above)
        _bd = dict(scoring_result.get("scoring_breakdown", {}) or {})
        if active_stage:
            _bd["stage"] = active_stage
        raw_guard_applied = scoring_result.get("guard_applied")
        if is_inline_follow_up:
            _bd["inline_follow_up"] = True
            _bd["raw_v3_final_score"] = scoring_result.get("final_score")
            if raw_guard_applied is not None:
                _bd["guard_applied"] = raw_guard_applied
            outcome_eval = evaluate_inline_follow_up_outcome(
                active_round=active_round,
                scoring_question_context=scoring_question_context,
                answer_text=request.answer_text or "",
                scoring_result=scoring_result,
            )
            inline_follow_up_outcome = {
                "targets_concept": outcome_eval["targets_concept"],
                "concept_label": outcome_eval["concept_label"],
                "demonstrated": outcome_eval["demonstrated"],
                "status": outcome_eval["status"],
            }
            inline_client_feedback = outcome_eval["feedback"]
            _bd["follow_up_outcome"] = inline_follow_up_outcome

        scoring_mode = (
            SCORING_MODE_PRACTICE_ESTIMATE
            if scoring_result.get("evaluation_mode") == SYSTEM_DESIGN_CONTENT_MODE
            else scoring_mode_at_write(
                self_reported=self_reported,
                scoring_breakdown=_bd,
                scoring_result=scoring_result,
            )
        )
        # Persist disclosure fields inside scoring_breakdown JSON — the
        # SQLAlchemy rounds table has no dedicated columns for them.
        _bd["scoring_mode"] = scoring_mode
        _bd["evidence_kind"] = evidence_kind
        if scoring_result.get("evaluation_mode"):
            _bd["evaluation_mode"] = scoring_result.get("evaluation_mode")
        if "semantic_scoring_available" not in _bd:
            _bd["semantic_scoring_available"] = scoring_result.get(
                "semantic_scoring_available"
            )
        if "semantic_fallback_reason" not in _bd and scoring_result.get(
            "semantic_fallback_reason"
        ):
            _bd["semantic_fallback_reason"] = scoring_result.get(
                "semantic_fallback_reason"
            )
        _bd["assessment_eligibility"] = {
            "decision": eligibility["decision"],
            "policy_version": eligibility["policy_version"],
            "exclusion_reasons": eligibility["exclusion_reasons"],
            "exposure_ids": eligibility["exposure_ids"],
            "cutoff_at": eligibility.get("cutoff_at"),
            "legacy": False,
        }
        _bd["eligibility_policy_version"] = eligibility["policy_version"]
        _bd["eligibility_exclusion_reasons"] = eligibility["exclusion_reasons"]
        _bd["eligibility_exposure_ids"] = eligibility["exposure_ids"]
        _bd["assessment_eligibility_decision"] = eligibility["decision"]
        # Scored-round payload, computed ONCE from this request's scoring
        # result. Every commit attempt merges it onto a fresh read instead
        # of rescoring, so a retried commit can never duplicate scoring,
        # attempt snapshots, Elo updates, narration jobs, or learning
        # effects: the losing attempt rolled back before any of them ran.
        _scored_base = next(
            (doc for doc in rounds if doc.get("round") == request.round),
            active_round,
        )
        scored_round_update = {
            "skill": current_skill,
            "answer_text": persisted_answer,
            "status": "submitted",
            "assisted": assisted,
            "assistance_kinds": assistance_kinds,
            "assessment_eligibility": eligibility["decision"],
            "eligibility_policy_version": eligibility["policy_version"],
            "eligibility_exclusion_reasons": eligibility["exclusion_reasons"],
            "eligibility_exposure_ids": eligibility["exposure_ids"],
            "is_follow_up": bool(is_follow_up_round(active_round)),
            "follow_up_parent_round": active_round.get("follow_up_parent_round")
            or (active_round.get("config_json") or {}).get("follow_up_parent_round"),
            "follow_up_identity": active_round.get("follow_up_identity")
            or (active_round.get("config_json") or {}).get("follow_up_identity"),
            "submitted_at": now,
            "nlp_score": scoring_result.get("nlp_score"),
            "svm_label": scoring_result.get("svm_label"),
            "kg_score": scoring_result.get("kg_score"),
            "kg_label": _bd.get("kg_label", ""),
            "covered_concepts": _bd.get("covered_concepts", []),
            "missing_concepts": _bd.get("missing_concepts", []),
            "ner_entities": scoring_result.get("ner_entities", []),
            "final_score": None if is_inline_follow_up else scoring_result["final_score"],
            "difficulty_change": difficulty_change,
            "feedback": (
                inline_client_feedback
                if is_inline_follow_up and inline_client_feedback is not None
                else scoring_result["feedback"]
            ),
            "score_explanation": {} if is_inline_follow_up else scoring_result.get("score_explanation", {}),
            "elo_before": elo_before,
            "elo_after": elo_after,
            "engagement_label": request.engagement_label,
            "engagement_confidence": request.engagement_confidence,
            "engagement_delta": request.engagement_delta,
            # Delivery signals (server-only; see backend/db/round_meta.py).
            "wpm": request.wpm,
            "pause_count": request.pause_count,
            "scoring_breakdown": _bd,
            "artifact_json": scoring_result.get("artifact_json") or _scored_base.get("artifact_json", {}),
            "guard_applied": None if is_inline_follow_up else scoring_result.get("guard_applied"),
            **(
                {
                    "config_json": {
                        **(active_round.get("config_json") or {}),
                        "follow_up_outcome": inline_follow_up_outcome,
                    },
                    "follow_up_outcome": inline_follow_up_outcome,
                }
                if is_inline_follow_up and inline_follow_up_outcome is not None
                else {}
            ),
            "evaluation_mode": scoring_result.get("evaluation_mode"),
            "evidence_kind": evidence_kind,
            "scoring_mode": scoring_mode,
            "semantic_scoring_available": _bd.get(
                "semantic_scoring_available",
                scoring_result.get("semantic_scoring_available"),
            ),
            "semantic_fallback_reason": _bd.get(
                "semantic_fallback_reason",
                scoring_result.get("semantic_fallback_reason"),
            ),
        }

        from backend.db.sqlalchemy_store import SessionWriteConflict

        inline_followup_result: dict[str, Any] | None = None
        for _commit_attempt in range(MAX_SUBMIT_COMMIT_ATTEMPTS):
            inline_followup_result = None
            if _commit_attempt:
                # Lost a write race: reload, revalidate ownership of this
                # round, and re-run progression against the fresh session so
                # the retry behaves like a submit that started after the
                # winner committed. Scoring is NOT re-run.
                logger.warning(
                    "Submit commit for session %s round %s lost a write race; "
                    "reloading (attempt %d of %d).",
                    request.session_id,
                    request.round,
                    _commit_attempt + 1,
                    MAX_SUBMIT_COMMIT_ATTEMPTS,
                )
                reloaded = db["sessions"].find_one(
                    {"session_id": request.session_id}
                )
                if not reloaded:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Session not found.",
                    )
                session = reloaded
                rounds = list(session.get("rounds") or [])
                live = next(
                    (
                        item
                        for item in rounds
                        if item.get("round") == request.round
                    ),
                    None,
                )
                if live is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Requested round not found in session.",
                    )
                live_status = str(live.get("status") or "")
                live_scored = bool(live.get("answer_text")) or (
                    live.get("final_score") is not None
                )
                if live_status == "expired":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Assessment deadline expired before submission.",
                    )
                if live_status == "submitted" or live_scored:
                    # Another worker finalized this round (a co-held claim
                    # committed first): our answer is recorded; resubmitting
                    # must not overwrite the winner's score.
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="This round has already been submitted.",
                    )
                if live_status != "finalizing":
                    # Our claim was overwritten by a racing writer: reclaim
                    # conditionally rather than assuming ownership.
                    reclaim = claim_round_finalizing(
                        db,
                        session_id=request.session_id,
                        round_number=request.round,
                        allow_stale_takeover=False,
                    )
                    if reclaim == "missing":
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail="Round not found.",
                        )
                    if reclaim != "claimed":
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="This round has already been submitted or is finalizing.",
                        )
                    live["status"] = "finalizing"
            # Merge the scored payload onto this attempt's rounds and freeze
            # the immutable attempt snapshot: everything the score depended
            # on, digested, committed once.
            for index, round_document in enumerate(rounds):
                if round_document.get("round") != request.round:
                    continue
                rounds[index] = {**round_document, **scored_round_update}
                rounds[index]["attempt_snapshot"] = freeze_attempt_snapshot(
                    rounds[index], scoring_result
                )
                active_round = rounds[index]
                break

            total_rounds = _total_rounds(session, settings)
            if settings.staged_inline_follow_ups:
                inline_followup_result = maybe_apply_inline_bundle_follow_up(
                    session=session,
                    active_round=active_round,
                    rounds=rounds,
                    total_rounds=total_rounds,
                    target_difficulty=next_difficulty,
                )
                total_rounds = int(inline_followup_result["total_rounds"])

            next_skill: str | None = None
            next_target: dict[str, object] | None = None
            response_next_difficulty = next_difficulty
            next_round_type: str | None = None
            next_block_id: str | None = None
            next_block_position: int | None = None
            next_block_category: str | None = None
            next_round_number: int | None = None
            next_round_status: str | None = None
            # When the next question cannot be supplied after a successful
            # evaluation, keep the scored result and mark the session blocked
            # instead of rolling the answer back.
            progression_blocked_reason: str | None = None

            session_status = "completed" if request.round >= total_rounds else "active"
            is_spaced_review = (
                (session.get("round_config") or {}).get("purpose") == "spaced_review"
            )
            # Assessment-eligible readiness only — self-reported, spaced-review,
            # and assisted/repeated/follow-up attempts stay out of the mean.
            completed_scores = [] if is_spaced_review else assessment_eligible_scores(rounds)
            try:
                # Expected inventory / topic exhaustion sets progression_blocked and
                # still commits the scored answer (content_blocked). Unrelated
                # DatabaseConnectionError during the attempt commit rolls the score
                # (and required learning effects) back so retry can resubmit via
                # stale-claim takeover. Elo, narration job, and graph/mastery
                # updates join the attempt transaction.
                # Queue the next round after recomputing the user's weakest skill
                # and concept from fresh learning state. Anonymous sessions keep the
                # existing rotation behavior. Block sessions honor the expanded plan
                # in requested order; legacy sessions honor round_plan.
                if request.round < total_rounds:
                    next_round = request.round + 1
                    # Idempotent progression: if the next round already exists (retry
                    # after a lost response), reuse it instead of appending a duplicate.
                    existing_next = next(
                        (item for item in rounds if item.get("round") == next_round),
                        None,
                    )
                    if existing_next is not None:
                        next_skill = existing_next.get("skill") or _skill_for_round(session, next_round)
                        next_round_type = existing_next.get("round_type")
                        response_next_difficulty = existing_next.get("difficulty", next_difficulty)
                        next_round_number = next_round
                        next_round_status = existing_next.get("status")
                        next_block_id = existing_next.get("block_id")
                        next_block_position = existing_next.get("block_position")
                        next_block_category = existing_next.get("block_category")
                        # No write here: the reused round is already persisted and
                        # the session-level next values join the commit below.
                    else:
                        plan = session.get("round_plan") or []
                        planned_type = None
                        if plan and next_round - 1 < len(plan):
                            planned_type = str(plan[next_round - 1])
                        expanded_spec = _expanded_spec_for_round(session, next_round)
                        if expanded_spec:
                            planned_type = str(expanded_spec.get("round_type") or planned_type)

                        rotation_skill = _skill_for_round(session, next_round)
                        candidate_doc = db["candidates"].find_one({"candidate_id": session["candidate_id"]})
                        candidate_elos = dict((candidate_doc or {}).get("elo_ratings", {}) or {})
                        if not practice_only and not is_spaced_review:
                            # The Elo commit below hasn't run yet; rotation must
                            # see this round's update exactly as if it had.
                            candidate_elos[current_skill] = elo_after
                        rotation_elo = float(candidate_elos.get(rotation_skill, elo_after))
                        rotation_difficulty = _difficulty_from_elo(rotation_elo)
                        session_user_id = session.get("user_id")
                        session_target_company = session.get("target_company_id")
                        session_target_role = session.get("target_role_id")
                        resume_skills = list((candidate_doc or {}).get("resume_skills") or session.get("skills") or [])
                        session_skills = list(session.get("skills") or [session.get("skill") or "DBMS"])
                        if expanded_spec:
                            spec_skills = [s for s in (expanded_spec.get("skills") or []) if s]
                            if spec_skills:
                                session_skills = spec_skills
                                rotation_skill = spec_skills[0]
                                rotation_elo = float(candidate_elos.get(rotation_skill, elo_after))
                                rotation_difficulty = (
                                    str(expanded_spec.get("difficulty"))
                                    if expanded_spec.get("difficulty")
                                    else _difficulty_from_elo(rotation_elo)
                                )

                        if planned_type in ("mcq", "sql", "coding", "system_design", "ml_primitives"):
                            if expanded_spec:
                                spec_config: dict[str, Any] = {
                                    "count": expanded_spec.get("count", 15),
                                    "duration_minutes": expanded_spec.get("duration_minutes"),
                                    "negative_marking": expanded_spec.get("negative_marking", 0.25),
                                    "review_policy": expanded_spec.get("review_policy", "none"),
                                    "difficulty": expanded_spec.get("difficulty"),
                                    "question_ids": expanded_spec.get("question_ids") or None,
                                    "problem_ids": expanded_spec.get("problem_ids") or None,
                                    "problem_id": (expanded_spec.get("problem_ids") or [None])[0],
                                }
                                if expanded_spec.get("stage"):
                                    spec_config["stage"] = expanded_spec["stage"]
                                legacy_cfg = dict(session.get("round_config") or {})
                                for key in ("max_rows", "timeout_seconds"):
                                    if key in legacy_cfg:
                                        spec_config[key] = legacy_cfg[key]
                                if spec_config.get("duration_minutes") is None:
                                    spec_config.pop("duration_minutes", None)
                                sql_index = 0
                            else:
                                if planned_type == "coding":
                                    sql_index = sum(
                                        1 for i, t in enumerate(plan[: next_round - 1]) if t == "coding"
                                    )
                                elif planned_type == "system_design":
                                    sql_index = sum(
                                        1 for i, t in enumerate(plan[: next_round - 1])
                                        if t == "system_design"
                                    )
                                else:
                                    sql_index = sum(
                                        1 for i, t in enumerate(plan[: next_round - 1]) if t == "sql"
                                    )
                                spec_config = dict(session.get("round_config") or {})
                            try:
                                next_doc = build_round_document(
                                    round_number=next_round,
                                    round_type=planned_type,
                                    skills=session_skills,
                                    elo_before=rotation_elo,
                                    difficulty=rotation_difficulty,
                                    sub_domain=_sub_domain_for_skill(candidate_doc, rotation_skill),
                                    round_config=spec_config,
                                    user_id=str(session_user_id) if session_user_id else None,
                                    target_company_id=str(session_target_company) if session_target_company else None,
                                    target_role_id=str(session_target_role) if session_target_role else None,
                                    resume_skills=resume_skills,
                                    asked=[item.get("question", "") for item in rounds],
                                    sql_problem_index=sql_index,
                                    block_id=(expanded_spec or {}).get("block_id"),
                                    block_position=(expanded_spec or {}).get("block_position"),
                                    block_category=(expanded_spec or {}).get("category"),
                                    block_index=(expanded_spec or {}).get("block_index"),
                                    block_total=(expanded_spec or {}).get("block_total"),
                                    allow_unknown_fallback=bool(session.get("allow_unknown_topic_fallback")),
                                )
                            except ValueError as exc:
                                progression_blocked_reason = str(exc)
                                next_doc = None
                            except IntegrationError as exc:
                                from modules.bundle_selector import (
                                    ReviewedInventoryUnavailable,
                                )

                                if isinstance(exc.__cause__, ReviewedInventoryUnavailable):
                                    progression_blocked_reason = str(exc)
                                    next_doc = None
                                else:
                                    progression_blocked_reason = str(exc)
                                    next_doc = None
                            if next_doc is None:
                                pass
                            else:
                                # Prepared, not started: the clock runs from
                                # POST /session/{id}/rounds/{n}/activate.
                                next_payload = prepare_round(next_doc.model_dump())
                                rounds.append(next_payload)
                                next_skill = rotation_skill
                                next_round_type = planned_type
                                response_next_difficulty = next_doc.difficulty
                                next_round_number = next_round
                                next_round_status = next_payload["status"]
                                next_block_id = next_doc.block_id
                                next_block_position = next_doc.block_position
                                next_block_category = next_doc.block_category
                                # No write here: the appended round joins the single
                                # commit below with the scored round and Elo.
                        elif is_inline_bundle_follow_up_spec(expanded_spec):
                            assert expanded_spec is not None
                            next_skill = str(expanded_spec.get("skill") or rotation_skill)
                            next_round_difficulty = str(
                                expanded_spec.get("difficulty") or rotation_difficulty
                            )
                            response_next_difficulty = next_round_difficulty
                            next_round_type = "technical_short_answer"
                            next_target = None
                            next_round_doc = build_bundle_follow_up_round_doc(
                                expanded_spec=expanded_spec,
                                round_number=next_round,
                                candidate_elos=candidate_elos,
                                initial_elo=settings.initial_elo,
                                ready_status=ROUND_STATUS_READY,
                            )
                            rounds.append(next_round_doc)
                            next_round_number = next_round
                            next_round_status = ROUND_STATUS_READY
                            next_block_id = expanded_spec.get("block_id")
                            next_block_position = expanded_spec.get("block_position")
                            next_block_category = (
                                expanded_spec.get("category")
                                or expanded_spec.get("block_category")
                            )
                        else:
                            asked = [item.get("question", "") for item in rounds]
                            next_spec_stage = (expanded_spec or {}).get("stage")
                            non_core = select_non_core_stage_question(
                                stage=next_spec_stage,
                                skill=rotation_skill,
                                asked=asked,
                            )
                            if non_core is not None:
                                question_payload, next_skill, next_round_difficulty = non_core
                                next_skill_elo = float(
                                    candidate_elos.get(next_skill, settings.initial_elo)
                                )
                                response_next_difficulty = next_round_difficulty
                                next_target = None
                                next_round_type = "technical_short_answer"
                            else:
                                # Block sessions constrain adaptation to the block's own
                                # skills; legacy sessions adapt across all session skills.
                                adaptive_skills = (
                                    session_skills if expanded_spec
                                    else (session.get("skills") or [session.get("skill")])
                                )
                                target = adaptive_question_selector.choose_adaptive_target(
                                    user_id=str(session_user_id) if session_user_id else None,
                                    fallback_skill=rotation_skill,
                                    fallback_difficulty=rotation_difficulty,
                                    session_skills=adaptive_skills,
                                    target_role_id=str(session_target_role) if session_target_role else None,
                                    candidate_elo_by_skill=candidate_elos,
                                )
                                next_skill = target.skill
                                if expanded_spec:
                                    # Stay inside the requested block topics.
                                    spec_skill_set = set(session_skills)
                                    if next_skill not in spec_skill_set:
                                        next_skill = rotation_skill
                                next_skill_elo = float(
                                    target.current_elo
                                    if target.current_elo is not None
                                    else candidate_elos.get(next_skill, elo_after)
                                )
                                next_round_difficulty = (
                                    str(expanded_spec.get("difficulty"))
                                    if expanded_spec and expanded_spec.get("difficulty")
                                    else target.difficulty
                                )
                                response_next_difficulty = next_round_difficulty
                                # The block's explicit topic (if any) stays pinned
                                # for every round of the block, like the opening
                                # round at start.
                                sub = ((expanded_spec or {}).get("topic")
                                       or _sub_domain_for_skill(candidate_doc, next_skill))
                                weak_context = list(target.target_concepts or [])
                                if target.source != "rotation" and target.skill:
                                    weak_context.insert(0, target.skill)

                                try:
                                    question_payload = _get_next_question(
                                        skill=next_skill,
                                        sub_domain=sub,
                                        difficulty=next_round_difficulty,
                                        asked=asked,
                                        user_id=str(session_user_id) if session_user_id else None,
                                        target_company_id=str(session_target_company) if session_target_company else None,
                                        target_role_id=str(session_target_role) if session_target_role else None,
                                        target_concepts=target.target_concepts,
                                        resume_skills=resume_skills,
                                        weak_skills=weak_context,
                                    )
                                except IntegrationError as exc:
                                    progression_blocked_reason = str(exc)
                                    question_payload = None
                                if question_payload is not None:
                                    try:
                                        _verify_served_topic(
                                            requested=(expanded_spec or {}).get("topic"),
                                            served=question_payload.get("sub_domain"),
                                            skill=next_skill,
                                            difficulty=next_round_difficulty,
                                        )
                                    except ValueError as exc:
                                        progression_blocked_reason = str(exc)
                                        question_payload = None
                                if question_payload is not None:
                                    question_payload["adaptive_target"] = target.to_dict()
                                    next_target = target.to_dict()
                                next_round_type = "technical_short_answer"
                            if question_payload is None:
                                pass
                            else:
                                next_config_value: dict[str, Any] = {}
                                if expanded_spec and expanded_spec.get("duration_minutes"):
                                    minutes = int(expanded_spec["duration_minutes"])
                                    next_config_value = {
                                        "duration_minutes": minutes,
                                        DURATION_SECONDS_KEY: minutes * 60,
                                    }
                                if next_spec_stage:
                                    next_config_value["stage"] = next_spec_stage
                                next_round_doc = {
                                    "round": next_round,
                                    "skill": next_skill,
                                    "round_type": "technical_short_answer",
                                    "artifact_json": {},
                                    "config_json": next_config_value,
                                    "question": question_payload["question"],
                                    "answer_text": None,
                                    "nlp_score": None,
                                    "svm_label": None,
                                    "kg_score": None,
                                    "ner_entities": [],
                                    "final_score": None,
                                    "difficulty": next_round_difficulty,
                                    "difficulty_change": None,
                                    "feedback": {"content": [], "strengths": [], "next_step": ""},
                                    "elo_before": next_skill_elo,
                                    "elo_after": None,
                                    "question_context": question_payload,
                                    # Prepared, not started (see backend/round_lifecycle.py).
                                    "started_at": None,
                                    "expires_at": None,
                                    "status": ROUND_STATUS_READY,
                                    "block_id": (expanded_spec or {}).get("block_id"),
                                    "block_position": (expanded_spec or {}).get("block_position"),
                                    "block_category": (expanded_spec or {}).get("category")
                                    or (expanded_spec or {}).get("block_category"),
                                    "block_index": (expanded_spec or {}).get("block_index"),
                                    "block_total": (expanded_spec or {}).get("block_total"),
                                }
                                if next_spec_stage:
                                    next_round_doc["stage"] = next_spec_stage
                                if expanded_spec and expanded_spec.get("is_follow_up"):
                                    next_round_doc["is_follow_up"] = True
                                    next_round_doc["follow_up_parent_round"] = (
                                        expanded_spec.get("follow_up_parent_round")
                                    )
                                    next_round_doc["follow_up_identity"] = (
                                        expanded_spec.get("follow_up_identity")
                                    )
                                    next_round_doc["follow_up_scoring"] = (
                                        expanded_spec.get("follow_up_scoring")
                                    )
                                    next_round_doc["purpose"] = "follow_up"
                                    cfg = dict(next_round_doc.get("config_json") or {})
                                    cfg["is_follow_up"] = True
                                    cfg["follow_up_parent_round"] = expanded_spec.get(
                                        "follow_up_parent_round"
                                    )
                                    cfg["follow_up_identity"] = expanded_spec.get(
                                        "follow_up_identity"
                                    )
                                    cfg["follow_up_scoring"] = expanded_spec.get(
                                        "follow_up_scoring"
                                    )
                                    next_round_doc["config_json"] = cfg
                                    if expanded_spec.get("follow_up_scoring") == "unreviewed":
                                        prompt = (
                                            expanded_spec.get("clarification_prompt")
                                            or "Clarify the key idea from the previous question."
                                        )
                                        next_round_doc["question"] = prompt
                                        next_round_doc["question_context"] = {
                                            **dict(question_payload or {}),
                                            "source": "follow_up_clarification",
                                            "followups": [],
                                        }
                                rounds.append(next_round_doc)
                                next_round_number = next_round
                                next_round_status = ROUND_STATUS_READY
                                next_block_id = (expanded_spec or {}).get("block_id")
                                next_block_position = (expanded_spec or {}).get("block_position")
                                next_block_category = (expanded_spec or {}).get("category")
                                # No write here: the appended round joins the single
                                # commit below with the scored round and Elo.

                if progression_blocked_reason and session_status == "active":
                    session_status = "content_blocked"

                # The single attempt commit: scored round (+ queued next round),
                # measured Elo, narration job, and required learning effects
                # (skill graph / mastery / Elo-delta signals) succeed or fail
                # together. A 503 here leaves the claimed-but-unscored round
                # behind, and the guard's stale-claim takeover makes the retry
                # a clean resubmit.
                # When progression is blocked, the scored answer is still committed
                # and the session becomes content_blocked (no false next round).
                session_update = {
                    "rounds": rounds,
                    "last_round": request.round,
                    "current_difficulty": response_next_difficulty,
                    "current_skill": next_skill or current_skill,
                    "status": session_status,
                }
                if progression_blocked_reason:
                    session_update["progression_blocked_reason"] = progression_blocked_reason
                if inline_followup_result and inline_followup_result.get("plan_update"):
                    session_update.update(inline_followup_result["plan_update"])
                if session_status == "completed":
                    session_update["completed_at"] = datetime.now(timezone.utc)
                    session_update["overall_readiness_score"] = (
                        round(sum(completed_scores) / len(completed_scores), 2)
                        if completed_scores
                        else None
                    )
                    session_update["overall_readiness_population"] = "assessment_eligible"
                with atomic(db):
                    db["sessions"].update_one(
                        {"session_id": request.session_id},
                        {"$set": session_update},
                        expected_revision=session.get("revision"),
                    )
                    if inline_followup_result and inline_followup_result.get("scheduled"):
                        exposure_concept = inline_followup_result.get("exposure_concept")
                        record_teaching_exposure(
                            db,
                            kind="follow_up_prompt",
                            item_type="follow_up",
                            item_id=str(inline_followup_result["follow_up_identity"]),
                            session=session,
                            user_id=session.get("user_id"),
                            round_number=int(inline_followup_result["parent_round"]),
                            block_id=active_round.get("block_id"),
                            content_fingerprint=str(inline_followup_result["follow_up_identity"]),
                            concept_topic_scope=(
                                {"concept": exposure_concept}
                                if exposure_concept
                                else None
                            ),
                            also_legacy_assistance=False,
                        )
                    if (
                        not practice_only
                        and not is_spaced_review
                        and assessment_eligible
                        and scoring_result.get("final_score") is not None
                    ):
                        db["candidates"].update_one(
                            {"candidate_id": session["candidate_id"]},
                            {"$set": {f"elo_ratings.{current_skill}": elo_after}},
                        )
                    # The narration job joins the same commit: a scored round
                    # always has exactly one job, never zero, never two.
                    scored_snapshot = next(
                        (item.get("attempt_snapshot") or {}
                         for item in rounds if item.get("round") == request.round),
                        {},
                    )
                    enqueue_narration_job(
                        db,
                        session_id=request.session_id,
                        round_number=request.round,
                        user_id=session.get("user_id"),
                        skill=current_skill,
                        final_score=(
                            None
                            if is_inline_follow_up
                            else scoring_result.get("final_score")
                        ),
                        feedback=(
                            inline_client_feedback
                            if is_inline_follow_up and inline_client_feedback is not None
                            else scoring_result["feedback"]
                        ),
                        snapshot_digest=scored_snapshot.get("digest"),
                    )
                    if (
                        not practice_only
                        and not is_spaced_review
                        and assessment_eligible
                        and scoring_result.get("final_score") is not None
                    ):
                        _update_learning_state(
                            session=session,
                            skill=current_skill,
                            final_score=float(scoring_result["final_score"]),
                            difficulty=active_round.get("difficulty", "medium"),
                            scoring_breakdown=scoring_result.get("scoring_breakdown", {}) or {},
                            elo_before=elo_before,
                            elo_after=elo_after,
                            session_id=request.session_id,
                            raise_on_error=True,
                        )
            except SessionWriteConflict:
                # Lost a cross-worker write race inside the attempt commit:
                # the ambient transaction rolled back before Elo, narration,
                # or learning effects ran, so reloading and retrying is safe
                # and cannot duplicate any of them.
                continue
            except DatabaseConnectionError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
                ) from exc
            except Exception as exc:
                if is_database_exception(exc):
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"MongoDB operation failed: {exc}",
                    ) from exc
                raise
            break
        else:
            logger.warning(
                "Submit commit for session %s round %s exhausted %d attempts "
                "under contention; returning 409.",
                request.session_id,
                request.round,
                MAX_SUBMIT_COMMIT_ATTEMPTS,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Concurrent session update; retry the submission.",
            )

        # Post-commit derived state that is not part of the assessment
        # learning unit: spaced-review schedule updates and draft cleanup.
        if is_spaced_review:
            try:
                from backend.routes.learning_hub import (
                    apply_review_outcome_for_session_round,
                )

                submitted = next(
                    (r for r in rounds if r.get("round") == request.round),
                    None,
                )
                if submitted is not None:
                    apply_review_outcome_for_session_round(
                        db,
                        session,
                        submitted,
                        assisted=bool(submitted.get("assisted")),
                    )
            except Exception:
                logger.warning(
                    "Failed to apply spaced-review schedule update.",
                    exc_info=True,
                )

        if (
            inline_followup_result is not None
            and inline_followup_result.get("decision_record")
        ):
            log_follow_up_decision(inline_followup_result["decision_record"])

        # Clear the saved draft for the submitted round: submitted attempts
        # are immutable and drafts must not survive submission.
        try:
            _clear_answer_draft(db, request.session_id, request.round)
        except Exception:
            logger.warning("Failed to clear answer draft.", exc_info=True)

        narration_status = _settle_narration(db, request.session_id, request.round)

        try:
            from modules import bundle_generator, bundle_jobs, llm_outbound_gate

            if (
                bundle_generator._LLM_OVERRIDE is not None
                or llm_outbound_gate.llm_live_fetch_enabled()
            ):
                bundle_jobs.trigger_background_bundle_worker()
        except Exception:
            logger.debug("Background bundle worker trigger skipped cleanly.", exc_info=True)

        resp_artifact = scoring_result.get("artifact_json")
        if round_type == "sql" and resp_artifact:
            resp_artifact = sanitize_sql_artifact_for_client(resp_artifact)

        response_payload: dict[str, Any] = {
            "svm_label": None if is_inline_follow_up else scoring_result.get("svm_label"),
            "nlp_score": None if is_inline_follow_up else scoring_result.get("nlp_score"),
            "kg_score": None if is_inline_follow_up else scoring_result.get("kg_score"),
            "ner_entities": [] if is_inline_follow_up else scoring_result.get("ner_entities", []),
            "final_score": None if is_inline_follow_up else scoring_result["final_score"],
            "feedback": (
                inline_client_feedback
                if is_inline_follow_up and inline_client_feedback is not None
                else scoring_result["feedback"]
            ),
            "score_explanation": {} if is_inline_follow_up else scoring_result.get("score_explanation", {}),
            "scoring_schema_version": scoring_result.get("scoring_schema_version"),
            "rubric": {} if is_inline_follow_up else scoring_result.get("rubric", {}),
            "evaluation_mode": scoring_result.get("evaluation_mode"),
            "evaluation_boundary": scoring_result.get("boundary"),
            "evidence_kind": evidence_kind,
            "scoring_mode": scoring_mode,
            "semantic_scoring_available": _bd.get(
                "semantic_scoring_available",
                scoring_result.get("semantic_scoring_available"),
            ),
            "semantic_fallback_reason": _bd.get(
                "semantic_fallback_reason",
                scoring_result.get("semantic_fallback_reason"),
            ),
            "scoring_mode_label": scoring_mode,
            "concepts": {} if is_inline_follow_up else scoring_result.get("concepts", {}),
            "guard": {} if is_inline_follow_up else scoring_result.get("guard", {}),
            "scoring_breakdown": scoring_result.get("scoring_breakdown", {}),
            "artifact_json": {} if is_inline_follow_up else resp_artifact,
            "guard_applied": None if is_inline_follow_up else scoring_result.get("guard_applied"),
            # The next prompt is revealed only by activation, so reading time
            # is never free; these keys stay for compatibility and are null.
            "next_question": None,
            "next_round_type": next_round_type,
            "next_question_context": None,
            "next_config_json": None,
            "next_expires_at": None,
            "next_round": next_round_number,
            "next_round_status": next_round_status,
            "narration_status": narration_status,
            "next_difficulty": response_next_difficulty,
            "next_skill": next_skill,
            "next_block_id": next_block_id,
            "next_block_position": next_block_position,
            "next_block_category": next_block_category,
            "adaptive_target": next_target,
            "current_skill": current_skill,
            "elo_after": elo_after,
            "difficulty_change": difficulty_change,
            "total_rounds": total_rounds,
            "session_complete": request.round >= total_rounds and not progression_blocked_reason,
            "session_status": session_status,
            "progression_blocked": bool(progression_blocked_reason),
            "progression_blocked_reason": progression_blocked_reason,
            "assisted": assisted,
            "assistance_kinds": assistance_kinds,
            "assessment_eligibility": eligibility["decision"],
            "eligibility_policy_version": eligibility["policy_version"],
            "eligibility_exclusion_reasons": eligibility["exclusion_reasons"],
            "is_follow_up": bool(is_follow_up_round(active_round)),
            "follow_up_scheduled": bool(
                inline_followup_result and inline_followup_result.get("scheduled")
            ),
        }
        if active_stage:
            response_payload["stage"] = active_stage
        if is_inline_follow_up:
            response_payload.pop("scoring_breakdown", None)
            if inline_follow_up_outcome is not None:
                response_payload["follow_up_outcome"] = dict(inline_follow_up_outcome)
        if is_staged_v1_session(session):
            response_payload = apply_deferred_answer_mask(response_payload)
        return response_payload
