"""Emit real Slice 1 follow-up payloads for the Node contract tests.

Drives the real routes (memory store, stubbed bank and scorer from
``tests/slice1_harness.py``) with system follow-ups enabled and a stub
trigger that proposes one follow-up after question 3 of 10. Also emits the
report of a session with a reviewed, scored candidate follow-up (80 / 60 /
100), a system follow-up report with a forced numeric score, and the flow of
a candidate-requested follow-up after two mandatory questions (flag-off path).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ["SYSTEM_FOLLOW_UPS_ENABLED"] = "true"

APP_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(APP_ROOT))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from modules import system_follow_ups  # noqa: E402
from modules.system_follow_ups import SystemFollowUpProposal  # noqa: E402
from tests import slice1_harness as harness  # noqa: E402

PROMPT = "Could you walk through a concrete example of that idea?"


def _interview(count, skill="DBMS"):
    return {"round_type": "technical_short_answer", "category": "interview",
            "skills": [skill], "count": count, "allow_optional_follow_ups": True}


def _system_flow(client, db):
    def trigger(context):
        if int(context["parent_round"]["round"]) == 3:
            return SystemFollowUpProposal(prompt=PROMPT)
        return None

    system_follow_ups.register_trigger(trigger)
    uid, headers = harness.make_user(db, prefix="emit-system")
    out = {}
    start = client.post("/session/start", headers=headers,
                        json={"blocks": [_interview(10)], "practice_mode": "coached_practice"}).json()
    sid = start["session_id"]
    out["start"] = start

    def submit(number, text=harness.TRANSCRIPT_ANSWERS[0]):
        return client.post("/session/answer", headers=headers,
                           json={"session_id": sid, "round": number, "answer_text": text}).json()

    def activate(number):
        return client.post(f"/session/{sid}/rounds/{number}/activate", headers=headers).json()

    def get():
        return client.get(f"/session/{sid}", headers=headers).json()

    for number in (1, 2):
        submit(number)
        activate(number + 1)
    out["parent_submit"] = submit(3)
    out["refresh_parent_review"] = get()
    out["follow_up_activate"] = activate(4)
    out["refresh_follow_up_answering"] = get()
    out["follow_up_continue"] = client.post(f"/session/{sid}/continue", headers=headers).json()
    out["follow_up_submit"] = submit(4, "a clarification answer")
    out["refresh_follow_up_review"] = get()
    out["next_activate"] = activate(5)
    out["refresh_next_answering"] = get()
    out["next_submit"] = submit(5)
    number = 5
    body = out["next_submit"]
    while not body.get("session_complete"):
        number = body["next_round"]
        activate(number)
        body = submit(number)
    doc = db["sessions"].find_one({"session_id": sid})
    forced = [dict(r, final_score=95.0) if r.get("is_follow_up") else r for r in doc["rounds"]]
    db["sessions"].update_one({"session_id": sid}, {"$set": {"rounds": forced}})
    out["system_report_forced_score"] = client.get(f"/dashboard/{sid}", headers=headers).json()
    system_follow_ups.reset_trigger()
    return out


def _reviewed_candidate_report(client, db):
    system_follow_ups.register_trigger(None)
    uid, headers = harness.make_user(db, prefix="emit-reviewed")
    sid = client.post("/session/start", headers=headers, json={
        "blocks": [_interview(1, "DBMS"), _interview(1, "OS")],
        "practice_mode": "coached_practice"}).json()["session_id"]
    body = client.post("/session/answer", headers=headers, json={
        "session_id": sid, "round": 1, "answer_text": harness.TRANSCRIPT_ANSWERS[0]}).json()
    client.post(f"/session/{sid}/follow-ups", headers=headers,
                json={"parent_round": 1, "accept_eligibility_consequence": True})
    doc = db["sessions"].find_one({"session_id": sid})
    plan = [dict(e, follow_up_scoring="reviewed") if e.get("is_follow_up") else e for e in doc["expanded_plan"]]
    db["sessions"].update_one({"session_id": sid}, {"$set": {"expanded_plan": plan}})
    for text in (harness.TRANSCRIPT_ANSWERS[1], "zeta reviewed follow-up answer"):
        number = body["next_round"]
        client.post(f"/session/{sid}/rounds/{number}/activate", headers=headers)
        body = client.post("/session/answer", headers=headers, json={
            "session_id": sid, "round": number, "answer_text": text}).json()
    system_follow_ups.reset_trigger()
    return client.get(f"/dashboard/{sid}", headers=headers).json()


def _candidate_follow_up_flow(client, db):
    system_follow_ups.register_trigger(None)
    uid, headers = harness.make_user(db, prefix="emit-candidate")
    sid = client.post("/session/start", headers=headers, json={
        "blocks": [_interview(2)], "practice_mode": "coached_practice"}).json()["session_id"]

    def submit(number, text):
        return client.post("/session/answer", headers=headers,
                           json={"session_id": sid, "round": number, "answer_text": text}).json()

    def activate(number):
        return client.post(f"/session/{sid}/rounds/{number}/activate", headers=headers).json()

    def get():
        return client.get(f"/session/{sid}", headers=headers).json()

    out = {}
    submit(1, harness.TRANSCRIPT_ANSWERS[0])
    client.post(f"/session/{sid}/follow-ups", headers=headers,
                json={"parent_round": 1, "accept_eligibility_consequence": True})
    activate(2)
    out["last_mandatory_submit"] = submit(2, harness.TRANSCRIPT_ANSWERS[1])
    out["follow_up_activate"] = activate(3)
    out["refresh_follow_up_answering"] = get()
    out["follow_up_continue"] = client.post(f"/session/{sid}/continue", headers=headers).json()
    out["follow_up_submit"] = submit(3, "epsilon follow-up answer")
    out["refresh_follow_up_review"] = get()
    system_follow_ups.reset_trigger()
    return out


def main() -> None:
    with pytest.MonkeyPatch.context() as mp:
        db = harness.install(mp)
        client = TestClient(app)
        payloads = _system_flow(client, db)
        payloads["reviewed_candidate_report"] = _reviewed_candidate_report(client, db)
        payloads["candidate_follow_up"] = _candidate_follow_up_flow(client, db)
    sys.stdout.write(json.dumps(payloads, default=str))


if __name__ == "__main__":
    main()
