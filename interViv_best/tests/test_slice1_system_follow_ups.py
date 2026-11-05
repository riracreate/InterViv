"""Slice 1 / Checkpoint B1: system follow-up allocation and placement.

System follow-ups are inserted immediately after their parent inside the
parent's own revision-checked attempt commit, built from a validated prompt
(no bank selector), never after the final mandatory round, and never for
legacy plans. Everything is default-off: the flag gates it, and the shipped
trigger proposes nothing, so these tests inject a stub trigger.

Backends: memory and SQLite (one disposable file, independent connections).
Postgres is NOT exercised here (``INTERVIV_TEST_DATABASE_URL`` unset).
"""

from __future__ import annotations

import copy
import itertools
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.main import app  # noqa: E402
from backend.models.blocks import expand_blocks, legacy_to_blocks  # noqa: E402
from backend.routes.session import _skill_for_round  # noqa: E402
from modules import system_follow_ups  # noqa: E402
from modules.follow_ups import (  # noqa: E402
    INITIATOR_SYSTEM,
    build_follow_up_plan_entry,
    build_system_follow_up_plan_entry,
    mandatory_remaining,
    remaining_questions,
    schedule_follow_up_in_session,
)
from modules.system_follow_ups import (  # noqa: E402
    SystemFollowUpProposal,
    validate_system_prompt,
)
from tests import slice1_harness as harness  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STUB_PROMPT = "Could you walk through a concrete example of that idea?"
ADDITIVE_FIELDS = [("session_doc", "expanded_plan", "*", "mandatory_index")]


# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def mem(monkeypatch):
    return harness.install(monkeypatch)


@pytest.fixture
def system_on(monkeypatch):
    """Flag on plus a stub trigger (``parents=None`` proposes for every parent)."""
    from backend import config

    monkeypatch.setenv("SYSTEM_FOLLOW_UPS_ENABLED", "true")
    config.get_settings.cache_clear()
    state = SimpleNamespace(calls=[], parents=None, prompt=STUB_PROMPT)

    def stub(context):
        parent = int(context["parent_round"]["round"])
        state.calls.append(parent)
        if state.parents is not None and parent not in state.parents:
            return None
        return SystemFollowUpProposal(prompt=state.prompt, kind="clarification")

    system_follow_ups.register_trigger(stub)
    yield state
    system_follow_ups.reset_trigger()
    config.get_settings.cache_clear()


def _client():
    return TestClient(app)


def _blocks(*counts, skills=("DBMS", "OS", "CN"), allow=True, max_follow_ups=None):
    blocks = []
    for count, skill in zip(counts, skills):
        block = {"round_type": "technical_short_answer", "category": "interview",
                 "skills": [skill], "count": count, "allow_optional_follow_ups": allow}
        if max_follow_ups is not None:
            block["max_follow_ups"] = max_follow_ups
        blocks.append(block)
    return blocks


def _start(client, headers, blocks, **extra):
    resp = client.post("/session/start", headers=headers,
                       json={"blocks": blocks, "practice_mode": "coached_practice", **extra})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _submit(client, headers, sid, number, text="alpha answer about normalization and indexing"):
    return client.post("/session/answer", headers=headers,
                       json={"session_id": sid, "round": number, "answer_text": text})


def _activate(client, headers, sid, number):
    resp = client.post(f"/session/{sid}/rounds/{number}/activate", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _plan(db, sid):
    doc = db["sessions"].find_one({"session_id": sid})
    return [(e.get("round"), bool(e.get("is_follow_up")), e.get("mandatory_index"))
            for e in doc["expanded_plan"]]


def _follow_up_entries(doc):
    return [e for e in doc.get("expanded_plan") or [] if e.get("is_follow_up")]


def _exposures(db, sid):
    return [d for d in (db["teaching_exposures"].find({"session_id": sid}) or [])
            if d.get("content_kind") == "follow_up_prompt"]


def _materialized(rounds, parent_round):
    return [{"round": int(n), "round_type": "technical_short_answer", "skill": "DBMS",
             "status": "submitted", "final_score": 60.0, "answer_text": f"answer {n}",
             "block_id": "b1", "question": f"Q{n}?", "config_json": {}}
            for n in range(1, parent_round + 1)]


# ── pure rules: prompt validation (system path only) ──────────────────


QC = {"question": "Explain normalization.", "skill": "DBMS",
      "ideal_keywords": "normalization, indexing"}


@pytest.mark.parametrize("prompt,answer,expected", [
    ("", "x", "prompt_empty"),
    ("   ", "x", "prompt_empty"),
    ("Tell me more.", "x", "prompt_question_mark_count"),
    ("Why? And how?", "x", "prompt_question_mark_count"),
    ("Why " + "x" * 300 + "?", "x", "prompt_too_long"),
    ("What score would you give this?", "x", "prompt_feedback_language"),
    ("That was correct; can you extend it?", "x", "prompt_feedback_language"),
    ("You missed a step; which one?", "x", "prompt_feedback_language"),
    ("Great answer, can you add an example?", "x", "prompt_feedback_language"),
    ("How would indexing change this?", "keys only", "prompt_reveals_unstated_concept"),
    ("How would indexing change this?", "I used indexing", ""),
    ("How would reindexing change this?", "keys only", ""),
    ("  Could you give one concrete example?  ", "keys only", ""),
])
def test_system_prompt_rules(prompt, answer, expected):
    ok, reason = validate_system_prompt(prompt, parent_answer=answer, question_context=QC)
    assert (ok, reason) == (expected == "", expected)


def test_prompt_exactly_300_chars_is_accepted():
    prompt = "Why " + "x" * 295 + "?"
    assert len(prompt) == 300
    assert validate_system_prompt(prompt, parent_answer="", question_context={}) == (True, "")


def _indexed_session(total=3, *, parent_round=1):
    expanded = expand_blocks(legacy_to_blocks(skills=["DBMS"], rounds_per_skill=total))
    return {"session_id": "s", "user_id": "u", "practice_mode": "coached_practice",
            "allow_optional_follow_ups": True, "total_rounds": total,
            "expanded_plan": expanded, "block_plan": [],
            "round_plan": [s["round_type"] for s in expanded],
            "rounds": _materialized(None, parent_round)}


def test_rejection_leaves_scheduling_unchanged():
    session = _indexed_session()
    before = copy.deepcopy(session)
    parent = session["rounds"][0]
    entry = build_system_follow_up_plan_entry(parent_round_doc=parent, prompt="Not a question.")
    result = schedule_follow_up_in_session(
        session, parent_round_doc=parent, plan_entry=entry,
        initiator=INITIATOR_SYSTEM, parent_answer="answer 1", question_context=QC)
    assert result == {"scheduled": False, "reason": "prompt_question_mark_count"}
    assert session == before


def test_candidate_path_never_runs_prompt_validation():
    # "Clarify X" fails every system rule (no '?'); the candidate path keeps it.
    session = _indexed_session()
    parent = session["rounds"][0]
    entry = build_follow_up_plan_entry(parent_round_doc=parent, reviewed_bundle=None,
                                       clarification_prompt="Clarify X")
    result = schedule_follow_up_in_session(session, parent_round_doc=parent, plan_entry=entry)
    assert result["scheduled"] is True
    appended = result["expanded_plan"][-1]
    assert appended["clarification_prompt"] == "Clarify X"
    assert appended["round"] == 4 and result["total_rounds"] == 4


def test_initiator_and_placement_are_not_request_fields():
    from backend.routes.answer import SubmitAnswerRequest
    from backend.routes.follow_ups import FollowUpRequest

    assert set(FollowUpRequest.model_fields) == {"parent_round", "accept_eligibility_consequence"}
    assert not {"initiator", "placement"} & set(SubmitAnswerRequest.model_fields)
    with pytest.raises(Exception):
        SubmitAnswerRequest.model_validate({"session_id": "s", "round": 1,
                                            "answer_text": "x", "initiator": "system"})


# ── test 1: final mandatory round ────────────────────────────────────


def test_final_mandatory_round_never_inserts_pure():
    session = _indexed_session(total=3, parent_round=3)
    parent = session["rounds"][-1]
    entry = build_system_follow_up_plan_entry(parent_round_doc=parent, prompt=STUB_PROMPT)
    assert remaining_questions(session, 3) == 0
    result = schedule_follow_up_in_session(
        session, parent_round_doc=parent, plan_entry=entry, initiator=INITIATOR_SYSTEM,
        parent_answer="answer 3", question_context={})
    assert result == {"scheduled": False, "reason": "no_mandatory_remaining"}


def test_one_round_session_completes_without_follow_up(mem, system_on):
    client = _client()
    user_id, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(1))["session_id"]
    resp = _submit(client, headers, sid, 1)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_rounds"] == 1
    assert body["session_complete"] is True and body["session_status"] == "completed"
    assert body["next_round"] is None
    doc = mem["sessions"].find_one({"session_id": sid})
    assert doc["total_rounds"] == 1 and _follow_up_entries(doc) == []
    assert len(doc["rounds"]) == 1
    # Gated before the trigger is even consulted: no mandatory work remains.
    assert system_on.calls == []


def test_never_after_final_mandatory_round_end_to_end(mem, system_on):
    client = _client()
    user_id, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(3))["session_id"]
    shape = []
    number, body = 1, None
    while True:
        resp = _submit(client, headers, sid, number)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        if body["session_complete"]:
            break
        number = body["next_round"]
        _activate(client, headers, sid, number)
    doc = mem["sessions"].find_one({"session_id": sid})
    shape = [(r["round"], bool(r.get("is_follow_up"))) for r in doc["rounds"]]
    # Parents 1 and 3 get follow-ups (block cap 2); the final mandatory round 5 never.
    assert shape == [(1, False), (2, True), (3, False), (4, True), (5, False)]
    assert system_on.calls == [1, 3]
    assert doc["total_rounds"] == 5 and doc["status"] == "completed"
    assert [e["mandatory_index"] for e in doc["expanded_plan"] if not e.get("is_follow_up")] == [1, 2, 3]


# ── test 2: placement, direct materialization, identities ─────────────


def test_immediate_next_placement_despite_bank_miss(mem, system_on, monkeypatch):
    from backend.integrations import IntegrationError

    client = _client()
    user_id, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(3))["session_id"]

    def bank_miss(**kwargs):
        raise IntegrationError("stub bank exhausted")

    for module in ("backend.routes.answer", "backend.routes.session", "backend.routes.session_continue"):
        monkeypatch.setattr(f"{module}._get_next_question", bank_miss)
    candidate_id = mem["sessions"].find_one({"session_id": sid})["candidate_id"]

    resp = _submit(client, headers, sid, 1)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["next_round"], body["next_round_status"]) == (2, "ready")
    assert body["progression_blocked"] is False and body["session_status"] == "active"
    assert body["total_rounds"] == 4
    doc = mem["sessions"].find_one({"session_id": sid})
    assert _plan(mem, sid) == [(1, False, 1), (2, True, None), (3, False, 2), (4, False, 3)]
    assert doc["round_plan"] == ["technical_short_answer"] * 4
    follow_up = doc["rounds"][1]
    assert follow_up["round"] == 2 and follow_up["is_follow_up"] is True
    assert follow_up["status"] == "ready" and follow_up["question"] == STUB_PROMPT
    assert follow_up["follow_up_parent_round"] == 1 and follow_up["skill"] == "DBMS"
    assert follow_up["question_context"]["source"] == "system_follow_up"
    assert follow_up["started_at"] is None
    assert _exposures(mem, sid) == []  # system follow-ups are exposure-free
    elo_after_parent = mem["candidates"].find_one({"candidate_id": candidate_id})["elo_ratings"]["DBMS"]

    # Normal ready -> activation lifecycle; served prompt is the validated text.
    active = _activate(client, headers, sid, 2)["active_round"]
    assert active["question"] == STUB_PROMPT and active["status"] == "in_progress"
    resp = _submit(client, headers, sid, 2, "a follow-up clarification answer")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["final_score"] is None
    # The NEXT mandatory question needs the bank: that miss blocks as before.
    assert body["progression_blocked"] is True and body["session_status"] == "content_blocked"
    candidate = mem["candidates"].find_one({"candidate_id": candidate_id})
    assert candidate["elo_ratings"]["DBMS"] == elo_after_parent

    for module in ("backend.routes.answer", "backend.routes.session", "backend.routes.session_continue"):
        monkeypatch.setattr(f"{module}._get_next_question", harness.stub_next_question)
    cont = client.post(f"/session/{sid}/continue", headers=headers)
    assert cont.status_code == 200, cont.text
    assert cont.json()["round"] == 3 and cont.json()["current_skill"] == "DBMS"


def test_materialized_identities_unchanged_and_pending_entries_shift(mem, system_on):
    system_on.parents = {2}
    client = _client()
    user_id, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(2, 2))["session_id"]
    assert _submit(client, headers, sid, 1).status_code == 200
    requested = client.post(f"/session/{sid}/follow-ups", headers=headers,
                            json={"parent_round": 1, "accept_eligibility_consequence": True})
    assert requested.json()["scheduled"] is True
    before = mem["sessions"].find_one({"session_id": sid})
    candidate_entry = _follow_up_entries(before)[0]
    assert candidate_entry["round"] == 5  # appended at the end, as today
    round_one = copy.deepcopy(before["rounds"][0])

    _activate(client, headers, sid, 2)
    resp = _submit(client, headers, sid, 2)
    assert resp.status_code == 200 and resp.json()["next_round"] == 3
    after = mem["sessions"].find_one({"session_id": sid})
    assert after["rounds"][0] == round_one  # materialized round 1 untouched
    assert [r["round"] for r in after["rounds"]] == [1, 2, 3]
    assert _plan(mem, sid) == [(1, False, 1), (2, False, 2), (3, True, None),
                               (4, False, 3), (5, False, 4), (6, True, None)]
    shifted = next(e for e in _follow_up_entries(after)
                   if e["follow_up_identity"] == candidate_entry["follow_up_identity"])
    assert {k: v for k, v in shifted.items() if k != "round"} == {
        k: v for k, v in candidate_entry.items() if k != "round"}
    assert shifted["round"] == 6 and after["total_rounds"] == 6
    assert len(_exposures(mem, sid)) == 1  # only the candidate allocation

    served = []
    number = 3
    while True:
        _activate(client, headers, sid, number)
        body = _submit(client, headers, sid, number).json()
        if body["session_complete"]:
            break
        number = body["next_round"]
    final = mem["sessions"].find_one({"session_id": sid})
    served = [(r["round"], r["skill"], bool(r.get("is_follow_up"))) for r in final["rounds"]]
    assert served[:5] == [(1, "DBMS", False), (2, "DBMS", False), (3, "DBMS", True),
                          (4, "OS", False), (5, "OS", False)]
    assert served[5][0] == 6 and served[5][2] is True and final["status"] == "completed"


# ── test 3: skill resolution ─────────────────────────────────────────


def _legacy_skill_for_round(session, round_number):
    """Verbatim pre-Slice-1 ``_skill_for_round`` (reference implementation)."""
    expanded = session.get("expanded_plan") or []
    spec = next((s for s in expanded if int(s.get("round") or 0) == int(round_number)), None)
    if spec:
        skills = [s for s in (spec.get("skills") or []) if s]
        if skills:
            return skills[0]
    skills = [s for s in (session.get("skills") or [session.get("skill")]) if s]
    if not skills:
        return session.get("skill") or "System Design"
    per = max(1, int(session.get("rounds_per_skill", 3)))
    idx = (int(round_number) - 1) // per
    if idx >= len(skills):
        idx = len(skills) - 1
    return skills[idx]


SKILL_POOL = ("DBMS", "OS", "CN", "OOP")


@pytest.mark.parametrize("per", [1, 2, 3, 4])
@pytest.mark.parametrize("n_skills", [1, 2, 3, 4])
@pytest.mark.parametrize("strip_spec_skills", [False, True])
def test_mandatory_index_resolution_equals_legacy_formula(per, n_skills, strip_spec_skills):
    for skills in itertools.permutations(SKILL_POOL, n_skills):
        expanded = expand_blocks(legacy_to_blocks(skills=list(skills), rounds_per_skill=per))
        if strip_spec_skills:  # force the formula path
            for spec in expanded:
                spec["skills"] = []
        n = len(expanded)
        session = {"skills": list(skills), "rounds_per_skill": per, "total_rounds": n,
                   "expanded_plan": expanded, "allow_optional_follow_ups": True,
                   "practice_mode": "coached_practice", "block_plan": [], "rounds": []}
        for r in range(1, n + 3):
            assert _skill_for_round(session, r) == _legacy_skill_for_round(session, r)
        original = [_legacy_skill_for_round(session, r) for r in range(1, n + 1)]
        for parent in range(1, n):
            parent_doc = {"round": parent, "round_type": "technical_short_answer",
                          "skill": original[parent - 1], "status": "submitted",
                          "final_score": 70.0, "block_id": expanded[parent - 1]["block_id"],
                          "config_json": {}}
            trial = {**copy.deepcopy(session), "rounds": [
                {**parent_doc, "round": k, "skill": original[k - 1]} for k in range(1, parent + 1)]}
            entry = build_system_follow_up_plan_entry(parent_round_doc=parent_doc, prompt=STUB_PROMPT)
            placed = schedule_follow_up_in_session(
                trial, parent_round_doc=parent_doc, plan_entry=entry,
                initiator=INITIATOR_SYSTEM, parent_answer="", question_context={})
            assert placed["scheduled"] is True, placed
            after = {**trial, **{k: placed[k] for k in ("expanded_plan", "total_rounds")}}
            mandatory = [s for s in after["expanded_plan"] if not s.get("is_follow_up")]
            for spec in mandatory:
                legacy = _legacy_skill_for_round(session, spec["mandatory_index"])
                assert _skill_for_round(after, spec["round"]) == legacy
            assert _skill_for_round(after, parent + 1) == original[parent - 1]
            assert [_skill_for_round(after, s["round"]) for s in mandatory] == original


def test_plan_less_legacy_session_rotation_is_unchanged():
    session = {"skills": ["A", "B", "C"], "rounds_per_skill": 3}
    assert [_skill_for_round(session, r) for r in range(1, 11)] == list("AAABBBCCCC")


def _walk_to_completion(client, headers, sid):
    number = 1
    while True:
        body = _submit(client, headers, sid, number).json()
        if body["session_complete"]:
            return
        number = body["next_round"]
        _activate(client, headers, sid, number)


@pytest.mark.parametrize("enabled", [False, True])
def test_legacy_abc_by_three_rotation_unchanged(mem, monkeypatch, enabled):
    from backend import config

    if enabled:
        monkeypatch.setenv("SYSTEM_FOLLOW_UPS_ENABLED", "true")
        config.get_settings.cache_clear()
    client = _client()
    user_id, headers = harness.make_user(mem)
    resp = client.post("/session/start", headers=headers, json={
        "skills": ["DBMS", "OS", "CN"], "rounds_per_skill": 3,
        "round_type": "technical_short_answer"})
    assert resp.status_code == 200, resp.text
    sid = resp.json()["session_id"]
    _walk_to_completion(client, headers, sid)
    doc = mem["sessions"].find_one({"session_id": sid})
    assert [r["skill"] for r in doc["rounds"]] == ["DBMS"] * 3 + ["OS"] * 3 + ["CN"] * 3
    assert doc["total_rounds"] == 9


def test_legacy_session_without_indices_never_inserts(mem, system_on):
    client = _client()
    user_id, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(3))["session_id"]
    doc = mem["sessions"].find_one({"session_id": sid})
    legacy_plan = [{k: v for k, v in s.items() if k != "mandatory_index"} for s in doc["expanded_plan"]]
    mem["sessions"].update_one({"session_id": sid}, {"$set": {"expanded_plan": legacy_plan}})
    resp = _submit(client, headers, sid, 1)
    assert resp.status_code == 200 and resp.json()["next_round"] == 2
    doc = mem["sessions"].find_one({"session_id": sid})
    assert _follow_up_entries(doc) == [] and doc["total_rounds"] == 3
    assert system_on.calls == []  # gated before the trigger
    parent = doc["rounds"][0]
    entry = build_system_follow_up_plan_entry(parent_round_doc=parent, prompt=STUB_PROMPT)
    assert schedule_follow_up_in_session(
        doc, parent_round_doc=parent, plan_entry=entry, initiator=INITIATOR_SYSTEM,
        parent_answer="", question_context={}) == {
            "scheduled": False, "reason": "mandatory_indices_incomplete"}


def test_parent_with_existing_follow_up_is_refused():
    session = _indexed_session(total=3, parent_round=1)
    parent = session["rounds"][0]
    pending = {**build_follow_up_plan_entry(parent_round_doc=parent, reviewed_bundle=None,
                                            clarification_prompt="Clarify X"), "round": 4}
    session["expanded_plan"].append(pending)
    session["total_rounds"] = 4
    entry = build_system_follow_up_plan_entry(parent_round_doc=parent, prompt=STUB_PROMPT)
    assert schedule_follow_up_in_session(
        session, parent_round_doc=parent, plan_entry=entry, initiator=INITIATOR_SYSTEM,
        parent_answer="", question_context={}) == {
            "scheduled": False, "reason": "parent_follow_up_exists"}


def test_system_insertion_never_uses_standalone_allocator(mem, system_on, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("system insertion must join the attempt commit")

    monkeypatch.setattr("backend.db.follow_up_allocate.allocate_follow_up", forbidden)
    monkeypatch.setattr("backend.routes.follow_ups.allocate_follow_up", forbidden)
    client = _client()
    user_id, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(3))["session_id"]
    resp = _submit(client, headers, sid, 1)
    assert resp.status_code == 200, resp.text
    assert len(_follow_up_entries(mem["sessions"].find_one({"session_id": sid}))) == 1


def test_later_materialized_round_blocks_insertion():
    session = _indexed_session(total=3, parent_round=2)
    parent = session["rounds"][0]  # round 1, while round 2 is materialized
    entry = build_system_follow_up_plan_entry(parent_round_doc=parent, prompt=STUB_PROMPT)
    assert schedule_follow_up_in_session(
        session, parent_round_doc=parent, plan_entry=entry, initiator=INITIATOR_SYSTEM,
        parent_answer="", question_context={}) == {
            "scheduled": False, "reason": "later_rounds_materialized"}


# ── gates ─────────────────────────────────────────────────────────────


def test_gates_flag_off_default_trigger_opt_out_and_bad_prompts(mem, monkeypatch, system_on):
    from backend import config

    client = _client()
    user_id, headers = harness.make_user(mem)

    def first_submit(blocks, **extra):
        sid = _start(client, headers, blocks, **extra)["session_id"]
        body = _submit(client, headers, sid, 1).json()
        doc = mem["sessions"].find_one({"session_id": sid})
        return body, doc

    # Session setting off (coached practice without the checkbox).
    body, doc = first_submit(_blocks(3, allow=False))
    assert _follow_up_entries(doc) == [] and body["total_rounds"] == 3
    # Assessment default disables the opt-in.
    body, doc = first_submit(_blocks(3, allow=False), practice_mode="assessment")
    assert _follow_up_entries(doc) == []
    assert system_on.calls == []
    # Invalid prompt: rejected inside the shared insertion; nothing changes.
    system_on.prompt = "Your answer was wrong. Try again?"
    body, doc = first_submit(_blocks(3))
    assert _follow_up_entries(doc) == [] and body["next_round"] == 2 and body["total_rounds"] == 3
    # Trigger failure is contained.
    system_follow_ups.register_trigger(lambda context: 1 / 0)
    body, doc = first_submit(_blocks(3))
    assert _follow_up_entries(doc) == [] and body["total_rounds"] == 3
    # Default trigger with the flag on: nothing.
    system_follow_ups.reset_trigger()
    body, doc = first_submit(_blocks(3))
    assert _follow_up_entries(doc) == []
    # Flag off with a proposing trigger registered: nothing, trigger not called.
    calls = []
    system_follow_ups.register_trigger(lambda context: calls.append(1) or STUB_PROMPT)
    monkeypatch.setenv("SYSTEM_FOLLOW_UPS_ENABLED", "false")
    config.get_settings.cache_clear()
    body, doc = first_submit(_blocks(3))
    assert _follow_up_entries(doc) == [] and calls == []


def test_system_path_never_requires_consent_and_honors_api_opt_in(mem, system_on):
    client = _client()
    user_id, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(3, allow=False), practice_mode="assessment",
                 allow_optional_follow_ups=True)["session_id"]
    body = _submit(client, headers, sid, 1).json()
    doc = mem["sessions"].find_one({"session_id": sid})
    assert len(_follow_up_entries(doc)) == 1 and body["next_round"] == 2
    assert _exposures(mem, sid) == []


def test_mandatory_remaining_excludes_pending_and_materialized_once():
    session = _indexed_session(total=3, parent_round=1)
    parent = session["rounds"][0]
    pending = {**build_follow_up_plan_entry(parent_round_doc=parent, reviewed_bundle=None,
                                            clarification_prompt="Clarify X"), "round": 4}
    session["expanded_plan"].append(pending)
    session["total_rounds"] = 4
    assert mandatory_remaining(session, 1) == 2 and remaining_questions(session, 1) == 2
    # Materialize it: plan entry + round row share the identity, counted once.
    session["rounds"].append({"round": 4, "is_follow_up": True, "status": "ready",
                              "follow_up_identity": pending["follow_up_identity"],
                              "follow_up_parent_round": 1})
    assert mandatory_remaining(session, 1) == 2 and remaining_questions(session, 1) == 2


# ── test 4: races (memory and SQLite) ─────────────────────────────────
#
# Every race has one deterministic variant per outcome (hooks order the
# contenders) and a free-running variant. All assertions are invariants of
# the outcome actually observed; nothing depends on how often a branch wins.
# Memory serializes on the process-local submit lock, so its variants order
# lock acquisition. SQLite variants use independent connections with no
# shared lock: both sides validate the SAME snapshot, then the hooks order
# the conflicting conditional writes and the loser must reload and retry.


def _count_scores(monkeypatch):
    calls = []
    real = harness.stub_score_round

    def counted(**kwargs):
        calls.append(kwargs.get("answer_text"))
        return real(**kwargs)

    monkeypatch.setattr("backend.routes.answer.score_round", counted)
    return calls


class _TracingLock:
    """Submit lock that records when a second request queues behind it."""

    def __init__(self):
        self._lock = threading.Lock()
        self.contended = threading.Event()

    def acquire(self, *args, **kwargs):
        if not self._lock.acquire(blocking=False):
            self.contended.set()
            self._lock.acquire()
        return True

    def release(self):
        self._lock.release()


def _tracing_submit_lock(monkeypatch):
    lock = _TracingLock()
    monkeypatch.setattr("backend.routes.answer._get_submit_lock", lambda session_id: lock)
    return lock


def _hold_first_call(monkeypatch, module, name, until):
    """First call of ``module.name`` sets the returned event, then waits for ``until``."""
    import importlib

    target = importlib.import_module(module)
    real = getattr(target, name)
    entered = threading.Event()
    state = {"first": True}
    guard = threading.Lock()

    def wrapper(*args, **kwargs):
        with guard:
            first, state["first"] = state["first"], False
        if first:
            entered.set()
            assert until.wait(timeout=30), f"{module}.{name} hold timed out"
        return real(*args, **kwargs)

    monkeypatch.setattr(target, name, wrapper)
    return entered


def _run_ordered(first_fn, second_fn, first_entered):
    """Start ``first_fn``; once it is inside its hold, start ``second_fn``."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_fn)
        assert first_entered.wait(timeout=30)
        second = pool.submit(second_fn)
        return first.result(timeout=60), second.result(timeout=60)


def _assert_duplicate_invariants(db, sid, results, score_calls, *, max_scores):
    assert sorted(r.status_code for r in results) == [200, 409], [r.text for r in results]
    doc = db["sessions"].find_one({"session_id": sid})
    assert len(_follow_up_entries(doc)) == 1 and doc["total_rounds"] == 4
    assert [(r["round"], bool(r.get("is_follow_up"))) for r in doc["rounds"]] == [(1, False), (2, True)]
    assert _exposures(db, sid) == []
    assert 1 <= len(score_calls) <= max_scores
    return doc


@pytest.mark.parametrize("variant", ["first_wins", "free"])
def test_memory_duplicate_submit_single_follow_up(mem, system_on, monkeypatch, variant):
    calls = _count_scores(monkeypatch)
    client = _client()
    user_id, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(3))["session_id"]
    lock = _tracing_submit_lock(monkeypatch)

    def submit():
        return _submit(TestClient(app), headers, sid, 1)

    if variant == "first_wins":
        # The first request holds the lock inside scoring until the duplicate
        # is queued on it; the duplicate then finds the round submitted.
        entered = _hold_first_call(monkeypatch, "backend.routes.answer", "score_round",
                                   lock.contended)
        first, second = _run_ordered(submit, submit, entered)
        assert (first.status_code, second.status_code) == (200, 409)
        results = [first, second]
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
    # The process lock serializes memory submits: the loser never scores.
    _assert_duplicate_invariants(mem, sid, results, calls, max_scores=1)


def _assert_one_winner(db, sid, cand, sub, *, expected=None):
    """Invariants for whichever side won; ``expected`` pins a deterministic variant."""
    doc = db["sessions"].find_one({"session_id": sid})
    entries = _follow_up_entries(doc)
    winner = "candidate" if cand["scheduled"] else "system"
    if expected is not None:
        assert winner == expected
    assert len(entries) == 1 and doc["total_rounds"] == 5
    exposures = _exposures(db, sid)
    if winner == "candidate":
        # Candidate allocation won: exposure recorded, appended at the end;
        # the submit's system insertion was refused on revalidation.
        assert len(exposures) == 1 and entries[0]["follow_up_parent_round"] == 1
        assert entries[0].get("follow_up_initiator") is None and entries[0]["round"] == 5
        assert sub["next_round"] == 3 and doc["rounds"][2].get("is_follow_up") is not True
    else:
        # System insertion won: no exposure; the candidate is refused by the cap.
        assert cand["reason"] == "block_follow_up_cap" and exposures == []
        assert entries[0]["follow_up_initiator"] == "system"
        assert entries[0]["follow_up_parent_round"] == 2 and entries[0]["round"] == 3
        assert doc["rounds"][2]["is_follow_up"] is True
    return winner


def _race_session(client, headers):
    sid = _start(client, headers, _blocks(4, max_follow_ups=1))["session_id"]
    assert _submit(client, headers, sid, 1).status_code == 200
    _activate(client, headers, sid, 2)
    return sid


def _contenders(sid, headers):
    def candidate():
        return TestClient(app).post(f"/session/{sid}/follow-ups", headers=headers, json={
            "parent_round": 1, "accept_eligibility_consequence": True})

    def system():
        return _submit(TestClient(app), headers, sid, 2)

    return candidate, system


@pytest.mark.parametrize("variant", ["candidate_wins", "system_wins", "free"])
def test_memory_candidate_vs_system_one_winner(mem, system_on, monkeypatch, variant):
    system_on.parents = {2}
    client = _client()
    user_id, headers = harness.make_user(mem)
    sid = _race_session(client, headers)
    candidate, system = _contenders(sid, headers)
    lock = _tracing_submit_lock(monkeypatch)
    if variant == "candidate_wins":
        entered = _hold_first_call(monkeypatch, "backend.routes.follow_ups",
                                   "allocate_follow_up", lock.contended)
        cand, sub = _run_ordered(candidate, system, entered)
    elif variant == "system_wins":
        entered = _hold_first_call(monkeypatch, "backend.routes.answer",
                                   "propose_system_follow_up", lock.contended)
        sub, cand = _run_ordered(system, candidate, entered)
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            cand, sub = list(pool.map(lambda fn: fn(), [candidate, system]))
    assert cand.status_code == 200 and sub.status_code == 200, (cand.text, sub.text)
    expected = {"candidate_wins": "candidate", "system_wins": "system"}.get(variant)
    _assert_one_winner(mem, sid, cand.json(), sub.json(), expected=expected)


# SQLite: independent connections on one file, no shared process lock.


def _clear_db_caches():
    from backend import config
    from backend.db import sqlalchemy_store

    config.get_settings.cache_clear()
    sqlalchemy_store.get_engine.cache_clear()
    sqlalchemy_store._sessionmaker.cache_clear()
    sqlalchemy_store.get_sqlalchemy_database.cache_clear()


@pytest.fixture
def sql_db(tmp_path, monkeypatch):
    from sqlalchemy import create_engine

    from backend import config as app_config
    from backend.db import sqlalchemy_store
    from tests.sql_test_url import is_postgres, resolve_sql_url

    url = resolve_sql_url(tmp_path, "slice1.db")
    if is_postgres(url):
        pytest.skip("Slice 1 race tests target SQLite only; Postgres is not exercised")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_db_caches()
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30},
                           pool_pre_ping=True, future=True)
    monkeypatch.setattr(sqlalchemy_store, "get_engine", lambda: engine)
    sqlalchemy_store._sessionmaker.cache_clear()
    sqlalchemy_store.get_sqlalchemy_database.cache_clear()
    sqlalchemy_store.create_all_for_smoke()
    harness.install_stubs(monkeypatch)
    try:
        yield sqlalchemy_store.get_sqlalchemy_database(), engine
    finally:
        engine.dispose()
        app_config.get_settings.cache_clear()
        sqlalchemy_store._sessionmaker.cache_clear()
        sqlalchemy_store.get_sqlalchemy_database.cache_clear()


@pytest.fixture
def independent_workers(monkeypatch):
    monkeypatch.setattr("backend.routes.answer._get_submit_lock",
                        lambda session_id: threading.Lock())


def _sql_user(db):
    return harness.make_user(db, prefix="slice1-sql")


def _hold_first_write(monkeypatch, keys):
    """Hold the first ``sessions.update_one`` whose $set covers ``keys``."""
    from backend.db import sqlalchemy_store

    original = sqlalchemy_store._SessionCollection.update_one
    state = SimpleNamespace(arrived=threading.Event(), release=threading.Event(),
                            held=False, guard=threading.Lock(), on_hold=None)

    def gated(self, query, update, upsert=False, *, expected_revision=None):
        hit = False
        with state.guard:
            if not state.held and set(keys) <= set(((update or {}).get("$set") or {})):
                state.held = hit = True
        if hit:
            state.arrived.set()
            if state.on_hold is not None:
                state.on_hold()
            else:
                assert state.release.wait(timeout=30)
        return original(self, query, update, upsert, expected_revision=expected_revision)

    monkeypatch.setattr(sqlalchemy_store._SessionCollection, "update_one", gated)
    return state


def _order_claims(monkeypatch):
    """First claim proceeds (sets ``claimed``); later claims wait for ``release``."""
    import backend.db.round_claim as round_claim

    original = round_claim.claim_round_finalizing
    state = SimpleNamespace(claimed=threading.Event(), release=threading.Event(),
                            n=0, guard=threading.Lock())

    def ordered(*args, **kwargs):
        with state.guard:
            state.n += 1
            index = state.n
        if index == 1:
            try:
                return original(*args, **kwargs)
            finally:
                state.claimed.set()
        assert state.release.wait(timeout=60)
        return original(*args, **kwargs)

    monkeypatch.setattr(round_claim, "claim_round_finalizing", ordered)
    return state


def _narrations(db, sid, number):
    return [d for d in (db["narration_jobs"].find({"session_id": sid}) or [])
            if d.get("round_number") == number or d.get("round") == number]


def _elo_deltas(sid):
    from backend.db.sqlalchemy_models import LearningEventRow
    from backend.db.sqlalchemy_store import session_scope
    from modules.learning_signals import EVENT_ELO_DELTA

    with session_scope() as session:
        return session.query(LearningEventRow).filter(
            LearningEventRow.session_id == sid,
            LearningEventRow.event_type == EVENT_ELO_DELTA).count()


@pytest.mark.parametrize("variant", ["later_wins", "earlier_wins", "free"])
def test_sql_duplicate_submit_single_follow_up(sql_db, independent_workers, system_on,
                                               monkeypatch, variant):
    db, engine = sql_db
    calls = _count_scores(monkeypatch)
    user_id, headers = _sql_user(db)
    sid = _start(_client(), headers, _blocks(3))["session_id"]

    def submit():
        return _submit(TestClient(app), headers, sid, 1)

    if variant == "later_wins":
        # First request is held before its commit write; the duplicate takes
        # over the stale ``finalizing`` claim and commits; the first then
        # loses its conditional write, reloads, sees ``submitted`` -> 409.
        gate = _hold_first_write(monkeypatch, {"last_round"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(submit)
            assert gate.arrived.wait(timeout=30)
            second = pool.submit(submit).result(timeout=60)
            gate.release.set()
            first = first.result(timeout=60)
        assert (first.status_code, second.status_code) == (409, 200)
        results, max_scores = [first, second], 2
    elif variant == "earlier_wins":
        # The duplicate is held before its claim until the first returned:
        # it then finds the round already submitted and never scores.
        order = _order_claims(monkeypatch)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(submit)
            assert order.claimed.wait(timeout=30)
            second = pool.submit(submit)
            first = first.result(timeout=60)
            order.release.set()
            second = second.result(timeout=60)
        assert (first.status_code, second.status_code) == (200, 409)
        results, max_scores = [first, second], 1
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: submit(), range(2)))
        max_scores = 2  # a stale-claim takeover may score twice; one commit wins
    engine.dispose()
    doc = _assert_duplicate_invariants(db, sid, results, calls, max_scores=max_scores)
    assert len(_narrations(db, sid, 1)) == 1 and _elo_deltas(sid) == 1
    # One session write carried the scored parent, the changed plan and the
    # prepared follow-up (claims update round rows, not the session revision).
    assert doc["revision"] == 1


def _ordered_commits(monkeypatch, winner):
    """Both sides validate one snapshot (barrier), then ``winner`` writes first.

    The loser's revision-gated write then conflicts and it must reload and
    revalidate. ``winner=None`` keeps only the barrier (free-running).
    Returns the list of sides whose write raised ``SessionWriteConflict``.
    """
    from backend.db import sqlalchemy_store
    from backend.db.sqlalchemy_store import SessionWriteConflict

    original = sqlalchemy_store._SessionCollection.update_one
    barrier = threading.Barrier(2)
    winner_wrote = threading.Event()
    seen, conflicts, guard = set(), [], threading.Lock()
    sides = [("system", {"last_round"}), ("candidate", {"expanded_plan"})]

    def gated(self, query, update, upsert=False, *, expected_revision=None):
        keys = set(((update or {}).get("$set") or {}))
        hit = None
        with guard:
            for name, want in sides:
                if name not in seen and want <= keys:
                    seen.add(name)
                    hit = name
                    break
        if hit is None:
            return original(self, query, update, upsert, expected_revision=expected_revision)
        barrier.wait(timeout=30)
        if winner is not None and hit != winner:
            assert winner_wrote.wait(timeout=30)
        try:
            return original(self, query, update, upsert, expected_revision=expected_revision)
        except SessionWriteConflict:
            with guard:
                conflicts.append(hit)
            raise
        finally:
            if hit == winner:
                winner_wrote.set()

    monkeypatch.setattr(sqlalchemy_store._SessionCollection, "update_one", gated)
    return conflicts


@pytest.mark.parametrize("variant", ["candidate_wins", "system_wins", "free"])
def test_sql_candidate_vs_system_one_winner(sql_db, independent_workers, system_on,
                                            monkeypatch, variant):
    db, engine = sql_db
    system_on.parents = {2}
    user_id, headers = _sql_user(db)
    sid = _race_session(_client(), headers)
    expected = {"candidate_wins": "candidate", "system_wins": "system"}.get(variant)
    conflicts = _ordered_commits(monkeypatch, expected)
    candidate, system = _contenders(sid, headers)
    with ThreadPoolExecutor(max_workers=2) as pool:
        cand, sub = list(pool.map(lambda fn: fn(), [candidate, system]))
    assert cand.status_code == 200 and sub.status_code == 200, (cand.text, sub.text)
    engine.dispose()
    winner = _assert_one_winner(db, sid, cand.json(), sub.json(), expected=expected)
    # Both validated the same snapshot; exactly the loser lost its write.
    assert conflicts == ["system" if winner == "candidate" else "candidate"]
    assert len(_narrations(db, sid, 2)) == 1 and _elo_deltas(sid) == 2


# ── stale tab: candidate request after a system insertion ────────────


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_stale_tab_candidate_request_after_system_insertion(backend, request, system_on):
    """The candidate's tab still offers "request follow-up" for a parent that
    already received a system follow-up: refused, no exposure, no cap used."""
    db = request.getfixturevalue("mem") if backend == "memory" else request.getfixturevalue("sql_db")[0]
    system_on.parents = {1}
    client = _client()
    user_id, headers = harness.make_user(db)
    sid = _start(client, headers, _blocks(3))["session_id"]  # block cap 2
    assert _submit(client, headers, sid, 1).json()["next_round"] == 2
    before = db["sessions"].find_one({"session_id": sid})
    assert len(_follow_up_entries(before)) == 1

    stale = client.post(f"/session/{sid}/follow-ups", headers=headers, json={
        "parent_round": 1, "accept_eligibility_consequence": True})
    assert stale.status_code == 200
    assert stale.json() == {"scheduled": False, "reason": "parent_follow_up_exists",
                            "session_id": sid, "parent_round": 1}
    after = db["sessions"].find_one({"session_id": sid})
    for key in ("expanded_plan", "total_rounds", "round_plan", "rounds"):
        assert after[key] == before[key], key
    if backend == "sqlite":
        assert after["revision"] == before["revision"]  # nothing written
    assert list(db["teaching_exposures"].find({"session_id": sid}) or []) == []

    # The refused request consumed no budget: the block's second slot is
    # still available to another parent.
    _activate(client, headers, sid, 2)
    assert _submit(client, headers, sid, 2, "a clarification answer").status_code == 200
    _activate(client, headers, sid, 3)
    assert _submit(client, headers, sid, 3).json()["next_round"] == 4
    other = client.post(f"/session/{sid}/follow-ups", headers=headers, json={
        "parent_round": 3, "accept_eligibility_consequence": True})
    assert other.json()["scheduled"] is True
    final = db["sessions"].find_one({"session_id": sid})
    assert len(_follow_up_entries(final)) == 2
    assert len(_exposures(db, sid)) == 1


# ── test 5: rollback and retry preservation ──────────────────────────


@pytest.mark.parametrize("backend", ["memory", "sqlite"])
def test_rollback_then_retry_inserts_once(backend, request, system_on, monkeypatch):
    from backend.db import DatabaseConnectionError

    db = request.getfixturevalue("mem") if backend == "memory" else request.getfixturevalue("sql_db")[0]
    client = _client()
    user_id, headers = harness.make_user(db)
    sid = _start(client, headers, _blocks(3))["session_id"]
    before = db["sessions"].find_one({"session_id": sid})
    candidate_id = before["candidate_id"]
    elo_before = db["candidates"].find_one({"candidate_id": candidate_id})["elo_ratings"]["DBMS"]

    import backend.routes.answer as answer_module

    real_enqueue = answer_module.enqueue_narration_job
    failures = {"left": 1}

    def flaky(*args, **kwargs):
        if failures["left"]:
            failures["left"] -= 1
            raise DatabaseConnectionError("injected commit failure")
        return real_enqueue(*args, **kwargs)

    monkeypatch.setattr(answer_module, "enqueue_narration_job", flaky)
    failed = _submit(client, headers, sid, 1)
    assert failed.status_code == 503, failed.text
    rolled = db["sessions"].find_one({"session_id": sid})
    assert rolled["expanded_plan"] == before["expanded_plan"]
    assert rolled["total_rounds"] == before["total_rounds"]
    assert rolled.get("round_plan") == before.get("round_plan")
    assert len(rolled["rounds"]) == 1 and rolled["rounds"][0]["final_score"] is None
    assert db["candidates"].find_one({"candidate_id": candidate_id})["elo_ratings"]["DBMS"] == elo_before

    retried = _submit(client, headers, sid, 1)
    assert retried.status_code == 200, retried.text
    doc = db["sessions"].find_one({"session_id": sid})
    assert len(_follow_up_entries(doc)) == 1 and doc["total_rounds"] == 4
    assert [(r["round"], bool(r.get("is_follow_up"))) for r in doc["rounds"]] == [(1, False), (2, True)]
    assert len(_narrations(db, sid, 1)) == 1


def test_sql_write_conflict_retry_preserves_single_insert(sql_db, independent_workers, system_on, monkeypatch):
    db, engine = sql_db
    calls = _count_scores(monkeypatch)
    user_id, headers = _sql_user(db)
    sid = _start(_client(), headers, _blocks(3))["session_id"]
    import backend.routes.answer as answer_module

    identities = []
    real_build = answer_module.build_system_follow_up_plan_entry

    def spy(**kwargs):
        entry = real_build(**kwargs)
        identities.append(entry["follow_up_identity"])
        return entry

    monkeypatch.setattr(answer_module, "build_system_follow_up_plan_entry", spy)
    gate = _hold_first_write(monkeypatch, {"last_round"})

    def concurrent_writer():
        # An unrelated committed write from another connection: bumps the
        # revision so the held attempt loses and must reload + revalidate.
        worker = threading.Thread(target=lambda: db["sessions"].update_one(
            {"session_id": sid}, {"$set": {"sub_domain": "bumped-by-other-writer"}}))
        worker.start()
        worker.join(timeout=30)

    gate.on_hold = concurrent_writer
    resp = _submit(_client(), headers, sid, 1)
    assert resp.status_code == 200, resp.text
    engine.dispose()
    doc = db["sessions"].find_one({"session_id": sid})
    entries = _follow_up_entries(doc)
    assert len(entries) == 1 and identities and len(set(identities)) == 1
    assert entries[0]["follow_up_identity"] == identities[0]
    assert doc["rounds"][1]["follow_up_identity"] == identities[0]
    assert doc["sub_domain"] == "bumped-by-other-writer"  # never overwritten
    assert len(calls) == 1 and len(_narrations(db, sid, 1)) == 1 and _elo_deltas(sid) == 1


# ── test 6: flag-off transcripts vs the pre-Slice-1 capture ──────────


def _allow_follow_up_snapshot_flip(current, expected):
    """B2 intended difference: NEW follow-up snapshots freeze
    ``rules_replayable=false``. Only follow-up rounds, only True -> False."""
    for now, then in zip(current["round_docs"], expected["round_docs"]):
        if not now.get("is_follow_up"):
            continue
        assert now["attempt_snapshot"]["rules_replayable"] is False
        assert then["attempt_snapshot"]["rules_replayable"] is True
        now["attempt_snapshot"]["rules_replayable"] = True


@pytest.mark.parametrize("which,fixture", [
    ("no_follow_up", "slice1_flag_off_transcript.json"),
    ("candidate_follow_up", "slice1_candidate_transcript.json"),
])
@pytest.mark.parametrize("flag", [None, "true"])
def test_transcript_matches_pre_slice1_capture(mem, monkeypatch, which, fixture, flag):
    """Round docs and API bodies (timestamps/ids normalized) equal the capture
    taken on the pre-Slice-1 tree (9c9b5f2), except listed additive fields.
    ``flag="true"`` keeps the shipped default trigger, which proposes nothing."""
    from backend import config

    if flag:
        monkeypatch.setenv("SYSTEM_FOLLOW_UPS_ENABLED", flag)
        config.get_settings.cache_clear()
    user_id, headers = harness.make_user(mem)
    transcript = harness.RUNNERS[which](_client(), mem, headers, user_id)
    expected = json.loads((FIXTURES / fixture).read_text())
    current = harness.drop_paths(transcript, ADDITIVE_FIELDS)
    _allow_follow_up_snapshot_flip(current, expected)
    assert json.dumps(current, sort_keys=True) == json.dumps(expected, sort_keys=True)
    # The only additive field is the server-only mandatory index on mandatory specs.
    mandatory = [s for s in transcript["session_doc"]["expanded_plan"] if not s.get("is_follow_up")]
    assert [s["mandatory_index"] for s in mandatory] == [s["round"] for s in mandatory]
    assert all("mandatory_index" not in s for s in transcript["session_doc"]["expanded_plan"]
               if s.get("is_follow_up"))


# ── server-only plan keys never reach an API body ────────────────────


def _server_only_paths(value, path="$"):
    from backend.serializers.plan_serializer import SERVER_ONLY_PLAN_KEYS

    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in SERVER_ONLY_PLAN_KEYS:
                found.append(f"{path}.{key}")
            found += _server_only_paths(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found += _server_only_paths(item, f"{path}[{index}]")
    return found


@pytest.mark.parametrize("which", ["no_follow_up", "candidate_follow_up"])
def test_flag_off_api_bodies_carry_no_server_only_plan_keys(mem, which):
    user_id, headers = harness.make_user(mem)
    transcript = harness.RUNNERS[which](_client(), mem, headers, user_id)
    assert {s["step"] for s in transcript["steps"]} >= {"dashboard_report", "account_progress"}
    for step in transcript["steps"]:
        assert _server_only_paths(step["body"]) == [], step["step"]
    # ...while the stored document does carry them (server state).
    assert _server_only_paths(transcript["session_doc"])


def test_system_flow_api_bodies_carry_no_server_only_plan_keys(mem, system_on):
    client = _client()
    user_id, headers = harness.make_user(mem)
    bodies = []

    def keep(response):
        assert response.status_code == 200, response.text
        bodies.append(response.json())
        return response.json()

    sid = keep(client.post("/session/start", headers=headers, json={
        "blocks": _blocks(3), "practice_mode": "coached_practice"}))["session_id"]
    number = 1
    while True:
        body = keep(_submit(client, headers, sid, number))
        keep(client.get(f"/session/{sid}", headers=headers))
        if body["session_complete"]:
            break
        number = body["next_round"]
        keep(client.post(f"/session/{sid}/rounds/{number}/activate", headers=headers))
        keep(client.post(f"/session/{sid}/continue", headers=headers))  # leave + return
    keep(client.get(f"/dashboard/{sid}", headers=headers))
    keep(client.get("/dashboard/progress", headers=headers))
    stored = mem["sessions"].find_one({"session_id": sid})
    assert any(e.get("follow_up_initiator") == "system" for e in stored["expanded_plan"])
    for body in bodies:
        assert _server_only_paths(body) == []


# ── rejection and trigger-failure logging ────────────────────────────


@pytest.fixture
def live_loggers(monkeypatch):
    """Undo ``logging.fileConfig`` side effects from earlier migration tests
    (alembic.ini disables existing loggers), for the loggers under test."""
    import logging

    for name in ("backend.routes.answer", "modules.system_follow_ups"):
        logger = logging.getLogger(name)
        monkeypatch.setattr(logger, "disabled", False)
        monkeypatch.setattr(logger, "propagate", True)


@pytest.mark.parametrize("prompt,category,level", [
    ("How would indexing change this?", "keyword", "WARNING"),
    ("Tell me more.", "question_mark", "WARNING"),
    ("Why " + "x" * 300 + "?", "length", "WARNING"),
    ("What score would you give this?", "score_language", "WARNING"),
])
def test_prompt_rejections_logged_by_category(mem, system_on, caplog, live_loggers, prompt, category, level):
    import logging

    system_on.prompt = prompt
    client = _client()
    user_id, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(3))["session_id"]
    with caplog.at_level(logging.INFO, logger="backend.routes.answer"):
        body = _submit(client, headers, sid, 1, "beta answer about keys").json()
    assert body["total_rounds"] == 3
    hits = [r for r in caplog.records if "System follow-up not scheduled" in r.getMessage()]
    assert len(hits) == 1
    assert f"category={category}" in hits[0].getMessage() and hits[0].levelname == level
    assert prompt not in hits[0].getMessage()  # categories, not prompt text


def test_scheduling_refusal_logged_as_info(mem, system_on, caplog, live_loggers):
    import logging

    client = _client()
    user_id, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(3, max_follow_ups=0))["session_id"]
    with caplog.at_level(logging.INFO, logger="backend.routes.answer"):
        _submit(client, headers, sid, 1)
    hits = [r for r in caplog.records if "System follow-up not scheduled" in r.getMessage()]
    assert len(hits) == 1 and hits[0].levelname == "INFO"
    assert "category=scheduling reason=block_follow_up_cap" in hits[0].getMessage()


def test_trigger_failures_are_logged_and_contained(mem, system_on, caplog, live_loggers):
    import asyncio
    import logging

    client = _client()
    user_id, headers = harness.make_user(mem)

    def explode(context):
        raise RuntimeError("trigger bug")

    async def coroutine_body():
        return STUB_PROMPT

    for trigger, needle, level in (
        (explode, "trigger raised", "WARNING"),
        (lambda context: coroutine_body(), "returned an awaitable", "ERROR"),
        (lambda context: 42, "unsupported int", "WARNING"),
    ):
        system_follow_ups.register_trigger(trigger)
        caplog.clear()
        sid = _start(client, headers, _blocks(3))["session_id"]
        with caplog.at_level(logging.INFO, logger="modules.system_follow_ups"):
            resp = _submit(client, headers, sid, 1)
        assert resp.status_code == 200 and resp.json()["total_rounds"] == 3
        hits = [r for r in caplog.records if needle in r.getMessage()]
        assert len(hits) == 1 and hits[0].levelname == level
        assert "category=trigger_error" in hits[0].getMessage()
        if trigger is explode:
            assert hits[0].exc_info is not None
    with pytest.raises(TypeError, match="synchronous"):
        system_follow_ups.register_trigger(coroutine_body)
    assert asyncio.iscoroutinefunction(coroutine_body)


# ── known issue (pre-existing, independent of system insertion) ──────


@pytest.mark.xfail(strict=True, reason=(
    "KNOWN ISSUE (pre-Slice-1): /continue builds a pending candidate "
    "follow-up as an ordinary question (no follow-up flags, bank prompt). "
    "Fix tracked separately; not part of B2."))
def test_continue_materializes_pending_candidate_follow_up(mem, monkeypatch):
    from backend.integrations import IntegrationError

    client = _client()
    user_id, headers = harness.make_user(mem)
    sid = _start(client, headers, _blocks(2))["session_id"]  # flag off
    assert _submit(client, headers, sid, 1).status_code == 200
    entry_resp = client.post(f"/session/{sid}/follow-ups", headers=headers, json={
        "parent_round": 1, "accept_eligibility_consequence": True}).json()
    assert entry_resp["scheduled"] is True and entry_resp["total_rounds"] == 3
    _activate(client, headers, sid, 2)

    def bank_miss(**kwargs):
        raise IntegrationError("stub bank exhausted")

    monkeypatch.setattr("backend.routes.answer._get_next_question", bank_miss)
    body = _submit(client, headers, sid, 2, "beta answer about keys").json()
    assert body["session_status"] == "content_blocked"  # follow-up round 3 not built
    monkeypatch.setattr("backend.routes.answer._get_next_question", harness.stub_next_question)
    cont = client.post(f"/session/{sid}/continue", headers=headers)
    assert cont.status_code == 200 and cont.json()["round"] == 3
    built = mem["sessions"].find_one({"session_id": sid})["rounds"][2]
    # Correct behaviour (what the submit path builds for the same spec):
    assert built.get("is_follow_up") is True
    assert built.get("follow_up_identity") == entry_resp["follow_up_identity"]
    assert built["question"] == "Clarify X"
