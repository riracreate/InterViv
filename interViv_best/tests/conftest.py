from __future__ import annotations

import os
import socket
import sqlite3
import sys
import urllib.request
from pathlib import Path
from typing import Any

import dotenv
import httpx
import pytest

from sqlalchemy import event
from sqlalchemy.engine import Engine

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPO_ENV_PATH = (_REPO_ROOT / ".env").resolve()

# Disable real .env loading and strip any leaked .env-sourced secrets/flags before collection.
os.environ["INTERVIV_DISABLE_DOTENV"] = "1"
for _leaked_var in (
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ADZUNA_APP_ID",
    "ADZUNA_APP_KEY",
    "OPENROUTER_MODEL",
    "OPENAI_MODEL",
    "QUESTION_LLM_MODEL",
    "OLLAMA_MODEL",
    "OLLAMA_API_KEY",
    "LLM_LIVE_FETCH",
):
    os.environ.pop(_leaked_var, None)

_ORIG_LOAD_DOTENV = dotenv.load_dotenv
_ORIG_DOTENV_VALUES = dotenv.dotenv_values


def _is_forbidden_dotenv_target(dotenv_path: Any, stream: Any) -> bool:
    if dotenv_path is None or str(dotenv_path).strip() == "":
        return stream is None
    try:
        resolved = Path(dotenv_path).expanduser().resolve()
    except (TypeError, OSError, ValueError):
        return True
    return resolved == _REPO_ENV_PATH


def _guarded_load_dotenv(
    dotenv_path: Any = None,
    stream: Any = None,
    *args: Any,
    **kwargs: Any,
) -> bool:
    if _is_forbidden_dotenv_target(dotenv_path, stream):
        raise AssertionError("Tests must not load the real .env file")
    return _ORIG_LOAD_DOTENV(dotenv_path, stream, *args, **kwargs)


def _guarded_dotenv_values(
    dotenv_path: Any = None,
    stream: Any = None,
    *args: Any,
    **kwargs: Any,
) -> dict[str, str | None]:
    if _is_forbidden_dotenv_target(dotenv_path, stream):
        raise AssertionError("Tests must not load the real .env file")
    return _ORIG_DOTENV_VALUES(dotenv_path, stream, *args, **kwargs)


@event.listens_for(Engine, "connect")
def _sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
# 32+ bytes so PyJWT does not warn about insecure HMAC key length (RFC 7518 §3.2).
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")


@pytest.fixture(autouse=True)
def isolated_test_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import backend.config as backend_config
    import backend.runtime_env as backend_runtime_env

    monkeypatch.setenv("INTERVIV_DISABLE_DOTENV", "1")
    monkeypatch.setenv(
        "REJECTED_BUNDLES_AUDIT_PATH",
        str(tmp_path / "rejected_bundles_audit.jsonl"),
    )
    monkeypatch.setenv(
        "DEMOTED_BUNDLES_AUDIT_PATH",
        str(tmp_path / "demoted_concepts_audit.jsonl"),
    )
    monkeypatch.setenv(
        "NEW_CANONICAL_SKILLS_AUDIT_PATH",
        str(tmp_path / "new_canonical_skills_audit.jsonl"),
    )
    monkeypatch.setenv(
        "FOLLOWUP_DECISIONS_AUDIT_PATH",
        str(tmp_path / "followup_decisions_audit.jsonl"),
    )

    monkeypatch.setattr(dotenv, "load_dotenv", _guarded_load_dotenv)
    monkeypatch.setattr(dotenv, "dotenv_values", _guarded_dotenv_values)
    monkeypatch.setattr(backend_config, "load_dotenv", _guarded_load_dotenv)
    monkeypatch.setattr(backend_runtime_env, "load_dotenv", _guarded_load_dotenv)
    if "scripts.run_local" in sys.modules:
        monkeypatch.setattr(sys.modules["scripts.run_local"], "load_dotenv", _guarded_load_dotenv)

    if os.getenv("INTERVIV_REAL_EXECUTOR") != "1":
        def _blocked_network(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("Unmocked outbound network call blocked in tests")

        async def _blocked_async_network(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("Unmocked outbound network call blocked in tests")

        monkeypatch.setattr(urllib.request, "urlopen", _blocked_network)
        monkeypatch.setattr(socket, "create_connection", _blocked_network)
        monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _blocked_network)
        monkeypatch.setattr(
            httpx.AsyncHTTPTransport, "handle_async_request", _blocked_async_network
        )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Real MiniLM checks skip on a cold cache. CI is offline and has no weights."""
    from tests.test_semantic import _find_semantic_snapshot

    if _find_semantic_snapshot() is not None:
        return
    skip = pytest.mark.skip(
        reason="all-MiniLM-L6-v2 not in the local cache — real-model assertions cannot run offline",
    )
    for item in items:
        if item.get_closest_marker("requires_semantic_model"):
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def isolated_auth_rate_limits(monkeypatch):
    # TestClient instances reuse the same client address across independent
    # tests; each test still exercises normal throttling within its own window.
    from backend.auth import throttling

    monkeypatch.setattr(throttling, "_windows", {})
