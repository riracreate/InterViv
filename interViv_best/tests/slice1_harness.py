"""Deterministic session harness for Slice 1 compatibility tests.

Drives the real FastAPI routes on an isolated in-memory store with a
stubbed question bank and scorer, then normalizes run-specific values
(ids, timestamps, digests) so transcripts compare byte-for-byte across
code versions. Uses only APIs that predate Slice 1, so the same module
captures the pre-change baseline:

    python -m tests.slice1_harness --write tests/fixtures/slice1_flag_off_transcript.json no_follow_up
    python -m tests.slice1_harness --write tests/fixtures/slice1_candidate_transcript.json candidate_follow_up
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
TRANSCRIPT_ANSWERS = list(STUB_SCORES)


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


def run_transcript(client, db, headers, user_id) -> dict[str, Any]:
    """Start → (GET, submit, GET, activate) × N → final GET, plus stored docs."""
    steps: list[dict[str, Any]] = []

    def record(name, response):
        steps.append({"step": name, "status": response.status_code, "body": response.json()})
        return response.json()

    started = record("start", client.post("/session/start", headers=headers, json={
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


RUNNERS = {"no_follow_up": run_transcript, "candidate_follow_up": run_candidate_transcript}


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
        raise SystemExit("usage: python -m tests.slice1_harness --write OUT.json {no_follow_up|candidate_follow_up}")
    capture(sys.argv[2], sys.argv[3])
