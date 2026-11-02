from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth import security, throttling
from backend.config import _validate_security_settings, get_settings
from backend.db.sqlalchemy_store import get_engine
from backend.main import app
from backend.readiness import readiness_status
from backend.routes import resume
from modules import resume_parser


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("REDIS_URL", "")
    get_settings.cache_clear()
    get_engine.cache_clear()
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()


def test_unicode_passphrase_signup_login_and_wrong_suffix():
    client = TestClient(app)
    email = f"long-{uuid4().hex}@example.com"
    password = "a1" + "界" * 100
    response = client.post("/auth/signup", json={"email": email, "password": password})
    assert response.status_code == 200
    assert client.post("/auth/login", json={"email": email, "password": password}).status_code == 200
    # Full passphrase matters, including bytes after bcrypt's old boundary.
    assert client.post("/auth/login", json={"email": email, "password": password + "x"}).status_code == 401


def test_oversized_password_is_validation_error():
    client = TestClient(app)
    for path in ("/auth/signup", "/auth/login"):
        response = client.post(path, json={"email": "long@example.com", "password": "a1" * 513})
        assert response.status_code == 422


def test_legacy_bcrypt_remains_valid_without_crashing_on_long_input():
    bcrypt = pytest.importorskip("bcrypt")
    legacy = bcrypt.hashpw(b"legacy-password-1", bcrypt.gensalt()).decode()
    assert security.verify_password("legacy-password-1", legacy)
    assert not security.verify_password("wrong-password", legacy)
    assert not security.verify_password("a1" * 80, legacy)


def test_legacy_pbkdf2_remains_valid(monkeypatch):
    monkeypatch.setattr(security, "PBKDF2_ITERATIONS", 260_000)
    legacy = security.hash_password("legacy-password-1")
    monkeypatch.setattr(security, "PBKDF2_ITERATIONS", 600_000)
    assert security.verify_password("legacy-password-1", legacy)


def test_login_throttles_before_password_work_and_expires(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(throttling, "monotonic", lambda: now[0])
    client = TestClient(app)
    body = {"email": "unregistered@example.com", "password": "wrong-password-1"}
    for _ in range(10):
        assert client.post("/auth/login", json=body).status_code == 401
    response = client.post("/auth/login", json=body)
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    now[0] += throttling.WINDOW_SECONDS + 1
    assert client.post("/auth/login", json=body).status_code == 401


def test_signup_is_throttled_across_different_accounts():
    client = TestClient(app)
    # Invalid-but-well-shaped passwords avoid creating users or expensive hashes.
    for i in range(10):
        response = client.post("/auth/signup", json={"email": f"signup-{i}@example.com", "password": "no-numbers"})
        assert response.status_code == 422
    response = client.post("/auth/signup", json={"email": "signup-11@example.com", "password": "no-numbers"})
    assert response.status_code == 429


def test_configured_redis_failure_does_not_bypass_auth_throttle(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    def unavailable(url):
        raise ConnectionError("private connection details")
    monkeypatch.setattr(throttling, "redis_client", unavailable)
    response = TestClient(app).post("/auth/login", json={"email": "test@example.com", "password": "password1"})
    assert response.status_code == 503
    assert "private connection" not in response.text


def test_production_refuses_missing_database():
    settings = replace(get_settings(), environment="production", database_url=None)
    with pytest.raises(RuntimeError, match="requires DATABASE_URL"):
        _validate_security_settings(settings)
    assert _validate_security_settings(replace(settings, database_url="postgresql://localhost/interviv"))


@pytest.fixture
def resume_client(monkeypatch):
    test_app = FastAPI()
    test_app.include_router(resume.router)
    test_app.dependency_overrides[resume.require_authenticated] = lambda: {"id": "test"}
    captured = []
    monkeypatch.setattr(resume, "get_database", lambda: {"candidates": SimpleNamespace(insert_one=captured.append)})
    return TestClient(test_app), captured


@pytest.mark.parametrize("failure", ["exception", "unreadable"])
def test_bad_resume_does_not_create_candidate(monkeypatch, resume_client, failure):
    def analyze(path):
        if failure == "exception":
            raise ValueError("broken PDF")
        return {"extract_ok": False, "skills": [], "likely_garbage": True}
    monkeypatch.setattr(resume, "load_module", lambda *a, **k: SimpleNamespace(parse_resume=lambda p: [], analyze_resume=analyze))
    client, captured = resume_client
    response = client.post("/resume", files={"file": ("resume.pdf", b"invalid", "application/pdf")})
    assert response.status_code == 422
    assert "manually" in response.json()["detail"]
    assert not captured


def test_readable_resume_without_known_skills_does_not_invent_python(monkeypatch, resume_client):
    analysis = resume_parser.analyze_resume_text("Education\nHistory graduate with experience in museums.")
    monkeypatch.setattr(resume, "load_module", lambda *a, **k: SimpleNamespace(parse_resume=lambda p: [], analyze_resume=lambda p: analysis))
    client, captured = resume_client
    response = client.post("/resume", files={"file": ("resume.pdf", b"stub", "application/pdf")})
    assert response.status_code == 200
    assert response.json()["skills"] == []
    assert captured[0]["resume_skills"] == []


def test_raw_pdf_bytes_are_not_used_as_resume_text(tmp_path, monkeypatch):
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.7 Python Java SQL metadata only")
    monkeypatch.setattr(resume_parser, "_extract_with_pymupdf", lambda p: "")
    monkeypatch.setattr(resume_parser, "_extract_with_pdfplumber", lambda p: "")
    assert resume_parser.analyze_resume(path)["extract_ok"] is False
    assert resume_parser.parse_resume(path) == []


def test_readiness_requires_migrated_database(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config

    url = f"sqlite:///{tmp_path / 'readiness.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    ready, payload = readiness_status()
    assert not ready
    assert payload["checks"]["database"]["migrations_current"] is False
    config = Config()
    config.set_main_option("script_location", str(get_settings().project_root / "alembic"))
    command.upgrade(config, "head")
    ready, payload = readiness_status()
    assert ready
    assert payload["checks"]["database"]["persistent"] is True
    get_engine().dispose()


def test_missing_content_changes_readiness_http_status(monkeypatch):
    from backend.ml_primitives import catalog

    monkeypatch.setattr(catalog, "list_problems", lambda: [])
    client = TestClient(app)
    assert client.get("/ready").status_code == 503
    assert client.get("/health").status_code == 200
