"""LLM token usage and latency logging (dual-backend: SQLAlchemy + memory).

Tracks prompt/completion/total token counts, latency, purpose, status, and
optional bundle/role context across LLM calls without ever raising on logging
errors.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from backend.config import get_settings

LOGGER = logging.getLogger(__name__)

_LOCK = threading.RLock()
_MEMORY_EVENTS: list[dict[str, Any]] = []
_MEMORY_NEXT_ID = 1


def _using_sqlalchemy() -> bool:
    return bool(get_settings().database_url)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _nonneg_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": _utc(row.created_at),
        "provider": row.provider,
        "model": row.model,
        "purpose": row.purpose,
        "prompt_tokens": int(row.prompt_tokens or 0),
        "completion_tokens": int(row.completion_tokens or 0),
        "total_tokens": int(row.total_tokens or 0),
        "latency_ms": int(row.latency_ms or 0),
        "bundle_id": row.bundle_id,
        "role": row.role,
        "status": row.status,
        "error": row.error,
    }


def reset_memory_usage() -> None:
    """Clear in-memory LLM usage events (for tests)."""
    global _MEMORY_NEXT_ID
    with _LOCK:
        _MEMORY_EVENTS.clear()
        _MEMORY_NEXT_ID = 1


def log_llm_usage(
    *,
    provider: str,
    model: str,
    purpose: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: int = 0,
    bundle_id: str | None = None,
    role: str | None = None,
    status: str = "ok",
    error: str | None = None,
) -> dict[str, Any]:
    """Persist one LLM usage event to SQL or in-memory store. Never raises."""
    global _MEMORY_NEXT_ID

    p_tok = _nonneg_int(prompt_tokens)
    c_tok = _nonneg_int(completion_tokens)
    t_tok = _nonneg_int(total_tokens)
    if t_tok == 0 and (p_tok > 0 or c_tok > 0):
        t_tok = p_tok + c_tok
    lat = _nonneg_int(latency_ms)
    now = _now()

    event: dict[str, Any] = {
        "id": None,
        "created_at": now,
        "provider": str(provider or "unknown")[:32],
        "model": str(model or "unknown")[:128],
        "purpose": str(purpose or "unknown")[:64],
        "prompt_tokens": p_tok,
        "completion_tokens": c_tok,
        "total_tokens": t_tok,
        "latency_ms": lat,
        "bundle_id": str(bundle_id)[:128] if bundle_id is not None else None,
        "role": str(role)[:256] if role is not None else None,
        "status": str(status or "ok")[:32],
        "error": str(error) if error is not None else None,
    }

    if _using_sqlalchemy():
        try:
            from backend.db.sqlalchemy_models import LLMUsageEventRow
            from backend.db.sqlalchemy_store import session_scope

            with session_scope() as session:
                row = LLMUsageEventRow(
                    created_at=event["created_at"],
                    provider=event["provider"],
                    model=event["model"],
                    purpose=event["purpose"],
                    prompt_tokens=event["prompt_tokens"],
                    completion_tokens=event["completion_tokens"],
                    total_tokens=event["total_tokens"],
                    latency_ms=event["latency_ms"],
                    bundle_id=event["bundle_id"],
                    role=event["role"],
                    status=event["status"],
                    error=event["error"],
                )
                session.add(row)
                session.flush()
                event["id"] = row.id
        except Exception as exc:
            LOGGER.warning("Failed to log LLM usage event to SQL store: %s", exc)
        return event

    with _LOCK:
        event["id"] = _MEMORY_NEXT_ID
        _MEMORY_NEXT_ID += 1
        _MEMORY_EVENTS.append(dict(event))
    return dict(event)


def list_usage_events(
    *,
    purpose: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return recorded usage events ordered newest-first (bounded by limit)."""
    max_rows = max(0, int(limit))
    if max_rows == 0:
        return []
    purpose_clean = str(purpose).strip()[:64] if purpose is not None else None

    if _using_sqlalchemy():
        from sqlalchemy import select
        from backend.db.sqlalchemy_models import LLMUsageEventRow
        from backend.db.sqlalchemy_store import session_scope

        stmt = select(LLMUsageEventRow).order_by(LLMUsageEventRow.id.desc())
        if purpose_clean is not None:
            stmt = stmt.where(LLMUsageEventRow.purpose == purpose_clean)
        stmt = stmt.limit(max_rows)
        with session_scope() as session:
            return [_row_to_dict(r) for r in session.scalars(stmt)]

    with _LOCK:
        rows = [
            dict(ev)
            for ev in reversed(_MEMORY_EVENTS)
            if purpose_clean is None or ev.get("purpose") == purpose_clean
        ]
    return rows[:max_rows]


def summarize_usage(*, purpose: str | None = None) -> dict[str, Any]:
    """Aggregate token and latency totals across stored usage events."""
    purpose_clean = str(purpose).strip()[:64] if purpose is not None else None

    if _using_sqlalchemy():
        from sqlalchemy import select
        from backend.db.sqlalchemy_models import LLMUsageEventRow
        from backend.db.sqlalchemy_store import session_scope

        stmt = select(LLMUsageEventRow)
        if purpose_clean is not None:
            stmt = stmt.where(LLMUsageEventRow.purpose == purpose_clean)
        with session_scope() as session:
            events = [_row_to_dict(r) for r in session.scalars(stmt)]
    else:
        with _LOCK:
            events = [
                dict(ev)
                for ev in _MEMORY_EVENTS
                if purpose_clean is None or ev.get("purpose") == purpose_clean
            ]

    count = len(events)
    ok_count = 0
    error_count = 0
    prompt_sum = 0
    completion_sum = 0
    total_sum = 0
    latency_sum = 0
    by_purpose: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}

    for ev in events:
        is_ok = ev.get("status") == "ok"
        if is_ok:
            ok_count += 1
        else:
            error_count += 1
        p_tok = int(ev.get("prompt_tokens") or 0)
        c_tok = int(ev.get("completion_tokens") or 0)
        t_tok = int(ev.get("total_tokens") or 0)
        lat = int(ev.get("latency_ms") or 0)
        prompt_sum += p_tok
        completion_sum += c_tok
        total_sum += t_tok
        latency_sum += lat

        p_key = str(ev.get("purpose") or "unknown")
        p_bucket = by_purpose.setdefault(
            p_key,
            {
                "count": 0,
                "ok_count": 0,
                "error_count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        )
        p_bucket["count"] += 1
        p_bucket["ok_count" if is_ok else "error_count"] += 1
        p_bucket["prompt_tokens"] += p_tok
        p_bucket["completion_tokens"] += c_tok
        p_bucket["total_tokens"] += t_tok

        m_key = str(ev.get("model") or "unknown")
        m_bucket = by_model.setdefault(
            m_key,
            {
                "count": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        )
        m_bucket["count"] += 1
        m_bucket["prompt_tokens"] += p_tok
        m_bucket["completion_tokens"] += c_tok
        m_bucket["total_tokens"] += t_tok

    return {
        "count": count,
        "ok_count": ok_count,
        "error_count": error_count,
        "prompt_tokens": prompt_sum,
        "completion_tokens": completion_sum,
        "total_tokens": total_sum,
        "total_latency_ms": latency_sum,
        "avg_latency_ms": round(latency_sum / count, 2) if count else 0.0,
        "purpose_filter": purpose_clean,
        "by_purpose": by_purpose,
        "by_model": by_model,
    }
