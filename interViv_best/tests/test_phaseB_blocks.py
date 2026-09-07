"""Phase B: block contract, Verbal/OA/SQL/Interview composition, drafts, presets."""

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


def _make_user(prefix="phaseb") -> dict[str, str]:
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


def test_legacy_standalone_verbal_preserved() -> None:
    client = TestClient(app)
    user = _make_user("verbal-legacy")
    headers = _headers(user)
    resp = client.post("/session/start", headers=headers, json={
        "skills": ["Verbal Ability"], "round_type": "mcq",
        "rounds_per_skill": 1, "round_config": {"count": 5},
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["round_type"] == "mcq"
    assert body["total_rounds"] == 1
    questions = body.get("questions") or []
    assert len(questions) == 5
    assert all(q.get("skill") == "Verbal Ability" for q in questions)
    assert body["block_plan"][0]["category"] == "verbal"
    for q in questions:
        assert "correct_option_ids" not in q
        assert "explanation" not in q


def test_legacy_verbal_mixing_rejected_without_blocks() -> None:
    client = TestClient(app)
    user = _make_user("verbal-mix")
    headers = _headers(user)
    resp = client.post("/session/start", headers=headers, json={
        "skills": ["Verbal Ability", "DBMS"], "round_type": "mcq",
        "rounds_per_skill": 1,
    })
    assert resp.status_code == 422
    assert "Verbal Ability" in resp.text


def test_verbal_only_via_blocks() -> None:
    client = TestClient(app)
    user = _make_user("verbal-blocks")
    headers = _headers(user)
    resp = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "verbal",
         "skills": ["Verbal Ability"], "count": 5, "duration_minutes": 10},
    ]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_rounds"] == 1
    assert body["block_category"] == "verbal"
    assert len(body.get("questions") or []) == 5


def test_oa_dbms_only_strict_and_available_count() -> None:
    client = TestClient(app)
    user = _make_user("oa-strict")
    headers = _headers(user)
    resp = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 5, "duration_minutes": 15},
    ]})
    assert resp.status_code == 200, resp.text
    questions = resp.json().get("questions") or []
    assert len(questions) == 5
    assert all(q.get("skill") == "DBMS" for q in questions)
    # OOP has 10; requesting 15 must explain availability, not fill.
    over = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["OOP"],
         "count": 15, "duration_minutes": 15},
    ]})
    assert over.status_code == 422, over.text
    assert "found 10" in over.text and "need 15" in over.text


def test_sql_only_and_interview_only_via_blocks() -> None:
    client = TestClient(app)
    user = _make_user("sql-interview")
    headers = _headers(user)
    sql_resp = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "sql", "category": "sql",
         "count": 1, "duration_minutes": 15},
    ]})
    assert sql_resp.status_code == 200, sql_resp.text
    assert sql_resp.json()["round_type"] == "sql"
    assert sql_resp.json()["block_category"] == "sql"
    iv_resp = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 1},
    ]})
    assert iv_resp.status_code == 200, iv_resp.text
    assert iv_resp.json()["round_type"] == "technical_short_answer"
    assert iv_resp.json()["total_rounds"] == 1


def test_verbal_interview_sql_composition_order() -> None:
    client = TestClient(app)
    user = _make_user("compose-vis")
    headers = _headers(user)
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "verbal",
         "skills": ["Verbal Ability"], "count": 3, "duration_minutes": 10},
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 1},
        {"round_type": "sql", "category": "sql",
         "count": 1, "duration_minutes": 15},
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["round_plan"] == ["mcq", "technical_short_answer", "sql"]
    assert [b["category"] for b in body["block_plan"]] == ["verbal", "interview", "sql"]
    session_id = body["session_id"]
    # Submit verbal block → interview next.
    ans1 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answers": _mcq_answers(body["questions"]),
    })
    assert ans1.status_code == 200, ans1.text
    assert ans1.json()["next_round_type"] == "technical_short_answer"
    assert ans1.json()["next_block_category"] == "interview"
    # Submit interview → SQL next.
    ans2 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 2,
        "answer_text": "A primary key uniquely identifies each row and enforces uniqueness.",
    })
    assert ans2.status_code == 200, ans2.text
    assert ans2.json()["next_round_type"] == "sql"
    # SQL answer → complete.
    db = get_database()
    raw = db["sessions"].find_one({"session_id": session_id})
    sql_ctx = raw["rounds"][2].get("question_context") or {}
    ref_query = sql_ctx.get("reference_query") or "SELECT 1"
    ans3 = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 3, "answer_text": ref_query,
    })
    assert ans3.status_code == 200, ans3.text
    assert ans3.json()["session_complete"] is True
    # Duplicate submission rejected; no duplicate scoring.
    dup = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 3, "answer_text": ref_query,
    })
    assert dup.status_code == 409


def test_two_oa_blocks_different_topics_and_settings() -> None:
    client = TestClient(app)
    user = _make_user("two-oa")
    headers = _headers(user)
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 4, "duration_minutes": 10, "difficulty": "easy"},
        {"round_type": "mcq", "category": "oa", "skills": ["Python"],
         "count": 3, "duration_minutes": 20, "difficulty": "medium"},
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["total_rounds"] == 2
    assert [b["position"] for b in body["block_plan"]] == [1, 2]
    assert body["block_plan"][0]["id"] != body["block_plan"][1]["id"]
    first_questions = body["questions"]
    assert all(q.get("skill") == "DBMS" for q in first_questions)
    ans = client.post("/session/answer", headers=headers, json={
        "session_id": body["session_id"], "round": 1,
        "answers": _mcq_answers(first_questions),
    })
    assert ans.status_code == 200, ans.text
    assert ans.json()["next_round_type"] == "mcq"
    assert ans.json()["next_block_position"] == 2
    next_questions = (ans.json().get("next_question_context") or {}).get("questions") or []
    assert len(next_questions) == 3
    assert all(q.get("skill") == "Python" for q in next_questions)


def test_adding_verbal_never_erases_sequence() -> None:
    client = TestClient(app)
    user = _make_user("verbal-add")
    headers = _headers(user)
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 3, "duration_minutes": 10},
        {"round_type": "mcq", "category": "verbal",
         "skills": ["Verbal Ability"], "count": 3, "duration_minutes": 10},
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    assert [b["category"] for b in body["block_plan"]] == ["oa", "verbal"]
    assert body["round_plan"] == ["mcq", "mcq"]
    assert body["total_rounds"] == 2


def test_block_refresh_stable_questions_and_deadline() -> None:
    client = TestClient(app)
    user = _make_user("block-refresh")
    headers = _headers(user)
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 5, "duration_minutes": 20},
    ]})
    assert start.status_code == 200, start.text
    body = start.json()
    session_id = body["session_id"]
    start_ids = [q["id"] for q in body["questions"]]
    start_options = [[o["id"] for o in q["options"]] for q in body["questions"]]
    start_expires = body["expires_at"]
    for _ in range(2):
        resume = client.get(f"/session/{session_id}", headers=headers)
        assert resume.status_code == 200, resume.text
        active = resume.json()["active_round"]
        refreshed = [q["id"] for q in active["question_context"]["questions"]]
        refreshed_options = [[o["id"] for o in q["options"]]
                             for q in active["question_context"]["questions"]]
        assert refreshed == start_ids
        assert refreshed_options == start_options
        assert active["expires_at"] == start_expires


def test_answer_drafts_save_recover_and_immutable() -> None:
    client = TestClient(app)
    user = _make_user("drafts")
    other = _make_user("drafts-other")
    headers = _headers(user)
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 3, "duration_minutes": 20},
    ]})
    session_id = start.json()["session_id"]
    questions = start.json()["questions"]
    # Save partial draft.
    save = client.put(f"/session/{session_id}/draft", headers=headers, json={
        "round": 1, "answers": [
            {"question_id": questions[0]["id"], "selected_option_ids": ["a"]},
        ],
    })
    assert save.status_code == 200, save.text
    # Recover as owner.
    got = client.get(f"/session/{session_id}/draft?round=1", headers=headers)
    assert got.status_code == 200, got.text
    assert got.json()["draft"]["answers"][0]["question_id"] == questions[0]["id"]
    # Other user cannot read.
    denied = client.get(f"/session/{session_id}/draft?round=1",
                        headers=_headers(other))
    assert denied.status_code in (403, 404)
    # Forged question ID rejected.
    forged = client.put(f"/session/{session_id}/draft", headers=headers, json={
        "round": 1, "answers": [
            {"question_id": "forged_999", "selected_option_ids": ["a"]},
        ],
    })
    assert forged.status_code == 422
    # Submit clears the draft; further drafts rejected as immutable.
    ans = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answers": _mcq_answers(questions),
    })
    assert ans.status_code == 200, ans.text
    after = client.get(f"/session/{session_id}/draft?round=1", headers=headers)
    assert after.status_code in (404, 409)
    resave = client.put(f"/session/{session_id}/draft", headers=headers, json={
        "round": 1, "answers": [],
    })
    assert resave.status_code == 409


def test_answer_draft_respects_deadline() -> None:
    client = TestClient(app)
    user = _make_user("draft-deadline")
    headers = _headers(user)
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 2, "duration_minutes": 20},
    ]})
    session_id = start.json()["session_id"]
    db = get_database()
    raw = db["sessions"].find_one({"session_id": session_id})
    raw["rounds"][0]["expires_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    db["sessions"].update_one({"session_id": session_id},
                              {"$set": {"rounds": raw["rounds"]}})
    save = client.put(f"/session/{session_id}/draft", headers=headers, json={
        "round": 1, "answers": [],
    })
    assert save.status_code == 400


def test_presets_crud_ownership_and_versions() -> None:
    client = TestClient(app)
    user = _make_user("presets")
    other = _make_user("presets-other")
    headers = _headers(user)
    blocks = [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 5, "duration_minutes": 15},
        {"round_type": "sql", "category": "sql",
         "count": 1, "duration_minutes": 20},
    ]
    created = client.post("/practice/presets", headers=headers, json={
        "name": "DBMS sprint", "version": 1, "blocks": blocks,
    })
    assert created.status_code == 200, created.text
    preset_id = created.json()["id"]
    assert created.json()["blocks"][0]["position"] == 1
    # Bad version rejected.
    bad = client.post("/practice/presets", headers=headers, json={
        "name": "bad", "version": 99, "blocks": blocks,
    })
    assert bad.status_code == 422
    # Owner lists; other user sees none and cannot read.
    listed = client.get("/practice/presets", headers=headers)
    assert listed.status_code == 200
    assert any(p["id"] == preset_id for p in listed.json()["presets"])
    other_list = client.get("/practice/presets", headers=_headers(other))
    assert all(p["id"] != preset_id for p in other_list.json()["presets"])
    forbidden = client.get(f"/practice/presets/{preset_id}",
                           headers=_headers(other))
    assert forbidden.status_code == 404
    # Update + delete as owner.
    updated = client.put(f"/practice/presets/{preset_id}", headers=headers,
                         json={"name": "DBMS sprint v2"})
    assert updated.status_code == 200, updated.text
    deleted = client.delete(f"/practice/presets/{preset_id}", headers=headers)
    assert deleted.status_code == 200
    gone = client.get(f"/practice/presets/{preset_id}", headers=headers)
    assert gone.status_code == 404


def test_builder_draft_autosave_and_validation() -> None:
    client = TestClient(app)
    user = _make_user("builder-draft")
    headers = _headers(user)
    blocks = [{"round_type": "mcq", "category": "verbal",
               "skills": ["Verbal Ability"], "count": 5,
               "duration_minutes": 10}]
    saved = client.put("/practice/builder-draft", headers=headers, json={
        "version": 1, "blocks": blocks,
    })
    assert saved.status_code == 200, saved.text
    assert saved.json()["blocks"][0]["category"] == "verbal"
    fetched = client.get("/practice/builder-draft", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["blocks"][0]["skills"] == ["Verbal Ability"]
    bad = client.put("/practice/builder-draft", headers=headers, json={
        "version": 99, "blocks": blocks,
    })
    assert bad.status_code == 422


def test_practice_bank_includes_verbal_and_safe_sql() -> None:
    client = TestClient(app)
    user = _make_user("bank-safe")
    headers = _headers(user)
    resp = client.get("/session/practice-bank", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["counts"]["mcq"] == 150
    assert data["counts"]["verbal"] == 30
    assert data["counts"]["sql"] == 30
    assert all("correct_option_ids" not in q for q in data["mcq"])
    assert all("explanation" not in q for q in data["verbal"])
    assert all("reference_query" not in p for p in data["sql"])
    assert all("schema_ddl" in p for p in data["sql"])
    assert all(q.get("skill") == "Verbal Ability" for q in data["verbal"])


def test_legacy_unknown_topics_keep_fallback_while_blocks_are_strict() -> None:
    client = TestClient(app)
    user = _make_user("unknown-fallback")
    headers = _headers(user)
    # Legacy mixed session with unknown MCQ topics preserves demo behavior.
    legacy = client.post("/session/start", headers=headers, json={
        "skills": ["SQL", "React"],
        "round_plan": ["technical_short_answer", "mcq"],
        "round_type": "technical_short_answer",
        "rounds_per_skill": 1,
    })
    assert legacy.status_code == 200, legacy.text
    # New blocks with unknown topics are strict and explain availability.
    strict = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["React"],
         "count": 5, "duration_minutes": 10},
    ]})
    assert strict.status_code == 422, strict.text
    assert "found 0" in strict.text


def test_block_session_ownership_enforced() -> None:
    client = TestClient(app)
    user = _make_user("owner-a")
    other = _make_user("owner-b")
    start = client.post("/session/start", headers=_headers(user), json={
        "blocks": [{"round_type": "mcq", "category": "oa",
                    "skills": ["DBMS"], "count": 3,
                    "duration_minutes": 15}],
    })
    session_id = start.json()["session_id"]
    denied = client.get(f"/session/{session_id}", headers=_headers(other))
    assert denied.status_code == 403
    denied_answer = client.post("/session/answer", headers=_headers(other),
                                json={"session_id": session_id, "round": 1,
                                      "answers": []})
    assert denied_answer.status_code == 403
