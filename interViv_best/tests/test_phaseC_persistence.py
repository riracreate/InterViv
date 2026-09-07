"""Phase C: coding attempts persist on the real SQLAlchemy adapter.

Every test binds the app to a disposable SQLite file (DATABASE_URL +
INTERVIV_USE_MEMORY_DB=false). Nothing here migrates, resets, or touches
the user's real database.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect

from backend import config as app_config
from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.db.sqlalchemy_store import (
    _sessionmaker,
    create_all_for_smoke,
    get_engine,
    get_sqlalchemy_database,
)
from backend.main import app
from tests.alembic_helpers import parent_revision

PHASE_C_REVISION = "20260907_0005"


def _clear_db_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def sa_url(tmp_path, monkeypatch):
    """Disposable SQLite file carrying the current models' schema."""
    db_file = tmp_path / "phasec.db"
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_db_caches()
    create_all_for_smoke()
    yield url
    try:
        get_engine().dispose()
    except Exception:
        pass
    _clear_db_caches()


def _run_alembic(engine_url: str, action: str, revision: str) -> None:
    here = os.path.dirname(__file__)
    interviv_dir = os.path.abspath(os.path.join(here, ".."))
    cfg = AlembicConfig(os.path.join(interviv_dir, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", engine_url)
    cfg.set_main_option("script_location", os.path.join(interviv_dir, "alembic"))
    if action == "upgrade":
        alembic_command.upgrade(cfg, revision)
    else:
        alembic_command.downgrade(cfg, revision)


def _make_user(prefix="c1"):
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one({
        "id": user_id,
        "email": f"{prefix}-{user_id[:8]}@example.com",
        "name": f"Test {prefix}",
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    })
    return {"id": user_id, "token": create_access_token(user_id)}


def _attempt_doc(**overrides):
    doc = {
        "id": str(uuid4()),
        "user_id": "u1",
        "session_id": "s1",
        "round": 1,
        "problem_id": "coding_two_sum",
        "language": "python",
        "source": "def two_sum(nums, target):\n    pass\n",
        "truncated": False,
        "status": "unavailable",
        "score": None,
        "visible_passed": None,
        "visible_total": None,
        "hidden_passed": None,
        "hidden_total": None,
        "error": "Code execution is unavailable in this environment.",
        "created_at": datetime.now(timezone.utc),
    }
    doc.update(overrides)
    return doc


def test_attempt_round_trips_on_sqlalchemy_store(sa_url) -> None:
    db = get_database()
    doc = _attempt_doc()
    db["coding_submissions"].insert_one(doc)

    found = db["coding_submissions"].find_one({"id": doc["id"]})
    assert found is not None
    for key in ("user_id", "session_id", "round", "problem_id",
                "language", "source", "truncated", "status", "score",
                "visible_passed", "visible_total", "hidden_passed",
                "hidden_total", "error"):
        assert found[key] == doc[key], key

    assert db["coding_submissions"].count_documents(
        {"session_id": "s1"}) == 1
    assert db["coding_submissions"].count_documents(
        {"user_id": "u1", "status": "unavailable"}) == 1
    assert db["coding_submissions"].count_documents(
        {"user_id": "u1", "status": "scored"}) == 0

    scored = _attempt_doc(status="scored", score=92.0, visible_passed=3,
                          visible_total=3, hidden_passed=4, hidden_total=5,
                          error=None)
    db["coding_submissions"].insert_one(scored)
    rows = list(db["coding_submissions"].find({"session_id": "s1"}))
    assert len(rows) == 2
    assert {r["status"] for r in rows} == {"unavailable", "scored"}


def test_submit_records_attempt_on_sqlalchemy_store(sa_url) -> None:
    """End to end: an unavailable submit persists its attempt row."""
    user = _make_user()
    headers = {"Authorization": f"Bearer {user['token']}"}
    client = TestClient(app)
    started = client.post(
        "/session/start",
        json={
            "candidate_id": "",
            "skills": ["DSA"],
            "rounds_per_skill": 1,
            "round_type": "coding",
            "round_config": {"problem_id": "coding_two_sum",
                             "duration_minutes": 30},
        },
        headers=headers,
    )
    assert started.status_code == 200, started.text
    session_id = started.json()["session_id"]

    resp = client.post(
        "/session/answer",
        json={"session_id": session_id, "round": 1,
              "answer_text": "def two_sum(nums, target): pass"},
        headers=headers,
    )
    assert resp.status_code == 503

    rows = list(get_database()["coding_submissions"].find(
        {"session_id": session_id}))
    assert len(rows) == 1
    assert rows[0]["user_id"] == user["id"]
    assert rows[0]["status"] == "unavailable"
    assert rows[0]["problem_id"] == "coding_two_sum"


def test_alembic_migration_creates_coding_submissions(tmp_path) -> None:
    db_file = tmp_path / "phasec_mig.db"
    url = f"sqlite:///{db_file}"
    _run_alembic(url, "upgrade", "head")

    engine = create_engine(url)
    inspector = sa_inspect(engine)
    assert "coding_submissions" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("coding_submissions")}
    for col in ("id", "user_id", "session_id", "round_number",
                "problem_id", "language", "source", "truncated", "status",
                "score", "visible_passed", "visible_total",
                "hidden_passed", "hidden_total", "error", "created_at"):
        assert col in cols, col
    engine.dispose()

    _run_alembic(url, "downgrade", parent_revision(PHASE_C_REVISION))
    engine = create_engine(url)
    try:
        assert "coding_submissions" not in sa_inspect(engine).get_table_names()
    finally:
        engine.dispose()
