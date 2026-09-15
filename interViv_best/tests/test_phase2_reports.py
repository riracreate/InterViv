"""Phase 2: per-block reports carry each block's own metric and counts.

- Every block reports its own average (never blended across blocks here);
  attempted / scored / unscored counts are distinguished server-side.
- Zero is a real score; no measurement is null.
- Historical (legacy-shaped) sessions keep their report shape.
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


def _make_user(prefix: str = "phase2reps") -> dict[str, str]:
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


def test_composed_session_reports_each_block_own_metric() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("reps-mixed"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "verbal",
         "skills": ["Verbal Ability"], "count": 3, "duration_minutes": 10},
        {"round_type": "sql", "category": "sql",
         "count": 1, "duration_minutes": 15},
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 1},
    ]})
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    ans1 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answers": _mcq_answers(start.json()["questions"]),
    })
    assert ans1.status_code == 200, ans1.text
    ans2 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 2,
        "answer_text": _sql_reference(session_id, 2),
    })
    assert ans2.status_code == 200, ans2.text
    ans3 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 3,
        "answer_text": "A primary key uniquely identifies each row.",
    })
    assert ans3.status_code == 200, ans3.text
    assert ans3.json()["session_complete"] is True

    report = client.get(f"/dashboard/{session_id}", headers=headers)
    assert report.status_code == 200, report.text
    body = report.json()
    blocks = body["block_results"]
    assert [b["block_category"] for b in blocks] == ["verbal", "sql", "interview"]
    assert [b["block_position"] for b in blocks] == [1, 2, 3]
    for block in blocks:
        assert block["rounds"] == 1
        assert block["attempted_rounds"] == 1
        assert block["scored_rounds"] == 1
        assert block["unscored_rounds"] == 0
        assert block["average_score"] is not None
    # Each block average equals its own round score (no blending here).
    by_category = {b["block_category"]: b for b in blocks}
    rounds = {r["round"]: r for r in body["rounds"]}
    assert by_category["verbal"]["average_score"] == rounds[1]["final_score"]
    assert by_category["sql"]["average_score"] == rounds[2]["final_score"]
    assert by_category["interview"]["average_score"] == rounds[3]["final_score"]
    assert body["coverage"]["scored_rounds"] == 3
    assert body["coverage"]["unscored_rounds"] == []


def test_repeated_oa_blocks_keep_distinct_identities_and_metrics() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("reps-repeat"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 2, "duration_minutes": 10},
        {"round_type": "mcq", "category": "oa", "skills": ["OOP"],
         "count": 2, "duration_minutes": 10},
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["block_plan"][0]["id"] != body["block_plan"][1]["id"]
    session_id = body["session_id"]
    ans1 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answers": _mcq_answers(body["questions"]),
    })
    assert ans1.status_code == 200, ans1.text
    assert ans1.json()["next_block_position"] == 2

    report = client.get(f"/dashboard/{session_id}", headers=headers)
    assert report.status_code == 200, report.text
    blocks = report.json()["block_results"]
    assert len(blocks) == 2
    assert blocks[0]["block_id"] != blocks[1]["block_id"]
    assert blocks[0]["skills"] == ["DBMS"]
    assert blocks[1]["skills"] == ["OOP"]
    assert blocks[0]["scored_rounds"] == 1
    assert blocks[1]["scored_rounds"] == 0
    assert blocks[1]["unscored_rounds"] == 1
    assert blocks[1]["average_score"] is None


def test_expired_round_is_unscored_and_unattempted_not_zero() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("reps-expired"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 2, "duration_minutes": 10},
    ]})
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    # Let the round expire without answering, then read the report.
    db = get_database()
    stored = db["sessions"].find_one({"session_id": session_id})
    stored["rounds"][0]["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    db["sessions"].update_one({"session_id": session_id},
                              {"$set": {"rounds": stored["rounds"]}})

    report = client.get(f"/dashboard/{session_id}", headers=headers)
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["averages"]["final_score"] is None
    block = body["block_results"][0]
    assert block["attempted_rounds"] == 0
    assert block["scored_rounds"] == 0
    assert block["unscored_rounds"] == 1
    assert block["average_score"] is None
    assert body["coverage"]["unscored_rounds"][0]["round"] == 1


def test_scored_zero_stays_zero_not_null() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("reps-zero"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 1, "duration_minutes": 10},
    ]})
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    question = start.json()["questions"][0]
    # Every option selected: negative marking floors the score at 0.
    options = [o["id"] for o in question["options"]]
    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answers": [{"question_id": question["id"],
                     "selected_option_ids": options}],
    })
    assert answer.status_code == 200, answer.text
    assert answer.json()["final_score"] == 0.0

    report = client.get(f"/dashboard/{session_id}", headers=headers)
    body = report.json()
    assert body["averages"]["final_score"] == 0.0
    block = body["block_results"][0]
    assert block["attempted_rounds"] == 1
    assert block["scored_rounds"] == 1
    assert block["average_score"] == 0.0


def test_legacy_shaped_session_report_shape_preserved() -> None:
    client = TestClient(app)
    user = _make_user("reps-legacy")
    headers = _headers(user)
    db = get_database()
    session_id = f"legacy-{uuid4().hex[:8]}"
    db["sessions"].insert_one({
        "session_id": session_id,
        "candidate_id": str(uuid4()),
        "user_id": user["id"],
        "skill": "DBMS",
        "skills": ["DBMS"],
        "status": "completed",
        "total_rounds": 1,
        "rounds": [{
            "round": 1,
            "round_type": "technical_short_answer",
            "skill": "DBMS",
            "question": "Explain normalization.",
            "answer_text": "Organize data to reduce redundancy.",
            "status": "submitted",
            "final_score": 62.5,
            "nlp_score": 60.0,
            "kg_score": 65.0,
            "difficulty": "medium",
            "feedback": {"content": [], "strengths": [], "next_step": "Keep going."},
            "elo_after": 1210.0,
            "question_context": {"topic": "Normalization"},
        }],
    })
    report = client.get(f"/dashboard/{session_id}", headers=headers)
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["averages"]["final_score"] == 62.5
    assert body["breakdown"] == {"Good": 0, "Average": 1, "Poor": 0}
    assert body["coverage"]["scored_rounds"] == 1
    assert body["block_results"][0]["attempted_rounds"] == 1
    assert body["block_results"][0]["unscored_rounds"] == 0
    # No reference material invented for legacy rows without pins.
    assert body["rounds"][0]["ideal_answer"] in (None, "")
