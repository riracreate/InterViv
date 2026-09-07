"""Phase D: target context and learning collections on SQLAlchemy.

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
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig

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


def _clear_db_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def sa_url(tmp_path, monkeypatch):
    db_file = tmp_path / "phased.db"
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


def _make_user(prefix="d1"):
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


def _headers(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def test_target_context_survives_dispose_and_reopen(sa_url) -> None:
    client = TestClient(app)
    user = _make_user("d-target")
    headers = _headers(user)
    saved = client.put("/target-context/me", headers=headers, json={
        "company_id": "tcs",
        "role_id": "tcs_swe",
        "jd_text": "Build APIs.",
        "jd_source": "paste",
    })
    assert saved.status_code == 200, saved.text
    target = saved.json()["target"]
    assert target["company_id"] == "tcs"
    assert target["role_id"] == "tcs_swe"
    assert target["jd_text"] == "Build APIs."
    assert target["jd_source"] == "paste"

    get_engine().dispose()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()

    fetched = client.get("/target-context/me", headers=headers)
    assert fetched.status_code == 200, fetched.text
    again = fetched.json()["target"]
    assert again["company_id"] == "tcs"
    assert again["role_id"] == "tcs_swe"
    assert again["jd_text"] == "Build APIs."
    assert again["required_skills"]

    db = get_database()
    row = db["target_contexts"].find_one({"user_id": user["id"]})
    for key in ("company_id", "role_id", "job_id", "jd_source", "jd_text",
                "resume_ref", "updated_at"):
        assert key in row, key


def test_learning_collections_round_trip_on_sqlalchemy(sa_url) -> None:
    db = get_database()
    user_id = "d-user"
    now = datetime.now(timezone.utc)
    db["retry_sets"].insert_one({
        "id": "rs1", "user_id": user_id, "name": "Retry DBMS",
        "items": [{"item_type": "mcq", "item_id": "q1", "skill": "DBMS"}],
        "source": "missed-topics", "created_at": now,
    })
    db["bookmarks"].insert_one({
        "user_id": user_id, "item_type": "coding",
        "item_id": "coding_two_sum", "created_at": now,
    })
    db["assistance_events"].insert_one({
        "id": "ev1", "user_id": user_id, "item_type": "mcq",
        "item_id": "q1", "kind": "hint", "session_id": "s1",
        "round": 1, "created_at": now,
    })

    get_engine().dispose()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()

    db = get_database()
    retry = db["retry_sets"].find_one({"id": "rs1"})
    assert retry["items"][0]["skill"] == "DBMS"
    assert retry["name"] == "Retry DBMS"
    bookmark = db["bookmarks"].find_one({
        "user_id": user_id, "item_type": "coding", "item_id": "coding_two_sum",
    })
    assert bookmark is not None
    event = db["assistance_events"].find_one({"id": "ev1"})
    assert event["kind"] == "hint"
    assert event["session_id"] == "s1"
    assert event["round"] == 1


def test_alembic_upgrade_downgrade_reupgrade_phase_d(tmp_path, monkeypatch) -> None:
    db_file = tmp_path / "phased_mig.db"
    url = f"sqlite:///{db_file}"
    _clear_db_caches()
    _run_alembic(url, "upgrade", "head")

    engine = create_engine(url)
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    for table in ("target_contexts", "retry_sets", "bookmarks", "assistance_events"):
        assert table in tables, table
    round_cols = {c["name"] for c in inspector.get_columns("rounds")}
    assert "assisted" in round_cols
    assert "assistance_kinds" in round_cols
    engine.dispose()

    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_db_caches()
    try:
        db = get_database()
        now = datetime.now(timezone.utc)
        db["target_contexts"].update_one(
            {"user_id": "u-mig"},
            {"$set": {
                "user_id": "u-mig", "company_id": "tcs", "role_id": "tcs_swe",
                "job_id": None, "jd_source": "role", "jd_text": None,
                "resume_ref": None, "updated_at": now,
            }},
            upsert=True,
        )
        back = db["target_contexts"].find_one({"user_id": "u-mig"})
        assert back["company_id"] == "tcs"
        assert back["role_id"] == "tcs_swe"
        db["retry_sets"].insert_one({
            "id": "rs-mig", "user_id": "u-mig", "name": "n",
            "items": [{"item_type": "mcq", "item_id": "q"}],
            "source": "missed-topics", "created_at": now,
        })
        assert db["retry_sets"].find_one({"id": "rs-mig"})["items"][0]["item_id"] == "q"
    finally:
        try:
            get_engine().dispose()
        except Exception:
            pass
        _clear_db_caches()

    # Pin: downgrade to the pre-Phase-D revision. Head is now 20260907_0007
    # (Phase E); ``-1`` would only drop system_design_attempts and leave
    # Phase D tables in place, which is the wrong assertion for this test.
    _run_alembic(url, "downgrade", "20260907_0005")
    engine = create_engine(url)
    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    assert "target_contexts" not in tables
    assert "retry_sets" not in tables
    assert "bookmarks" not in tables
    assert "assistance_events" not in tables
    round_cols = {c["name"] for c in inspector.get_columns("rounds")}
    assert "assisted" not in round_cols
    engine.dispose()

    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    tables = sa_inspect(engine).get_table_names()
    assert "target_contexts" in tables
    assert "system_design_attempts" in tables
    engine.dispose()
    # Alembic's env.py caches get_settings() while DATABASE_URL is still
    # monkeypatched. Clear so later in-memory tests do not inherit SQL.
    _clear_db_caches()
