"""Deterministic session harness for Slice 1 compatibility tests.

Drives the real FastAPI routes on an isolated in-memory store with a
stubbed question bank and scorer, then normalizes run-specific values so
transcripts compare byte-for-byte across code versions.

Normalization (everything else is compared verbatim):

- dropped keys (any depth): ``TIME_KEYS`` -- started_at, expires_at,
  submitted_at, created_at, completed_at, updated_at, cutoff_at,
  last_active_at, delivered_at, activated_at, digest, delivery_order,
  server_time, last_practiced_at;
- string replacements: session id -> ``<sid>`` (``<s1>``/``<s2>`` in the
  account transcript), candidate id -> ``<cid>``, user id -> ``<uid>``,
  block ids -> ``<blockN>``, follow-up identity suffix
  ``followup:N:<id>``, any UUID -> ``<uuid>``, 32-64 hex runs -> ``<hex>``;
- datetime objects -> ``"<datetime>"``; floats rounded to 6 places;
  dict keys sorted; stored ``session_doc`` omits ``rounds``/``revision``;
- order-only: exposures sorted after normalization; Progress
  ``learning_signals.elo_deltas`` sorted (no stable order between events
  written in quick succession). Uses only APIs that predate Slice 1, so the same module
captures the pre-change baseline:

    python -m tests.slice1_harness --write tests/fixtures/slice1_flag_off_transcript.json no_follow_up
    python -m tests.slice1_harness --write tests/fixtures/slice1_candidate_transcript.json candidate_follow_up
    python -m tests.slice1_harness --write tests/fixtures/slice1_account_transcript.json account_candidate_follow_ups
    python -m tests.slice1_harness --write tests/fixtures/slice1_upload_start_transcript.json upload_start
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

TIME_KEYS = frozenset({
    "started_at", "expires_at", "submitted_at", "created_at", "completed_at",
    "updated_at", "cutoff_at", "last_active_at", "delivered_at", "activated_at",
    "digest",
    # Process-wide counter (modules/teaching_exposures.py): run-specific.
    "delivery_order",
    # Wall-clock fields in the report / Progress payloads.
    "server_time", "last_practiced_at",
})
_FOLLOW_UP_ID = re.compile(r"followup:(\d+):[0-9a-f]{8}")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_HEX_ID = re.compile(r"\b[0-9a-f]{32,64}\b")

STUB_SCORES = {
    "alpha answer about normalization and indexing": 80.0,
    "beta answer about keys": 60.0,
    "gamma answer about processes": 40.0,
    "delta answer about scheduling": 90.0,
    "zeta reviewed follow-up answer": 100.0,
}


def stub_next_question(*, skill, sub_domain, difficulty, asked, **_ignored):
    prefix = f"[{skill}]"
    n = sum(1 for q in (asked or []) if str(q).startswith(prefix)) + 1
    return {
        "question": f"{prefix} Stub question {n}: explain the core idea?",
        "ideal_answer": f"{skill} reference answer {n}.",
        "ideal_keywords": "normalization, indexing",
        "ideal_keywords_list": ["normalization", "indexing"],
        "skill": skill,
        "sub_domain": sub_domain,
        "topic": sub_domain,
        "difficulty": difficulty,
        "question_type": "conceptual",
        "company": "",
        "role": "",
        "followups": ["Clarify X"],
        "source": "test_stub",
        "llm_provider": None,
        "llm_model": None,
        "target_concepts": [],
        "adaptive_selected": False,
    }


def stub_score_round(**kwargs):
    text = str(kwargs.get("answer_text") or "")
    score = STUB_SCORES.get(text, 55.0)
    return {
        "final_score": score,
        "nlp_score": round(score / 10, 2),
        "svm_label": "Good" if score >= 70 else "Average",
        "kg_score": 0.5,
        "ner_entities": [],
        "feedback": {
            "content": [f"Stub feedback for {score:.0f}."],
            "strengths": ["stub strength"],
            "weakness": ["stub weakness"],
            "next_step": "stub next step",
        },
        "scoring_breakdown": {
            "covered_concepts": [],
            "missing_concepts": [],
            "concepts": {"covered": [], "missing": []},
            "semantic_scoring_available": False,
        },
        "score_explanation": {},
        "guard_applied": None,
        "scoring_schema_version": "stub-v1",
        "rubric": {},
        "concepts": {},
        "guard": {},
    }


def install_stubs(monkeypatch, next_question=stub_next_question):
    """Deterministic bank and scorer on every route (any store backend)."""
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    for module in ("backend.routes.session", "backend.routes.answer", "backend.routes.session_continue"):
        monkeypatch.setattr(f"{module}._get_next_question", next_question)
    monkeypatch.setattr("backend.routes.answer.score_round", stub_score_round)


def install(monkeypatch, db=None):
    """Point every route at a fresh memory store with stubbed bank/scorer."""
    from backend import config as app_config
    from backend.db.memory import _MemoryDB

    db = db or _MemoryDB()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "true")
    app_config.get_settings.cache_clear()
    monkeypatch.setattr("backend.db.get_database", lambda: db)
    monkeypatch.setattr("backend.db.memory.get_memory_database", lambda: db)
    monkeypatch.setattr("backend.db._get_memory_db", lambda: db)
    install_stubs(monkeypatch)
    return db


def make_user(db, prefix="slice1"):
    from backend.auth.security import create_access_token, hash_password

    user_id = str(uuid4())
    now = datetime.now(timezone.utc)
    db["users"].insert_one({
        "id": user_id,
        "email": f"{prefix}-{user_id[:8]}@example.com",
        "name": f"Test {prefix}",
        "password_hash": hash_password("passw0rd123"),
        "created_at": now,
        "last_active_at": now,
    })
    return user_id, {"Authorization": f"Bearer {create_access_token(user_id)}"}


TRANSCRIPT_BLOCKS = [
    {"round_type": "technical_short_answer", "category": "interview",
     "skills": ["DBMS"], "count": 2, "allow_optional_follow_ups": True},
    {"round_type": "technical_short_answer", "category": "interview",
     "skills": ["OS"], "count": 2, "allow_optional_follow_ups": True},
]
TRANSCRIPT_ANSWERS = [
    "alpha answer about normalization and indexing",
    "beta answer about keys",
    "gamma answer about processes",
    "delta answer about scheduling",
]


def normalize(value: Any, replacements: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            k: normalize(v, replacements)
            for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
            if k not in TIME_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [normalize(v, replacements) for v in value]
    if isinstance(value, datetime):
        return "<datetime>"
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, str):
        for raw, token in replacements.items():
            if raw:
                value = value.replace(raw, token)
        value = _FOLLOW_UP_ID.sub(r"followup:\1:<id>", value)
        value = _UUID.sub("<uuid>", value)
        return _HEX_ID.sub("<hex>", value)
    return value


def record_reports(record, client, headers, sid) -> None:
    """Session report (whole-document payload) and account Progress."""
    record("dashboard_report", client.get(f"/dashboard/{sid}", headers=headers))
    record("account_progress", client.get("/dashboard/progress", headers=headers))


# The Upload page's start body (frontend/src/pages/Upload.jsx): legacy skills
# and rounds_per_skill -- no blocks, no practice_mode, no follow-up opt-in.
UPLOAD_START = {"skill": "DBMS", "skills": ["DBMS", "OS"], "sub_domain": "general", "rounds_per_skill": 2}


def run_transcript(client, db, headers, user_id, start_payload=None) -> dict[str, Any]:
    """Start → (GET, submit, GET, activate) × N → final GET, plus stored docs."""
    steps: list[dict[str, Any]] = []

    def record(name, response):
        steps.append({"step": name, "status": response.status_code, "body": response.json()})
        return response.json()

    started = record("start", client.post("/session/start", headers=headers, json=start_payload or {
        "blocks": TRANSCRIPT_BLOCKS, "practice_mode": "coached_practice",
    }))
    sid = started["session_id"]
    record("get_after_start", client.get(f"/session/{sid}", headers=headers))
    for number, answer in enumerate(TRANSCRIPT_ANSWERS, start=1):
        body = record(f"submit_{number}", client.post("/session/answer", headers=headers, json={
            "session_id": sid, "round": number, "answer_text": answer,
        }))
        record(f"get_after_submit_{number}", client.get(f"/session/{sid}", headers=headers))
        if body.get("next_round_status") == "ready":
            record(f"activate_{body['next_round']}", client.post(
                f"/session/{sid}/rounds/{body['next_round']}/activate", headers=headers))
    record("get_final", client.get(f"/session/{sid}", headers=headers))
    record_reports(record, client, headers, sid)
    stored = db["sessions"].find_one({"session_id": sid}) or {}
    session_doc = {k: v for k, v in stored.items() if k not in ("rounds", "revision")}
    replacements = {
        sid: "<sid>",
        str(started.get("candidate_id") or ""): "<cid>",
        str(user_id): "<uid>",
    }
    for position, block in enumerate(started.get("block_plan") or [], start=1):
        replacements[str(block.get("id") or "")] = f"<block{position}>"
    return normalize({
        "steps": steps,
        "round_docs": stored.get("rounds") or [],
        "session_doc": session_doc,
    }, replacements)


def run_upload_start_transcript(client, db, headers, user_id) -> dict[str, Any]:
    """The same flow from a non-Practice start (the Upload page's body)."""
    return run_transcript(client, db, headers, user_id, start_payload=UPLOAD_START)


def run_candidate_transcript(client, db, headers, user_id) -> dict[str, Any]:
    """Candidate-requested follow-up after round 1, walked to completion."""
    steps: list[dict[str, Any]] = []

    def record(name, response):
        steps.append({"step": name, "status": response.status_code, "body": response.json()})
        return response.json()

    started = record("start", client.post("/session/start", headers=headers, json={
        "blocks": TRANSCRIPT_BLOCKS, "practice_mode": "coached_practice",
    }))
    sid = started["session_id"]
    body = record("submit_1", client.post("/session/answer", headers=headers, json={
        "session_id": sid, "round": 1, "answer_text": TRANSCRIPT_ANSWERS[0],
    }))
    record("follow_up_without_consent", client.post(
        f"/session/{sid}/follow-ups", headers=headers, json={"parent_round": 1}))
    record("follow_up_request", client.post(
        f"/session/{sid}/follow-ups", headers=headers,
        json={"parent_round": 1, "accept_eligibility_consequence": True}))
    record("follow_up_repeat", client.post(
        f"/session/{sid}/follow-ups", headers=headers,
        json={"parent_round": 1, "accept_eligibility_consequence": True}))
    record("get_after_request", client.get(f"/session/{sid}", headers=headers))
    answers = TRANSCRIPT_ANSWERS[1:] + ["epsilon follow-up answer"]
    number = 1
    for answer in answers:
        if body.get("next_round_status") != "ready":
            break
        number = body["next_round"]
        record(f"activate_{number}", client.post(
            f"/session/{sid}/rounds/{number}/activate", headers=headers))
        body = record(f"submit_{number}", client.post("/session/answer", headers=headers, json={
            "session_id": sid, "round": number, "answer_text": answer,
        }))
        record(f"get_after_submit_{number}", client.get(f"/session/{sid}", headers=headers))
    record_reports(record, client, headers, sid)
    stored = db["sessions"].find_one({"session_id": sid}) or {}
    exposures = sorted(
        (doc for doc in (db["teaching_exposures"].find({"session_id": sid}) or [])),
        key=lambda doc: (str(doc.get("content_kind")), int(doc.get("round") or 0)),
    )
    replacements = {
        sid: "<sid>",
        str(started.get("candidate_id") or ""): "<cid>",
        str(user_id): "<uid>",
    }
    for position, block in enumerate(started.get("block_plan") or [], start=1):
        replacements[str(block.get("id") or "")] = f"<block{position}>"
    return normalize({
        "steps": steps,
        "round_docs": stored.get("rounds") or [],
        "session_doc": {k: v for k, v in stored.items() if k not in ("rounds", "revision")},
        "exposures": exposures,
    }, replacements)


# Checkpoint C additive, server-derived API fields (allowed differences in
# API bodies; their values are asserted separately).
ADDITIVE_BODY_KEYS = frozenset({
    "mandatory_index", "mandatory_total", "mandatory_completed",
    "current_mandatory_index", "next_mandatory_index",
    "system_follow_up_scheduled", "report_section", "follow_up_label",
    "progress_label",
})


def drop_additive_body_keys(transcript: dict[str, Any]) -> dict[str, Any]:
    """Copy of ``transcript`` with ADDITIVE_BODY_KEYS removed from step bodies.

    Plan entries inside bodies are skipped on purpose: a plan-level
    ``mandatory_index`` in a body is a leak, not an additive field.
    """
    out = json.loads(json.dumps(transcript))

    def strip(node, in_plan=False):
        if isinstance(node, dict):
            for key in list(node):
                if key in ADDITIVE_BODY_KEYS and not in_plan:
                    node.pop(key)
                else:
                    strip(node[key], in_plan or key == "expanded_plan")
        elif isinstance(node, list):
            for item in node:
                strip(item, in_plan)

    for step in out.get("steps", []):
        strip(step.get("body"))
    return out


def drop_paths(value: Any, patterns: list[tuple[str, ...]]) -> Any:
    """Remove allowed additive fields (``*`` matches any key/index)."""
    value = json.loads(json.dumps(value))

    def _drop(node, pattern):
        if not pattern:
            return
        head, rest = pattern[0], pattern[1:]
        if isinstance(node, dict):
            keys = list(node) if head == "*" else ([head] if head in node else [])
            for key in keys:
                if not rest:
                    node.pop(key, None)
                else:
                    _drop(node[key], rest)
        elif isinstance(node, list):
            items = node if head == "*" else []
            for item in items:
                _drop(item, rest)

    for pattern in patterns:
        _drop(value, pattern)
    return value


def run_account_transcript(client, db, headers, user_id) -> dict[str, Any]:
    """Account-level view of candidate follow-ups (readiness, graph, history).

    Session 1: DBMS 80 then OS 60 (separate blocks, so the follow-up
    request's DBMS exposure leaves the OS round eligible) plus a REVIEWED
    candidate follow-up scored 100. The route never builds reviewed
    follow-ups, so the pending entry is marked reviewed in storage before it
    materializes -- identical seeding on every code version. Session 2:
    OS 40 / 90 plus an unreviewed candidate follow-up.
    """
    steps: list[dict[str, Any]] = []

    def record(name, response):
        steps.append({"step": name, "status": response.status_code, "body": response.json()})
        return response.json()

    db["target_contexts"].insert_one({"user_id": user_id, "company_id": "tcs", "role_id": "tcs_swe"})
    def interview(skill, count):
        return {"round_type": "technical_short_answer", "category": "interview",
                "skills": [skill], "count": count, "allow_optional_follow_ups": True}

    plans = [
        ("s1", [interview("DBMS", 1), interview("OS", 1)],
         [TRANSCRIPT_ANSWERS[0], TRANSCRIPT_ANSWERS[1], "zeta reviewed follow-up answer"], True),
        ("s2", [interview("OS", 2)],
         [TRANSCRIPT_ANSWERS[2], TRANSCRIPT_ANSWERS[3], "epsilon follow-up answer"], False),
    ]
    replacements: dict[str, str] = {str(user_id): "<uid>"}
    sids = []
    for label, blocks, answers, reviewed in plans:
        started = record(f"{label}_start", client.post("/session/start", headers=headers, json={
            "blocks": blocks, "practice_mode": "coached_practice",
        }))
        sid = started["session_id"]
        sids.append(sid)
        replacements[sid] = f"<{label}>"
        replacements[str(started.get("candidate_id") or "")] = "<cid>"
        for position, block in enumerate(started.get("block_plan") or [], start=1):
            replacements[str(block.get("id") or "")] = f"<{label}_block{position}>"
        body = record(f"{label}_submit_1", client.post("/session/answer", headers=headers, json={
            "session_id": sid, "round": 1, "answer_text": answers[0]}))
        record(f"{label}_follow_up", client.post(f"/session/{sid}/follow-ups", headers=headers,
                                                  json={"parent_round": 1, "accept_eligibility_consequence": True}))
        if reviewed:
            doc = db["sessions"].find_one({"session_id": sid})
            plan = [dict(e, follow_up_scoring="reviewed") if e.get("is_follow_up") else e
                    for e in doc["expanded_plan"]]
            db["sessions"].update_one({"session_id": sid}, {"$set": {"expanded_plan": plan}})
        for answer in answers[1:]:
            number = body.get("next_round")
            if body.get("next_round_status") != "ready":
                break
            record(f"{label}_activate_{number}", client.post(
                f"/session/{sid}/rounds/{number}/activate", headers=headers))
            body = record(f"{label}_submit_{number}", client.post("/session/answer", headers=headers, json={
                "session_id": sid, "round": number, "answer_text": answer}))
    record("progress_before_reports", client.get("/dashboard/progress", headers=headers))
    for label, sid in zip(("s1", "s2"), sids):
        record(f"{label}_report", client.get(f"/dashboard/{sid}", headers=headers))
    record("progress_after_reports", client.get("/dashboard/progress", headers=headers))
    exposures = [doc for sid in sids for doc in (db["teaching_exposures"].find({"session_id": sid}) or [])]
    out = normalize({"steps": steps, "exposures": exposures}, replacements)
    # Sort after normalization: raw session ids are random per run.
    out["exposures"].sort(key=lambda doc: (str(doc.get("session_id")), str(doc.get("content_kind")),
                                           int(doc.get("round") or 0)))
    # Progress ``learning_signals.elo_deltas`` has no stable order between
    # events written in quick succession; compare its contents, not order.
    for step in out["steps"]:
        signals = (step.get("body") or {}).get("learning_signals")
        if isinstance(signals, dict) and isinstance(signals.get("elo_deltas"), list):
            signals["elo_deltas"].sort(key=lambda item: json.dumps(item, sort_keys=True))
    return out


def run_two_candidate_transcript(client, db, headers, user_id) -> dict[str, Any]:
    """Two REVIEWED candidate follow-ups in one session.

    A reviewed follow-up serves a real bank question. This pins that the
    second follow-up's selection still sees the first in the asked list (so
    it is not re-served). Reviewed is seeded in storage, as in the account
    run, because the route never builds reviewed entries.
    """
    steps: list[dict[str, Any]] = []

    def record(name, response):
        steps.append({"step": name, "status": response.status_code, "body": response.json()})
        return response.json()

    started = record("start", client.post("/session/start", headers=headers, json={
        "blocks": [{"round_type": "technical_short_answer", "category": "interview",
                    "skills": ["DBMS"], "count": 3, "allow_optional_follow_ups": True}],
        "practice_mode": "coached_practice",
    }))
    sid = started["session_id"]
    body = record("submit_1", client.post("/session/answer", headers=headers, json={
        "session_id": sid, "round": 1, "answer_text": TRANSCRIPT_ANSWERS[0]}))
    def mark_reviewed():
        doc = db["sessions"].find_one({"session_id": sid})
        plan = [dict(e, follow_up_scoring="reviewed") if e.get("is_follow_up") else e
                for e in doc["expanded_plan"]]
        db["sessions"].update_one({"session_id": sid}, {"$set": {"expanded_plan": plan}})

    record("follow_up_parent_1", client.post(f"/session/{sid}/follow-ups", headers=headers,
                                             json={"parent_round": 1, "accept_eligibility_consequence": True}))
    mark_reviewed()
    answers = [TRANSCRIPT_ANSWERS[1], TRANSCRIPT_ANSWERS[2], "zeta reviewed follow-up answer",
               "zeta reviewed follow-up answer"]
    for answer in answers:
        if body.get("next_round_status") != "ready":
            break
        number = body["next_round"]
        record(f"activate_{number}", client.post(f"/session/{sid}/rounds/{number}/activate", headers=headers))
        body = record(f"submit_{number}", client.post("/session/answer", headers=headers, json={
            "session_id": sid, "round": number, "answer_text": answer}))
        if number == 2:
            record("follow_up_parent_2", client.post(
                f"/session/{sid}/follow-ups", headers=headers,
                json={"parent_round": 2, "accept_eligibility_consequence": True}))
            mark_reviewed()
    record_reports(record, client, headers, sid)
    stored = db["sessions"].find_one({"session_id": sid}) or {}
    replacements = {sid: "<sid>", str(started.get("candidate_id") or ""): "<cid>", str(user_id): "<uid>"}
    for position, block in enumerate(started.get("block_plan") or [], start=1):
        replacements[str(block.get("id") or "")] = f"<block{position}>"
    return normalize({
        "steps": steps,
        "served_questions": [(r.get("round"), bool(r.get("is_follow_up")), r.get("question"))
                             for r in stored.get("rounds") or []],
    }, replacements)


RUNNERS = {
    "two_candidate_follow_ups": run_two_candidate_transcript,
    "no_follow_up": run_transcript,
    "upload_start": run_upload_start_transcript,
    "candidate_follow_up": run_candidate_transcript,
    "account_candidate_follow_ups": run_account_transcript,
}


def capture(path: str, which: str) -> None:
    import pytest
    from fastapi.testclient import TestClient

    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    from backend.main import app

    with pytest.MonkeyPatch.context() as mp:
        db = install(mp)
        user_id, headers = make_user(db)
        transcript = RUNNERS[which](TestClient(app), db, headers, user_id)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(transcript, handle, indent=1, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--write" or sys.argv[3] not in RUNNERS:
        raise SystemExit("usage: python -m tests.slice1_harness --write OUT.json " + "|".join(RUNNERS))
    capture(sys.argv[2], sys.argv[3])
