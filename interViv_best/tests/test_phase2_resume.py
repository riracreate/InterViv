"""Phase 2: refresh/resume preserve server-owned session state.

- Repeated reads never extend deadlines or duplicate rounds/results.
- Duplicate submissions are rejected without double-counting.
- Resume eligibility comes from server ownership, lifecycle, and window.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app


def _make_user(prefix: str = "phase2resume") -> dict[str, str]:
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


def _mcq_answers(questions):
    return [{"question_id": q["id"],
             "selected_option_ids": [q["options"][0]["id"]]}
            for q in questions]


def test_refresh_preserves_config_round_timing_and_results() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("resume-refresh"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 3, "duration_minutes": 20},
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 1},
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    session_id = body["session_id"]
    first_deadline = body["expires_at"]
    first_questions = body["questions"]

    # Refresh before answering: identical assignment and deadline.
    for _ in range(3):
        fetched = client.get(f"/session/{session_id}", headers=headers)
        assert fetched.status_code == 200, fetched.text
        data = fetched.json()
        assert data["block_plan"] == body["block_plan"]
        assert data["active_round"]["expires_at"] == first_deadline
        assert (data["active_round"]["question_context"]["questions"]
                == first_questions)
        assert data["last_round"] == 1

    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answers": _mcq_answers(first_questions),
    })
    assert answer.status_code == 200, answer.text
    assert answer.json()["next_block_position"] == 2
    scored = answer.json()["final_score"]

    # Refresh after submit: completed result kept, active round advanced,
    # configuration unchanged.
    resumed = client.get(f"/session/{session_id}", headers=headers).json()
    assert resumed["block_plan"] == body["block_plan"]
    assert resumed["last_round"] == 1
    assert resumed["active_round"]["round"] == 2
    assert resumed["active_round"]["block_position"] == 2
    stored = get_database()["sessions"].find_one({"session_id": session_id})
    assert stored["rounds"][0]["final_score"] == scored
    assert stored["rounds"][0]["status"] == "submitted"
    assert len(stored["rounds"]) == 2


def test_duplicate_submit_rejected_without_double_count() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("resume-dup"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 2, "duration_minutes": 20},
    ]})
    session_id = start.json()["session_id"]
    payload = {"session_id": session_id, "round": 1,
               "answers": _mcq_answers(start.json()["questions"])}
    first = client.post("/session/answer", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["session_complete"] is True

    dup = client.post("/session/answer", headers=headers, json=payload)
    assert dup.status_code == 409
    stored = get_database()["sessions"].find_one({"session_id": session_id})
    assert len(stored["rounds"]) == 1
    assert stored["rounds"][0]["final_score"] == first.json()["final_score"]

    report = client.get(f"/dashboard/{session_id}", headers=headers).json()
    assert report["coverage"]["scored_rounds"] == 1
    assert report["block_results"][0]["scored_rounds"] == 1


def test_expired_timed_round_is_not_resumable() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("resume-expired"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 2, "duration_minutes": 20},
    ]})
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    progress = client.get("/dashboard/progress", headers=headers).json()
    assert progress["resumable_session"]["session_id"] == session_id

    db = get_database()
    stored = db["sessions"].find_one({"session_id": session_id})
    stored["rounds"][0]["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    db["sessions"].update_one({"session_id": session_id},
                              {"$set": {"rounds": stored["rounds"]}})
    progress = client.get("/dashboard/progress", headers=headers).json()
    assert progress["resumable_session"] is None


def test_resume_is_owner_only() -> None:
    client = TestClient(app)
    owner = _headers(_make_user("resume-owner"))
    stranger = _headers(_make_user("resume-stranger"))
    start = client.post("/session/start", headers=owner, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 2, "duration_minutes": 20},
    ]})
    session_id = start.json()["session_id"]
    assert client.get("/dashboard/progress", headers=owner).json()[
        "resumable_session"]["session_id"] == session_id
    assert client.get("/dashboard/progress", headers=stranger).json()[
        "resumable_session"] is None
    assert client.get(f"/session/{session_id}", headers=stranger).status_code == 403
