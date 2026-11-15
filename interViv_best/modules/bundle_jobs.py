"""Durable background outbox for WS2 question bundle generation (Answer 3).

Modeled directly on ``modules/narration_jobs.py``:
- SQLAlchemy backend (``BundleGenerationJobRow`` via ``session_scope()``) when
  ``DATABASE_URL`` is configured.
- Thread-safe in-memory backend when ``DATABASE_URL`` is absent (default
  local/test posture).
- Lease/claim_token fencing (``LEASE_SECONDS = 60``) so crashed workers recover
  and duplicate enqueues for the same ``(skill, topic, difficulty)`` cell are
  coalesced idempotently.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from modules import bundle_generator, bundle_store, llm_outbound_gate, role_skills
from modules.llm_errors import LLMCreditExhaustedError
from modules.question_bundles import safe_slug

log = logging.getLogger("interviv.bundle_jobs")

LEASE_SECONDS = 60
MAX_ATTEMPTS = 3

_MEMORY_LOCK = threading.RLock()
_MEMORY_JOBS: dict[str, dict[str, Any]] = {}

_BG_LOCK = threading.Lock()
_BG_THREAD: threading.Thread | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _use_sql() -> bool:
    from backend.config import get_settings

    return bool(get_settings().database_url)


def reset_memory_bundle_jobs() -> None:
    """Clear in-memory bundle generation jobs (unit-test helper)."""
    with _MEMORY_LOCK:
        _MEMORY_JOBS.clear()


def bundle_job_id(skill: str, topic: str | None, difficulty: str) -> str:
    """Build deterministic idempotency key for a (skill, topic, difficulty) job."""
    canon_skill, _ = role_skills.resolve_skill_identity(skill, register=False)
    clean_topic = " ".join(str(topic or "").strip().split()) or canon_skill
    diff = str(difficulty or "medium").strip().lower()
    s_slug = safe_slug(canon_skill, 40)
    t_slug = safe_slug(clean_topic, 64)
    d_slug = safe_slug(diff, 16)
    return f"bjob:{s_slug}:{t_slug}:{d_slug}"[:160]


def _serialize_mem_job(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for k in ("lease_until", "created_at", "updated_at"):
        val = out.get(k)
        if isinstance(val, datetime):
            out[k] = val.isoformat()
    return out


def _serialize_sql_job(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "role": row.role,
        "skill": row.skill,
        "topic": row.topic,
        "difficulty": row.difficulty,
        "status": row.status,
        "attempts": int(row.attempts or 0),
        "bundle_id": row.bundle_id,
        "last_error": row.last_error,
        "claim_token": row.claim_token,
        "lease_until": row.lease_until.isoformat() if row.lease_until else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _cached_terminal_bundle(
    *,
    canonical_skill: str,
    clean_topic: str,
    norm_diff: str,
    role: str | None,
) -> dict[str, Any] | None:
    cached = bundle_store.find_cached_bundle(
        skill=canonical_skill,
        topic=clean_topic,
        difficulty=norm_diff,
        role=role,
    )
    if cached is None:
        return None
    attr = cached.get("attribution_json") or {}
    if cached.get("status") in {"reviewed", "auto_checked"} or attr.get("auto_check_ran"):
        return cached
    return None


def enqueue_bundle_job(
    *,
    skill: str,
    topic: str | None = None,
    difficulty: str = "medium",
    role: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Idempotently enqueue a background bundle generation job."""
    canonical_skill, _ = role_skills.resolve_skill_identity(skill, register=True)
    clean_topic = " ".join(str(topic or "").strip().split()) or canonical_skill
    norm_diff = bundle_generator.normalize_difficulty(difficulty)
    clean_role = " ".join(str(role or "").strip().split()) or None
    job_id = bundle_job_id(canonical_skill, clean_topic, norm_diff)
    now = _utcnow()

    cached = _cached_terminal_bundle(
        canonical_skill=canonical_skill,
        clean_topic=clean_topic,
        norm_diff=norm_diff,
        role=clean_role,
    )

    if not _use_sql():
        with _MEMORY_LOCK:
            existing = _MEMORY_JOBS.get(job_id)
            if existing is not None:
                if existing["status"] in {"queued", "processing", "done", "skipped"}:
                    return _serialize_mem_job(existing)
                if existing["status"] == "failed" and int(existing.get("attempts") or 0) >= MAX_ATTEMPTS:
                    return _serialize_mem_job(existing)
                # Re-queue failed job with remaining attempts
                existing["status"] = "done" if cached else "queued"
                if cached:
                    existing["bundle_id"] = cached["bundle_id"]
                existing["session_id"] = session_id or existing.get("session_id")
                existing["role"] = clean_role or existing.get("role")
                existing["updated_at"] = now
                return _serialize_mem_job(existing)

            rec: dict[str, Any] = {
                "id": job_id,
                "session_id": session_id,
                "role": clean_role,
                "skill": canonical_skill,
                "topic": clean_topic,
                "difficulty": norm_diff,
                "status": "done" if cached else "queued",
                "attempts": 0,
                "bundle_id": cached["bundle_id"] if cached else None,
                "last_error": None,
                "claim_token": None,
                "lease_until": None,
                "created_at": now,
                "updated_at": now,
            }
            _MEMORY_JOBS[job_id] = rec
            return _serialize_mem_job(rec)

    from backend.db.sqlalchemy_models import BundleGenerationJobRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as db:
        row = (
            db.query(BundleGenerationJobRow)
            .filter(BundleGenerationJobRow.id == job_id)
            .first()
        )
        if row is not None:
            if row.status in {"queued", "processing", "done", "skipped"}:
                return _serialize_sql_job(row)
            if row.status == "failed" and int(row.attempts or 0) >= MAX_ATTEMPTS:
                return _serialize_sql_job(row)
            row.status = "done" if cached else "queued"
            if cached:
                row.bundle_id = cached["bundle_id"]
            if session_id and not row.session_id:
                row.session_id = session_id
            if clean_role and not row.role:
                row.role = clean_role
            row.updated_at = now
            db.flush()
            return _serialize_sql_job(row)

        row = BundleGenerationJobRow(
            id=job_id,
            session_id=session_id,
            role=clean_role,
            skill=canonical_skill,
            topic=clean_topic,
            difficulty=norm_diff,
            status="done" if cached else "queued",
            attempts=0,
            bundle_id=cached["bundle_id"] if cached else None,
            last_error=None,
            claim_token=None,
            lease_until=None,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.flush()
        return _serialize_sql_job(row)


def get_bundle_job(job_id: str) -> dict[str, Any] | None:
    if not _use_sql():
        with _MEMORY_LOCK:
            row = _MEMORY_JOBS.get(job_id)
            return _serialize_mem_job(row) if row else None

    from backend.db.sqlalchemy_models import BundleGenerationJobRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as db:
        row = (
            db.query(BundleGenerationJobRow)
            .filter(BundleGenerationJobRow.id == job_id)
            .first()
        )
        return _serialize_sql_job(row) if row else None


def list_bundle_jobs(
    *, status: str | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    cap = max(1, min(int(limit or 50), 500))
    if not _use_sql():
        with _MEMORY_LOCK:
            rows = list(_MEMORY_JOBS.values())
            if status:
                rows = [r for r in rows if r.get("status") == status]
            rows.sort(key=lambda r: r.get("created_at") or _utcnow())
            return [_serialize_mem_job(r) for r in rows[:cap]]

    from backend.db.sqlalchemy_models import BundleGenerationJobRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as db:
        q = db.query(BundleGenerationJobRow)
        if status:
            q = q.filter(BundleGenerationJobRow.status == status)
        rows = q.order_by(BundleGenerationJobRow.created_at.asc()).limit(cap).all()
        return [_serialize_sql_job(r) for r in rows]


def _claim_job(job_id: str) -> tuple[dict[str, Any] | None, str | None]:
    now = _utcnow()
    claim_token = uuid4().hex
    lease_until = now + timedelta(seconds=LEASE_SECONDS)

    if not _use_sql():
        with _MEMORY_LOCK:
            rec = _MEMORY_JOBS.get(job_id)
            if rec is None:
                return None, None
            if rec["status"] in {"done", "skipped", "failed"}:
                return _serialize_mem_job(rec), None
            if int(rec.get("attempts") or 0) >= MAX_ATTEMPTS:
                rec["status"] = "failed"
                rec["claim_token"] = None
                rec["lease_until"] = None
                rec["updated_at"] = now
                return _serialize_mem_job(rec), None
            if rec["status"] == "processing":
                cur_lease = rec.get("lease_until")
                if isinstance(cur_lease, datetime) and cur_lease > now:
                    return _serialize_mem_job(rec), None
            rec["status"] = "processing"
            rec["attempts"] = int(rec.get("attempts") or 0) + 1
            rec["claim_token"] = claim_token
            rec["lease_until"] = lease_until
            rec["updated_at"] = now
            return _serialize_mem_job(rec), claim_token

    from backend.db.sqlalchemy_models import BundleGenerationJobRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as db:
        row = (
            db.query(BundleGenerationJobRow)
            .filter(BundleGenerationJobRow.id == job_id)
            .first()
        )
        if row is None:
            return None, None
        if row.status in {"done", "skipped", "failed"}:
            return _serialize_sql_job(row), None
        if int(row.attempts or 0) >= MAX_ATTEMPTS:
            row.status = "failed"
            row.claim_token = None
            row.lease_until = None
            row.updated_at = now
            db.flush()
            return _serialize_sql_job(row), None
        if row.status == "processing" and row.lease_until and row.lease_until > now:
            return _serialize_sql_job(row), None
        row.status = "processing"
        row.attempts = int(row.attempts or 0) + 1
        row.claim_token = claim_token
        row.lease_until = lease_until
        row.updated_at = now
        db.flush()
        return _serialize_sql_job(row), claim_token


def _finish_job(
    job_id: str,
    *,
    claim_token: str,
    status: str,
    bundle_id: str | None = None,
    last_error: str | None = None,
    force_attempts: int | None = None,
) -> dict[str, Any] | None:
    now = _utcnow()
    if not _use_sql():
        with _MEMORY_LOCK:
            rec = _MEMORY_JOBS.get(job_id)
            if rec is None or rec.get("claim_token") != claim_token:
                return _serialize_mem_job(rec) if rec else None
            rec["status"] = status
            if bundle_id is not None:
                rec["bundle_id"] = bundle_id
            rec["last_error"] = last_error
            if force_attempts is not None:
                rec["attempts"] = force_attempts
            rec["claim_token"] = None
            rec["lease_until"] = None
            rec["updated_at"] = now
            return _serialize_mem_job(rec)

    from backend.db.sqlalchemy_models import BundleGenerationJobRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as db:
        row = (
            db.query(BundleGenerationJobRow)
            .filter(
                BundleGenerationJobRow.id == job_id,
                BundleGenerationJobRow.claim_token == claim_token,
            )
            .first()
        )
        if row is None:
            cur = (
                db.query(BundleGenerationJobRow)
                .filter(BundleGenerationJobRow.id == job_id)
                .first()
            )
            return _serialize_sql_job(cur) if cur else None
        row.status = status
        if bundle_id is not None:
            row.bundle_id = bundle_id
        row.last_error = last_error
        if force_attempts is not None:
            row.attempts = force_attempts
        row.claim_token = None
        row.lease_until = None
        row.updated_at = now
        db.flush()
        return _serialize_sql_job(row)


def process_bundle_job(
    job_id: str, *, allow_live: bool | None = None
) -> dict[str, Any]:
    """Claim and run one bundle generation job under lease fencing."""
    claimed_job, claim_token = _claim_job(job_id)
    if not claimed_job:
        return {"claimed": False, "status": "not_found", "job": None}
    if not claim_token:
        return {
            "claimed": False,
            "status": claimed_job.get("status"),
            "job": claimed_job,
        }

    try:
        res = bundle_generator.generate_and_check_bundle(
            skill=str(claimed_job["skill"]),
            topic=str(claimed_job["topic"]),
            difficulty=str(claimed_job["difficulty"]),
            role=claimed_job.get("role"),
            allow_live=allow_live,
        )
    except LLMCreditExhaustedError as exc:
        attempts = max(0, int(claimed_job.get("attempts") or 1) - 1)
        final_job = _finish_job(
            job_id,
            claim_token=claim_token,
            status="queued",
            last_error=str(exc)[:500],
            force_attempts=attempts,
        )
        return {
            "claimed": True,
            "status": "queued",
            "credit_exhausted": True,
            "job": final_job,
            "error": str(exc),
        }
    except Exception as exc:
        attempts = int(claimed_job.get("attempts") or 1)
        next_status = "failed" if attempts >= MAX_ATTEMPTS else "queued"
        final_job = _finish_job(
            job_id,
            claim_token=claim_token,
            status=next_status,
            last_error=str(exc)[:500],
        )
        return {"claimed": True, "status": next_status, "job": final_job, "error": str(exc)}

    if res.get("status") in {"reviewed", "auto_checked"}:
        final_job = _finish_job(
            job_id,
            claim_token=claim_token,
            status="done",
            bundle_id=res.get("bundle_id"),
            last_error=None,
        )
        return {"claimed": True, "status": "done", "job": final_job, "result": res}

    final_job = _finish_job(
        job_id,
        claim_token=claim_token,
        status="failed",
        bundle_id=res.get("bundle_id"),
        last_error="Step E blind check rejected bundle after audit/retry.",
        force_attempts=MAX_ATTEMPTS,
    )
    return {"claimed": True, "status": "failed", "job": final_job, "result": res}


def _claimable_job_ids(limit: int) -> list[str]:
    now = _utcnow()
    cap = max(1, min(int(limit or 10), 100))
    if not _use_sql():
        with _MEMORY_LOCK:
            candidates = []
            for rec in _MEMORY_JOBS.values():
                if rec["status"] == "queued":
                    candidates.append(rec)
                elif rec["status"] == "processing":
                    cur_lease = rec.get("lease_until")
                    if not isinstance(cur_lease, datetime) or cur_lease <= now:
                        candidates.append(rec)
            candidates.sort(key=lambda r: r.get("created_at") or now)
            return [r["id"] for r in candidates[:cap]]

    from sqlalchemy import or_

    from backend.db.sqlalchemy_models import BundleGenerationJobRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as db:
        rows = (
            db.query(BundleGenerationJobRow.id)
            .filter(
                or_(
                    BundleGenerationJobRow.status == "queued",
                    (
                        (BundleGenerationJobRow.status == "processing")
                        & (
                            (BundleGenerationJobRow.lease_until.is_(None))
                            | (BundleGenerationJobRow.lease_until <= now)
                        )
                    ),
                )
            )
            .order_by(BundleGenerationJobRow.created_at.asc())
            .limit(cap)
            .all()
        )
        return [str(r[0]) for r in rows]


def run_bundle_worker_once(
    *, limit: int = 10, allow_live: bool | None = None
) -> dict[str, Any]:
    """Process up to ``limit`` queued or lease-expired bundle generation jobs."""
    ids = _claimable_job_ids(limit)
    summary: dict[str, Any] = {
        "processed": 0,
        "done": 0,
        "failed": 0,
        "skipped": 0,
        "aborted": False,
        "abort_reason": None,
        "abort_error": None,
        "jobs": [],
    }
    for job_id in ids:
        outcome = process_bundle_job(job_id, allow_live=allow_live)
        if outcome.get("claimed"):
            summary["processed"] += 1
            st = outcome.get("status")
            if st == "done":
                summary["done"] += 1
            elif st == "failed":
                summary["failed"] += 1
            elif st == "skipped":
                summary["skipped"] += 1
        summary["jobs"].append(outcome)
        if outcome.get("credit_exhausted"):
            summary["aborted"] = True
            summary["abort_reason"] = "credit_exhausted"
            summary["abort_error"] = outcome.get("error")
            break
    return summary


def trigger_background_bundle_worker(
    *, limit: int = 10, allow_live: bool | None = None
) -> threading.Thread | None:
    """Spawn a daemon worker thread to drain queued bundle generation jobs."""
    global _BG_THREAD
    if not (
        allow_live is True
        or llm_outbound_gate.llm_live_fetch_enabled()
        or bundle_generator._LLM_OVERRIDE is not None
    ):
        return None
    if not _claimable_job_ids(1):
        return None

    with _BG_LOCK:
        if _BG_THREAD is not None and _BG_THREAD.is_alive():
            return _BG_THREAD

        def _runner() -> None:
            try:
                run_bundle_worker_once(limit=limit, allow_live=allow_live)
            except Exception as exc:  # pragma: no cover - defensive daemon guard
                log.warning("Background bundle worker error: %s", exc)

        t = threading.Thread(target=_runner, name="ws2-bundle-worker", daemon=True)
        t.start()
        _BG_THREAD = t
        return t
