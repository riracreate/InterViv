"""Phase 2: per-block interview topics end to end.

- Standalone and composed interview blocks accept an explicit topic;
  repeated blocks keep independent topics.
- The topic is recorded on each round and guides selection; an omitted
  topic keeps legacy behavior (unrestricted, never a "general" pin).
- Restrictions stay strict under the reviewed gate with no silent
  substitution; availability and start agree on the same payload.
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


def _make_user(prefix: str = "phase2topics") -> dict[str, str]:
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
        "attribution": {"note": "isolated topic fixture"},
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


def test_standalone_interview_topic_recorded_and_reported(isolated_inventory) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("topics-solo"))
    # Fresh candidates assess at medium; transactions/medium exists, so
    # legacy selection serves the pin exactly and deterministically.
    payload = {"blocks": [_interview_block(["DBMS"], topic="transactions")]}

    probe = client.post("/session/availability", headers=headers, json=payload)
    assert probe.status_code == 200, probe.text
    assert probe.json()["available"] is True
    assert probe.json()["blocks"][0]["topic"] == "transactions"
    assert probe.json()["blocks"][0]["detail"]["selection_policy"] == "legacy_or_adaptive"

    start = client.post("/session/start", headers=headers, json=payload)
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    assert start.json()["block_plan"][0]["topic"] == "transactions"
    assert _round_sub_domain(session_id, 1) == "transactions"

    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "ACID transactions keep related writes atomic.",
    })
    assert answer.status_code == 200, answer.text
    assert answer.json()["session_complete"] is True

    report = client.get(f"/dashboard/{session_id}", headers=headers)
    assert report.status_code == 200, report.text
    assert report.json()["block_plan"][0]["topic"] == "transactions"


def test_interview_inside_composed_session_keeps_topic(isolated_inventory) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("topics-composed"))
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 2, "duration_minutes": 10},
        _interview_block(["DBMS"], topic="transactions"),
        {"round_type": "sql", "category": "sql",
         "count": 1, "duration_minutes": 15},
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    assert [b["category"] for b in body["block_plan"]] == ["oa", "interview", "sql"]
    session_id = body["session_id"]

    ans1 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answers": [{"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}
                    for q in body["questions"]],
    })
    assert ans1.status_code == 200, ans1.text
    assert ans1.json()["next_block_category"] == "interview"
    assert _round_sub_domain(session_id, 2) == "transactions"

    ans2 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 2,
        "answer_text": "ACID transactions keep related writes atomic.",
    })
    assert ans2.status_code == 200, ans2.text
    assert ans2.json()["next_block_category"] == "sql"


def test_repeated_interview_blocks_keep_different_topics(isolated_inventory) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("topics-repeat"))
    # Pinned medium difficulty keeps both rounds deterministic: each
    # block's own topic is served exactly.
    start = client.post("/session/start", headers=headers, json={"blocks": [
        _interview_block(["DBMS"], topic="transactions", difficulty="medium"),
        _interview_block(["DBMS"], topic="joins", difficulty="medium"),
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["block_plan"][0]["id"] != body["block_plan"][1]["id"]
    session_id = body["session_id"]
    assert _round_sub_domain(session_id, 1) == "transactions"

    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answer_text": "ACID transactions keep related writes atomic.",
    })
    assert answer.status_code == 200, answer.text
    assert answer.json()["next_block_position"] == 2
    assert _round_sub_domain(session_id, 2) == "joins"


def test_topic_omitted_keeps_legacy_unrestricted_behavior(isolated_inventory) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("topics-omitted"))
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"])],
    })
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["block_plan"][0]["topic"] is None
    session_id = body["session_id"]
    # Unrestricted: legacy selection serves from the skill bank and the
    # round records what was served (no literal pin either way).
    served = _round_sub_domain(session_id, 1)
    assert served in ("aggregation", "indexes", "joins", "normalization",
                      "query_planning", "transactions")


def test_literal_general_topic_means_unrestricted(
    isolated_inventory, monkeypatch
) -> None:
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    _clear_settings()
    _seed_reviewed("python.topics-locks", skill="Python", topic="Locks",
                   difficulty="easy",
                   question="Which construct releases a lock automatically?")
    client = TestClient(app)
    headers = _headers(_make_user("topics-general"))
    # The reserved default never pins: the unpinned Locks bundle serves.
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["Python"], topic="general",
                                    difficulty="easy")],
    })
    assert start.status_code == 200, start.text
    assert start.json()["question_context"]["bundle_id"] == "python.topics-locks"


def test_gate_on_explicit_topic_stays_strict(
    isolated_inventory, monkeypatch
) -> None:
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    _clear_settings()
    _seed_reviewed("python.topics-strict", skill="Python", topic="Locks",
                   difficulty="easy",
                   question="Which construct releases a lock automatically?")
    client = TestClient(app)
    headers = _headers(_make_user("topics-strict"))
    payload = {"blocks": [_interview_block(["Python"], topic="Sockets",
                                           difficulty="easy")]}
    db = get_database()
    sessions_before = len(list(db["sessions"].find({})))

    probe = client.post("/session/availability", headers=headers, json=payload)
    assert probe.status_code == 200, probe.text
    assert probe.json()["available"] is False
    assert "Sockets" in probe.json()["blocks"][0]["reason"]

    # Matching pin works and selects the pinned bundle.
    ok = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["Python"], topic="Locks",
                                    difficulty="easy")],
    })
    assert ok.status_code == 200, ok.text
    assert ok.json()["question_context"]["bundle_id"] == "python.topics-strict"

    # Non-matching pin fails before any session write; never substituted.
    denied = client.post("/session/start", headers=headers, json=payload)
    assert denied.status_code == 422, denied.text
    assert "Sockets" in denied.text
    assert "Locks" not in denied.text
    assert len(list(db["sessions"].find({}))) == sessions_before + 1


def test_topic_rejected_on_non_interview_blocks(isolated_inventory) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("topics-scope"))
    resp = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 2, "duration_minutes": 10, "topic": "normalization"},
    ]})
    assert resp.status_code == 422
    assert "only supported for interview" in resp.text


def test_topic_length_capped(isolated_inventory) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("topics-long"))
    resp = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], topic="x" * 121)],
    })
    assert resp.status_code == 422
    assert "at most 120" in resp.text


def test_availability_and_start_agree_on_topic_payloads(
    isolated_inventory, monkeypatch
) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("topics-agree"))

    # Gate off: the same body probes available and starts.
    legacy = {"blocks": [_interview_block(["DBMS"], topic="transactions")]}
    assert client.post("/session/availability", headers=headers,
                       json=legacy).json()["available"] is True
    started = client.post("/session/start", headers=headers, json=legacy)
    assert started.status_code == 200, started.text

    # Gate on, empty inventory: probe and start agree it is unavailable.
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    _clear_settings()
    db = get_database()
    sessions_before = len(list(db["sessions"].find({})))
    probe = client.post("/session/availability", headers=headers, json=legacy)
    assert probe.json()["available"] is False
    denied = client.post("/session/start", headers=headers, json=legacy)
    assert denied.status_code == 422, denied.text
    assert len(list(db["sessions"].find({}))) == sessions_before


def test_practice_bank_exposes_safe_topic_metadata(isolated_inventory) -> None:
    client = TestClient(app)
    assert client.get("/session/practice-bank").status_code == 401
    bank = client.get("/session/practice-bank",
                      headers=_headers(_make_user("topics-bank")))
    assert bank.status_code == 200, bank.text
    topics = bank.json()["interview_topics"]
    assert "normalization" in topics["DBMS"]
    assert "indexes" in topics["DBMS"]
    assert topics["DBMS"] == sorted(topics["DBMS"])
    blob = str(topics)
    for forbidden in ("ideal_answer", "reference_answer", "ideal_keywords",
                      "required_concepts", "misconceptions", "rubric"):
        assert forbidden not in blob


def test_draft_preset_preserve_topic_and_older_configs_work(isolated_inventory) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("topics-persist"))

    with_topic = [_interview_block(["DBMS"], topic="normalization")]
    saved = client.put("/practice/builder-draft", headers=headers, json={
        "version": 1, "blocks": with_topic,
    })
    assert saved.status_code == 200, saved.text
    draft = client.get("/practice/builder-draft", headers=headers).json()
    assert draft["blocks"][0]["topic"] == "normalization"

    created = client.post("/practice/presets", headers=headers, json={
        "name": "topic preset", "version": 1, "blocks": with_topic,
    })
    assert created.status_code == 200, created.text
    preset = client.get(f"/practice/presets/{created.json()['id']}",
                        headers=headers).json()
    assert preset["blocks"][0]["topic"] == "normalization"

    # Older configurations without the topic field still validate, save,
    # and start.
    legacy_blocks = [_interview_block(["DBMS"])]
    assert "topic" not in legacy_blocks[0]
    saved_legacy = client.put("/practice/builder-draft", headers=headers, json={
        "version": 1, "blocks": legacy_blocks,
    })
    assert saved_legacy.status_code == 200, saved_legacy.text
    start = client.post("/session/start", headers=headers,
                        json={"blocks": legacy_blocks})
    assert start.status_code == 200, start.text
    assert start.json()["block_plan"][0]["topic"] is None
