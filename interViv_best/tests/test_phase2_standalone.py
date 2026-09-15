"""Phase 2: standalone journeys need no resume/JD/company/role or builder.

Verbal-only, OA-only, SQL-only, and Interview-only each run
start → answer → submit → completion → report from a single-block
payload. Server caps (MAX_BLOCKS / MAX_TOTAL_ROUNDS) are enforced.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app


def _make_user(prefix: str = "phase2solo") -> dict[str, str]:
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


def _sql_reference(session_id: str, round_number: int) -> str:
    raw = get_database()["sessions"].find_one({"session_id": session_id})
    round_doc = next(r for r in raw["rounds"] if r["round"] == round_number)
    return (round_doc.get("question_context") or {}).get("reference_query") or "SELECT 1"


def test_verbal_only_journey() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("solo-verbal"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "verbal",
         "skills": ["Verbal Ability"], "count": 5, "duration_minutes": 10},
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["total_rounds"] == 1
    assert len(body["block_plan"]) == 1
    assert len(body["questions"]) == 5

    answer = client.post("/session/answer", headers=headers, json={
        "session_id": body["session_id"], "round": 1,
        "answers": _mcq_answers(body["questions"]),
    })
    assert answer.status_code == 200, answer.text
    assert answer.json()["session_complete"] is True

    report = client.get(f"/dashboard/{body['session_id']}", headers=headers)
    assert report.status_code == 200, report.text
    blocks = report.json()["block_results"]
    assert len(blocks) == 1
    assert blocks[0]["block_category"] == "verbal"
    assert blocks[0]["scored_rounds"] == 1
    assert blocks[0]["average_score"] is not None


def test_oa_only_journey_with_topics_and_difficulty() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("solo-oa"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 4, "duration_minutes": 12, "difficulty": "easy"},
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["total_rounds"] == 1
    assert all(q.get("skill") == "DBMS" for q in body["questions"])

    answer = client.post("/session/answer", headers=headers, json={
        "session_id": body["session_id"], "round": 1,
        "answers": _mcq_answers(body["questions"]),
    })
    assert answer.status_code == 200, answer.text
    assert answer.json()["session_complete"] is True

    report = client.get(f"/dashboard/{body['session_id']}", headers=headers)
    assert report.status_code == 200, report.text
    blocks = report.json()["block_results"]
    assert blocks[0]["block_category"] == "oa"
    assert blocks[0]["skills"] == ["DBMS"]
    assert blocks[0]["scored_rounds"] == 1


def test_sql_only_journey() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("solo-sql"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "sql", "category": "sql",
         "count": 1, "duration_minutes": 15},
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["round_type"] == "sql"
    assert body["schema_ddl"]

    answer = client.post("/session/answer", headers=headers, json={
        "session_id": body["session_id"], "round": 1,
        "answer_text": _sql_reference(body["session_id"], 1),
    })
    assert answer.status_code == 200, answer.text
    assert answer.json()["session_complete"] is True

    report = client.get(f"/dashboard/{body['session_id']}", headers=headers)
    assert report.status_code == 200, report.text
    blocks = report.json()["block_results"]
    assert blocks[0]["block_category"] == "sql"
    assert blocks[0]["scored_rounds"] == 1


def test_interview_only_journey() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("solo-interview"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 2},
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["total_rounds"] == 2
    session_id = body["session_id"]

    first = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "Normalization organizes data to reduce redundancy.",
    })
    assert first.status_code == 200, first.text
    assert first.json()["session_complete"] is False
    assert first.json()["next_round_type"] == "technical_short_answer"

    second = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 2,
        "answer_text": "An index speeds up lookups on a column.",
    })
    assert second.status_code == 200, second.text
    assert second.json()["session_complete"] is True

    report = client.get(f"/dashboard/{session_id}", headers=headers)
    assert report.status_code == 200, report.text
    blocks = report.json()["block_results"]
    assert len(blocks) == 1
    assert blocks[0]["block_category"] == "interview"
    assert blocks[0]["rounds"] == 2
    assert blocks[0]["scored_rounds"] == 2
    assert blocks[0]["average_score"] is not None


def test_server_enforces_max_blocks() -> None:
    client = TestClient(app)
    user = _make_user("solo-caps")
    headers = _headers(user)
    resp = client.post("/session/start", headers=headers, json={
        "blocks": [
            {"round_type": "technical_short_answer", "category": "interview",
             "skills": ["DBMS"], "count": 1}
            for _ in range(11)
        ],
    })
    assert resp.status_code == 422
    assert "At most 10 blocks" in resp.text
    assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None


def test_server_enforces_max_total_rounds() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("solo-caps-rounds"))
    resp = client.post("/session/start", headers=headers, json={
        "blocks": [
            {"round_type": "technical_short_answer", "category": "interview",
             "skills": ["DBMS"], "count": 6}
            for _ in range(10)
        ],
    })
    assert resp.status_code == 422
    assert "maximum is 50" in resp.text


def test_fifty_rounds_is_accepted_at_start() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("solo-caps-ok"))
    resp = client.post("/session/start", headers=headers, json={
        "blocks": [
            {"round_type": "technical_short_answer", "category": "interview",
             "skills": ["DBMS"], "count": 5}
            for _ in range(10)
        ],
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["total_rounds"] == 50
