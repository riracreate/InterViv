"""Adzuna client + jobs explorer extension tests (mocked provider)."""

from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["JOBS_LIVE_FETCH"] = "0"
os.environ["ADZUNA_APP_ID"] = ""
os.environ["ADZUNA_APP_KEY"] = ""

from backend.auth.security import create_access_token, hash_password
from backend.config import get_settings
from backend.db import get_database
from backend.main import app
from modules.adzuna_client import (
    AdzunaClientError,
    normalize_country,
    safe_redirect_url,
)
from modules.jobs_explorer import (
    fetch_adzuna,
    load_fixture_jobs,
    reset_memory_store,
    search_jobs,
    set_fetch_error_override,
    set_fetch_override,
)


def _user():
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one({
        "id": user_id,
        "email": f"adz-{user_id[:8]}@example.com",
        "name": "Adzuna",
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    })
    return {"id": user_id, "token": create_access_token(user_id)}


def test_country_validation_no_silent_substitute():
    assert normalize_country("in") == "in"
    assert normalize_country("GB") == "gb"
    with pytest.raises(AdzunaClientError) as exc:
        normalize_country("xx")
    assert exc.value.kind == "unsupported_country"


def test_safe_redirect_rejects_unsafe():
    assert safe_redirect_url("https://www.adzuna.co.in/details/1")
    assert safe_redirect_url("javascript:alert(1)") is None
    assert safe_redirect_url("https://evil.example/phish") is None
    assert safe_redirect_url("data:text/html,hi") is None


def test_httpx_info_logs_redact_live_credentials(monkeypatch, caplog):
    """The underlying HTTP library must not log Adzuna query credentials."""
    from modules import adzuna_client

    monkeypatch.setenv("JOBS_LIVE_FETCH", "1")
    monkeypatch.setenv("ADZUNA_APP_ID", "test-sensitive-id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "test-sensitive-key")
    get_settings.cache_clear()
    original = httpx.Client
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"results": [], "count": 0}))
    monkeypatch.setattr(adzuna_client.httpx, "Client", lambda **kwargs: original(transport=transport, **kwargs))
    caplog.set_level(logging.INFO, logger="httpx")
    try:
        result = adzuna_client.fetch_search(q="python", where="", page=1, country="in")
        assert result["jobs"] == []
        assert "api.adzuna.com" in caplog.text
        assert "test-sensitive-id" not in caplog.text
        assert "test-sensitive-key" not in caplog.text
        assert caplog.text.count("[redacted]") >= 2
    finally:
        get_settings.cache_clear()


def test_live_empty_results_distinct_from_config_failure(monkeypatch):
    reset_memory_store()
    get_settings.cache_clear()
    monkeypatch.setenv("JOBS_LIVE_FETCH", "1")
    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    get_settings.cache_clear()

    set_fetch_override(lambda **kwargs: [])
    try:
        jobs, provenance = fetch_adzuna(q="nobody", where="", page=1, country="in")
        assert jobs == []
        assert provenance == "override"
    finally:
        set_fetch_override(None)

    set_fetch_error_override(AdzunaClientError("auth", "bad creds"))
    try:
        with pytest.raises(AdzunaClientError) as exc:
            fetch_adzuna(q="x", where="", page=1, country="in")
        assert exc.value.kind == "auth"
    finally:
        set_fetch_error_override(None)
        monkeypatch.setenv("JOBS_LIVE_FETCH", "0")
        get_settings.cache_clear()
        reset_memory_store()


def test_api_unsupported_country_422():
    client = TestClient(app)
    user = _user()
    headers = {"Authorization": f"Bearer {user['token']}"}
    resp = client.get("/jobs?q=python&country=zz", headers=headers)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "unsupported_country"


def test_api_rate_limit_and_timeout_kinds(monkeypatch):
    client = TestClient(app)
    user = _user()
    headers = {"Authorization": f"Bearer {user['token']}"}
    reset_memory_store()
    monkeypatch.setenv("JOBS_LIVE_FETCH", "1")
    monkeypatch.setenv("ADZUNA_APP_ID", "id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "key")
    get_settings.cache_clear()

    set_fetch_error_override(AdzunaClientError("rate_limit", "quota"))
    try:
        resp = client.get("/jobs?q=python&country=in", headers=headers)
        assert resp.status_code == 429
        assert resp.json()["detail"]["error"] == "rate_limit"
    finally:
        set_fetch_error_override(None)

    set_fetch_error_override(AdzunaClientError("timeout", "slow"))
    try:
        resp = client.get("/jobs?q=python&country=in", headers=headers)
        assert resp.status_code == 504
    finally:
        set_fetch_error_override(None)
        monkeypatch.setenv("JOBS_LIVE_FETCH", "0")
        get_settings.cache_clear()
        reset_memory_store()


def test_pagination_and_missing_fields_and_cache(monkeypatch):
    reset_memory_store()
    calls = {"n": 0}

    def page_fetch(**kwargs):
        calls["n"] += 1
        page = int(kwargs.get("page") or 1)
        if page == 1:
            return [{
                "id": "100",
                "title": "Backend Eng",
                "company": "Acme",
                "location": "Pune",
                "description": "Python SQL <script>x</script>",
                "redirect_url": "https://www.adzuna.co.in/details/100",
                "salary_min": 10,
                "salary_max": 20,
                "salary_is_predicted": 1,
            }]
        if page == 2:
            return [{
                "id": "101",
                "title": "Data Intern",
                "company": {"display_name": "Beta"},
                "location": {"display_name": "Mumbai"},
                "description": "SQL",
                "redirect_url": "https://www.adzuna.co.in/details/101",
            }]
        return []

    set_fetch_override(page_fetch)
    try:
        user = _user()
        first = search_jobs(q="backend", where="Pune", page=1, user_id=user["id"], country="in")
        assert first["cache_hit"] is False
        assert first["jobs"][0]["salary_is_predicted"] is True
        assert "<script" not in (first["jobs"][0].get("snippet") or "").lower() or "&lt;" in first["jobs"][0]["snippet"]
        assert first["jobs"][0]["attribution"]["label"] == "Jobs by Adzuna"
        second = search_jobs(q="backend", where="Pune", page=1, user_id=user["id"], country="in")
        assert second["cache_hit"] is True
        assert calls["n"] == 1
        page2 = search_jobs(q="backend", where="Pune", page=2, user_id=user["id"], country="in")
        assert page2["cache_hit"] is False
        assert page2["jobs"][0]["id"].endswith("101")
        assert calls["n"] == 2
    finally:
        set_fetch_override(None)
        reset_memory_store()


def test_prepare_then_confirm_preserves_practice_choice():
    client = TestClient(app)
    user = _user()
    headers = {"Authorization": f"Bearer {user['token']}"}
    reset_memory_store()
    listing = client.get("/jobs?q=intern&where=Pune&page=1", headers=headers)
    assert listing.status_code == 200
    job_id = listing.json()["jobs"][0]["id"]

    draft = client.post(f"/jobs/{job_id}/prepare", headers=headers, json={})
    assert draft.status_code == 200, draft.text
    body = draft.json()
    assert body["confirmation_required"] is True
    assert body["snippet_is_incomplete"] is True
    assert body["proposed_skills"]
    assert body["proposed_blocks"]

    unconfirmed = client.post(f"/jobs/{job_id}/practice", headers=headers, json={})
    assert unconfirmed.status_code == 200
    assert unconfirmed.json().get("started") is False

    started = client.post(
        f"/jobs/{job_id}/practice",
        headers=headers,
        json={
            "confirm": True,
            "skills": body["proposed_skills"][:2] or ["DSA"],
            "blocks": body["proposed_blocks"][:1],
            "company": body["company"],
            "role": body["role"],
        },
    )
    assert started.status_code == 200, started.text
    assert started.json().get("started") is True
    assert started.json().get("session_id")
    reset_memory_store()


def test_httpx_mock_live_search_success(monkeypatch):
    """Bounded live-path unit test with httpx mock (no real network)."""
    reset_memory_store()
    monkeypatch.setenv("JOBS_LIVE_FETCH", "1")
    monkeypatch.setenv("ADZUNA_APP_ID", "demo-id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "demo-key")
    get_settings.cache_clear()

    payload = {
        "results": [{
            "id": "9",
            "title": "SWE",
            "company": {"display_name": "Co"},
            "location": {"display_name": "Delhi"},
            "description": "Python",
            "redirect_url": "https://www.adzuna.co.in/details/9",
            "salary_min": 100,
            "salary_max": 200,
            "salary_is_predicted": 0,
        }],
        "count": 1,
    }

    class FakeResp:
        status_code = 200

        def json(self):
            return payload

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            assert "app_key" in (params or {})
            assert "/jobs/in/search/" in url
            # Ensure we never stringify credentials into assertions that log.
            return FakeResp()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    try:
        jobs, provenance = fetch_adzuna(q="python", where="Delhi", page=1, country="in")
        assert provenance == "live"
        assert len(jobs) == 1
        assert jobs[0]["salary_is_predicted"] is False
        assert jobs[0]["redirect_url"].startswith("https://")
    finally:
        monkeypatch.setenv("JOBS_LIVE_FETCH", "0")
        get_settings.cache_clear()
        reset_memory_store()
