"""Narration-job infrastructure: durable outbox + deterministic worker.

Phase 3A: every attempt commit enqueues one narration job for the scored
round (inside the same atomic commit, so jobs are never orphaned and never
missing). A worker later claims each job under a lease and renders a
narration artifact.

Phase 3B: when ``llm_live_fetch_enabled()`` is on, the worker may call a
narration provider **outside** any scoring transaction, then validate the
payload against the attempt snapshot. Invalid/unavailable generation keeps
the deterministic rules artifact. With the live gate off (Phase 3B default),
jobs finish as ``skipped`` with rules feedback — never labeled AI-written.

Job lifecycle: queued -> processing -> done, or -> failed (retried up to
MAX_ATTEMPTS by later worker passes, then left for inspection), or
-> skipped when generation is disabled / provider unavailable. Leases
expire so a crashed worker can be reclaimed; a stale worker whose lease
was taken cannot overwrite a newer claim's result (claim_token fence).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

NARRATION_JOB_VERSION = 1
MAX_ATTEMPTS = 3
LEASE_SECONDS = 60

STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"


def narration_job_id(session_id: str, round_number: int) -> str:
    """Deterministic id: one job per scored round, idempotent by key."""
    return f"{session_id}:{int(round_number)}:narration"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_narration_job(
    db: Any,
    *,
    session_id: str,
    round_number: int,
    user_id: str | None,
    skill: str | None,
    final_score: float | None,
    feedback: Any,
    snapshot_digest: str | None,
) -> dict[str, Any]:
    """Enqueue the narration job for a scored round, idempotently.

    Returns the existing job when the deterministic id is already present.
    Called inside the attempt commit; the per-session submit lock means no
    two commits for the same round run concurrently in this process.
    """
    from backend.integrations import normalize_feedback

    job_id = narration_job_id(session_id, round_number)
    existing = db["narration_jobs"].find_one({"id": job_id})
    if existing is not None:
        return existing
    now = _now()
    # Type-specific scorers may store feedback as a plain string; the job
    # keeps the canonical content/strengths/weakness/next_step shape.
    stored_feedback = normalize_feedback(feedback or {})
    db["narration_jobs"].insert_one({
        "id": job_id,
        "user_id": user_id,
        "session_id": session_id,
        "round": int(round_number),
        "status": STATUS_QUEUED,
        "attempts": 0,
        "feedback": stored_feedback,
        "snapshot_digest": snapshot_digest,
        "skill": skill,
        "final_score": final_score,
        "artifact": None,
        "last_error": None,
        "claim_token": None,
        "lease_until": None,
        "created_at": now,
        "updated_at": now,
    })
    return db["narration_jobs"].find_one({"id": job_id})


def render_narration_artifact(
    *,
    round_number: int,
    skill: str | None,
    final_score: float | None,
    feedback: dict[str, Any] | None,
) -> dict[str, Any]:
    """Deterministic narration script from stored feedback. Pure function.

    No models, no network, no clock: identical inputs always produce the
    identical artifact. This rules render stands in for live narration
    until a later phase wires generation behind the outbound gate.
    """
    data = dict(feedback or {})

    def _lines(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    content = _lines(data.get("content"))
    strengths = _lines(data.get("strengths"))
    weakness = _lines(data.get("weakness") or data.get("weaknesses"))
    next_step = str(data.get("next_step") or data.get("recommendation") or "").strip()

    head = f"Round {int(round_number)}"
    if skill:
        head += f" ({skill})"
    if final_score is not None:
        head += f": scored {final_score:g} out of 100"
    head += "."
    parts = [head, *content]
    if strengths:
        parts.append("Strengths: " + "; ".join(strengths) + ".")
    if weakness:
        parts.append("To improve: " + "; ".join(weakness) + ".")
    if next_step:
        parts.append("Next step: " + next_step)
    return {
        "version": NARRATION_JOB_VERSION,
        "source": "rules_feedback",
        "script": " ".join(parts),
        "sections": {
            "content": content,
            "strengths": strengths,
            "weakness": weakness,
            "next_step": next_step,
        },
    }


def _load_round_snapshot(db: Any, job: dict[str, Any]) -> dict[str, Any]:
    """Load the scored round's snapshot; raise if session/round is missing."""
    session = db["sessions"].find_one({"session_id": job["session_id"]})
    if not session:
        raise ValueError(f"Session {job['session_id']} not found.")
    active = next(
        (item for item in session.get("rounds", [])
         if item.get("round") == job["round"]),
        None,
    )
    if active is None:
        raise ValueError(f"Round {job['round']} not found in session.")
    snapshot = active.get("attempt_snapshot") or {}
    expected = job.get("snapshot_digest")
    if expected and snapshot and snapshot.get("digest") != expected:
        raise ValueError("Snapshot verification failed: round changed after enqueue.")
    return snapshot if isinstance(snapshot, dict) else {}


def _lease_expired(job: dict[str, Any], now: datetime) -> bool:
    lease = job.get("lease_until")
    if lease is None:
        return True
    if hasattr(lease, "tzinfo") and lease.tzinfo is None:
        lease = lease.replace(tzinfo=timezone.utc)
    return lease <= now


def process_narration_job(db: Any, job_id: str) -> dict[str, Any]:
    """Claim one job under a lease and render it. Returns the stored job.

    Done / skipped / exhausted failures return unchanged (re-entrant).
    A worker that lost its lease cannot overwrite a newer claim's result.
    Always builds the deterministic rules artifact first. Provider calls
    (when the live gate is on) run outside scoring transactions — this
    worker path only — and validated payloads replace the rules script
    while retaining ``rules_artifact`` / job ``feedback``. With live
    generation disabled, the job finishes as ``skipped`` with rules
    feedback — never labeled AI-written.
    Raises ``KeyError`` for an unknown id.
    """
    from modules.llm_outbound_gate import llm_consumer_enabled
    from modules.narration_provider import get_narration_provider
    from modules.narration_validator import validate_narration_artifact

    job = db["narration_jobs"].find_one({"id": job_id})
    if job is None:
        raise KeyError(f"Unknown narration job '{job_id}'.")
    if job.get("status") in (STATUS_DONE, STATUS_SKIPPED):
        return job
    if job.get("status") == STATUS_FAILED and int(job.get("attempts") or 0) >= MAX_ATTEMPTS:
        return job

    now = _now()
    if job.get("status") == STATUS_PROCESSING and not _lease_expired(job, now):
        return job

    claim_token = str(uuid4())
    lease_until = now + timedelta(seconds=LEASE_SECONDS)
    db["narration_jobs"].update_one(
        {"id": job_id},
        {"$set": {
            "status": STATUS_PROCESSING,
            "attempts": int(job.get("attempts") or 0) + 1,
            "claim_token": claim_token,
            "lease_until": lease_until,
            "updated_at": now,
        }},
    )
    try:
        snapshot = _load_round_snapshot(db, job)
        rules_artifact = render_narration_artifact(
            round_number=job["round"],
            skill=job.get("skill"),
            final_score=job.get("final_score"),
            feedback=job.get("feedback"),
        )
    except Exception as exc:
        logger.warning("Narration job %s failed: %s", job_id, exc)
        current = db["narration_jobs"].find_one({"id": job_id}) or {}
        if current.get("claim_token") != claim_token:
            return current
        db["narration_jobs"].update_one(
            {"id": job_id},
            {"$set": {
                "status": STATUS_FAILED,
                "last_error": str(exc),
                "claim_token": claim_token,
                "lease_until": None,
                "updated_at": _now(),
            }},
        )
        return db["narration_jobs"].find_one({"id": job_id})

    current = db["narration_jobs"].find_one({"id": job_id}) or {}
    if current.get("claim_token") != claim_token:
        # Stale worker: a newer claim owns the job; do not overwrite.
        return current

    artifact = dict(rules_artifact)
    final_status = STATUS_SKIPPED
    last_error: str | None = (
        "Live narration generation disabled; deterministic rules feedback saved."
    )
    metadata = {
        "snapshot_digest": job.get("snapshot_digest") or snapshot.get("digest"),
        "source": "rules_feedback",
        "model": None,
        "prompt_version": None,
        "schema_version": NARRATION_JOB_VERSION,
        "validation": "generation_disabled",
    }

    if llm_consumer_enabled("narration"):
        # Provider boundary: outside scoring transactions (worker only).
        last_error = None
        try:
            proposed = get_narration_provider().generate_narration(
                snapshot=snapshot,
                rules_feedback=job.get("feedback"),
                job=job,
            )
        except Exception as exc:
            logger.warning("Narration provider failed for %s: %s", job_id, exc)
            proposed = None
            last_error = str(exc)
            final_status = STATUS_FAILED
            metadata["validation"] = "provider_error"
        else:
            if proposed is None:
                final_status = STATUS_SKIPPED
                last_error = "Narration provider returned no payload; rules feedback saved."
                metadata["validation"] = "provider_unavailable"
            else:
                ok, result = validate_narration_artifact(proposed, snapshot)
                if ok and isinstance(result, dict):
                    model_name = (
                        (result.get("metadata") or {}).get("model")
                        if isinstance(result.get("metadata"), dict)
                        else None
                    ) or result.get("source") or "provider"
                    artifact = dict(result)
                    artifact["source"] = (
                        "provider" if model_name in (None, "", "provider") else str(model_name)
                    )
                    artifact["rules_artifact"] = rules_artifact
                    metadata.update({
                        "source": artifact["source"],
                        "model": model_name if model_name != "provider" else None,
                        "prompt_version": (
                            (result.get("metadata") or {}).get("prompt_version")
                            if isinstance(result.get("metadata"), dict)
                            else None
                        ),
                        "schema_version": result.get("version") or NARRATION_JOB_VERSION,
                        "validation": "passed",
                    })
                    final_status = STATUS_DONE
                    last_error = None
                else:
                    final_status = STATUS_SKIPPED
                    last_error = f"Narration validation failed: {result}"
                    metadata["validation"] = "failed"
                    metadata["validation_error"] = str(result)

    artifact["metadata"] = metadata
    if "rules_artifact" not in artifact:
        # Rules path is the sole artifact; keep source explicit.
        artifact["source"] = "rules_feedback"

    db["narration_jobs"].update_one(
        {"id": job_id},
        {"$set": {
            "status": final_status,
            "artifact": artifact,
            "last_error": last_error,
            "claim_token": claim_token,
            "lease_until": None,
            "updated_at": _now(),
        }},
    )
    return db["narration_jobs"].find_one({"id": job_id})


def run_narration_worker_once(db: Any, *, limit: int = 25) -> dict[str, int]:
    """Process up to ``limit`` due jobs. Returns outcome counts.

    Due jobs are queued ones, failures with attempts remaining, and
    processing jobs whose lease has expired (reclaim), oldest first.
    """
    now = _now()
    queued = list(db["narration_jobs"].find({"status": STATUS_QUEUED}) or [])
    failed = [
        job for job in (db["narration_jobs"].find({"status": STATUS_FAILED}) or [])
        if int(job.get("attempts") or 0) < MAX_ATTEMPTS
    ]
    reclaimable = [
        job for job in (db["narration_jobs"].find({"status": STATUS_PROCESSING}) or [])
        if _lease_expired(job, now)
    ]
    due = sorted(
        queued + failed + reclaimable,
        key=lambda job: str(job.get("created_at") or ""),
    )[: max(0, int(limit))]
    counts = {"processed": 0, "done": 0, "failed": 0, "skipped": 0}
    for job in due:
        try:
            finished = process_narration_job(db, job["id"])
        except KeyError:
            continue
        counts["processed"] += 1
        status = finished.get("status")
        if status == STATUS_DONE:
            counts["done"] += 1
        elif status == STATUS_SKIPPED:
            counts["skipped"] += 1
        elif status == STATUS_FAILED:
            counts["failed"] += 1
    return counts


if __name__ == "__main__":  # `python -m modules.narration_jobs --once`
    import argparse

    parser = argparse.ArgumentParser(description="Run the narration worker once.")
    parser.add_argument("--once", action="store_true", required=True)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    from backend.db import get_database

    print(run_narration_worker_once(get_database(), limit=args.limit))
