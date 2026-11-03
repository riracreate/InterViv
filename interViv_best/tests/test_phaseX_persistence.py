"""Disposable-file SQLAlchemy fidelity, including the actual migrated schema."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect
from fastapi.testclient import TestClient

from backend.db import get_database
from backend.db.sqlalchemy_store import get_engine
from backend.main import app
from backend.models.session import RoundDocument
from tests.alembic_helpers import parent_revision, _script_directory
from tests.test_phaseE_system_design import _clear_db_caches, _run_alembic


@pytest.fixture
def migrated_store(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'ml-primitives.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_db_caches()
    _run_alembic(url, "upgrade", "head")
    yield url
    get_engine().dispose()
    _clear_db_caches()


def attempt_document():
    return {
        "id": "attempt-x", "user_id": "owner-x", "session_id": "session-x",
        "round": 3, "block_id": "repeated-block-x", "problem_id": "contract.v1",
        "problem_version": 1, "language": "python", "source": "# exact bytes: λ\n\n  ",
        "status": "unavailable", "error_code": "execution_unavailable",
        "created_at": datetime(2026, 9, 8, 12, 30, 1, 123456, tzinfo=timezone.utc),
    }


def assert_roundtrip(doc):
    collection = get_database()["ml_primitives_attempts"]
    collection.insert_one(doc)
    assert collection.find_one({"id": doc["id"]}) == doc
    assert list(collection.find({"user_id": doc["user_id"]})) == [doc]
    get_engine().dispose()
    _clear_db_caches()
    reopened = get_database()["ml_primitives_attempts"]
    assert reopened.find_one({"id": doc["id"]}) == doc
    assert reopened.count_documents({"block_id": doc["block_id"]}) == 1


def test_every_attempt_field_survives_migrated_store_reopen(migrated_store):
    assert_roundtrip(attempt_document())


def test_upgrade_store_downgrade_one_revision_reupgrade_store(migrated_store):
    script = _script_directory()
    assert script.get_heads() == ["20261103_0017"]  # must track the current chain head
    assert_roundtrip(attempt_document())
    get_engine().dispose()
    _clear_db_caches()
    # Downgrade below Phase X's own revision (tests/alembic_helpers.py convention;
    # "head" moved when Phase 1A added 20260913_0010).
    _run_alembic(migrated_store, "downgrade", parent_revision("20260908_0009"))
    assert "ml_primitives_attempts" not in inspect(get_engine()).get_table_names()
    get_engine().dispose()
    _clear_db_caches()
    _run_alembic(migrated_store, "upgrade", "head")
    assert_roundtrip(attempt_document())
    assert script.get_heads() == ["20261103_0017"]  # must track the current chain head


def test_unavailable_submission_and_ownership_on_durable_adapter(migrated_store, monkeypatch, tmp_path):
    """Submission contract independent of pack content; this is a stored-round fixture."""
    from backend.routes import answer
    from backend.ml_primitives import grading

    def forbidden(*args, **kwargs):
        raise AssertionError("Candidate scoring must not run.")
    monkeypatch.setattr(answer, "score_round", forbidden)
    monkeypatch.setattr(grading, "grade", forbidden)
    client = TestClient(app)
    def signup(email):
        response = client.post("/auth/signup", json={"email": email, "password": "contract123", "name": "X"})
        assert response.status_code == 200, response.text
        return response.json()["user"]["id"], {"Authorization": f"Bearer {response.json()['access_token']}"}
    owner_id, owner = signup("ml-owner@example.com")
    _, stranger = signup("ml-stranger@example.com")
    now = datetime.now(timezone.utc)
    round_doc = RoundDocument(
        round=1, round_type="ml_primitives", question="Stored contract fixture",
        difficulty="easy", elo_before=1200, status="in_progress",
        block_id="block-x", block_position=1, block_category="ml_primitives",
        block_index=1, block_total=1, started_at=now, expires_at=now + timedelta(minutes=30),
        config_json={"problem_id": "contract.v1", "problem_version": 1},
    ).model_dump()
    db = get_database()
    db["sessions"].insert_one({"session_id": "s-x", "user_id": owner_id,
                                "skills": ["ML primitives"], "rounds": [round_doc]})
    before = db["sessions"].find_one({"session_id": "s-x"})
    marker = tmp_path / "candidate-must-not-execute"
    source = f"open({str(marker)!r}, 'w').write('executed')\n# λ\n  "
    payload = {"session_id": "s-x", "round": 1, "answer_text": source}
    assert client.post("/session/answer", headers=stranger, json=payload).status_code == 403
    assert client.post("/session/answer", json=payload).status_code == 401
    for _ in range(2):
        response = client.post("/session/answer", headers=owner, json=payload)
        assert response.status_code == 503, response.text
        detail = response.json()["detail"]
        assert detail["submission_saved"] is True and detail["retryable"] is True
        attempt_id = detail["attempt_id"]
        assert client.get(f"/ml-primitives/attempts/{attempt_id}", headers=stranger).status_code == 403
        assert client.delete(f"/ml-primitives/attempts/{attempt_id}", headers=stranger).status_code == 403
    assert not marker.exists()
    after = db["sessions"].find_one({"session_id": "s-x"})
    # Each 503 claimed then released the round (content restored, round
    # left openly resubmittable); the version counter records exactly the
    # two release writes, and everything else is byte-identical.
    assert after.pop("revision") == before.pop("revision") + 2
    assert after == before
    get_engine().dispose()
    _clear_db_caches()
    attempts = client.get("/ml-primitives/attempts", headers=owner).json()["attempts"]
    assert len(attempts) == 2
    assert all(a["source"] == source and a["status"] == "unavailable" for a in attempts)
    assert all("score" not in a for a in attempts)
    assert client.get("/ml-primitives/attempts", headers=stranger).json()["count"] == 0
    assert client.delete(f"/ml-primitives/attempts/{attempt_id}", headers=owner).status_code == 200


def test_storage_error_never_claims_submission_was_saved(migrated_store, monkeypatch):
    from backend.routes.ml_primitives import store_unavailable_attempt
    from backend.db.sqlalchemy_store import SQLAlchemyDatabaseError, _MLPrimitivesAttemptCollection
    from fastapi import HTTPException

    def unavailable(*args):
        raise SQLAlchemyDatabaseError("offline")
    monkeypatch.setattr(_MLPrimitivesAttemptCollection, "insert_one", unavailable)
    with pytest.raises(HTTPException) as caught:
        store_unavailable_attempt(get_database(), {"session_id": "s", "user_id": "u"}, {
            "round": 1, "block_id": "b", "config_json": {"problem_id": "p", "problem_version": 1},
        }, "pass")
    assert caught.value.status_code == 503
    assert caught.value.detail["submission_saved"] is False
