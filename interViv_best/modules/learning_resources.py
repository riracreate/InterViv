"""Curated learning resources — fixture-backed, no scrape / no YouTube API.

Lookup by skill (canonical name or numeric skills.id) or by bank question_id.
Uses SQLAlchemy when DATABASE_URL is set; otherwise an in-memory copy of the
seed fixture (for INTERVIV_USE_MEMORY_DB tests).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import get_settings

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "data" / "learning_resources_seed.json"

LEVELS = ("beginner", "intermediate", "advanced")
SOURCES = ("youtube", "docs", "other")

# skill_name -> list of resource dicts (memory mode)
_MEMORY: list[dict[str, Any]] = []
_SEEDED = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _using_sqlalchemy() -> bool:
    return bool(get_settings().database_url)


def load_seed_fixture() -> list[dict[str, Any]]:
    raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    out = []
    for row in raw:
        if row.get("_skip_reason"):
            continue
        skill = str(row.get("skill") or "").strip()
        url = str(row.get("url") or "").strip()
        level = str(row.get("level") or "").strip().lower()
        source = str(row.get("source") or "").strip().lower()
        title = str(row.get("title") or "").strip()
        if not skill or not url or not title:
            continue
        if level not in LEVELS or source not in SOURCES:
            continue
        out.append(
            {
                "skill": skill,
                "level": level,
                "title": title,
                "url": url,
                "source": source,
                "question_id": (str(row["question_id"]).strip() if row.get("question_id") else None),
            }
        )
    return out


def reset_memory_store() -> None:
    global _SEEDED
    _MEMORY.clear()
    _SEEDED = False


def ensure_seeded() -> None:
    """Idempotent seed into memory and/or SQL tables."""
    global _SEEDED
    rows = load_seed_fixture()
    if not _SEEDED:
        _MEMORY.clear()
        for i, row in enumerate(rows, start=1):
            _MEMORY.append({**row, "id": i, "created_at": _now()})
        _SEEDED = True

    if _using_sqlalchemy():
        _seed_sql(rows)


def _seed_sql(rows: list[dict[str, Any]]) -> None:
    from sqlalchemy import select

    from backend.db.sqlalchemy_models import LearningResourceRow, SkillRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        existing_skills = {
            s.canonical_name: s.id for s in session.scalars(select(SkillRow)).all()
        }
        for name in sorted({r["skill"] for r in rows}):
            if name not in existing_skills:
                skill = SkillRow(canonical_name=name, sub_domain="general")
                session.add(skill)
                session.flush()
                existing_skills[name] = skill.id

        existing_pairs = {
            (r.skill_id, r.url)
            for r in session.scalars(select(LearningResourceRow)).all()
        }
        for row in rows:
            skill_id = existing_skills[row["skill"]]
            key = (skill_id, row["url"])
            if key in existing_pairs:
                continue
            session.add(
                LearningResourceRow(
                    skill_id=skill_id,
                    level=row["level"],
                    title=row["title"],
                    url=row["url"],
                    source=row["source"],
                    question_id=row.get("question_id"),
                    created_at=_now(),
                )
            )
            existing_pairs.add(key)


def resolve_skill_id(skill_ref: str | int | None) -> tuple[int | None, str | None]:
    """Return (numeric_id or None, canonical_name or None)."""
    if skill_ref is None or str(skill_ref).strip() == "":
        return None, None
    ref = str(skill_ref).strip()

    if _using_sqlalchemy():
        from sqlalchemy import select

        from backend.db.sqlalchemy_models import SkillRow
        from backend.db.sqlalchemy_store import session_scope

        with session_scope() as session:
            if ref.isdigit():
                row = session.get(SkillRow, int(ref))
                if row:
                    return row.id, row.canonical_name
                return int(ref), None
            row = session.scalars(
                select(SkillRow).where(SkillRow.canonical_name == ref)
            ).first()
            if row:
                return row.id, row.canonical_name
            return None, ref

    # Memory: treat non-digit as canonical name; digit as synthetic id unmatched → empty
    if ref.isdigit():
        return int(ref), None
    return None, ref


def list_resources(
    *,
    skill_id: str | int | None = None,
    question_id: str | None = None,
    limit_per_level: int = 3,
) -> dict[str, Any]:
    ensure_seeded()
    qid = (question_id or "").strip() or None
    numeric_id, skill_name = resolve_skill_id(skill_id)

    if _using_sqlalchemy() and (numeric_id is not None or qid):
        return _list_sql(
            skill_id=numeric_id,
            skill_name=skill_name,
            question_id=qid,
            limit_per_level=limit_per_level,
        )

    items = list(_MEMORY)
    if qid:
        items = [r for r in items if r.get("question_id") == qid]
    elif skill_name:
        items = [r for r in items if r.get("skill") == skill_name]
    elif numeric_id is not None:
        # Unknown numeric skill in memory mode → empty
        items = []
    else:
        items = []

    return _group_payload(items, skill_name=skill_name, question_id=qid, limit_per_level=limit_per_level)


def _list_sql(
    *,
    skill_id: int | None,
    skill_name: str | None,
    question_id: str | None,
    limit_per_level: int,
) -> dict[str, Any]:
    from sqlalchemy import select

    from backend.db.sqlalchemy_models import LearningResourceRow, SkillRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        stmt = select(LearningResourceRow, SkillRow.canonical_name).join(
            SkillRow, LearningResourceRow.skill_id == SkillRow.id
        )
        if question_id:
            stmt = stmt.where(LearningResourceRow.question_id == question_id)
        elif skill_id is not None:
            stmt = stmt.where(LearningResourceRow.skill_id == skill_id)
        else:
            return _group_payload([], skill_name=skill_name, question_id=question_id, limit_per_level=limit_per_level)

        rows = session.execute(stmt).all()
        items = [
            {
                "id": lr.id,
                "skill": name,
                "skill_id": lr.skill_id,
                "level": lr.level,
                "title": lr.title,
                "url": lr.url,
                "source": lr.source,
                "question_id": lr.question_id,
            }
            for lr, name in rows
        ]
        resolved_name = skill_name or (items[0]["skill"] if items else None)
        return _group_payload(
            items,
            skill_name=resolved_name,
            question_id=question_id,
            limit_per_level=limit_per_level,
        )


def _group_payload(
    items: list[dict[str, Any]],
    *,
    skill_name: str | None,
    question_id: str | None,
    limit_per_level: int,
) -> dict[str, Any]:
    by_level: dict[str, list[dict[str, Any]]] = {level: [] for level in LEVELS}
    for row in items:
        level = row.get("level") or "beginner"
        if level not in by_level:
            continue
        if len(by_level[level]) >= limit_per_level:
            continue
        by_level[level].append(
            {
                "id": row.get("id"),
                "title": row["title"],
                "url": row["url"],
                "source": row["source"],
                "level": level,
                "question_id": row.get("question_id"),
            }
        )
    flat = [item for level in LEVELS for item in by_level[level]]
    return {
        "skill": skill_name,
        "question_id": question_id,
        "by_level": by_level,
        "resources": flat,
        "count": len(flat),
    }
