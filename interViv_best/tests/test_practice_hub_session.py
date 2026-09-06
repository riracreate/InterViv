"""Ticket A: mixed MCQ + SQL session via round_plan."""

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


def _make_user() -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one(
        {
            "id": user_id,
            "email": f"practice-{user_id[:8]}@example.com",
            "name": "Practice User",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    return {"id": user_id, "token": create_access_token(user_id)}


def test_round_plan_mcq_then_sql_session() -> None:
    client = TestClient(app)
    user = _make_user()
    headers = {"Authorization": f"Bearer {user['token']}"}

    start = client.post(
        "/session/start",
        headers=headers,
        json={
            "skills": ["DBMS"],
            "round_plan": ["mcq", "sql"],
            "round_type": "mcq",
            "round_config": {"count": 3, "duration_minutes": 20},
        },
    )
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["round_type"] == "mcq"
    assert body["total_rounds"] == 2
    assert body["round_plan"] == ["mcq", "sql"]
    questions = (body.get("question_context") or {}).get("questions") or []
    assert len(questions) == 3

    answers = [
        {"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}
        for q in questions
    ]
    ans = client.post(
        "/session/answer",
        headers=headers,
        json={"session_id": body["session_id"], "round": 1, "answers": answers},
    )
    assert ans.status_code == 200, ans.text
    data = ans.json()
    assert data["session_complete"] is False
    assert data["next_round_type"] == "sql"
    assert data.get("next_question")
    assert data.get("next_question_context")
    assert "schema_ddl" in (data.get("next_question_context") or {})


def test_practice_bank_lists_mcq_and_sql_without_answers() -> None:
    client = TestClient(app)
    user = _make_user()
    headers = {"Authorization": f"Bearer {user['token']}"}
    resp = client.get("/session/practice-bank", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["counts"]["mcq"] > 0
    assert data["counts"]["sql"] > 0
    assert "correct_option_ids" not in data["mcq"][0]
    assert "reference_query" not in data["sql"][0]


def test_round_plan_rejects_unknown_type() -> None:
    client = TestClient(app)
    user = _make_user()
    headers = {"Authorization": f"Bearer {user['token']}"}
    resp = client.post(
        "/session/start",
        headers=headers,
        json={
            "skills": ["DBMS"],
            "round_plan": ["mcq", "coding"],
        },
    )
    assert resp.status_code == 422
