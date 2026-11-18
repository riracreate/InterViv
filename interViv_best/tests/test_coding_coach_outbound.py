"""Coding-coach hints talk only to local Ollama, and the prompt includes language."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend import coding_coach  # noqa: E402
from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.coding_coach import build_hint  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.main import app  # noqa: E402
from modules import interview_llm, question_bank  # noqa: E402

PROBLEM = {"title": "Two Sum", "function": "two_sum", "topics": ["hashing"], "statement": "Find two indices."}

# Cloud chat hosts the coding coach must never open. OpenRouter plus the
# direct providers used or reserved elsewhere in the app.
FORBIDDEN_HOSTS = (
    "openrouter.ai",
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "api.groq.com",
    "integrate.api.nvidia.com",
)

CLOUD_COACH_URLS = (
    "https://openrouter.ai/api/v1",
    "https://api.openai.com/v1",
    "https://api.anthropic.com",
    "https://generativelanguage.googleapis.com/v1beta",
    "https://api.groq.com/openai/v1",
    "https://integrate.api.nvidia.com/v1",
)


class _Body:
    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode()

    def read(self, _n: int = -1) -> bytes:
        return self._raw

    def __enter__(self) -> "_Body":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


def _user() -> dict[str, str]:
    user_id = str(uuid4())
    get_database()["users"].insert_one({
        "id": user_id,
        "email": f"coach-{user_id[:8]}@example.com",
        "name": "Coach",
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    })
    return {"id": user_id, "token": create_access_token(user_id)}


def _seed_coding(user_id: str) -> str:
    session_id = f"s-{uuid4().hex[:8]}"
    get_database()["sessions"].insert_one({
        "session_id": session_id,
        "user_id": user_id,
        "status": "active",
        "rounds": [{
            "round": 1,
            "round_type": "coding",
            "status": "in_progress",
            "config_json": {"problem_id": "coding_two_sum"},
        }],
    })
    return session_id


def _forbid_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("coding coach called a cloud provider")

    monkeypatch.setattr(question_bank, "_generate_via_llm", boom)
    monkeypatch.setattr(interview_llm.InterviewRouter, "_chat_once", staticmethod(boom))

    def forbid_urlopen(*args: object, **_kwargs: object) -> None:
        raise AssertionError(f"coding coach used urlopen: {args[:1]}")

    monkeypatch.setattr("urllib.request.urlopen", forbid_urlopen)


def test_ollama_hint_times_out_after_15_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODING_COACH_URL", raising=False)
    seen: dict[str, float | None] = {}

    def fake_open(self, request, timeout=None):  # noqa: ANN001
        seen["timeout"] = timeout
        return _Body({"message": {"content": "Name the invariant."}})

    monkeypatch.setattr("urllib.request.OpenerDirector.open", fake_open)
    payload = build_hint(problem=PROBLEM, level=1, language="python")
    assert payload["kind"] == "ai"
    assert seen["timeout"] == 15
    assert coding_coach.HINT_TIMEOUT_SECONDS == 15


def test_hint_requests_stay_on_local_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    monkeypatch.delenv("CODING_COACH_URL", raising=False)
    _forbid_cloud(monkeypatch)
    opened: list[str] = []
    prompts: list[str] = []

    def fake_open(self, request, timeout=None):  # noqa: ANN001
        url = request.full_url
        opened.append(url)
        parsed = urlsplit(url)
        assert parsed.scheme == "http"
        assert parsed.hostname == "127.0.0.1"
        assert parsed.path == "/api/chat"
        assert all(host not in url for host in FORBIDDEN_HOSTS)
        assert timeout is not None
        body = json.loads(request.data.decode())
        prompts.append(body["messages"][1]["content"])
        return _Body({"message": {"content": "Name the invariant before you write the loop."}})

    # The constant is still 45 until the timeout fix. Pin the call to it.
    monkeypatch.setattr("urllib.request.OpenerDirector.open", fake_open)
    payload = build_hint(
        problem=PROBLEM,
        level=1,
        source="def two_sum(nums, target):\n    return []\n",
        last_error="IndexError: list index out of range",
        language="python",
    )
    assert payload["kind"] == "ai"
    assert opened == ["http://127.0.0.1:11434/api/chat"]
    assert "Language: python" in prompts[0]
    assert "IndexError" in prompts[0]
    assert "Candidate draft" in prompts[0]


@pytest.mark.parametrize("cloud_url", CLOUD_COACH_URLS)
def test_cloud_coach_url_is_refused_without_a_request(
    monkeypatch: pytest.MonkeyPatch, cloud_url: str
) -> None:
    monkeypatch.setenv("CODING_COACH_URL", cloud_url)
    _forbid_cloud(monkeypatch)
    opened: list[str] = []

    def fake_open(self, request, timeout=None):  # noqa: ANN001
        opened.append(request.full_url)
        raise AssertionError(f"refused URL still opened {request.full_url}")

    monkeypatch.setattr("urllib.request.OpenerDirector.open", fake_open)
    payload = build_hint(problem=PROBLEM, level=2, language="javascript", prefer_ai=True)
    assert payload["kind"] == "curated"
    assert opened == []


def test_route_forwards_source_language_and_last_error(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_ollama(**kwargs):
        captured.update(kwargs)
        return "Keep a map of values you have already seen."

    monkeypatch.setattr(coding_coach, "_ollama_hint", fake_ollama)
    user = _user()
    session_id = _seed_coding(user["id"])
    client = TestClient(app)
    resp = client.post(
        "/problems/coach/hint",
        headers={"Authorization": f"Bearer {user['token']}"},
        json={
            "session_id": session_id,
            "round": 1,
            "level": 1,
            "source": "def two_sum(nums, target):\n    pass\n",
            "language": "python",
            "last_error": "{\"input\": [[2, 7], 9], \"expected\": [0, 1], \"actual\": null}",
        },
    )
    assert resp.status_code == 200, resp.text
    assert captured["language"] == "python"
    assert "def two_sum" in captured["source"]
    assert "expected" in captured["last_error"]
    assert resp.json()["kind"] == "ai"
