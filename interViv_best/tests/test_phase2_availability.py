"""Phase 2: reviewed-inventory availability; gate OFF preserves legacy practice.

The reviewed-only gate stays OFF in production. These tests pin the
effective selection policy both ways:

- Gate OFF + zero reviewed bundles: legacy/adaptive practice is fully
  available (availability probe and start both succeed).
- Gate ON (isolated, monkeypatched): empty reviewed inventory yields a
  clear unavailable outcome *before* any write — no session, no
  candidate, no silent switch to drafts or another topic.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from backend.auth.security import create_access_token, hash_password
from backend.config import get_settings
from backend.db import get_database
from backend.main import app
from modules import bundle_store
from tests.test_phase1a_bundles import CALIB, CHECK_OK, REASON


def _clear_settings() -> None:
    get_settings.cache_clear()


def _make_user(prefix: str = "phase2avail") -> dict[str, str]:
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


def _seed_reviewed(bundle_id: str, *, skill: str, topic: str,
                   difficulty: str, question: str) -> None:
    bundle_store.import_bundle({
        "bundle_id": bundle_id,
        "version": 1,
        "skill": skill,
        "topic": topic,
        "difficulty": difficulty,
        "question": question,
        "reference_answer": "Synthetic reviewed reference (test-only).",
        "required_concepts": [{"id": "c1", "descriptor": "test concept"}],
        "source": "human_authored",
        "author": "synthetic-test",
        "attribution": {"note": "isolated availability fixture"},
    }, actor_id="test")
    bundle_store.submit_for_review(bundle_id, 1, actor_id="admin")
    content_hash = bundle_store.get_version(bundle_id, 1)["content_hash"]
    for reviewer in ("reviewer-a", "reviewer-b"):
        bundle_store.record_decision(
            bundle_id, 1, reviewer_id=reviewer, content_hash=content_hash,
            decision="approve", checklist=CHECK_OK, reasons=REASON,
            calibration=CALIB,
        )


@pytest.fixture
def isolated_inventory(monkeypatch):
    """Empty bundle inventory, memory DB, gate OFF; restored afterwards."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "true")
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    _clear_settings()
    bundle_store.reset_memory_store()
    assert get_settings().reviewed_bundles_only is False
    yield
    bundle_store.reset_memory_store()
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    _clear_settings()


def _interview_blocks(skills, **over):
    block = {"round_type": "technical_short_answer", "category": "interview",
             "skills": list(skills), "count": 1}
    block.update(over)
    return [block]


def test_gate_off_zero_reviewed_legacy_interview_available(isolated_inventory) -> None:
    client = TestClient(app)
    user = _make_user("avail-legacy")
    headers = _headers(user)
    payload = {"blocks": _interview_blocks(["DBMS"])}

    probe = client.post("/session/availability", headers=headers, json=payload)
    assert probe.status_code == 200, probe.text
    body = probe.json()
    assert body["reviewed_only"] is False
    assert body["available"] is True
    assert body["blocks"][0]["available"] is True
    assert body["blocks"][0]["detail"]["selection_policy"] == "legacy_or_adaptive"

    start = client.post("/session/start", headers=headers, json=payload)
    assert start.status_code == 200, start.text
    assert start.json()["round_type"] == "technical_short_answer"


def test_availability_requires_auth_for_phase2_payloads(isolated_inventory) -> None:
    client = TestClient(app)
    user = _make_user("avail-auth")
    oa = {"blocks": [{"round_type": "mcq", "category": "oa",
                      "skills": ["DBMS"], "count": 3, "duration_minutes": 15}]}
    denied = client.post("/session/availability", json=oa)
    assert denied.status_code == 401
    ok = client.post("/session/availability", headers=_headers(user), json=oa)
    assert ok.status_code == 200, ok.text
    assert ok.json()["available"] is True


def test_availability_reports_mcq_shortage_without_starting(isolated_inventory) -> None:
    client = TestClient(app)
    user = _make_user("avail-short")
    headers = _headers(user)
    db = get_database()
    before = len(list(db["sessions"].find({})))
    probe = client.post("/session/availability", headers=headers, json={
        "blocks": [{"round_type": "mcq", "category": "oa", "skills": ["OOP"],
                    "count": 15, "duration_minutes": 15}],
    })
    assert probe.status_code == 200, probe.text
    body = probe.json()
    assert body["available"] is False
    reason = body["blocks"][0]["reason"]
    assert "OOP" in reason and "15" in reason
    assert len(list(db["sessions"].find({}))) == before


def test_gate_on_empty_inventory_unavailable_before_any_write(
    isolated_inventory, monkeypatch
) -> None:
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    _clear_settings()
    client = TestClient(app)
    user = _make_user("avail-gateon")
    headers = _headers(user)
    payload = {"blocks": _interview_blocks(["DBMS"])}
    db = get_database()
    sessions_before = len(list(db["sessions"].find({})))
    candidates_before = len(list(db["candidates"].find({})))

    probe = client.post("/session/availability", headers=headers, json=payload)
    assert probe.status_code == 200, probe.text
    body = probe.json()
    assert body["reviewed_only"] is True
    assert body["available"] is False
    reason = body["blocks"][0]["reason"]
    assert "DBMS" in reason and "reviewed" in reason.lower()

    # Start fails cleanly (422, not 503) before creating anything.
    start = client.post("/session/start", headers=headers, json=payload)
    assert start.status_code == 422, start.text
    assert "reviewed" in start.text.lower()
    assert len(list(db["sessions"].find({}))) == sessions_before
    assert len(list(db["candidates"].find({}))) == candidates_before


def test_gate_on_never_switches_to_another_topic(
    isolated_inventory, monkeypatch
) -> None:
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    _clear_settings()
    _seed_reviewed("python.avail-stocked", skill="Python", topic="Locks",
                   difficulty="easy",
                   question="Which construct releases a lock automatically?")
    client = TestClient(app)
    headers = _headers(_make_user("avail-noswitch"))

    missing = client.post("/session/availability", headers=headers, json={
        "blocks": _interview_blocks(["DBMS"]),
    })
    assert missing.status_code == 200, missing.text
    assert missing.json()["available"] is False
    assert "DBMS" in missing.json()["blocks"][0]["reason"]

    stocked = client.post("/session/availability", headers=headers, json={
        "blocks": _interview_blocks(["Python"], difficulty="easy"),
    })
    assert stocked.status_code == 200, stocked.text
    assert stocked.json()["available"] is True

    start = client.post("/session/start", headers=headers, json={
        "blocks": _interview_blocks(["Python"], difficulty="easy"),
    })
    assert start.status_code == 200, start.text
    body = start.json()
    assert "releases a lock" in body["question"]
    assert body["question_context"].get("bundle_id") == "python.avail-stocked"
    assert "ideal_answer" not in body["question_context"]
    assert "reference_answer" not in body["question_context"]


def test_gate_on_difficulty_pin_checked_upfront(
    isolated_inventory, monkeypatch
) -> None:
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    _clear_settings()
    _seed_reviewed("python.avail-easy", skill="Python", topic="Locks",
                   difficulty="easy",
                   question="Which construct releases a lock automatically?")
    client = TestClient(app)
    headers = _headers(_make_user("avail-diff"))

    hard = client.post("/session/availability", headers=headers, json={
        "blocks": _interview_blocks(["Python"], difficulty="hard"),
    })
    assert hard.status_code == 200, hard.text
    assert hard.json()["available"] is False
    assert "hard" in hard.json()["blocks"][0]["reason"]

    easy = client.post("/session/availability", headers=headers, json={
        "blocks": _interview_blocks(["Python"], difficulty="easy"),
    })
    assert easy.status_code == 200, easy.text
    assert easy.json()["available"] is True


def test_gate_on_drafts_never_count_as_available(
    isolated_inventory, monkeypatch
) -> None:
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    _clear_settings()
    bundle_store.import_bundle({
        "bundle_id": "dbms.avail-draft-only",
        "version": 1,
        "skill": "DBMS",
        "topic": "Indexing",
        "difficulty": "medium",
        "question": "Draft-only question?",
        "reference_answer": "Draft reference.",
        "required_concepts": [{"id": "c1", "descriptor": "draft concept"}],
        "source": "human_authored",
        "author": "synthetic-test",
        "attribution": {"note": "draft fixture"},
    }, actor_id="test")
    client = TestClient(app)
    headers = _headers(_make_user("avail-draft"))
    probe = client.post("/session/availability", headers=headers, json={
        "blocks": _interview_blocks(["DBMS"]),
    })
    assert probe.status_code == 200, probe.text
    assert probe.json()["available"] is False


def test_availability_rejects_invalid_shapes_like_start(isolated_inventory) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("avail-shape"))
    too_many = client.post("/session/availability", headers=headers, json={
        "blocks": [
            {"round_type": "technical_short_answer", "category": "interview",
             "skills": ["DBMS"], "count": 1}
            for _ in range(11)
        ],
    })
    assert too_many.status_code == 422
    assert "At most 10 blocks" in too_many.text


def test_gate_on_anonymous_legacy_probe_mirrors_start_policy(
    isolated_inventory, monkeypatch
) -> None:
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    _clear_settings()
    client = TestClient(app)
    # Same rule as start: a token is required before the probe runs.
    headers = _headers(_make_user("avail-anon"))
    probe = client.post("/session/availability", headers=headers, json={
        "skills": ["DBMS"], "rounds_per_skill": 1,
        "round_type": "technical_short_answer",
    })
    assert probe.status_code == 200, probe.text
    assert probe.json()["available"] is False
    assert "reviewed" in probe.json()["blocks"][0]["reason"].lower()


def test_gate_on_explicit_topic_pin_is_strict(
    isolated_inventory, monkeypatch
) -> None:
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    _clear_settings()
    _seed_reviewed("python.avail-locks", skill="Python", topic="Locks",
                   difficulty="easy",
                   question="Which construct releases a lock automatically?")
    client = TestClient(app)
    headers = _headers(_make_user("avail-pin"))

    # Matching pin: available and starts with the pinned bundle.
    pinned = client.post("/session/availability", headers=headers, json={
        "sub_domain": "Locks",
        "blocks": _interview_blocks(["Python"], difficulty="easy"),
    })
    assert pinned.status_code == 200, pinned.text
    assert pinned.json()["available"] is True
    start = client.post("/session/start", headers=headers, json={
        "sub_domain": "Locks",
        "blocks": _interview_blocks(["Python"], difficulty="easy"),
    })
    assert start.status_code == 200, start.text
    assert start.json()["question_context"]["bundle_id"] == "python.avail-locks"

    # Non-matching pin: unavailable, never silently switched to Locks.
    other = client.post("/session/availability", headers=headers, json={
        "sub_domain": "Sockets",
        "blocks": _interview_blocks(["Python"], difficulty="easy"),
    })
    assert other.status_code == 200, other.text
    assert other.json()["available"] is False
    assert "Sockets" in other.json()["blocks"][0]["reason"]
    denied = client.post("/session/start", headers=headers, json={
        "sub_domain": "Sockets",
        "blocks": _interview_blocks(["Python"], difficulty="easy"),
    })
    assert denied.status_code == 422, denied.text


def test_gate_on_mid_run_exhaustion_preserves_scored_answer(
    isolated_inventory, monkeypatch
) -> None:
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    _clear_settings()
    _seed_reviewed("python.avail-one", skill="Python", topic="Locks",
                   difficulty="easy",
                   question="Which construct releases a lock automatically?")
    client = TestClient(app)
    headers = _headers(_make_user("avail-exhaust"))
    start = client.post("/session/start", headers=headers, json={
        "blocks": _interview_blocks(["Python"], difficulty="easy", count=2),
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    # The single reviewed bundle is consumed by round 1; round 2 has
    # nothing eligible. The answer is still committed; progression blocks.
    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "A with statement releases the lock automatically.",
    })
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["final_score"] is not None
    assert body["progression_blocked"] is True
    assert "reviewed" in (body.get("progression_blocked_reason") or "").lower()
    assert body["next_question"] is None
    assert body["session_status"] == "content_blocked"

    stored = get_database()["sessions"].find_one({"session_id": session_id})
    assert stored["rounds"][0]["status"] == "submitted"
    assert stored["rounds"][0]["final_score"] is not None
    assert stored["rounds"][0].get("answer_text")
    assert len(stored["rounds"]) == 1
    assert stored["status"] == "content_blocked"

    # Duplicate submit of the preserved answer is a 409, not a rewrite.
    retry = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "Different text must not overwrite the committed attempt.",
    })
    assert retry.status_code == 409, retry.text
