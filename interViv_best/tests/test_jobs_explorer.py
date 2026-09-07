"""Ticket D — jobs explorer cache, lexicon overlay, practice-for-role.
Phase O — live-fetch gate + provenance survives cache warm path.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("JOBS_LIVE_FETCH", "0")

from backend.auth.security import create_access_token, hash_password
from backend.config import get_settings
from backend.db import get_database
from backend.main import app
from modules.jobs_explorer import (
    fetch_adzuna,
    load_fixture_jobs,
    match_pct,
    reset_memory_store,
    search_jobs,
    set_fetch_override,
)


def _make_user() -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one(
        {
            "id": user_id,
            "email": f"jobs-{user_id[:8]}@example.com",
            "name": "Jobs User",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    return {"id": user_id, "token": create_access_token(user_id)}


def test_fixture_job_maps_known_lexicon_skill() -> None:
    jobs = load_fixture_jobs()
    assert jobs
    skills = set()
    for job in jobs:
        skills.update(job["skills"])
    assert "Python" in skills or "SQL" in skills or "DSA" in skills


def test_cache_hit_does_not_call_provider() -> None:
    reset_memory_store()
    calls = {"n": 0}

    def fake_fetch(**kwargs):
        calls["n"] += 1
        return load_fixture_jobs()[:2]

    set_fetch_override(fake_fetch)
    try:
        user = _make_user()
        first = search_jobs(q="backend", where="Pune", page=1, user_id=user["id"])
        assert first["cache_hit"] is False
        assert calls["n"] == 1
        second = search_jobs(q="backend", where="Pune", page=1, user_id=user["id"])
        assert second["cache_hit"] is True
        assert calls["n"] == 1  # no second provider call
    finally:
        set_fetch_override(None)
        reset_memory_store()


def test_default_jobs_live_fetch_skips_httpx(monkeypatch) -> None:
    """Under default JOBS_LIVE_FETCH=0, credentials must not trigger Adzuna HTTP."""
    reset_memory_store()
    monkeypatch.setenv("ADZUNA_APP_ID", "test-app-id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "test-app-key")
    monkeypatch.setenv("JOBS_LIVE_FETCH", "0")
    get_settings.cache_clear()

    class BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            raise AssertionError("Adzuna HTTP must not run when JOBS_LIVE_FETCH=0")

    monkeypatch.setattr("modules.jobs_explorer.httpx.Client", BoomClient)
    try:
        jobs, provenance = fetch_adzuna(q="backend", where="Pune", page=1)
        assert provenance == "fixture"
        assert len(jobs) >= 1
    finally:
        get_settings.cache_clear()
        reset_memory_store()


def test_live_fetch_enabled_without_credentials_uses_fixtures(monkeypatch) -> None:
    """Gate on + no credentials: same fixture path as today, honestly labeled."""
    reset_memory_store()
    monkeypatch.setenv("JOBS_LIVE_FETCH", "1")
    monkeypatch.delenv("ADZUNA_APP_ID", raising=False)
    monkeypatch.delenv("ADZUNA_APP_KEY", raising=False)
    get_settings.cache_clear()
    try:
        user = _make_user()
        body = search_jobs(q="intern", where="Pune", page=1, user_id=user["id"])
        assert body["provenance"] == "fixture"
        assert body["source"] == "fixture"
        assert body["empty_reason"]
        assert "ADZUNA" in body["empty_reason"]
        assert body["cache_hit"] is False
    finally:
        monkeypatch.setenv("JOBS_LIVE_FETCH", "0")
        get_settings.cache_clear()
        reset_memory_store()


def test_cache_hit_preserves_fixture_provenance_and_label() -> None:
    """Warm path: second request keeps fixture provenance, sample banner, fetched_at."""
    reset_memory_store()
    get_settings.cache_clear()
    user = _make_user()
    try:
        first = search_jobs(q="warm-path", where="Pune", page=1, user_id=user["id"])
        assert first["cache_hit"] is False
        assert first["source"] == "fixture"
        assert first["provenance"] == "fixture"
        assert first["empty_reason"]
        assert first["fetched_at"]
        assert all(j.get("provenance") == "fixture" for j in first["jobs"])

        second = search_jobs(q="warm-path", where="Pune", page=1, user_id=user["id"])
        assert second["cache_hit"] is True
        assert second["source"] == "fixture"
        assert second["provenance"] == "fixture"
        assert second["empty_reason"] == first["empty_reason"]
        assert second["fetched_at"] == first["fetched_at"]
        assert all(j.get("provenance") == "fixture" for j in second["jobs"])
    finally:
        reset_memory_store()


def test_match_pct_omitted_without_user_skills() -> None:
    assert match_pct(["Python", "SQL"], None) is None
    assert match_pct(["Python", "SQL"], []) is None
    assert match_pct(["Python", "SQL"], ["Python"]) == 50.0


def test_list_jobs_and_practice_session_shape() -> None:
    reset_memory_store()
    set_fetch_override(lambda **kwargs: load_fixture_jobs()[:2])
    client = TestClient(app)
    user = _make_user()
    headers = {"Authorization": f"Bearer {user['token']}"}

    # Seed resume skills so match_pct can appear
    get_database()["candidates"].insert_one(
        {
            "candidate_id": str(uuid4()),
            "user_id": user["id"],
            "resume_skills": ["Python", "SQL"],
            "elo_ratings": {},
            "session_history": [],
        }
    )

    listing = client.get("/jobs?q=intern&where=Pune&page=1", headers=headers)
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["count"] >= 1
    assert "disclaimer" in body
    job_id = body["jobs"][0]["id"]
    assert body["jobs"][0]["redirect_url"].startswith("http")

    practice = client.post(f"/jobs/{job_id}/practice", headers=headers)
    assert practice.status_code == 200, practice.text
    data = practice.json()
    assert data.get("session_id")
    assert data.get("navigate", "").startswith("/interview/")
    assert isinstance(data.get("skills"), list) and len(data["skills"]) >= 1
    assert data.get("round_plan")

    set_fetch_override(None)
    reset_memory_store()


def test_jobs_require_auth() -> None:
    client = TestClient(app)
    assert client.get("/jobs").status_code == 401
