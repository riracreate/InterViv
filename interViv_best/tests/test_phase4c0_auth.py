"""Phase 4C-0: missing tokens are 401 before handler validation."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")

from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.main import app  # noqa: E402

# Clearly public. Each entry is method, path template, reason.
PUBLIC_ROUTES = {
    ("POST", "/auth/signup"): "Account creation has no prior token.",
    ("POST", "/auth/login"): "Login exchanges credentials for a token.",
    ("GET", "/health"): "Liveness probe; no user records.",
    ("GET", "/openapi.json"): "API schema for the documented surface.",
    ("GET", "/docs"): "Swagger UI for the documented surface.",
    ("GET", "/docs/oauth2-redirect"): "Swagger OAuth redirect, part of the docs UI.",
    ("GET", "/redoc"): "ReDoc UI for the documented surface.",
}

# Intentionally anonymous. Not public product surface; listed so the audit
# does not treat a preserved guest path as an auth pass.
ANONYMOUS_BY_DESIGN = {
    ("POST", "/session/start"): "Legacy technical start stays guest-accessible.",
    ("POST", "/session/availability"): "Same guest policy as session start.",
    ("GET", "/session/{session_id}"): "Legacy technical session read stays guest-accessible.",
    ("POST", "/session/answer"): "Legacy technical submit stays guest-accessible.",
    ("POST", "/session/{session_id}/continue"): "Guest continue follows session ownership.",
    ("POST", "/session/{session_id}/follow-ups"): "Guest follow-up follows session ownership.",
    ("GET", "/session/{session_id}/rounds/{round_number}/feedback"): "Guest feedback follows session ownership.",
    ("GET", "/dashboard/{session_id}"): "Guest dashboard follows session ownership.",
}

_PARAM = re.compile(r"\{([^}]+)\}")


def _fill(path: str) -> str:
    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in {"round_number", "version", "round"}:
            return "1"
        return "probe"
    return _PARAM.sub(repl, path)


def _mounted(application):
    found = []
    for route in application.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        methods = getattr(route, "methods", None)
        if methods is None:
            if type(route).__name__ == "WebSocketRoute":
                found.append(("WEBSOCKET", path))
            continue
        for method in sorted(methods):
            if method in {"HEAD", "OPTIONS"}:
                continue
            found.append((method, path))
    return found


def _assert_closed(application) -> None:
    client = TestClient(application)
    failures = []
    for method, path in _mounted(application):
        key = (method, path)
        if key in PUBLIC_ROUTES or key in ANONYMOUS_BY_DESIGN:
            continue
        if method == "WEBSOCKET":
            failures.append(f"{method} {path} is mounted and not allowlisted")
            continue
        response = client.request(method, _fill(path))
        if response.status_code != 401:
            failures.append(f"{method} {path} -> {response.status_code}")
            continue
        if response.headers.get("www-authenticate") != "Bearer":
            failures.append(f"{method} {path} missing WWW-Authenticate")
    assert not failures, "\n".join(failures)


def test_route_audit_default_settings() -> None:
    _assert_closed(app)


def test_route_audit_with_admin_endpoints(monkeypatch) -> None:
    from backend.routes.admin import router as admin_router

    monkeypatch.setenv("ENABLE_ADMIN_ENDPOINTS", "true")
    before = list(app.router.routes)
    app.include_router(admin_router)
    try:
        paths = {path for _, path in _mounted(app)}
        assert any(path.startswith("/admin") for path in paths)
        _assert_closed(app)
    finally:
        app.router.routes[:] = before


def _user(email: str) -> dict[str, str]:
    user_id = str(uuid4())
    get_database()["users"].insert_one({
        "id": user_id,
        "email": email,
        "name": email,
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    })
    return {"id": user_id, "token": create_access_token(user_id)}


def _headers(user: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


@pytest.fixture
def pair():
    tag = uuid4().hex[:8]
    return _user(f"owner-{tag}@example.com"), _user(f"other-{tag}@example.com")


ROLE = "amazon_sde_intern"


@pytest.mark.parametrize(
    "path_for",
    [
        lambda owner: f"/gap-analysis/{owner['id']}/{ROLE}",
        lambda owner: f"/gap-analysis/me/{ROLE}",
        lambda owner: f"/roadmap/{owner['id']}/{ROLE}",
        lambda owner: f"/roadmap/me/{ROLE}",
        lambda owner: f"/skill-graph/{owner['id']}",
        lambda owner: "/skill-graph/me",
        lambda owner: f"/mastery/{owner['id']}",
        lambda owner: "/mastery/me",
        lambda owner: f"/learning/signals/{owner['id']}",
        lambda owner: "/learning/signals/me",
    ],
)
def test_owned_reads_require_matching_user(pair, path_for) -> None:
    owner, other = pair
    path = path_for(owner)
    client = TestClient(app)
    missing = client.get(path)
    assert missing.status_code == 401
    assert missing.headers.get("www-authenticate") == "Bearer"
    if "/me/" in path or path.endswith("/me"):
        assert client.get(path, headers=_headers(other)).status_code == 200
    else:
        assert client.get(path, headers=_headers(other)).status_code == 403
    assert client.get(path, headers=_headers(owner)).status_code == 200


def test_transcribe_requires_user(pair, monkeypatch) -> None:
    owner, other = pair

    class _Segment:
        text = "hello"

    class _Model:
        def transcribe(self, path, language="en"):
            return [_Segment()], None

    monkeypatch.setattr("backend.routes.transcribe.get_model", lambda: _Model())
    client = TestClient(app)
    files = {"audio": ("answer.webm", b"not-audio", "audio/webm")}
    missing = client.post("/transcribe", files=files)
    assert missing.status_code == 401
    assert missing.headers.get("www-authenticate") == "Bearer"
    # A token for any real user is enough; transcribe has no path user id.
    assert client.post("/transcribe", files=files, headers=_headers(other)).status_code == 200
    owned = client.post("/transcribe", files=files, headers=_headers(owner))
    assert owned.status_code == 200
    assert owned.json()["text"] == "hello"
