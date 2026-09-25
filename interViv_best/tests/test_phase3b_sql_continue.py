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

    from tests.user_fixtures import ensure_session_parents
    db = get_database()
    assert isinstance(db, SQLAlchemyDatabase)
    session_id = "sess-phase3b-blocked"
    doc = {
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
    }
    ensure_session_parents(db, doc)
    db["sessions"].insert_one(doc)

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


def test_sql_continue_after_reopen(sql_db, monkeypatch):
    """Continue recovers on SQLAlchemy after process reopen without rescoring."""
    from datetime import datetime, timezone
    from uuid import uuid4

    from backend.auth.security import create_access_token, hash_password
    from backend.db import get_database
    from backend.db.sqlalchemy_store import SQLAlchemyDatabase
    from backend.main import app
    from backend.routes import session_continue as sc
    from fastapi.testclient import TestClient

    db = get_database()
    assert isinstance(db, SQLAlchemyDatabase)
    user_id = str(uuid4())
    db["users"].insert_one({
        "id": user_id,
        "email": f"sql-cont-{user_id[:8]}@example.com",
        "name": "SQL Continue",
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    })
    candidate_id = str(uuid4())
    session_id = f"sess-sql-cont-{user_id[:8]}"
    db["candidates"].insert_one({
        "candidate_id": candidate_id,
        "user_id": user_id,
        "resume_skills": ["DBMS"],
        "elo_ratings": {"DBMS": 1500.0},
        "session_history": [],
    })
    db["sessions"].insert_one({
        "session_id": session_id,
        "user_id": user_id,
        "candidate_id": candidate_id,
        "status": "content_blocked",
        "progression_blocked_reason": "No matching transactions inventory.",
        "skill": "DBMS",
        "skills": ["DBMS"],
        "total_rounds": 2,
        "last_round": 1,
        "expanded_plan": [{
            "round_type": "technical_short_answer",
            "skills": ["DBMS"],
            "topic": "transactions",
            "block_id": "b1",
            "block_position": 0,
            "category": "interview",
        }, {
            "round_type": "technical_short_answer",
            "skills": ["DBMS"],
            "topic": "transactions",
            "block_id": "b1",
            "block_position": 1,
            "category": "interview",
        }],
        "block_plan": [{"id": "b1", "category": "interview", "skills": ["DBMS"],
                        "topic": "transactions", "count": 2}],
        "rounds": [{
            "round": 1,
            "round_type": "technical_short_answer",
            "status": "submitted",
            "skill": "DBMS",
            "final_score": 72.0,
            "elo_before": 1500.0,
            "elo_after": 1505.0,
            "question": "What is ACID?",
            "answer_text": "Atomicity Consistency Isolation Durability.",
            "feedback": {
                "content": ["ok"], "strengths": [], "weakness": [], "next_step": "Practice more.",
            },
            "attempt_snapshot": {"digest": "abc", "snapshot_version": 2},
            "block_id": "b1",
            "block_position": 0,
        }],
    })

    _clear_database_caches()
    db2 = get_database()
    stored = db2["sessions"].find_one({"session_id": session_id})
    assert stored["status"] == "content_blocked"
    score = stored["rounds"][0]["final_score"]
    elo = float(db2["candidates"].find_one({"candidate_id": candidate_id})["elo_ratings"]["DBMS"])

    monkeypatch.setattr(
        sc,
        "_get_next_question",
        lambda **kwargs: {
            "question": "What does atomicity guarantee?",
            "ideal_answer": "All or nothing.",
            "ideal_keywords": "atomicity",
            "skill": "DBMS",
            "sub_domain": "transactions",
            "source": "legacy",
        },
    )
    monkeypatch.setattr(
        "backend.routes.session_continue._verify_served_topic",
        lambda **kwargs: None,
    )

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {create_access_token(user_id)}"}
    resp = client.post(f"/session/{session_id}/continue", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["continued"] is True
    assert body["status"] == "active"
    assert body["round"] == 2

    after = get_database()["sessions"].find_one({"session_id": session_id})
    assert after["status"] == "active"
    assert after["rounds"][0]["final_score"] == score
    assert len(after["rounds"]) == 2
    elo2 = float(get_database()["candidates"].find_one(
        {"candidate_id": candidate_id})["elo_ratings"]["DBMS"])
    assert elo2 == elo
