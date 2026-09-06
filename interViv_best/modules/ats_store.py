"""ATS run persistence — memory for tests, SQLAlchemy when DATABASE_URL is set."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.config import get_settings

_MEMORY_RUNS: list[dict[str, Any]] = []


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _using_sqlalchemy() -> bool:
    return bool(get_settings().database_url)


def reset_memory_store() -> None:
    _MEMORY_RUNS.clear()


def save_ats_run(record: dict[str, Any]) -> dict[str, Any]:
    row = {
        **record,
        "id": record.get("id") or (len(_MEMORY_RUNS) + 1),
        "created_at": record.get("created_at") or _now(),
    }
    if _using_sqlalchemy():
        return _save_sql(row)
    _MEMORY_RUNS.append(row)
    return row


def list_ats_runs(user_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    user_id = str(user_id)
    if _using_sqlalchemy():
        return _list_sql(user_id, limit=limit)
    rows = [r for r in _MEMORY_RUNS if r.get("user_id") == user_id]
    rows = sorted(rows, key=lambda r: r.get("created_at") or _now(), reverse=True)
    return rows[:limit]


def _save_sql(row: dict[str, Any]) -> dict[str, Any]:
    from backend.db.sqlalchemy_models import AtsRunRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        entity = AtsRunRow(
            user_id=row["user_id"],
            resume_id=row["resume_id"],
            role_id=row.get("role_id"),
            jd_hash=row.get("jd_hash"),
            parse_score=float(row["parse_score"]),
            section_score=float(row["section_score"]),
            keyword_score=float(row["keyword_score"]),
            heuristic_score=float(row["heuristic_score"]),
            total=float(row["total"]),
            flags=list(row.get("flags") or []),
            missing_skills=list(row.get("missing_skills") or []),
            present_skills=list(row.get("present_skills") or []),
            created_at=row.get("created_at") or _now(),
        )
        session.add(entity)
        session.flush()
        return {
            "id": entity.id,
            "user_id": entity.user_id,
            "resume_id": entity.resume_id,
            "role_id": entity.role_id,
            "jd_hash": entity.jd_hash,
            "parse_score": entity.parse_score,
            "section_score": entity.section_score,
            "keyword_score": entity.keyword_score,
            "heuristic_score": entity.heuristic_score,
            "total": entity.total,
            "flags": entity.flags,
            "missing_skills": entity.missing_skills,
            "present_skills": entity.present_skills,
            "created_at": entity.created_at,
        }


def _list_sql(user_id: str, *, limit: int) -> list[dict[str, Any]]:
    from backend.db.sqlalchemy_models import AtsRunRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        rows = (
            session.query(AtsRunRow)
            .filter(AtsRunRow.user_id == user_id)
            .order_by(AtsRunRow.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "resume_id": r.resume_id,
                "role_id": r.role_id,
                "jd_hash": r.jd_hash,
                "parse_score": r.parse_score,
                "section_score": r.section_score,
                "keyword_score": r.keyword_score,
                "heuristic_score": r.heuristic_score,
                "total": r.total,
                "flags": r.flags or [],
                "missing_skills": r.missing_skills or [],
                "present_skills": r.present_skills or [],
                "created_at": r.created_at,
            }
            for r in rows
        ]
