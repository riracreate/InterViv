"""Greenhouse board search. No network."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("JOBS_LIVE_FETCH", "0")

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app
from modules.greenhouse_client import (
    filter_jobs,
    html_to_text,
    listing_from_api,
    safe_greenhouse_url,
)
from modules.jobs_explorer import get_job, reset_memory_store, search_greenhouse_jobs


def _make_user() -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one(
        {
            "id": user_id,
            "email": f"gh-{user_id[:8]}@example.com",
            "name": "Greenhouse User",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    return {"id": user_id, "token": create_access_token(user_id)}


def test_html_and_urls_stay_on_greenhouse_hosts() -> None:
    text = html_to_text("<style>x{}</style><script>alert(1)</script><p>Hello&nbsp;world</p>")
    assert "alert" not in text
    assert "Hello" in text
    assert "<" not in text
    escaped = html_to_text("&lt;p&gt;&lt;strong&gt;Hello&lt;/strong&gt;&lt;/p&gt;")
    assert "<" not in escaped
    assert "Hello" in escaped
    assert safe_greenhouse_url("https://boards.greenhouse.io/stripe/jobs/1")
    assert safe_greenhouse_url("https://stripe.com/jobs/listing/backend/1")
    assert safe_greenhouse_url("https://user:pass@stripe.com/jobs/1") is None
    assert safe_greenhouse_url("http://stripe.com/jobs/1") is None
    assert safe_greenhouse_url("javascript:alert(1)") is None
    item = listing_from_api(
        {
            "id": 9,
            "title": "Backend Engineer",
            "location": {"name": "Remote"},
            "absolute_url": "https://not-greenhouse.example/jobs/9",
            "content": "<p>Payments</p>",
        },
        "Stripe",
        "stripe",
    )
    assert item is not None
    assert item["redirect_url"] == "https://not-greenhouse.example/jobs/9"
    assert item["snippet"] == "Payments"


def test_missing_city_keeps_keyword_matches() -> None:
    jobs = [
        {"title": "Backend Engineer", "company": "Stripe", "location": "Remote", "snippet": ""},
        {"title": "Designer", "company": "Airbnb", "location": "Pune", "snippet": ""},
    ]
    matched, note = filter_jobs(jobs, q="backend", where="Pune")
    assert [job["company"] for job in matched] == ["Stripe"]
    assert note and "Pune" in note


def test_search_pages_without_network(monkeypatch) -> None:
    reset_memory_store()
    boards = [
        {
            "token": "stripe",
            "company": "Stripe",
            "external_id": "1",
            "title": "Backend Engineer",
            "location": "Remote",
            "redirect_url": "https://boards.greenhouse.io/stripe/jobs/1",
            "snippet": "",
            "updated_at": None,
        },
        {
            "token": "airbnb",
            "company": "Airbnb",
            "external_id": "2",
            "title": "Designer",
            "location": "Pune",
            "redirect_url": "https://evilgreenhouse.io/phish",
            "snippet": "<script>alert(1)</script>Design systems",
            "updated_at": None,
        },
    ]
    monkeypatch.setattr("modules.jobs_explorer.load_board_jobs", lambda: boards)
    monkeypatch.setattr(
        "modules.jobs_explorer.attach_descriptions",
        lambda jobs: [{**job, "snippet": job.get("snippet") or "Builds payment APIs"} for job in jobs],
    )
    user = _make_user()
    body = search_greenhouse_jobs(q="backend", where="Pune", page=1, user_id=user["id"])
    assert body["source"] == "greenhouse"
    assert body["provenance"] == "greenhouse"
    assert body["note"]
    assert len(body["jobs"]) == 1
    card = body["jobs"][0]
    assert card["company"] == "Stripe"
    assert card["redirect_url"] == "https://boards.greenhouse.io/stripe/jobs/1"
    assert "script" not in card["snippet"].lower()
    stored = get_job(card["id"])
    assert stored is not None
    assert stored["provider"] == "greenhouse"

    calls = {"n": 0}

    def _boom():
        calls["n"] += 1
        return boards

    monkeypatch.setattr("modules.jobs_explorer.load_board_jobs", _boom)
    again = search_greenhouse_jobs(q="backend", where="Pune", page=1, user_id=user["id"])
    assert again["cache_hit"] is True
    assert calls["n"] == 0
    reset_memory_store()


def test_unknown_source_is_rejected() -> None:
    client = TestClient(app)
    user = _make_user()
    response = client.get(
        "/jobs?source=linkedin",
        headers={"Authorization": f"Bearer {user['token']}"},
    )
    assert response.status_code == 422
