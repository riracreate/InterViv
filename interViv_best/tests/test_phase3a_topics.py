"""Phase 3A: explicit topics are honored under both selection policies.

- Gate OFF: an explicit block topic must be served exactly; relaxation
  without a topic is preserved, including legacy session-level pins.
- Unsuppliable scope fails upfront (or at build) with an actionable
  unavailable outcome — never a silent substitution.
- Multi-skill blocks require the topic on every skill (split hint).
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


def _make_user(prefix: str = "phase3atopics") -> dict[str, str]:
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


def _interview_block(skills, topic=None, **over):
    block = {"round_type": "technical_short_answer", "category": "interview",
             "skills": list(skills), "count": 1}
    if topic is not None:
        block["topic"] = topic
    block.update(over)
    return block


def _round_sub_domain(session_id: str, round_number: int) -> str | None:
    raw = get_database()["sessions"].find_one({"session_id": session_id})
    round_doc = next(r for r in raw["rounds"] if r["round"] == round_number)
    return (round_doc.get("question_context") or {}).get("sub_domain")


def test_gate_off_pinned_topic_and_difficulty_served_exactly() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-exact"))
    # normalization exists at easy only; pinning easy serves it exactly.
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], topic="normalization",
                                    difficulty="easy")],
    })
    assert start.status_code == 200, start.text
    assert _round_sub_domain(start.json()["session_id"], 1) == "normalization"


def test_gate_off_unknown_topic_fails_upfront_without_session() -> None:
    client = TestClient(app)
    user = _make_user("t3a-unknown")
    headers = _headers(user)
    payload = {"blocks": [_interview_block(["DBMS"], topic="zzzz-nope")]}

    probe = client.post("/session/availability", headers=headers, json=payload)
    assert probe.status_code == 200, probe.text
    assert probe.json()["available"] is False
    assert "zzzz-nope" in probe.json()["blocks"][0]["reason"]

    start = client.post("/session/start", headers=headers, json=payload)
    assert start.status_code == 422, start.text
    assert "zzzz-nope" in start.text
    assert "DBMS" in start.text
    assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None


def test_gate_off_legacy_session_pin_still_relaxes() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-legacy"))
    # No explicit block topic: the legacy session-level pin keeps its
    # long-standing relaxed behavior (served from the skill bank).
    start = client.post("/session/start", headers=headers, json={
        "sub_domain": "zzzz-nope",
        "blocks": [_interview_block(["DBMS"])],
    })
    assert start.status_code == 200, start.text
    served = _round_sub_domain(start.json()["session_id"], 1)
    assert served != "zzzz-nope"


def test_gate_off_topic_difficulty_mismatch_names_offered_levels() -> None:
    client = TestClient(app)
    user = _make_user("t3a-diff")
    headers = _headers(user)
    payload = {"blocks": [_interview_block(["DBMS"], topic="normalization",
                                           difficulty="medium")]}
    probe = client.post("/session/availability", headers=headers, json=payload)
    assert probe.json()["available"] is False
    reason = probe.json()["blocks"][0]["reason"]
    assert "normalization" in reason and "easy" in reason

    start = client.post("/session/start", headers=headers, json=payload)
    assert start.status_code == 422, start.text
    assert "offered at: easy" in start.text
    assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None


def test_gate_off_adaptive_mismatch_fails_at_build_without_substitution() -> None:
    client = TestClient(app)
    user = _make_user("t3a-adaptive")
    headers = _headers(user)
    # Topic exists (probe passes) but fresh-user medium cannot supply it;
    # the build serves another topic and orchestration rejects it.
    payload = {"blocks": [_interview_block(["DBMS"], topic="normalization")]}
    assert client.post("/session/availability", headers=headers,
                       json=payload).json()["available"] is True
    start = client.post("/session/start", headers=headers, json=payload)
    assert start.status_code == 422, start.text
    assert "normalization" in start.text
    assert "offered at: easy" in start.text
    assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None


def test_gate_off_multi_skill_topic_requires_every_skill() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-multiskill"))
    # transactions exists for DBMS but not OOP: no silent skill drop.
    payload = {"blocks": [_interview_block(["DBMS", "OOP"],
                                           topic="transactions")]}
    probe = client.post("/session/availability", headers=headers, json=payload)
    assert probe.json()["available"] is False
    assert "OOP" in probe.json()["blocks"][0]["reason"]

    start = client.post("/session/start", headers=headers, json=payload)
    assert start.status_code == 422, start.text
    assert "OOP" in start.text
    assert "Split the block" in start.text


def test_gate_off_shared_topic_multi_skill_block_starts() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-shared"))
    # concurrency exists for both OS and Python; the opening OS round at
    # medium serves it exactly.
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["OS", "Python"], topic="concurrency")],
    })
    assert start.status_code == 200, start.text
    assert _round_sub_domain(start.json()["session_id"], 1) == "concurrency"


def test_gate_off_topic_exhaustion_preserves_scored_answer() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-exhaust"))
    # One transactions/medium row exists: round 2 cannot be supplied.
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], topic="transactions",
                                    difficulty="medium", count=2)],
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    candidate_id = start.json()["candidate_id"]

    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "ACID transactions keep related writes atomic.",
    })
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["final_score"] is not None
    assert body["feedback"]
    assert body["progression_blocked"] is True
    assert "transactions" in (body.get("progression_blocked_reason") or "")
    assert body["next_question"] is None
    assert body["session_complete"] is False
    assert body["session_status"] == "content_blocked"

    db = get_database()
    stored = db["sessions"].find_one({"session_id": session_id})
    assert stored["status"] == "content_blocked"
    assert stored.get("progression_blocked_reason")
    assert len(stored["rounds"]) == 1
    round_doc = stored["rounds"][0]
    assert round_doc["status"] == "submitted"
    assert round_doc["final_score"] is not None
    assert round_doc.get("answer_text")
    snapshot = round_doc.get("attempt_snapshot") or {}
    assert snapshot.get("digest")
    assert snapshot.get("feedback") == round_doc.get("feedback")

    # Elo and narration job joined the same attempt commit.
    candidate = db["candidates"].find_one({"candidate_id": candidate_id})
    assert float(candidate["elo_ratings"]["DBMS"]) == float(body["elo_after"])
    from modules.narration_jobs import narration_job_id
    job = db["narration_jobs"].find_one({"id": narration_job_id(session_id, 1)})
    assert job is not None
    assert job["status"] == "queued"
    assert job["snapshot_digest"] == snapshot["digest"]
    assert job["final_score"] == body["final_score"]

    # Duplicate submit of the preserved answer is still a 409, not a rewrite
    # or a second Elo / narration apply.
    elo_before_retry = float(candidate["elo_ratings"]["DBMS"])
    jobs_before = db["narration_jobs"].count_documents({})
    retry = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "Different text must not overwrite the committed attempt.",
    })
    assert retry.status_code == 409, retry.text
    again = db["sessions"].find_one({"session_id": session_id})
    assert again["rounds"][0]["final_score"] == round_doc["final_score"]
    assert again["rounds"][0]["answer_text"] == round_doc["answer_text"]
    assert again["rounds"][0]["attempt_snapshot"] == snapshot
    assert again["status"] == "content_blocked"
    assert len(again["rounds"]) == 1
    candidate_after = db["candidates"].find_one({"candidate_id": candidate_id})
    assert float(candidate_after["elo_ratings"]["DBMS"]) == elo_before_retry
    assert db["narration_jobs"].count_documents({}) == jobs_before


def test_gate_off_unrestricted_multi_skill_start_preserved() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-open"))
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS", "OOP"])],
    })
    assert start.status_code == 200, start.text
    assert start.json()["block_plan"][0]["topic"] is None
