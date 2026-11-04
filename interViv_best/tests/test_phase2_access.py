"""Phase 2: access matrix for block practice paths.

- Every start requires a user. Phase 2 (MCQ/SQL blocks, drafts,
  presets, bank, previews) requires a user, and cross-user access is
  denied or isolated.
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


def _make_user(prefix: str = "phase2access") -> dict[str, str]:
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


def test_anonymous_legacy_technical_start_preserved() -> None:
    """Guest start is closed. A technical session is stored under the caller."""
    client = TestClient(app)
    refused = client.post("/session/start", json={
        "skills": ["DBMS"], "rounds_per_skill": 1,
        "round_type": "technical_short_answer",
    })
    assert refused.status_code == 401, refused.text

    owner = _make_user("access-technical")
    start = client.post("/session/start", headers=_headers(owner), json={
        "skills": ["DBMS"], "rounds_per_skill": 1,
        "round_type": "technical_short_answer",
    })
    assert start.status_code == 200, start.text
    body = start.json()
    assert body.get("user_id") == owner["id"]
    session_id = body["session_id"]

    assert client.get(f"/session/{session_id}").status_code == 401
    fetched = client.get(f"/session/{session_id}", headers=_headers(owner))
    assert fetched.status_code == 200, fetched.text
    report = client.get(f"/dashboard/{session_id}", headers=_headers(owner))
    assert report.status_code == 200, report.text


def test_block_start_requires_auth_for_mcq_and_sql() -> None:
    client = TestClient(app)
    for block in (
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
         "count": 2, "duration_minutes": 10},
        {"round_type": "sql", "category": "sql",
         "count": 1, "duration_minutes": 15},
    ):
        resp = client.post("/session/start", json={"blocks": [block]})
        assert resp.status_code == 401, resp.text


def test_block_start_rejects_other_users_candidate() -> None:
    client = TestClient(app)
    owner = _make_user("access-owner")
    attacker = _make_user("access-attacker")
    candidate_id = str(uuid4())
    get_database()["candidates"].insert_one({
        "candidate_id": candidate_id,
        "user_id": owner["id"],
        "resume_skills": ["DBMS"],
        "sub_domain_profile": {"DBMS": "general"},
        "elo_ratings": {"DBMS": 1500.0},
        "session_history": [],
    })
    resp = client.post("/session/start", headers=_headers(attacker), json={
        "candidate_id": candidate_id,
        "blocks": [{"round_type": "mcq", "category": "oa",
                    "skills": ["DBMS"], "count": 2,
                    "duration_minutes": 10}],
    })
    assert resp.status_code == 403, resp.text


def test_answer_drafts_require_owner() -> None:
    client = TestClient(app)
    owner = _make_user("access-draft-owner")
    stranger = _make_user("access-draft-stranger")
    headers = _headers(owner)
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 1},
    ]})
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    draft = {"round": 1, "answer_text": "draft text"}

    assert client.put(f"/session/{session_id}/draft",
                      json=draft).status_code == 401
    assert client.get(f"/session/{session_id}/draft?round=1").status_code == 401
    assert client.put(f"/session/{session_id}/draft", headers=_headers(stranger),
                      json=draft).status_code == 403
    assert client.get(f"/session/{session_id}/draft?round=1",
                      headers=_headers(stranger)).status_code == 403


def test_presets_and_builder_draft_require_auth_and_isolate() -> None:
    client = TestClient(app)
    assert client.get("/practice/presets").status_code == 401
    assert client.get("/practice/builder-draft").status_code == 401
    assert client.post("/practice/presets", json={
        "name": "x", "version": 1, "blocks": [],
    }).status_code == 401

    owner = _headers(_make_user("access-preset-owner"))
    stranger = _headers(_make_user("access-preset-stranger"))
    created = client.post("/practice/presets", headers=owner, json={
        "name": "mine", "version": 1,
        "blocks": [{"round_type": "mcq", "category": "oa",
                    "skills": ["DBMS"], "count": 2,
                    "duration_minutes": 10}],
    })
    assert created.status_code == 200, created.text
    preset_id = created.json()["id"]
    # Cross-user preset reads look absent, never leak.
    assert client.get(f"/practice/presets/{preset_id}",
                      headers=stranger).status_code == 404
    assert client.get("/practice/presets", headers=stranger).json()[
        "presets"] == []

    saved = client.put("/practice/builder-draft", headers=owner, json={
        "version": 1,
        "blocks": [{"round_type": "mcq", "category": "oa",
                    "skills": ["DBMS"], "count": 2,
                    "duration_minutes": 10}],
    })
    assert saved.status_code == 200, saved.text
    other = client.get("/practice/builder-draft", headers=stranger)
    assert other.status_code == 200, other.text
    assert other.json().get("blocks") in (None, [])


def test_practice_bank_and_sql_preview_require_auth() -> None:
    client = TestClient(app)
    assert client.get("/session/practice-bank").status_code == 401

    owner = _make_user("access-preview-owner")
    stranger = _make_user("access-preview-stranger")
    start = client.post("/session/start", headers=_headers(owner), json={
        "blocks": [{"round_type": "sql", "category": "sql",
                    "count": 1, "duration_minutes": 15}],
    })
    assert start.status_code == 200, start.text
    payload = {"session_id": start.json()["session_id"], "round": 1,
               "query": "SELECT 1;"}
    assert client.post("/session/sql/run", json=payload).status_code == 401
    assert client.post("/session/sql/run", headers=_headers(stranger),
                       json=payload).status_code == 403
