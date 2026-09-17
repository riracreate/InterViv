"""Phase 3A: immutable attempt snapshots + deterministic rules feedback.

- Every scored round freezes an `attempt_snapshot` (question served, answer
  as scored, scores, breakdown, feedback, Elo, policies) with a digest;
  `verify_attempt_snapshot` detects any later mutation.
- Later submits/progression never alter an earlier round's snapshot.
- Rules-scored (interview) feedback regenerates byte-identical from the
  snapshot alone; type-specific scorers replay to None.
- Snapshots are server-side only: no client surface leaks them.
"""

from __future__ import annotations

import copy
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect

from backend import config as app_config
from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.db.sqlalchemy_store import (
    _sessionmaker,
    create_all_for_smoke,
    get_engine,
    get_sqlalchemy_database,
)
from backend.main import app
from modules.attempt_snapshot import (
    regenerate_rules_feedback,
    verify_attempt_snapshot,
)
from tests.alembic_helpers import parent_revision

SNAPSHOT_REVISION = "20260914_0011"


def _make_user(prefix: str = "phase3asnap") -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one({
        "id": user_id,
        "email": f"{prefix}-{user_id[:8]}@example.com",
        "name": f"Test {prefix}",
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc),
        "last_active_at": datetime.now(timezone.utc),
    })
    return {"id": user_id, "token": create_access_token(user_id)}


def _headers(user) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def _interview_block(skills, topic=None, **over):
    block = {"round_type": "technical_short_answer", "category": "interview",
             "skills": list(skills), "count": 1}
    if topic is not None:
        block["topic"] = topic
    block.update(over)
    return block


def _stored_round(session_id: str, number: int) -> dict:
    raw = get_database()["sessions"].find_one({"session_id": session_id})
    return next(r for r in raw["rounds"] if r["round"] == number)


def _submit_interview(client, headers, session_id, number, text):
    return client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": number, "answer_text": text,
    })


# ── memory backend ──────────────────────────────────────────────────────


def test_interview_submit_freezes_verifiable_snapshot() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-freeze"))
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], count=1)],
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    served_question = start.json()["question"]

    answer = _submit_interview(
        client, headers, session_id, 1,
        "A B-tree index keeps sorted keys so range lookups stay fast.",
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()

    stored = _stored_round(session_id, 1)
    snapshot = stored.get("attempt_snapshot")
    assert isinstance(snapshot, dict)
    assert verify_attempt_snapshot(snapshot) is True
    assert snapshot["snapshot_version"] == 2
    assert isinstance(snapshot.get("reference"), dict)
    assert isinstance(snapshot.get("scorer_provenance"), dict)
    assert snapshot["round"] == 1
    assert snapshot["round_type"] == "technical_short_answer"
    assert snapshot["question"] == served_question
    assert snapshot["answer"] == stored["answer_text"]
    assert snapshot["scores"]["final_score"] == stored["final_score"]
    assert snapshot["scores"]["svm_label"] == stored["svm_label"]
    assert snapshot["feedback"] == stored["feedback"] == body["feedback"]
    assert snapshot["elo_before"] == stored["elo_before"]
    assert snapshot["elo_after"] == stored["elo_after"] == body["elo_after"]
    assert snapshot["scoring_schema_version"]
    assert snapshot["submitted_at"]
    assert snapshot["rules_replayable"] is True
    # Tamper-evidence: any mutation breaks the digest.
    tampered = copy.deepcopy(snapshot)
    tampered["scores"]["final_score"] = 100.0
    assert verify_attempt_snapshot(tampered) is False
    assert verify_attempt_snapshot(None) is False
    assert verify_attempt_snapshot({}) is False


def test_rules_feedback_replays_byte_identical() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-replay"))
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], count=1)],
    })
    session_id = start.json()["session_id"]
    answer = _submit_interview(
        client, headers, session_id, 1,
        "Normalization removes redundancy by splitting tables; indexes then "
        "speed up filtered lookups on the normalized keys.",
    )
    assert answer.status_code == 200, answer.text

    snapshot = _stored_round(session_id, 1)["attempt_snapshot"]
    assert regenerate_rules_feedback(snapshot) == snapshot["feedback"]


def test_guard_round_feedback_replays_with_prepended_message() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-guardreplay"))
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], count=1)],
    })
    session_id = start.json()["session_id"]
    # Too short: the brevity guard fires and the pipeline prepends its
    # fixed message — the replay must mirror both exactly.
    answer = _submit_interview(client, headers, session_id, 1, "x")
    assert answer.status_code == 200, answer.text

    stored = _stored_round(session_id, 1)
    assert stored["attempt_snapshot"]["guard_applied"] == "too_short"
    assert regenerate_rules_feedback(stored["attempt_snapshot"]) == stored["feedback"]


def test_snapshot_immutable_across_later_submits() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-immutable"))
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], count=2)],
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    first = _submit_interview(
        client, headers, session_id, 1,
        "Transactions group writes so they commit or roll back together.",
    )
    assert first.status_code == 200, first.text
    frozen = copy.deepcopy(_stored_round(session_id, 1)["attempt_snapshot"])

    second = _submit_interview(
        client, headers, session_id, 2,
        "A primary key uniquely identifies each row in a table.",
    )
    assert second.status_code == 200, second.text

    assert _stored_round(session_id, 1)["attempt_snapshot"] == frozen
    assert verify_attempt_snapshot(_stored_round(session_id, 1)["attempt_snapshot"]) is True
    assert verify_attempt_snapshot(_stored_round(session_id, 2)["attempt_snapshot"]) is True


def test_snapshot_never_reaches_clients() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-noleak"))
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], count=1)],
    })
    session_id = start.json()["session_id"]
    answer = _submit_interview(
        client, headers, session_id, 1,
        "An index trades write cost and space for faster reads.",
    )
    assert answer.status_code == 200, answer.text
    assert "attempt_snapshot" not in answer.text

    fetched = client.get(f"/session/{session_id}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert "attempt_snapshot" not in fetched.text
    assert "attempt_snapshot" not in (fetched.json().get("active_round") or {})

    dashboard = client.get(f"/dashboard/{session_id}", headers=headers)
    assert dashboard.status_code == 200, dashboard.text
    assert "attempt_snapshot" not in dashboard.text


def test_mcq_snapshot_present_but_not_replayable() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-mcqsnap"))
    start = client.post("/session/start", headers=headers, json={
        "candidate_id": "", "skills": ["DBMS"], "round_type": "mcq",
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    answer = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1, "answers": [],
    })
    assert answer.status_code == 200, answer.text
    snapshot = _stored_round(session_id, 1).get("attempt_snapshot")
    assert isinstance(snapshot, dict)
    assert verify_attempt_snapshot(snapshot) is True
    assert snapshot["round_type"] == "mcq"
    assert snapshot["rules_replayable"] is False
    assert regenerate_rules_feedback(snapshot) is None


# ── sqlalchemy backend (disposable SQLite) ──────────────────────────────


def _clear_db_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def sa_url(tmp_path, monkeypatch):
    db_file = tmp_path / "phase3a_snap.db"
    url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_db_caches()
    create_all_for_smoke()
    yield url
    try:
        get_engine().dispose()
    except Exception:
        pass
    _clear_db_caches()


def test_snapshot_round_trips_sqlalchemy_and_replays(sa_url) -> None:
    client = TestClient(app)
    headers = _headers(_make_user("t3a-sasnap"))
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview_block(["DBMS"], count=2)],
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    first = _submit_interview(
        client, headers, session_id, 1,
        "Transactions group writes so they commit or roll back together.",
    )
    assert first.status_code == 200, first.text
    snapshot = _stored_round(session_id, 1)["attempt_snapshot"]
    assert verify_attempt_snapshot(snapshot) is True
    assert regenerate_rules_feedback(snapshot) == snapshot["feedback"]
    frozen = copy.deepcopy(snapshot)

    second = _submit_interview(
        client, headers, session_id, 2,
        "A primary key uniquely identifies each row in a table.",
    )
    assert second.status_code == 200, second.text
    assert _stored_round(session_id, 1)["attempt_snapshot"] == frozen


def _run_alembic(engine_url: str, action: str, revision: str) -> None:
    here = os.path.dirname(__file__)
    interviv_dir = os.path.abspath(os.path.join(here, ".."))
    cfg = AlembicConfig(os.path.join(interviv_dir, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", engine_url)
    cfg.set_main_option("script_location", os.path.join(interviv_dir, "alembic"))
    if action == "upgrade":
        alembic_command.upgrade(cfg, revision)
    else:
        alembic_command.downgrade(cfg, revision)


def test_alembic_snapshot_column_upgrades_and_downgrades(tmp_path) -> None:
    db_file = tmp_path / "phase3a_snap_mig.db"
    url = f"sqlite:///{db_file}"

    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    cols = {c["name"] for c in sa_inspect(engine).get_columns("rounds")}
    assert "attempt_snapshot_json" in cols
    engine.dispose()

    _run_alembic(url, "downgrade", parent_revision(SNAPSHOT_REVISION))
    engine = create_engine(url)
    cols = {c["name"] for c in sa_inspect(engine).get_columns("rounds")}
    assert "attempt_snapshot_json" not in cols
    engine.dispose()

    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    cols = {c["name"] for c in sa_inspect(engine).get_columns("rounds")}
    assert "attempt_snapshot_json" in cols
    engine.dispose()
