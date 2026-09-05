"""Production-path refresh/rehydration regression tests for Phase 2 rounds.

Covers the backend half of the refresh contract (the frontend half — the
production normalizer and countdown — is covered in
``frontend/tests/roundContract.test.js`` against the real helpers):

1. Start an authenticated 15-question MCQ round.
2. Record assigned question IDs and ``expires_at``.
3. Fetch the session again as a page refresh would (twice).
4. Confirm IDs, ordering, and ``expires_at`` are unchanged.
5. Repeat the equivalent flow for SQL.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app


def _make_user(prefix: str) -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one(
        {
            "id": user_id,
            "email": f"{prefix}-{user_id[:8]}@example.com",
            "name": f"Test {prefix}",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    return {"id": user_id, "token": create_access_token(user_id)}


def _start_mcq(client: TestClient, headers: dict[str, str]) -> dict:
    resp = client.post(
        "/session/start",
        json={
            "candidate_id": "",
            "skills": ["DBMS", "Python", "OS", "Computer Networks", "DSA"],
            "round_type": "mcq",
            "round_config": {"count": 15, "duration_minutes": 20, "negative_marking": 0.25},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _start_sql(client: TestClient, headers: dict[str, str]) -> dict:
    resp = client.post(
        "/session/start",
        json={
            "candidate_id": "",
            "skills": ["DBMS"],
            "round_type": "sql",
            "round_config": {"problem_id": "sql_prob_026", "duration_minutes": 25},
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_mcq_refresh_returns_identical_assignment_and_deadline() -> None:
    """MCQ page refresh: same 15 IDs in order, same expires_at, across fetches."""
    client = TestClient(app)
    user = _make_user("refresh-mcq")
    headers = {"Authorization": f"Bearer {user['token']}"}

    started = _start_mcq(client, headers)
    session_id = started["session_id"]
    start_ids = [q["id"] for q in started["questions"]]
    assert len(start_ids) == 15
    start_expires = started["expires_at"]
    assert start_expires

    for _ in range(2):
        resume = client.get(f"/session/{session_id}", headers=headers)
        assert resume.status_code == 200, resume.text
        body = resume.json()
        # Production normalizer mirrors active_round <-> current_round;
        # either key must carry the identical round.
        active = body.get("active_round") or body.get("current_round")
        assert active is not None
        assert active["round_type"] == "mcq"
        assert active["status"] == "in_progress"
        refreshed_ids = [q["id"] for q in active["question_context"]["questions"]]
        assert refreshed_ids == start_ids
        assert active["expires_at"] == start_expires


def test_sql_refresh_returns_identical_problem_and_deadline() -> None:
    """SQL page refresh: same problem, same sample, same expires_at, across fetches."""
    client = TestClient(app)
    user = _make_user("refresh-sql")
    headers = {"Authorization": f"Bearer {user['token']}"}

    started = _start_sql(client, headers)
    session_id = started["session_id"]
    start_ctx = started["question_context"]
    start_problem_id = start_ctx.get("id")
    assert start_problem_id
    start_expires = started["expires_at"]
    assert start_expires
    start_samples = started.get("sample_cases") or []

    for _ in range(2):
        resume = client.get(f"/session/{session_id}", headers=headers)
        assert resume.status_code == 200, resume.text
        body = resume.json()
        active = body.get("active_round") or body.get("current_round")
        assert active is not None
        assert active["round_type"] == "sql"
        assert active["status"] == "in_progress"
        assert active["expires_at"] == start_expires
        refreshed_ctx = active["question_context"] or {}
        assert refreshed_ctx.get("id") == start_problem_id
        refreshed_samples = refreshed_ctx.get("sample_cases") or []
        assert refreshed_samples == start_samples
