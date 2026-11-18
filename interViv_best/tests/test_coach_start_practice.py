"""POST /coach/start-practice accepts practice mode and flow preset."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.main import app  # noqa: E402
from backend.routes import coach as coach_routes  # noqa: E402


def _user() -> dict[str, str]:
    user_id = str(uuid4())
    get_database()["users"].insert_one({
        "id": user_id,
        "email": f"start-{user_id[:8]}@example.com",
        "name": "Start",
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    })
    return {"id": user_id, "token": create_access_token(user_id)}


def test_start_practice_forwards_mode_and_preset(monkeypatch) -> None:
    captured: list = []

    def fake_start(request, authorization=None):  # noqa: ANN001
        captured.append(request)
        return {"session_id": "sess-practice", "question": "q", "skills": list(request.skills)}

    monkeypatch.setattr(coach_routes, "start_session", fake_start)
    user = _user()
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {user['token']}"}

    assessment = client.post(
        "/coach/start-practice",
        headers=headers,
        json={"skills": ["Python", "SQL"], "practice_mode": "assessment", "flow_preset": "legacy"},
    )
    assert assessment.status_code == 200, assessment.text
    assert captured[0].practice_mode == "assessment"
    assert captured[0].preset is None
    assert captured[0].flow_version is None

    quick = client.post(
        "/coach/start-practice",
        headers=headers,
        json={"skills": ["Python"], "practice_mode": "coached_practice", "flow_preset": "quick"},
    )
    assert quick.status_code == 200, quick.text
    assert captured[1].practice_mode == "coached_practice"
    assert captured[1].preset == "quick"
    assert captured[1].flow_version == "staged_v1"
    assert not captured[1].round_plan

    full = client.post(
        "/coach/start-practice",
        headers=headers,
        json={"skills": ["SQL"], "flow_preset": "Full"},
    )
    assert full.status_code == 200, full.text
    assert captured[2].preset == "full"
    assert captured[2].flow_version == "staged_v1"


def test_start_practice_rejects_unknown_mode_and_preset() -> None:
    user = _user()
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {user['token']}"}
    bad_mode = client.post(
        "/coach/start-practice",
        headers=headers,
        json={"skills": ["Python"], "practice_mode": "exam"},
    )
    assert bad_mode.status_code == 422
    bad_preset = client.post(
        "/coach/start-practice",
        headers=headers,
        json={"skills": ["Python"], "flow_preset": "marathon"},
    )
    assert bad_preset.status_code == 422


def test_assessment_legacy_is_stored_on_the_session() -> None:
    user = _user()
    client = TestClient(app)
    resp = client.post(
        "/coach/start-practice",
        headers={"Authorization": f"Bearer {user['token']}"},
        json={"skills": ["Python"], "practice_mode": "assessment", "flow_preset": "legacy"},
    )
    assert resp.status_code == 200, resp.text
    stored = get_database()["sessions"].find_one({"session_id": resp.json()["session_id"]})
    assert stored["practice_mode"] == "assessment"
    assert not stored.get("flow_version")


def test_only_one_empty_skill_guard_remains() -> None:
    source = open(coach_routes.__file__, encoding="utf-8").read()
    start = source.index("def coach_start_practice")
    end = source.index("@router.post(\"/conversations\")")
    body = source[start:end]
    assert body.count("if not skills:") == 1
    assert "refusing silent substitution" not in body
