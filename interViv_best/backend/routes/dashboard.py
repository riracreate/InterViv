from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, status

from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.evidence_kind import (
    is_self_reported_round,
    measured_scores,
    scoring_mode_for_round,
    scoring_mode_label_for_display,
)
from backend.routes.auth import require_user
from backend.serializers.round_serializer import sanitize_sql_artifact_for_client
from modules.gap_analysis import GapAnalyzer, GapAnalysisError
from modules.learning_signals import build_signals_payload
from modules.skill_graph import StudentSkillGraph

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


# Confidence band constants (spec: "variance / 2, capped at 10")
CONFIDENCE_BAND_CAP = 10.0


def _score_bucket(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Average"
    return "Poor"


def compute_confidence_band(layer_scores: list[float | None]) -> float | None:
    """Confidence band per spec — Phase 2 Task 6b.

        variance        = stdev([layer1_score, layer2_score, layer3_score])
        confidence_band = variance / 2  (capped at 10)

    Returns ``None`` if we don't have at least two real layer scores
    (stdev requires >=2 inputs and produces a noisy result on a single
    point — better to surface the absence than fake a band).
    """
    usable = [float(s) for s in layer_scores if s is not None]
    if len(usable) < 2:
        return None
    variance = statistics.stdev(usable)
    band = variance / 2.0
    return round(min(band, CONFIDENCE_BAND_CAP), 2)


def _sanitize_rounds(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized = []
    for round_document in rounds:
        if round_document.get("round_type") == "ml_primitives":
            from backend.serializers.round_serializer import sanitize_round_for_client
            round_document = sanitize_round_for_client(round_document)
        cleaned = dict(round_document)
        question_context = cleaned.get("question_context", {}) or {}
        cleaned["ideal_answer"] = question_context.get("ideal_answer", "")
        cleaned["ideal_keywords"] = question_context.get("ideal_keywords", "")
        cleaned["topic"] = question_context.get("topic") or question_context.get("sub_domain")
        cleaned["sub_domain"] = question_context.get("sub_domain") or cleaned.get("sub_domain")
        cleaned["question_type"] = question_context.get("question_type")
        cleaned["company"] = question_context.get("company")
        cleaned["role"] = question_context.get("role")
        cleaned["followups"] = question_context.get("followups") or []
        cleaned.pop("question_context", None)
        # Persisted SQL artifacts carry per-case grading detail (hidden-case
        # descriptions, expected row counts). Reduce to safe aggregates.
        if cleaned.get("round_type") == "sql" and cleaned.get("artifact_json"):
            cleaned["artifact_json"] = sanitize_sql_artifact_for_client(cleaned["artifact_json"])
        cleaned["performance_band"] = _score_bucket(cleaned.get("final_score"))
        mode = scoring_mode_for_round(cleaned)
        cleaned["scoring_mode"] = mode
        cleaned["scoring_mode_label"] = scoring_mode_label_for_display(mode)

        breakdown = cleaned.get("scoring_breakdown") or {}
        layer_scores = [
            breakdown.get("layer1_score"),
            breakdown.get("layer2_score"),
            breakdown.get("layer3_score"),
        ]
        cleaned["confidence_band"] = compute_confidence_band(layer_scores)
        sanitized.append(cleaned)
    return sanitized


def _unscored_rounds(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rounds without scores, each with an honest reason.

    Coding rounds without scores are execution-unavailable, never
    candidate zeros; other unscored rounds are simply not submitted.
    """
    unscored = []
    for item in rounds:
        if item.get("final_score") is not None:
            continue
        kind = item.get("round_type", "technical_short_answer")
        if kind in ("coding", "ml_primitives"):
            reason = "execution_unavailable"
        elif item.get("status") not in (None, "in_progress"):
            reason = str(item.get("status"))
        else:
            reason = "not_submitted"
        unscored.append({
            "round": item.get("round"),
            "round_type": kind,
            "block_id": item.get("block_id"),
            "block_category": item.get("block_category"),
            "reason": reason,
        })
    return unscored


def _block_results(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-block results with evidence-backed next-practice suggestions."""
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for item in rounds:
        key = str(item.get("block_id") or f"round-{item.get('round')}")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)
    results = []
    for key in order:
        group = groups[key]
        scored = [r for r in group if r.get("final_score") is not None]
        measured = [r for r in scored if not is_self_reported_round(r)]
        self_reported = [r for r in scored if is_self_reported_round(r)]
        skills = sorted({str(r.get("skill") or "General") for r in group})
        avg = (
            round(sum(float(r["final_score"]) for r in measured) / len(measured), 2)
            if measured
            else None
        )
        self_avg = (
            round(
                sum(float(r["final_score"]) for r in self_reported) / len(self_reported),
                2,
            )
            if self_reported
            else None
        )
        suggestion = None
        if measured:
            weakest = min(measured, key=lambda r: float(r["final_score"]))
            if float(weakest["final_score"]) < 61.0:
                skill = str(weakest.get("skill") or "General")
                suggestion = {
                    "text": (
                        f"Round {weakest.get('round')} scored "
                        f"{weakest['final_score']} on {skill}; retry "
                        f"{skill} misses next."
                    ),
                    "action": {"type": "retry_set", "skills": [skill]},
                }
        results.append({
            "block_id": group[0].get("block_id"),
            "block_category": group[0].get("block_category"),
            "round_types": list(dict.fromkeys(
                r.get("round_type", "technical_short_answer") for r in group
            )),
            "skills": skills,
            "rounds": len(group),
            "scored_rounds": len(scored),
            "measured_rounds": len(measured),
            "self_reported_rounds": len(self_reported),
            "average_score": avg,
            "average_score_population": "measured",
            "self_reported_average": self_avg,
            "assisted_rounds": sum(1 for r in measured if r.get("assisted")),
            "scoring_modes": sorted({
                scoring_mode_for_round(r) for r in scored
            }),
            "suggestion": suggestion,
        })
    return results


def _compute_topic_scores(session: dict[str, Any]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for round_document in session.get("rounds", []):
        score = round_document.get("final_score")
        if score is None:
            continue
        if is_self_reported_round(round_document):
            continue
        context = round_document.get("question_context", {}) or {}
        label = (
            context.get("topic")
            or context.get("sub_topic")
            or context.get("sub_domain")
            or session.get("skill")
            or "Overall"
        )
        buckets.setdefault(str(label), []).append(float(score))

    return {
        label: round(sum(values) / len(values), 2) for label, values in buckets.items()
    }


def _utc_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        return None


@router.get("/progress")
def get_account_progress(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    """Owned summaries only; never serialize questions, answers or artifacts.

    Resume follows the existing engine: technical rounds have no persisted
    deadline; timed MCQ/SQL rounds must still be inside their stored window.
    This read does not activate rounds or extend deadlines.
    """
    user = require_user(authorization)
    user_id = str(user["id"])
    try:
        owned = list(get_database()["sessions"].find({"user_id": user_id}))
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(status_code=503, detail="Practice history is temporarily unavailable.") from exc
        raise
    now = datetime.now(timezone.utc)
    owned.sort(key=lambda row: (_utc_date(row.get("created_at")) or datetime.min.replace(tzinfo=timezone.utc), str(row.get("session_id", ""))), reverse=True)
    history = []
    resumable = None
    for session in owned:
        rounds = session.get("rounds") or []
        scored = [r for r in rounds if r.get("final_score") is not None]
        measured = measured_scores(rounds)
        summary = {
            "session_id": session["session_id"],
            "created_at": _utc_date(session.get("created_at")),
            "status": session.get("status"),
            "skills": session.get("skills") or [session.get("skill") or "General"],
            "round_types": list(dict.fromkeys(r.get("round_type", "technical_short_answer") for r in rounds)),
            "completed_rounds": len(scored),
            "total_rounds": session.get("total_rounds") or len(rounds),
            "average_score": (
                round(statistics.mean(measured), 2) if measured else None
            ),
            "average_score_population": "measured",
            "self_reported_rounds": sum(
                1 for r in scored if is_self_reported_round(r)
            ),
            "scoring_modes": sorted({
                scoring_mode_for_round(r) for r in scored
            }),
            # What the average covers and what it excludes: unscored
            # coding rounds are execution-unavailable, not zeros.
            "unscored_rounds": _unscored_rounds(rounds),
        }
        # Coding-only sessions have no scores while execution is
        # unavailable. Include them so they are not silently omitted
        # (which would inflate the appearance of overall readiness).
        has_coding = any(r.get("round_type") == "coding" for r in rounds)
        has_ml = any(r.get("round_type") == "ml_primitives" for r in rounds)
        if scored or has_coding or has_ml:
            history.append(summary)
        active = rounds[-1] if rounds else None
        if resumable is not None or session.get("status") != "active" or not active:
            continue
        if active.get("status") != "in_progress" or active.get("final_score") is not None:
            continue
        kind = active.get("round_type", "technical_short_answer")
        if kind not in {"technical_short_answer", "mcq", "sql", "coding", "ml_primitives"}:
            continue
        deadline = _utc_date(active.get("expires_at"))
        if active.get("expires_at") and deadline is None:
            continue
        if kind in {"mcq", "sql", "coding", "ml_primitives"} and deadline is None:
            continue
        if deadline is not None and deadline <= now:
            continue
        resumable = {**summary, "expires_at": deadline}
    graph = StudentSkillGraph(user_id).to_api_payload()
    target = None
    if user.get("target_role_id"):
        try:
            target = GapAnalyzer().compute_gap(user_id, user["target_role_id"]).to_dict()
        except GapAnalysisError:
            pass  # A removed/unknown target is unavailable, not a measured zero.
    from backend.routes.learning_hub import assistance_breakdown_for_user

    return {
        "user": {key: user.get(key) for key in ("id", "name", "target_company_id", "target_role_id")},
        "server_time": now,
        "target": target,
        "readiness": target["overall_readiness_percentage"] if target and target["tested_skill_count"] > 0 else None,
        # Readiness math is unchanged; the split sits alongside so
        # assisted evidence is never silently mixed into the signal.
        "readiness_assistance": assistance_breakdown_for_user(user_id),
        "skills": graph["skills"],
        "scored_session_count": sum(
            1 for row in history if row.get("average_score") is not None
        ),
        "coding_coverage": {
            "scored_coding_rounds": sum(
                1
                for session in owned
                for r in (session.get("rounds") or [])
                if r.get("round_type") == "coding" and r.get("final_score") is not None
            ),
            "unscored_coding_rounds": sum(
                1
                for session in owned
                for r in (session.get("rounds") or [])
                if r.get("round_type") == "coding" and r.get("final_score") is None
            ),
            "reason": "execution_unavailable",
            "note": (
                "Coding attempts produce no scored evidence while "
                "execution is unavailable. They are not treated as "
                "zeros and are not omitted from coverage."
            ),
        },
        # simplification: latest 100 summaries suit local practice; paginate when histories grow.
        "history": history[:100],
        "resumable_session": resumable,
        "learning_signals": build_signals_payload(user_id),
    }


@router.get("/{session_id}")
def get_dashboard(
    session_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        session = get_database()["sessions"].find_one(
            {"session_id": session_id}, {"_id": 0}
        )
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
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )
    # Same gate as GET /session/{session_id}: owned sessions and Phase 2
    # (MCQ/SQL) rounds always require a JWT for the owning user. Anonymous
    # legacy sessions keep the guest-readable path; anonymous Phase 2 data
    # is never served (a bare session_id must not become a capability URL
    # for assessment content).
    has_phase2_round = any(
        r.get("round_type") in ("mcq", "sql", "coding", "system_design", "ml_primitives")
        for r in session.get("rounds", [])
    )
    if has_phase2_round or session.get("user_id"):
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication is required for this session.",
            )
        user = require_user(authorization)
        if session.get("user_id"):
            if str(session["user_id"]) != str(user["id"]):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You cannot access another user's session.",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Anonymous sessions are not permitted for this round type.",
            )

    rounds = _sanitize_rounds(session.get("rounds", []))
    completed_rounds = [item for item in rounds if item.get("final_score") is not None]
    measured_rounds = [item for item in completed_rounds if not is_self_reported_round(item)]
    self_reported_rounds = [
        item for item in completed_rounds if is_self_reported_round(item)
    ]

    if measured_rounds:
        # Phase 2 (MCQ/SQL) rounds persist None for NLP/KG layer scores;
        # coerce missing layer scores to 0.0 so the dashboard never crashes.
        averages = {
            "final_score": round(
                sum(float(item.get("final_score") or 0) for item in measured_rounds)
                / len(measured_rounds),
                2,
            ),
            "nlp_score": round(
                sum(float(item.get("nlp_score") or 0) for item in measured_rounds)
                / len(measured_rounds),
                2,
            ),
            "kg_score": round(
                sum(float(item.get("kg_score") or 0) for item in measured_rounds)
                / len(measured_rounds),
                2,
            ),
            "population": "measured",
        }
    elif completed_rounds:
        # Session only has self-reported scores: absence of measured average,
        # not a fabricated zero.
        averages = {
            "final_score": None,
            "nlp_score": None,
            "kg_score": None,
            "population": "measured",
        }
    else:
        averages = {
            "final_score": None,
            "nlp_score": None,
            "kg_score": None,
            "population": "measured",
        }

    breakdown = {"Good": 0, "Average": 0, "Poor": 0}
    for item in measured_rounds:
        band = item.get("performance_band")
        if band in breakdown:
            breakdown[band] += 1

    last_feedback = completed_rounds[-1].get("feedback", {}) if completed_rounds else {}
    # System-design (and some older rows) store feedback as a plain string.
    if isinstance(last_feedback, str):
        next_step = last_feedback
    elif isinstance(last_feedback, dict):
        next_step = last_feedback.get("next_step", "") or ""
    else:
        next_step = ""

    session["rounds"] = rounds
    session["averages"] = averages
    session["self_reported_average"] = (
        round(
            sum(float(item.get("final_score") or 0) for item in self_reported_rounds)
            / len(self_reported_rounds),
            2,
        )
        if self_reported_rounds
        else None
    )
    session["breakdown"] = breakdown
    session["elo_progression"] = [
        item.get("elo_after") for item in completed_rounds if item.get("elo_after") is not None
    ]
    session["difficulty_progression"] = [item.get("difficulty") for item in completed_rounds]
    session["topic_scores"] = _compute_topic_scores(session)
    session["next_step"] = next_step
    unscored = _unscored_rounds(rounds)
    session["coverage"] = {
        "scored_rounds": len(completed_rounds),
        "unscored_rounds": unscored,
        "note": (
            "Averages cover scored rounds only. "
            + (
                f"{len(unscored)} unscored round(s) excluded "
                f"({', '.join(sorted({u['reason'] for u in unscored}))})."
                if unscored
                else "All rounds scored."
            )
        ),
    }
    session["block_results"] = _block_results(rounds)
    return session
