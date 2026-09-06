"""Backend tests for learning effectiveness signal endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app
from modules.learning_signals import (
    mark_roadmap_block_complete,
    record_elo_delta,
    reset_memory_store,
)


def _make_user(prefix: str) -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one(
        {
            "id": user_id,
            "email": f"{prefix}-{user_id[:8]}@example.com",
            "name": f"Test {prefix}",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    return {"id": user_id, "token": create_access_token(user_id)}


def test_learning_signals_elo_revisit_and_roadmap() -> None:
    reset_memory_store()
    client = TestClient(app)
    user = _make_user("signals")
    headers = {"Authorization": f"Bearer {user['token']}"}

    record_elo_delta(
        user_id=user["id"],
        session_id="sess-a",
        skill="DBMS",
        elo_before=1500.0,
        elo_after=1512.0,
    )
    record_elo_delta(
        user_id=user["id"],
        session_id="sess-b",
        skill="DBMS",
        elo_before=1512.0,
        elo_after=1505.0,
    )
    mark_roadmap_block_complete(
        user_id=user["id"],
        role_id="sde-intern",
        plan_days=7,
        block_index=1,
        blocks_total=4,
    )
    mark_roadmap_block_complete(
        user_id=user["id"],
        role_id="sde-intern",
        plan_days=7,
        block_index=2,
        blocks_total=4,
    )

    response = client.get("/learning/signals/me", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user_id"] == user["id"]
    assert len(body["elo_deltas"]) == 2
    by_session = {row["session_id"]: row for row in body["elo_deltas"]}
    assert by_session["sess-a"]["delta"] == 12.0
    assert by_session["sess-a"]["cumulative_delta"] == 5.0
    assert by_session["sess-b"]["delta"] == -7.0
    assert by_session["sess-b"]["cumulative_delta"] == 5.0

    revisit = {row["skill"]: row for row in body["revisit_rates"]}
    assert revisit["DBMS"]["sessions"] == 2
    assert revisit["DBMS"]["retries"] == 1
    assert revisit["DBMS"]["rate"] == 0.5

    assert body["roadmap_completion"]["7"] == 0.5
    assert body["roadmap_completion"]["14"] is None
    assert body["roadmap_completion"]["30"] is None


def test_roadmap_progress_endpoint() -> None:
    reset_memory_store()
    client = TestClient(app)
    user = _make_user("roadmap-prog")
    headers = {"Authorization": f"Bearer {user['token']}"}

    response = client.post(
        "/learning/roadmap-progress",
        headers=headers,
        json={
            "role_id": "backend-dev",
            "plan_days": 14,
            "block_index": 1,
            "blocks_total": 5,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["completion_fraction"] == 0.2
    assert body["completed_blocks"] == [1]

    me = client.get("/learning/roadmap-completion/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["roadmap_completion"]["14"] == 0.2


def test_learning_signals_requires_auth() -> None:
    client = TestClient(app)
    assert client.get("/learning/signals/me").status_code == 401
