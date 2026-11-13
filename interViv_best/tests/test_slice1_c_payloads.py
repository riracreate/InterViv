"""Slice 1 / Checkpoint C: server-derived, backward-compatible payload fields.

Memory backend through the real routes. Postgres is not exercised.
"""

from __future__ import annotations

import pytest

from backend.main import app  # noqa: F401
from modules import system_follow_ups
from modules.system_follow_ups import SystemFollowUpProposal
from tests import slice1_harness as harness
from tests.test_slice1_system_follow_ups import (  # noqa: F401  (fixtures)
    STUB_PROMPT,
    _activate,
    _client,
    _server_only_paths,
    _start,
    _submit,
    mem,
    system_on,
)

LABEL = "Follow-up (not scored)"
TEN = [{"round_type": "technical_short_answer", "category": "interview",
        "skills": ["DBMS"], "count": 10, "allow_optional_follow_ups": True}]
MANDATORY_KEYS = {"mandatory_total", "mandatory_completed", "mandatory_index",
                  "current_mandatory_index", "next_mandatory_index"}


def _only_parent(number):
    def trigger(context):
        if int(context["parent_round"]["round"]) == number:
            return SystemFollowUpProposal(prompt=STUB_PROMPT)
        return None
    return trigger


def _history(body, number):
    return next(e for e in body["round_history"] if e["round"] == number)


def _keys_anywhere(value):
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys_anywhere(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys_anywhere(v)}
    return set()


def test_parent_follow_up_and_next_mandatory_progress_fields(mem, system_on):
    """Parent 3/10, follow-up 3/10, next mandatory 4/10 -- through submit,
    activation, refresh (GET) and /continue; the follow-up never advances
    ``mandatory_completed``."""
    system_follow_ups.register_trigger(_only_parent(3))
    client = _client()
    uid, headers = harness.make_user(mem)
    start = _start(client, headers, TEN)
    sid = start["session_id"]
    assert (start["mandatory_index"], start["mandatory_total"], start["mandatory_completed"]) == (1, 10, 0)
    bodies = [start]
    for number in (1, 2):
        body = _submit(client, headers, sid, number).json()
        assert (body["current_mandatory_index"], body["next_mandatory_index"]) == (number, number + 1)
        bodies += [body, _activate(client, headers, sid, number + 1)]

    parent = _submit(client, headers, sid, 3).json()
    bodies.append(parent)
    assert (parent["current_mandatory_index"], parent["next_mandatory_index"]) == (3, 3)
    assert (parent["mandatory_completed"], parent["mandatory_total"]) == (3, 10)
    assert parent["system_follow_up_scheduled"] is True and parent["next_round"] == 4
    assert parent["total_rounds"] == 11 and "follow_up_label" not in parent

    restored = client.get(f"/session/{sid}", headers=headers).json()  # refresh during review
    bodies.append(restored)
    assert restored["review_round"] == 3 and restored["mandatory_completed"] == 3
    assert _history(restored, 3)["system_follow_up_scheduled"] is True
    assert _history(restored, 3)["mandatory_index"] == 3

    activated = client.post(f"/session/{sid}/rounds/4/activate", headers=headers).json()
    bodies.append(activated)
    fu = activated["active_round"]
    assert (fu["round"], fu["is_follow_up"], fu["mandatory_index"]) == (4, True, 3)
    assert fu["follow_up_label"] == LABEL and "system_follow_up_scheduled" not in fu
    assert activated["mandatory_completed"] == 3

    answering = client.get(f"/session/{sid}", headers=headers).json()  # refresh while answering
    reopened = client.post(f"/session/{sid}/continue", headers=headers).json()  # leave + return
    bodies += [answering, reopened]
    assert answering["active_round"]["mandatory_index"] == 3
    assert answering["active_round"]["follow_up_label"] == LABEL
    assert reopened["mandatory_index"] == 3 and reopened["active_round"]["follow_up_label"] == LABEL
    assert answering["mandatory_completed"] == reopened["mandatory_completed"] == 3

    done = _submit(client, headers, sid, 4, "a clarification answer").json()
    bodies.append(done)
    assert (done["current_mandatory_index"], done["next_mandatory_index"]) == (3, 4)
    assert done["mandatory_completed"] == 3 and done["follow_up_label"] == LABEL
    assert "system_follow_up_scheduled" not in done
    review = client.get(f"/session/{sid}", headers=headers).json()  # refresh during follow-up review
    bodies.append(review)
    assert review["review_round"] == 4 and review["mandatory_completed"] == 3
    entry = _history(review, 4)
    assert (entry["mandatory_index"], entry["follow_up_label"]) == (3, LABEL)
    assert _history(review, 3)["system_follow_up_scheduled"] is True

    nxt = client.post(f"/session/{sid}/rounds/5/activate", headers=headers).json()
    bodies.append(nxt)
    assert (nxt["active_round"]["mandatory_index"], nxt["mandatory_completed"]) == (4, 3)
    assert "follow_up_label" not in nxt["active_round"]
    after = _submit(client, headers, sid, 5).json()
    bodies.append(after)
    assert (after["current_mandatory_index"], after["mandatory_completed"]) == (4, 4)
    for body in bodies:
        assert _server_only_paths(body) == []


def test_continue_after_blocked_follow_up_reports_next_mandatory_index(mem, system_on, monkeypatch):
    from backend.integrations import IntegrationError

    system_follow_ups.register_trigger(_only_parent(1))
    client = _client()
    uid, headers = harness.make_user(mem)
    sid = _start(client, headers, TEN)["session_id"]
    _submit(client, headers, sid, 1)
    _activate(client, headers, sid, 2)

    def bank_miss(**kwargs):
        raise IntegrationError("stub bank exhausted")

    monkeypatch.setattr("backend.routes.answer._get_next_question", bank_miss)
    blocked = _submit(client, headers, sid, 2, "a clarification answer").json()
    assert blocked["session_status"] == "content_blocked" and blocked["next_mandatory_index"] is None
    monkeypatch.setattr("backend.routes.answer._get_next_question", harness.stub_next_question)
    resumed = client.post(f"/session/{sid}/continue", headers=headers).json()
    assert resumed["round"] == 3 and resumed["mandatory_index"] == 2
    assert resumed["active_round"]["mandatory_index"] == 2 and resumed["mandatory_completed"] == 1


def test_legacy_plans_omit_mandatory_fields(mem):
    client = _client()
    uid, headers = harness.make_user(mem)
    sid = _start(client, headers, TEN)["session_id"]
    doc = mem["sessions"].find_one({"session_id": sid})
    legacy = [{k: v for k, v in e.items() if k != "mandatory_index"} for e in doc["expanded_plan"]]
    mem["sessions"].update_one({"session_id": sid}, {"$set": {"expanded_plan": legacy}})
    bodies = [_submit(client, headers, sid, 1).json(),
              client.post(f"/session/{sid}/rounds/2/activate", headers=headers).json(),
              client.get(f"/session/{sid}", headers=headers).json(),
              client.post(f"/session/{sid}/continue", headers=headers).json()]
    for body in bodies:
        assert not (_keys_anywhere(body) & MANDATORY_KEYS)
    assert bodies[0]["system_follow_up_scheduled"] is False  # not a mandatory field


def _seed_reviewed(db, sid):
    doc = db["sessions"].find_one({"session_id": sid})
    plan = [dict(e, follow_up_scoring="reviewed") if e.get("is_follow_up") else e for e in doc["expanded_plan"]]
    db["sessions"].update_one({"session_id": sid}, {"$set": {"expanded_plan": plan}})


@pytest.mark.parametrize("reviewed", [False, True])
def test_candidate_follow_up_fields(mem, reviewed):
    """Candidate follow-ups derive their parent's index, get no system label,
    and land in the follow-up report section only when unreviewed."""
    client = _client()
    uid, headers = harness.make_user(mem)
    blocks = [dict(TEN[0], count=2)]
    sid = _start(client, headers, blocks)["session_id"]
    _submit(client, headers, sid, 1)
    req = client.post(f"/session/{sid}/follow-ups", headers=headers, json={
        "parent_round": 1, "accept_eligibility_consequence": True}).json()
    assert req["scheduled"] is True and set(req) >= {"label", "eligibility_note"}  # unchanged shape
    if reviewed:
        _seed_reviewed(mem, sid)
    _activate(client, headers, sid, 2)
    last = _submit(client, headers, sid, 2).json()
    assert (last["current_mandatory_index"], last["next_mandatory_index"]) == (2, 1)
    fu = client.post(f"/session/{sid}/rounds/3/activate", headers=headers).json()["active_round"]
    assert fu["is_follow_up"] is True and fu["mandatory_index"] == 1 and "follow_up_label" not in fu
    text = "zeta reviewed follow-up answer" if reviewed else "epsilon follow-up answer"
    done = _submit(client, headers, sid, 3, text).json()
    assert "follow_up_label" not in done and done["mandatory_completed"] == 2
    report = client.get(f"/dashboard/{sid}", headers=headers).json()
    sections = {r["round"]: r["report_section"] for r in report["rounds"]}
    assert sections == {1: "rounds", 2: "rounds", 3: "rounds" if reviewed else "follow_ups"}
    assert all("follow_up_label" not in r for r in report["rounds"])


def test_report_section_uses_the_backend_predicate_even_with_a_score(mem, system_on):
    system_follow_ups.register_trigger(_only_parent(1))
    client = _client()
    uid, headers = harness.make_user(mem)
    sid = _start(client, headers, [dict(TEN[0], count=2)])["session_id"]
    _submit(client, headers, sid, 1)
    _activate(client, headers, sid, 2)
    _submit(client, headers, sid, 2, "a clarification answer")
    _activate(client, headers, sid, 3)
    _submit(client, headers, sid, 3, harness.TRANSCRIPT_ANSWERS[1])
    doc = mem["sessions"].find_one({"session_id": sid})
    forced = [dict(r, final_score=95.0) if r.get("is_follow_up") else r for r in doc["rounds"]]
    mem["sessions"].update_one({"session_id": sid}, {"$set": {"rounds": forced}})
    report = client.get(f"/dashboard/{sid}", headers=headers).json()
    by_round = {r["round"]: r for r in report["rounds"]}
    assert by_round[2]["report_section"] == "follow_ups" and by_round[2]["follow_up_label"] == LABEL
    assert by_round[2]["final_score"] == 95.0  # shown in its own section only
    assert {by_round[1]["report_section"], by_round[3]["report_section"]} == {"rounds"}
    # Scored series exclude the follow-up section despite its numeric score.
    assert len(report["elo_progression"]) == len(report["difficulty_progression"]) == 2
    assert report["coverage"]["scored_rounds"] == 2
    assert _server_only_paths(report) == []
