"""Phase 3B: progression_blocked_reason survives SQLAlchemy reopen."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")


def _clear_database_caches() -> None:
    from backend import config
    from backend.db import sqlalchemy_store

    config.get_settings.cache_clear()
    sqlalchemy_store.get_engine.cache_clear()
    sqlalchemy_store._sessionmaker.cache_clear()
    sqlalchemy_store.get_sqlalchemy_database.cache_clear()


@pytest.fixture()
def sql_db(tmp_path, monkeypatch):
    from backend.db import sqlalchemy_store

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'phase3b_continue.db'}")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_database_caches()
    sqlalchemy_store.create_all_for_smoke()
    # Apply focused migration for progression_blocked_reason when create_all
    # already built schema from models (column present). Re-open clears caches.
    yield
    _clear_database_caches()


def test_progression_blocked_reason_survives_sql_reopen(sql_db):
    from backend.db import get_database
    from backend.db.sqlalchemy_store import SQLAlchemyDatabase, get_engine

    db = get_database()
    assert isinstance(db, SQLAlchemyDatabase)
    session_id = "sess-phase3b-blocked"
    db["sessions"].insert_one({
        "session_id": session_id,
        "candidate_id": "cand-1",
        "status": "content_blocked",
        "progression_blocked_reason": "No matching transactions inventory.",
        "skill": "DBMS",
        "skills": ["DBMS"],
        "last_round": 1,
        "rounds": [{
            "round": 1,
            "round_type": "technical_short_answer",
            "status": "submitted",
            "final_score": 70.0,
            "question": "What is ACID?",
            "feedback": {
                "content": ["ok"], "strengths": [], "weakness": [], "next_step": "",
            },
        }],
    })

    _clear_database_caches()
    db2 = get_database()
    assert isinstance(db2, SQLAlchemyDatabase)
    stored = db2["sessions"].find_one({"session_id": session_id})
    assert stored is not None
    assert stored["status"] == "content_blocked"
    assert stored["progression_blocked_reason"] == "No matching transactions inventory."
    assert stored["rounds"][0]["final_score"] == 70.0

    with get_engine().connect() as conn:
        row = conn.execute(
            text(
                "SELECT progression_blocked_reason, status FROM sessions WHERE id = :id"
            ),
            {"id": session_id},
        ).one()
    assert row[0] == "No matching transactions inventory."
    assert row[1] == "content_blocked"
