"""Learning effectiveness signals.

Persists lightweight events (Elo deltas, skill attempts) and roadmap-block
completion so the home dashboard can show whether practice is moving needles.

Storage: in-memory for INTERVIV_USE_MEMORY_DB / no DATABASE_URL; SQLAlchemy
tables when PostgreSQL is configured (see LearningEventRow / RoadmapProgressRow).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from backend.config import get_settings
from modules.roadmap_generator import SUPPORTED_DAYS

EVENT_ELO_DELTA = "elo_delta"
EVENT_SKILL_ATTEMPT = "skill_attempt"

_MEMORY_EVENTS: list[dict[str, Any]] = []
# (user_id, role_id, plan_days) -> {completed: set[int], blocks_total: int}
_MEMORY_ROADMAP: dict[tuple[str, str, int], dict[str, Any]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _using_sqlalchemy() -> bool:
    return bool(get_settings().database_url)


def reset_memory_store() -> None:
    """Test helper — clears in-memory events/progress."""
    _MEMORY_EVENTS.clear()
    _MEMORY_ROADMAP.clear()


def snapshot_memory_store() -> dict[str, Any]:
    import copy

    return {
        "events": copy.deepcopy(_MEMORY_EVENTS),
        "roadmap": copy.deepcopy(_MEMORY_ROADMAP),
    }


def restore_memory_store(snapshot: dict[str, Any] | None) -> None:
    if not snapshot:
        return
    import copy

    _MEMORY_EVENTS.clear()
    _MEMORY_EVENTS.extend(copy.deepcopy(snapshot.get("events") or []))
    _MEMORY_ROADMAP.clear()
    _MEMORY_ROADMAP.update(copy.deepcopy(snapshot.get("roadmap") or {}))


def record_elo_delta(
    *,
    user_id: str,
    session_id: str,
    skill: str,
    elo_before: float,
    elo_after: float,
) -> None:
    user_id = str(user_id or "").strip()
    if not user_id:
        return
    skill = str(skill or "").strip() or "General"
    delta = round(float(elo_after) - float(elo_before), 2)
    payload = {
        "user_id": user_id,
        "session_id": str(session_id or ""),
        "skill": skill,
        "event_type": EVENT_ELO_DELTA,
        "payload": {
            "elo_before": float(elo_before),
            "elo_after": float(elo_after),
            "delta": delta,
        },
        "created_at": _now(),
    }
    # Every Elo change is also a skill attempt for revisit math.
    attempt = {
        **payload,
        "event_type": EVENT_SKILL_ATTEMPT,
        "payload": {"session_id": str(session_id or "")},
    }
    if _using_sqlalchemy():
        _record_sql(payload)
        _record_sql(attempt)
        return
    _MEMORY_EVENTS.append(payload)
    _MEMORY_EVENTS.append(attempt)


def mark_roadmap_block_complete(
    *,
    user_id: str,
    role_id: str,
    plan_days: int,
    block_index: int,
    blocks_total: int,
) -> dict[str, Any]:
    user_id = str(user_id or "").strip()
    role_id = str(role_id or "").strip()
    if not user_id or not role_id:
        raise ValueError("user_id and role_id are required")
    if plan_days not in SUPPORTED_DAYS:
        raise ValueError(f"plan_days must be one of {SUPPORTED_DAYS}")
    if block_index < 1 or (blocks_total > 0 and block_index > blocks_total):
        raise ValueError("block_index out of range")

    if _using_sqlalchemy():
        return _mark_roadmap_sql(
            user_id=user_id,
            role_id=role_id,
            plan_days=plan_days,
            block_index=block_index,
            blocks_total=blocks_total,
        )

    key = (user_id, role_id, plan_days)
    entry = _MEMORY_ROADMAP.setdefault(
        key, {"completed": set(), "blocks_total": int(blocks_total)}
    )
    done: set[int] = entry["completed"]
    done.add(int(block_index))
    total = max(int(blocks_total), int(entry.get("blocks_total") or 0), max(done))
    entry["blocks_total"] = total
    return {
        "user_id": user_id,
        "role_id": role_id,
        "plan_days": plan_days,
        "completed_blocks": sorted(done),
        "blocks_total": total,
        "completion_fraction": round(len(done) / total, 4) if total else 0.0,
    }


def get_roadmap_completion(user_id: str, role_id: str | None = None) -> dict[str, Any]:
    """Return completion fractions for 7/14/30 plans (null if never started)."""
    user_id = str(user_id or "").strip()
    out: dict[str, Any] = {str(d): None for d in SUPPORTED_DAYS}
    if not user_id:
        return out

    if _using_sqlalchemy():
        return _roadmap_completion_sql(user_id, role_id)

    for (uid, rid, days), entry in _MEMORY_ROADMAP.items():
        if uid != user_id:
            continue
        if role_id and rid != str(role_id):
            continue
        done: set[int] = entry.get("completed") or set()
        total = int(entry.get("blocks_total") or 0) or (max(done) if done else 0)
        frac = round(len(done) / total, 4) if total else 0.0
        prev = out[str(days)]
        if prev is None or frac >= float(prev):
            out[str(days)] = frac
    return out


def build_signals_payload(user_id: str) -> dict[str, Any]:
    user_id = str(user_id or "").strip()
    events = _list_events(user_id)
    elo_by_skill_session: dict[tuple[str, str], float] = defaultdict(float)
    elo_by_skill: dict[str, float] = defaultdict(float)
    sessions_by_skill: dict[str, set[str]] = defaultdict(set)

    for event in events:
        skill = event["skill"]
        et = event["event_type"]
        payload = event.get("payload") or {}
        if et == EVENT_ELO_DELTA:
            sid = event.get("session_id") or payload.get("session_id") or ""
            delta = float(payload.get("delta") or 0.0)
            elo_by_skill_session[(skill, sid)] += delta
            elo_by_skill[skill] += delta
        elif et == EVENT_SKILL_ATTEMPT:
            sid = event.get("session_id") or payload.get("session_id") or ""
            if sid:
                sessions_by_skill[skill].add(str(sid))

    elo_deltas = []
    for (skill, session_id), delta in sorted(elo_by_skill_session.items()):
        elo_deltas.append(
            {
                "skill": skill,
                "session_id": session_id,
                "delta": round(delta, 2),
                "cumulative_delta": round(elo_by_skill[skill], 2),
            }
        )

    revisit_rates = []
    for skill, sessions in sorted(sessions_by_skill.items()):
        n = len(sessions)
        retries = max(0, n - 1)
        revisit_rates.append(
            {
                "skill": skill,
                "sessions": n,
                "retries": retries,
                "rate": round(retries / n, 4) if n else 0.0,
            }
        )

    return {
        "user_id": user_id,
        "elo_deltas": elo_deltas,
        "revisit_rates": revisit_rates,
        "roadmap_completion": get_roadmap_completion(user_id),
    }


def _list_events(user_id: str) -> list[dict[str, Any]]:
    if _using_sqlalchemy():
        return _list_events_sql(user_id)
    return [e for e in _MEMORY_EVENTS if e.get("user_id") == user_id]


def _record_sql(event: dict[str, Any]) -> None:
    from backend.db.sqlalchemy_models import LearningEventRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        session.add(
            LearningEventRow(
                user_id=event["user_id"],
                session_id=event.get("session_id") or None,
                skill=event["skill"],
                event_type=event["event_type"],
                payload_json=event.get("payload") or {},
                created_at=event.get("created_at") or _now(),
            )
        )


def _list_events_sql(user_id: str) -> list[dict[str, Any]]:
    from backend.db.sqlalchemy_models import LearningEventRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        rows = (
            session.query(LearningEventRow)
            .filter(LearningEventRow.user_id == user_id)
            .order_by(LearningEventRow.created_at.asc())
            .all()
        )
        return [
            {
                "user_id": row.user_id,
                "session_id": row.session_id or "",
                "skill": row.skill,
                "event_type": row.event_type,
                "payload": row.payload_json or {},
                "created_at": row.created_at,
            }
            for row in rows
        ]


def _mark_roadmap_sql(
    *,
    user_id: str,
    role_id: str,
    plan_days: int,
    block_index: int,
    blocks_total: int,
) -> dict[str, Any]:
    from backend.db.sqlalchemy_models import RoadmapProgressRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        row = (
            session.query(RoadmapProgressRow)
            .filter_by(user_id=user_id, role_id=role_id, plan_days=plan_days)
            .one_or_none()
        )
        if row is None:
            row = RoadmapProgressRow(
                user_id=user_id,
                role_id=role_id,
                plan_days=plan_days,
                completed_blocks=[],
                blocks_total=blocks_total,
            )
            session.add(row)
        done = set(int(x) for x in (row.completed_blocks or []))
        done.add(int(block_index))
        row.completed_blocks = sorted(done)
        row.blocks_total = max(int(blocks_total), int(row.blocks_total or 0), max(done))
        row.updated_at = _now()
        total = int(row.blocks_total or 0)
        return {
            "user_id": user_id,
            "role_id": role_id,
            "plan_days": plan_days,
            "completed_blocks": list(row.completed_blocks),
            "blocks_total": total,
            "completion_fraction": round(len(done) / total, 4) if total else 0.0,
        }


def _roadmap_completion_sql(user_id: str, role_id: str | None) -> dict[str, Any]:
    from backend.db.sqlalchemy_models import RoadmapProgressRow
    from backend.db.sqlalchemy_store import session_scope

    out: dict[str, Any] = {str(d): None for d in SUPPORTED_DAYS}
    with session_scope() as session:
        q = session.query(RoadmapProgressRow).filter(RoadmapProgressRow.user_id == user_id)
        if role_id:
            q = q.filter(RoadmapProgressRow.role_id == str(role_id))
        for row in q.all():
            done = row.completed_blocks or []
            total = int(row.blocks_total or 0) or (max(done) if done else 0)
            frac = round(len(done) / total, 4) if total else 0.0
            key = str(row.plan_days)
            prev = out.get(key)
            if prev is None or frac >= float(prev):
                out[key] = frac
    return out
