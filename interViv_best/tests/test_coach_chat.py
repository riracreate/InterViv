"""Coach chat v1 offline tests. Fake transport only; no real provider."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.main import app  # noqa: E402
from modules import coach_chat, coach_conversation  # noqa: E402
from modules.coach_conversation import get_or_create_conversation, owner_key, post_message  # noqa: E402
from modules.interview_llm import enforce_coach_chat_outbound  # noqa: E402
from modules.interview_llm import PrivacyViolation  # noqa: E402

DET = {
    "kind": "planning", "mode": "deterministic",
    "message": "Deterministic fallback without invented figures.",
    "clarifying_questions": [], "actions": [],
}
CONTEXT = (
    "[Role]\nBlueprint: backend-engineer Title: Backend Engineer Level: junior\n"
    "[Resume skills]\nPython, SQL\n"
    "[App scores]\nOverall readiness: 66.7% Conservative: 50%\n"
    "[Recent debriefs]\nSession sess-1: missed indexing\n"
    "[Plan]\nPlan p1 v2 kind starter goal Backend hours 6 Task Python: Practice Python"
)


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    coach_conversation.reset_memory_store()
    coach_chat.set_coach_chat_transport(None)
    monkeypatch.setenv("INTERVIEW_LLM_STATE_PATH", str(tmp_path / "limits.json"))
    monkeypatch.setenv("COACH_CHAT_LLM_ENABLED", "1")
    yield
    coach_chat.set_coach_chat_transport(None)
    coach_conversation.reset_memory_store()


def _gen(transport, *, user_id="u-chat", sessions=None, context=CONTEXT, tmp=None):
    return coach_chat.generate_coach_reply(
        user_id=user_id, user_text="How am I doing?", context_block=context,
        deterministic=dict(DET), sessions=sessions or [], transport=transport,
        state_path=tmp,
    )


def test_flag_off_never_calls_transport(monkeypatch, tmp_path):
    monkeypatch.setenv("COACH_CHAT_LLM_ENABLED", "0")
    calls = []
    reply = _gen(lambda c, u: calls.append(1) or {"message": "Uses 66.7% well."}, tmp=tmp_path / "a.json")
    assert calls == []
    assert reply["mode"] == "deterministic"
    assert reply["tool_proposal"] is None


def test_valid_reply_and_tool_pass(tmp_path):
    reply = _gen(
        lambda c, u: {"message": "Python is at 66.7% in your plan context.",
                      "tool_proposal": {"tool": "start_practice", "args": {"skills": ["Python"]}},
                      "prompt_tokens": 100, "completion_tokens": 20},
        tmp=tmp_path / "a.json",
    )
    assert reply["mode"] == "provider"
    assert reply["tool_proposal"]["tool"] == "start_practice"


def test_number_rule_rejects_invented_and_percent_boundary(tmp_path):
    assert coach_chat.validate_number_rule("score 3 here", "score 30 here", "") is False
    assert coach_chat.validate_number_rule("score 30 here", "score 30 here", "") is True
    assert coach_chat.validate_number_rule("at 66.7%", "at 66.7%", "") is True
    assert coach_chat.validate_number_rule("at 66.7%", "at 66.7", "") is False
    reply = _gen(lambda c, u: {"message": "Your readiness is 99% now."}, tmp=tmp_path / "a.json")
    assert reply["mode"] == "deterministic"
    assert reply["provider_rejected"] is True
    assert "99" not in reply["message"]


def test_list_markers_are_not_numbers(tmp_path):
    reply = _gen(lambda c, u: {"message": "1. Practise Python\n2) Review SQL"}, tmp=tmp_path / "a.json")
    assert reply["mode"] == "provider"


def test_number_in_current_user_message_is_allowed(tmp_path):
    reply = coach_chat.generate_coach_reply(
        user_id="u-chat", user_text="I study 9 hours", context_block=CONTEXT,
        deterministic=dict(DET), sessions=[],
        transport=lambda c, u: {"message": "Nine is written out, 9 matches your message."},
        state_path=tmp_path / "a.json",
    )
    assert reply["mode"] == "provider"


def test_transport_error_and_out_of_context_tool(tmp_path):
    def boom(_c, _u):
        raise RuntimeError("down")

    reply = _gen(boom, tmp=tmp_path / "a.json")
    assert reply["mode"] == "deterministic" and reply["provider_error"] == "provider"
    reply = _gen(
        lambda c, u: {"message": "Practise Python next.",
                      "tool_proposal": {"tool": "start_practice", "args": {"skills": ["Rust"]}}},
        tmp=tmp_path / "b.json",
    )
    assert reply["mode"] == "provider" and reply["tool_proposal"] is None


def _assessment_sessions(*, minutes_ago=30, status="in_progress", started=True):
    now = datetime.now(timezone.utc)
    round_doc = {"round": 1, "status": status, "question": "Explain database indexing in detail with an example please"}
    if started:
        round_doc["started_at"] = now - timedelta(minutes=minutes_ago)
    return [{"session_id": "s-open", "user_id": "u-chat", "status": "active",
             "practice_mode": "assessment", "rounds": [round_doc]}]


def test_recent_assessment_refuses_without_transport(tmp_path):
    calls = []
    reply = _gen(lambda c, u: calls.append(1) or {"message": "ok"}, sessions=_assessment_sessions(), tmp=tmp_path / "a.json")
    assert calls == [] and reply["refusal"] is True and reply["tool_proposal"] is None


def test_ready_unstarted_and_old_assessment_do_not_refuse(tmp_path):
    for sessions in (_assessment_sessions(status="ready", started=False), _assessment_sessions(minutes_ago=200)):
        reply = _gen(lambda c, u: {"message": "Practise Python next."}, sessions=sessions, tmp=tmp_path / "a.json")
        assert reply["mode"] == "provider", sessions


def test_pasted_live_question_refuses_without_transport(tmp_path):
    sessions = _assessment_sessions(minutes_ago=200)
    question = sessions[0]["rounds"][0]["question"]
    calls = []
    reply = coach_chat.generate_coach_reply(
        user_id="u-chat", user_text=f"Help: {question}", context_block=CONTEXT,
        deterministic=dict(DET), sessions=sessions,
        transport=lambda c, u: calls.append(1) or {"message": "ok"}, state_path=tmp_path / "a.json",
    )
    assert calls == [] and reply["refusal"] is True


def test_caps_per_user_and_global(tmp_path):
    path = tmp_path / "caps.json"
    for _ in range(40):
        coach_chat.record_turn("u-cap", prompt_tokens=10, completion_tokens=10, path=path)
    state = json.loads(path.read_text())
    assert state["coach_chat"]["users"]["u-cap"]["turns"] == 40
    assert "message" not in path.read_text() and state["coach_chat"]["rates"]
    calls = []
    reply = _gen(lambda c, u: calls.append(1) or {"message": "ok"}, user_id="u-cap", tmp=path)
    assert calls == [] and reply["capped"] is True


def test_global_cap_blocks_other_user(monkeypatch, tmp_path):
    monkeypatch.setenv("COACH_CHAT_GLOBAL_DAILY_USD", "0.001")
    path = tmp_path / "global.json"
    coach_chat.record_turn("someone", prompt_tokens=100000, completion_tokens=0, path=path)
    assert coach_chat.is_capped("another", path=path) is True


def test_context_block_last_six_role_and_trim():
    convo = {"rolling_summary": "Earlier summary text.", "goals": {}, "messages": [
        {"role": "user" if i % 2 == 0 else "assistant", "text": f"message {i}"} for i in range(10)
    ]}
    block = coach_chat.build_context_block(
        user_id="u-ctx", conversation=convo, user_text="current question",
        sessions=[], resume_skills=["Python"], gap=None, due_rows=[],
        role_target={"blueprint_id": "backend-engineer", "title": "Backend Engineer", "level": "mid", "role_id": None},
    )
    assert "Backend Engineer" in block and "Level: mid" in block
    assert block.count("message ") == 5 and "current question" in block
    big = coach_chat.build_context_block(
        user_id="u-ctx", conversation={"rolling_summary": "x" * 20000, "goals": {}, "messages": []},
        user_text="keep this current message", sessions=[], resume_skills=[], gap=None, due_rows=[],
        role_target={"blueprint_id": "backend-engineer", "title": "Backend Engineer", "level": "mid", "role_id": None},
    )
    assert coach_chat.estimate_tokens(big) <= 3200
    assert "Backend Engineer" in big and "keep this current message" in big


def test_role_target_and_gemini_gate():
    target = coach_chat.get_coach_role_target({"id": "nobody", "target_role_id": "backend-engineer"})
    assert target["blueprint_id"] == "backend-engineer" and target["title"] == "Backend Engineer"
    with pytest.raises(PrivacyViolation):
        enforce_coach_chat_outbound(model="gemini-2.5-flash-lite", provider="gemini_paid")
    with pytest.raises(PrivacyViolation):
        enforce_coach_chat_outbound(model="anthropic/claude-haiku-4.5:free")
    enforce_coach_chat_outbound(model="anthropic/claude-haiku-4.5")


def test_explain_records_exposure_only_when_gates_pass():
    db = get_database()
    db["sessions"].insert_one({
        "session_id": "done-1", "user_id": "u-exp", "status": "completed",
        "rounds": [{"round": 1, "round_type": "technical_short_answer", "question_id": "q-exp",
                    "final_score": 42.0, "scoring_breakdown": {"concepts": {"missing": ["indexing"]}}}],
    })
    out = coach_chat.explain_last_interview(db, "u-exp", "done-1")
    assert out["available"] is True and out["rounds"][0]["missed"] == ["indexing"]
    assert out["recorded_exposure_ids"] and "24 hours" in out["note"]
    assert db["sessions"].find_one({"session_id": "done-1"})["rounds"][0]["final_score"] == 42.0
    db["sessions"].insert_one({
        "session_id": "done-2", "user_id": "u-exp2", "status": "completed",
        "rounds": [{"round": 1, "round_type": "technical_short_answer", "question_id": "q-open",
                    "final_score": 42.0, "scoring_breakdown": {"concepts": {"missing": ["joins"]}}}],
    })
    db["sessions"].insert_one({
        "session_id": "live-2", "user_id": "u-exp2", "status": "active",
        "rounds": [{"round": 1, "round_type": "technical_short_answer", "question_id": "q-open", "status": "in_progress"}],
    })
    blocked = coach_chat.explain_last_interview(db, "u-exp2", "done-2")
    assert blocked["rounds"][0]["exposure_recorded"] is False


def _user_and_conversation(client: TestClient, user_id: str) -> tuple[str, str]:
    get_database()["users"].insert_one({
        "id": user_id, "email": f"{user_id}@example.com", "name": user_id,
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc), "last_active_at": datetime.now(timezone.utc),
    })
    token = create_access_token(user_id)
    resp = client.post("/coach/conversations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    return token, resp.json()["conversation"]["conversation_id"]


def test_confirm_tools_call_existing_functions(monkeypatch):
    client = TestClient(app)
    token, cid = _user_and_conversation(client, "u-confirm")
    headers = {"Authorization": f"Bearer {token}"}
    calls = {"plan": 0, "practice": 0}

    def fake_plan(*a, **k):
        calls["plan"] += 1
        return {"plan_id": "p", "version": 3, "tasks": []}

    def fake_practice(body, authorization=None):
        calls["practice"] += 1
        return {"session_id": "s-new", "navigate": "/interview/s-new"}

    monkeypatch.setattr("backend.routes.coach.ensure_plan", fake_plan)
    monkeypatch.setattr("backend.routes.coach.coach_start_practice", fake_practice)
    assert calls == {"plan": 0, "practice": 0}
    resp = client.post(f"/coach/conversations/{cid}/tools/confirm", headers=headers,
                       json={"tool": "update_plan", "args": {"skills": []}})
    assert resp.status_code == 200 and calls["plan"] == 1
    resp = client.post(f"/coach/conversations/{cid}/tools/confirm", headers=headers,
                       json={"tool": "start_practice", "args": {"skills": ["Python"]}})
    assert resp.status_code == 200 and calls["practice"] == 1


def test_stream_sends_only_validated_text(monkeypatch, tmp_path):
    client = TestClient(app)
    token, cid = _user_and_conversation(client, "u-stream")
    coach_chat.set_coach_chat_transport(lambda c, u: {"message": "Invented 99% claim."})
    resp = client.post(f"/coach/conversations/{cid}/messages/stream",
                       headers={"Authorization": f"Bearer {token}"}, json={"text": "How am I doing?"})
    assert resp.status_code == 200
    assert "Invented" not in resp.text and "99%" not in resp.text
    assert "event: token" in resp.text and "event: done" in resp.text
    streamed = "".join(json.loads(line[5:])["text"] for line in resp.text.splitlines() if line.startswith('data: {"text"'))
    assert streamed


def test_post_message_flag_off_is_deterministic(monkeypatch):
    monkeypatch.setenv("COACH_CHAT_LLM_ENABLED", "0")
    calls = []
    coach_chat.set_coach_chat_transport(lambda c, u: calls.append(1) or {"message": "Uses 66.7%."})
    doc = get_or_create_conversation(user_id="u-off", role_id="amazon_sde_intern")
    result = post_message(doc["conversation_id"], owner=owner_key("u-off"), user_id="u-off", text="Why Python?")
    assert calls == [] and result["reply"]["mode"] == "deterministic"
