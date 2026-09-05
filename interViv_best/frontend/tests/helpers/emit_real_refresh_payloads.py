"""Emit real Phase 2 start/fetch payloads for the Node refresh contract tests."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.main import app


def _make_user() -> dict[str, str]:
    user_id = str(uuid4())
    get_database()["users"].insert_one(
        {
            "id": user_id,
            "email": f"refresh-contract-{user_id[:8]}@example.com",
            "name": "Refresh Contract",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    return {"id": user_id, "token": create_access_token(user_id)}


def _start_and_fetch(
    client: TestClient, headers: dict[str, str], start_body: dict
) -> dict[str, dict]:
    started = client.post("/session/start", json=start_body, headers=headers)
    if started.status_code != 200:
        raise RuntimeError(f"start failed: {started.status_code} {started.text}")

    started_body = started.json()
    fetched = client.get(f"/session/{started_body['session_id']}", headers=headers)
    if fetched.status_code != 200:
        raise RuntimeError(f"fetch failed: {fetched.status_code} {fetched.text}")

    return {"start": started_body, "fetch": fetched.json()}


def main() -> None:
    client = TestClient(app)
    user = _make_user()
    headers = {"Authorization": f"Bearer {user['token']}"}

    payloads = {
        "mcq": _start_and_fetch(
            client,
            headers,
            {
                "candidate_id": "",
                "skills": ["DBMS", "Python", "OS", "Computer Networks", "DSA"],
                "round_type": "mcq",
                "round_config": {
                    "count": 15,
                    "duration_minutes": 20,
                    "negative_marking": 0.25,
                },
            },
        ),
        "sql": _start_and_fetch(
            client,
            headers,
            {
                "candidate_id": "",
                "skills": ["DBMS"],
                "round_type": "sql",
                "round_config": {
                    "problem_id": "sql_prob_026",
                    "duration_minutes": 25,
                },
            },
        ),
    }

    print(json.dumps(payloads, separators=(",", ":"), default=str))


if __name__ == "__main__":
    main()
