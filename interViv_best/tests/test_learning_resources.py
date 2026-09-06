"""Ticket B — learning resources API + seed."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app
from modules.learning_resources import (
    ensure_seeded,
    list_resources,
    load_seed_fixture,
    reset_memory_store,
)


def _make_user() -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one(
        {
            "id": user_id,
            "email": f"resources-{user_id[:8]}@example.com",
            "name": "Resources User",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    return {"id": user_id, "token": create_access_token(user_id)}


@pytest.fixture(autouse=True)
def _reset_resources():
    reset_memory_store()
    ensure_seeded()
    yield
    reset_memory_store()


def test_seed_returns_for_known_skill() -> None:
    payload = list_resources(skill_id="DBMS")
    assert payload["count"] >= 2
    assert payload["skill"] == "DBMS"
    titles = {r["title"] for r in payload["resources"]}
    assert any("PostgreSQL" in t for t in titles)
    for level, rows in payload["by_level"].items():
        assert len(rows) <= 3


def test_unknown_skill_returns_empty() -> None:
    payload = list_resources(skill_id="NotARealSkillXYZ")
    assert payload["resources"] == []
    assert payload["count"] == 0


def test_question_id_filter() -> None:
    payload = list_resources(question_id="mcq_dbms_001")
    assert payload["count"] >= 1
    assert all(r.get("question_id") == "mcq_dbms_001" for r in payload["resources"])


def test_resources_endpoint_auth_and_seed() -> None:
    client = TestClient(app)
    assert client.get("/resources?skill_id=DBMS").status_code == 401
    user = _make_user()
    headers = {"Authorization": f"Bearer {user['token']}"}
    resp = client.get("/resources?skill_id=DSA", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["count"] >= 2
    assert body["resources"][0]["url"].startswith("http")


def test_unique_skill_url_constraint_sqlalchemy(monkeypatch: pytest.MonkeyPatch) -> None:
    """When SQL is available, (skill_id, url) must be unique; otherwise skip."""
    database_url = os.getenv("DATABASE_URL") or ""
    if not database_url.strip():
        pytest.skip("DATABASE_URL not set — unique constraint covered by model UniqueConstraint")

    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    from backend.config import get_settings

    get_settings.cache_clear()
    try:
        from sqlalchemy import select

        from backend.db.sqlalchemy_models import LearningResourceRow, SkillRow
        from backend.db.sqlalchemy_store import session_scope
        from modules.learning_resources import ensure_seeded

        ensure_seeded()
        with session_scope() as session:
            skill = session.scalars(select(SkillRow).where(SkillRow.canonical_name == "DBMS")).first()
            assert skill is not None
            session.add(
                LearningResourceRow(
                    skill_id=skill.id,
                    level="beginner",
                    title="dup",
                    url="https://www.postgresql.org/docs/current/tutorial.html",
                    source="docs",
                    created_at=datetime.now(timezone.utc),
                )
            )
            with pytest.raises(IntegrityError):
                session.flush()
    finally:
        get_settings.cache_clear()


def test_memory_seed_is_idempotent_and_unique_by_skill_url() -> None:
    ensure_seeded()
    first = list_resources(skill_id="Python")["count"]
    ensure_seeded()
    second = list_resources(skill_id="Python")["count"]
    assert first == second
    urls = [r["url"] for r in list_resources(skill_id="Python")["resources"]]
    assert len(urls) == len(set(urls))


def test_seed_fixture_skips_hr_and_has_no_junk_flags() -> None:
    rows = load_seed_fixture()
    skills = {r["skill"] for r in rows}
    assert "HR/Professional Judgment" not in skills
    assert all(not r.get("_skip_reason") for r in rows)
