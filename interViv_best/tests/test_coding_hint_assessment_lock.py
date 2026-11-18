"""Assessment coding hints warn in the UI. The server rejects them after submit."""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend import coding_coach  # noqa: E402
from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.main import app  # noqa: E402
from backend.routes.answer import _submit_locked  # noqa: E402


def _user() -> dict[str, str]:
    user_id = str(uuid4())
    get_database()["users"].insert_one({
        "id": user_id,
        "email": f"hint-{user_id[:8]}@example.com",
        "name": "Hint",
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    })
    return {"id": user_id, "token": create_access_token(user_id)}


def _seed(user_id: str, *, round_status: str, session_status: str = "active", score=None, submitted_at=None) -> str:
    session_id = f"s-{uuid4().hex[:8]}"
    get_database()["sessions"].insert_one({
        "session_id": session_id,
        "user_id": user_id,
        "status": session_status,
        "practice_mode": "assessment",
        "rounds": [{
            "round": 1,
            "round_type": "coding",
            "status": round_status,
            "final_score": score,
            "submitted_at": submitted_at,
            "config_json": {"problem_id": "coding_two_sum"},
        }],
    })
    return session_id


def _post(client: TestClient, token: str, session_id: str):
    return client.post(
        "/problems/coach/hint",
        headers={"Authorization": f"Bearer {token}"},
        json={"session_id": session_id, "round": 1, "level": 1, "language": "python", "source": "x = 1\n"},
    )


def test_open_round_hint_waits_on_the_submit_lock(monkeypatch) -> None:
    monkeypatch.setattr(coding_coach, "_ollama_hint", lambda **_: "Name the invariant.")
    user = _user()
    session_id = _seed(user["id"], round_status="in_progress")
    client = TestClient(app)
    held = threading.Event()
    release = threading.Event()

    def holder() -> None:
        with _submit_locked(session_id):
            held.set()
            assert release.wait(5)

    thread = threading.Thread(target=holder)
    thread.start()
    assert held.wait(2)
    result: dict = {}

    def caller() -> None:
        result["resp"] = _post(client, user["token"], session_id)

    caller_thread = threading.Thread(target=caller)
    caller_thread.start()
    caller_thread.join(0.4)
    assert caller_thread.is_alive()
    release.set()
    caller_thread.join(5)
    thread.join(2)
    assert result["resp"].status_code == 200, result["resp"].text


def test_submitted_and_closed_rounds_reject_hints(monkeypatch) -> None:
    monkeypatch.setattr(coding_coach, "_ollama_hint", lambda **_: "Name the invariant.")
    user = _user()
    client = TestClient(app)
    submitted = _seed(user["id"], round_status="submitted", score=40)
    before = list(get_database()["assistance_events"].find({"user_id": user["id"]}))
    denied = _post(client, user["token"], submitted)
    assert denied.status_code == 409
    assert "submitted" in denied.json()["detail"]
    closed = _seed(user["id"], round_status="in_progress", session_status="completed")
    denied_closed = _post(client, user["token"], closed)
    assert denied_closed.status_code == 409
    assert "closed" in denied_closed.json()["detail"]
    expired = _seed(user["id"], round_status="expired")
    denied_expired = _post(client, user["token"], expired)
    assert denied_expired.status_code == 409
    assert "closed" in denied_expired.json()["detail"]
    after = list(get_database()["assistance_events"].find({"user_id": user["id"]}))
    assert after == before


def test_session_resume_does_not_add_a_practice_mode_field() -> None:
    # The client already knows the mode it started with. Adding the field to
    # GET /session changes the flag-off interview transcript capture.
    user = _user()
    session_id = _seed(user["id"], round_status="in_progress")
    resp = TestClient(app).get(
        f"/session/{session_id}",
        headers={"Authorization": f"Bearer {user['token']}"},
    )
    assert resp.status_code == 200, resp.text
    assert "practice_mode" not in resp.json()
