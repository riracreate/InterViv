from __future__ import annotations

import ipaddress
import os
import socket
import sqlite3
import pytest

# The suite is offline and does not depend on whether a developer has a
# ``.env``. Set before anything imports the backend: the project ``.env`` is
# not loaded, and provider credentials inherited from the shell are blanked,
# so no test can authenticate against a real service.
os.environ["INTERVIV_SKIP_DOTENV"] = "1"
for _credential in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ADZUNA_APP_ID", "ADZUNA_APP_KEY"):
    os.environ[_credential] = ""

from sqlalchemy import event
from sqlalchemy.engine import Engine


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


def _is_local(host: object) -> bool:
    text = str(host or "").strip().strip("[]").lower()
    if text in ("", "localhost"):
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    """Only loopback connections are possible during a test.

    Provider calls are stubbed by the tests that exercise them. Anything
    that still tries to leave the machine gets a connection error at once
    and fails the test that caused it, whatever the environment holds.
    """
    blocked: list[str] = []
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def refuse(host: object) -> None:
        blocked.append(str(host))
        raise ConnectionRefusedError(f"tests are offline: blocked connection to {host}")

    def connect(self, address, *args, **kwargs):
        if isinstance(address, tuple) and not _is_local(address[0]):
            refuse(address[0])
        return real_connect(self, address, *args, **kwargs)

    def connect_ex(self, address, *args, **kwargs):
        if isinstance(address, tuple) and not _is_local(address[0]):
            refuse(address[0])
        return real_connect_ex(self, address, *args, **kwargs)

    def getaddrinfo(host, *args, **kwargs):
        if not _is_local(host.decode() if isinstance(host, bytes) else host):
            refuse(host)
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    yield blocked
    assert not blocked, f"test tried to reach the network: {sorted(set(blocked))}"


@pytest.fixture(autouse=True)
def isolated_auth_rate_limits(monkeypatch):
    # TestClient instances reuse the same client address across independent
    # tests; each test still exercises normal throttling within its own window.
    from backend.auth import throttling

    monkeypatch.setattr(throttling, "_windows", {})
