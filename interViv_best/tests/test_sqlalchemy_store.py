"""End-to-end coverage for the SQLAlchemy persistence layer (DATABASE_URL mode).

Every other test runs against the in-memory store. This file points
DATABASE_URL at a throwaway SQLite database and drives the real API flow —
signup → login → session start → answer → dashboard — through the same
SQLAlchemy store used for PostgreSQL, then asserts the rows actually landed:

- users / candidates / sessions / rounds via the document-style collections
- student_skill_graph via StudentSkillGraph's direct ORM path
- companies / roles / skills via the startup seeding in the app lifespan

SQLite works here because the models only use dialect-agnostic column types
(JSON, not JSONB). A real PostgreSQL deployment additionally needs
``alembic upgrade head``, which creates the same tables.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("QUESTION_GENERATION_MODE", "llm_csv_fallback")
os.environ.setdefault("QUESTION_REQUIRE_LLM", "false")


def _clear_database_caches() -> None:
    """Drop every lru_cache that may have captured the other database mode."""
    from backend import config
    from backend.db import sqlalchemy_store

    config.get_settings.cache_clear()
    sqlalchemy_store.get_engine.cache_clear()
    sqlalchemy_store._sessionmaker.cache_clear()
    sqlalchemy_store.get_sqlalchemy_database.cache_clear()


@pytest.fixture()
def sql_client(tmp_path, monkeypatch):
    from backend.db import sqlalchemy_store

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'interviv_e2e.db'}")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "llm_csv_fallback")
    monkeypatch.setenv("QUESTION_REQUIRE_LLM", "false")
    _clear_database_caches()

    from backend.main import app

    sqlalchemy_store.create_all_for_smoke()
    engine = sqlalchemy_store.get_engine()
    try:
        # Context-managed client runs the lifespan, which seeds the company
        # hiring graph into the SQL tables.
        with TestClient(app) as client:
            yield client, engine
    finally:
        engine.dispose()
        _clear_database_caches()


def _count(engine, table: str) -> int:
    from sqlalchemy import text

    with engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def test_full_flow_persists_through_sqlalchemy(sql_client) -> None:
    client, engine = sql_client

    from backend.db import get_database
    from backend.db.sqlalchemy_store import SQLAlchemyDatabase

    assert isinstance(get_database(), SQLAlchemyDatabase)

    # Startup seeding wrote the company hiring graph into SQL tables.
    assert _count(engine, "companies") >= 5
    assert _count(engine, "roles") >= 5
    assert _count(engine, "skills") > 0

    # ── auth ────────────────────────────────────────────────────────────
    signup = client.post(
        "/auth/signup",
        json={"email": "contributors@example.invalid", "password": "passw0rd1", "name": "SQL E2E"},
    )
    assert signup.status_code == 200, signup.text

    login = client.post(
        "/auth/login", json={"email": "contributors@example.invalid", "password": "passw0rd1"}
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    assert _count(engine, "users") == 1

    # ── interview flow ──────────────────────────────────────────────────
    start = client.post(
        "/session/start",
        json={"candidate_id": "", "skills": ["DSA"], "rounds_per_skill": 3},
        headers=headers,
    )
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    assert _count(engine, "candidates") == 1
    assert _count(engine, "sessions") == 1
    assert _count(engine, "rounds") == 1

    answer = client.post(
        "/session/answer",
        json={
            "session_id": session_id,
            "round": 1,
            "answer_text": (
                "A binary search tree keeps keys in sorted order so lookup, "
                "insertion, and deletion run in O(log n) time on a balanced "
                "tree by discarding half of the remaining nodes at each step."
            ),
            "word_count": 34,
        },
    )
    assert answer.status_code == 200, answer.text
    assert answer.json().get("final_score") is not None

    # Scored round 1 plus the queued round 2 are both persisted.
    assert _count(engine, "rounds") == 2

    # The answer route updated the persistent skill graph through the ORM.
    assert _count(engine, "student_skill_graph") >= 1

    # ── read paths ──────────────────────────────────────────────────────
    dashboard = client.get(f"/dashboard/{session_id}", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    rounds = dashboard.json().get("rounds") or []
    assert rounds and rounds[0].get("final_score") is not None

    stored = get_database()["sessions"].find_one({"session_id": session_id})
    assert stored is not None
    assert stored["user_id"] == me.json()["user"]["id"]
    assert len(stored["rounds"]) == 2


def test_unknown_collection_error_names_the_contract(sql_client) -> None:
    _, _ = sql_client
    from backend.db import get_database

    with pytest.raises(KeyError) as excinfo:
        get_database()["companies"]
    assert "session_scope" in str(excinfo.value)
