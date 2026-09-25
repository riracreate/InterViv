"""Slugs are the target identifiers outside the database, in both modes."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.db.sqlalchemy_store import (
    _sessionmaker,
    create_all_for_smoke,
    get_engine,
    get_sqlalchemy_database,
)
from backend.main import app
from backend import config as app_config


def _clear_db_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


def _user(prefix: str) -> dict[str, str]:
    user_id = str(uuid4())
    get_database()["users"].insert_one({
        "id": user_id,
        "email": f"{prefix}-{user_id[:8]}@example.com",
        "name": prefix,
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    })
    return {"id": user_id, "token": create_access_token(user_id)}


def _headers(user: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def _assert_slug_surface(client: TestClient, user: dict[str, str]) -> None:
    headers = _headers(user)
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["user"]["target_company_id"] == "tcs"
    assert me.json()["user"]["target_role_id"] == "tcs_swe"

    progress = client.get("/dashboard/progress", headers=headers)
    assert progress.status_code == 200, progress.text
    body = progress.json()
    assert body["user"]["target_company_id"] == "tcs"
    assert body["user"]["target_role_id"] == "tcs_swe"
    assert body["target"]["role_id"] == "tcs_swe"

    gap = client.get("/gap-analysis/me/tcs_swe", headers=headers)
    assert gap.status_code == 200, gap.text
    roadmap = client.get("/roadmap/me/tcs_swe?days=30", headers=headers)
    assert roadmap.status_code == 200, roadmap.text
    plan = client.post(
        "/coach/plan",
        headers=headers,
        json={"goal_text": "Prepare for TCS", "include_dashboard": False},
    )
    assert plan.status_code == 200, plan.text


def _stored_slugs(user_id: str) -> tuple[str | None, str | None]:
    context = get_database()["target_contexts"].find_one({"user_id": user_id}) or {}
    return context.get("company_id"), context.get("role_id")


@pytest.fixture
def memory_client(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "true")
    _clear_db_caches()
    return TestClient(app)


@pytest.fixture
def sql_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'slugs.db'}")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_db_caches()
    create_all_for_smoke()
    from backend.db.company_seed import seed_company_graph

    seed_company_graph()
    client = TestClient(app)
    yield client
    get_engine().dispose()
    _clear_db_caches()


@pytest.mark.parametrize("mode", ["memory", "sql"])
def test_saved_target_is_a_slug_in_both_modes(mode, memory_client, sql_client):
    client = memory_client if mode == "memory" else sql_client
    user = _user(f"slug-{mode}")
    saved = client.put(
        "/target-context/me",
        headers=_headers(user),
        json={"company_id": "tcs", "role_id": "tcs_swe"},
    )
    assert saved.status_code == 200, saved.text
    _assert_slug_surface(client, user)


@pytest.mark.parametrize("mode", ["memory", "sql"])
def test_both_write_paths_store_the_same_slugs(mode, memory_client, sql_client):
    client = memory_client if mode == "memory" else sql_client
    via_put = _user(f"put-{mode}")
    via_patch = _user(f"patch-{mode}")
    put = client.put(
        "/target-context/me",
        headers=_headers(via_put),
        json={"company_id": "tcs", "role_id": "tcs_swe"},
    )
    patch = client.patch(
        "/auth/me/target",
        headers=_headers(via_patch),
        json={"target_company_id": "tcs", "target_role_id": "tcs_swe"},
    )
    assert put.status_code == 200, put.text
    assert patch.status_code == 200, patch.text
    assert _stored_slugs(via_put["id"]) == ("tcs", "tcs_swe")
    assert _stored_slugs(via_patch["id"]) == ("tcs", "tcs_swe")
    assert client.get("/auth/me", headers=_headers(via_patch)).json()["user"]["target_role_id"] == "tcs_swe"
