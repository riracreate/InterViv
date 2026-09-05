"""Phase 2 auth attacks not covered by the dashboard ownership matrix."""

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


def _insert_candidate(user_id: str) -> str:
    candidate_id = str(uuid4())
    get_database()["candidates"].insert_one(
        {
            "candidate_id": candidate_id,
            "user_id": user_id,
            "resume_skills": ["DBMS"],
            "sub_domain_profile": {"DBMS": "general"},
            "elo_ratings": {"DBMS": 1500.0},
            "session_history": [],
        }
    )
    return candidate_id


def _start_payload(candidate_id: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "skills": ["DBMS"],
        "rounds_per_skill": 1,
        "round_type": "mcq",
        "round_config": {"count": 1},
    }


def test_phase2_start_rejects_cross_user_candidate() -> None:
    client = TestClient(app)
    owner = _make_user("start-owner")
    attacker = _make_user("start-attacker")
    candidate_id = _insert_candidate(owner["id"])

    response = client.post(
        "/session/start",
        json=_start_payload(candidate_id),
        headers={"Authorization": f"Bearer {attacker['token']}"},
    )

    print(f"cross-user Start status: {response.status_code}")
    assert response.status_code == 403, response.text
    assert "another user's candidate" in response.text


def test_phase2_start_rejects_forged_candidate_id() -> None:
    client = TestClient(app)
    user = _make_user("forged-candidate")
    forged_candidate_id = f"forged-{uuid4()}"

    response = client.post(
        "/session/start",
        json=_start_payload(forged_candidate_id),
        headers={"Authorization": f"Bearer {user['token']}"},
    )

    print(f"forged candidate_id status: {response.status_code}")
    assert response.status_code == 403, response.text
    assert "another user's candidate" in response.text
    assert get_database()["candidates"].find_one(
        {"candidate_id": forged_candidate_id}
    ) is None


def test_anonymous_legacy_session_cannot_reach_phase2_sql_preview() -> None:
    client = TestClient(app)
    user = _make_user("legacy-phase2")
    session_id = str(uuid4())
    get_database()["sessions"].insert_one(
        {
            "session_id": session_id,
            "candidate_id": str(uuid4()),
            "skill": "DBMS",
            "status": "active",
            "rounds": [
                {
                    "round": 1,
                    "round_type": "technical_short_answer",
                    "question": "Explain normalization.",
                    "status": "in_progress",
                    "question_context": {},
                }
            ],
        }
    )

    response = client.post(
        "/session/sql/run",
        json={"session_id": session_id, "round": 1, "query": "SELECT 1;"},
        headers={"Authorization": f"Bearer {user['token']}"},
    )

    print(f"anonymous legacy to Phase 2 SQL preview status: {response.status_code}")
    assert response.status_code == 401, response.text
    assert "Anonymous sessions are not permitted" in response.text


def test_answer_payload_cannot_control_round_type_transition() -> None:
    client = TestClient(app)
    user = _make_user("round-transition")
    headers = {"Authorization": f"Bearer {user['token']}"}
    started = client.post(
        "/session/start",
        json=_start_payload(""),
        headers=headers,
    )
    assert started.status_code == 200, started.text
    session_id = started.json()["session_id"]

    response = client.post(
        "/session/answer",
        json={
            "session_id": session_id,
            "round": 1,
            "round_type": "sql",
            "answer_text": "SELECT 1;",
        },
        headers=headers,
    )

    print(f"request-controlled round_type transition status: {response.status_code}")
    assert response.status_code == 422, response.text
    assert "Unknown extra fields rejected" in response.text
    stored_round = get_database()["sessions"].find_one(
        {"session_id": session_id}
    )["rounds"][0]
    assert stored_round["round_type"] == "mcq"
    assert stored_round["status"] == "in_progress"
