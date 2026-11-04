"""Phase AB on the migrated durable store the browser defects were seen on.

Z-F01: a fresh round's deadline must be served with its UTC offset after
a SQLite read. The stored value was always correct UTC wall time; the read
dropped tzinfo, the API sent an offset-less string, and the browser parsed
it as local time — at +05:30 every fresh round showed 00:00.

Z-F02: the session report and coverage read an expired round that could
not be evaluated as unscored, never as a candidate zero; a genuinely
scored zero stays a zero.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.db import get_database
from backend.db.sqlalchemy_store import get_engine
from backend.main import app
from backend.routes.dashboard import _utc_date
from tests.test_phaseE_system_design import _clear_db_caches, _run_alembic
from tests.test_phaseY_expiry import (
    BLOCKS,
    SUBMITS,
    _force_expiry,
    _headers,
    _make_user,
    _start,
)


@pytest.fixture
def durable(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'phase-ab.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_db_caches()
    _run_alembic(url, "upgrade", "head")
    yield TestClient(app), _headers(_make_user("phaseab"))
    get_engine().dispose()
    _clear_db_caches()


def _stored_round(session_id):
    return get_database()["sessions"].find_one({"session_id": session_id})["rounds"][0]


def _served_deadline(client, headers, session_id):
    body = client.get(f"/session/{session_id}", headers=headers).json()
    return body["active_round"]["expires_at"]


@pytest.mark.parametrize("category", list(BLOCKS))
def test_fresh_round_deadline_is_served_with_utc_offset(durable, category):
    client, headers = durable
    started = client.post("/session/start", headers=headers,
                          json={"blocks": [BLOCKS[category]]}).json()
    served = _served_deadline(client, headers, started["session_id"])
    deadline = datetime.fromisoformat(served)
    assert deadline.tzinfo is not None, served
    assert deadline == datetime.fromisoformat(started["expires_at"])
    remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
    budget = BLOCKS[category]["duration_minutes"] * 60
    assert budget - 60 < remaining <= budget


def test_deadline_round_trips_through_store_reopen_unchanged(durable):
    client, headers = durable
    session_id = _start(client, headers, "ml_primitives")
    first = _stored_round(session_id)["expires_at"]
    get_engine().dispose()
    _clear_db_caches()
    reopened = _stored_round(session_id)["expires_at"]
    assert reopened.tzinfo is not None
    assert reopened == first
    with get_engine().connect() as conn:
        raw = conn.exec_driver_sql(
            "select expires_at from rounds where session_id = ?", (session_id,)
        ).scalar_one()
    # Rows already stored hold UTC wall time, so the read fix needs no migration.
    assert raw == reopened.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")


@pytest.mark.parametrize("category,expected", [
    ("coding", None),         # Phase Y: unevaluable on expiry → unscored
    ("ml_primitives", None),
    ("verbal", 0.0),          # scoreable but unfinished keeps the zero
])
def test_genuine_expiry_still_expires_on_durable_store(durable, category, expected):
    client, headers = durable
    session_id = _start(client, headers, category)
    _force_expiry(session_id)
    served = _served_deadline(client, headers, session_id)
    # Expiry, not serialization, is under test here (the offset is pinned by
    # the fresh-round tests); parse the way the server does, naive as UTC.
    assert _utc_date(served) < datetime.now(timezone.utc)
    resp = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1, **SUBMITS[category]})
    assert resp.status_code == 400, resp.text
    stored = _stored_round(session_id)
    assert stored["status"] == "expired"
    assert stored["final_score"] == expected


def test_report_reads_expired_unevaluated_round_as_unscored(durable):
    client, headers = durable
    session_id = _start(client, headers, "coding")
    _force_expiry(session_id)
    assert client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1, **SUBMITS["coding"]}).status_code == 400

    report = client.get(f"/dashboard/{session_id}", headers=headers).json()
    assert report["averages"]["final_score"] is None
    assert report["topic_scores"] == {}
    assert report["breakdown"] == {"Good": 0, "Average": 0, "Poor": 0}
    assert report["coverage"]["scored_rounds"] == 0
    [unscored] = report["coverage"]["unscored_rounds"]
    assert (unscored["round"], unscored["round_type"], unscored["reason"]) == (
        1, "coding", "execution_unavailable")
    [block] = report["block_results"]
    assert block["scored_rounds"] == 0
    assert block["average_score"] is None
    assert block["suggestion"] is None
    [round_doc] = report["rounds"]
    assert round_doc["final_score"] is None
    assert round_doc["performance_band"] is None

    progress = client.get("/dashboard/progress", headers=headers).json()
    assert progress["coding_coverage"]["scored_coding_rounds"] == 0
    assert progress["coding_coverage"]["unscored_coding_rounds"] == 1
    history = next(h for h in progress["history"] if h["session_id"] == session_id)
    assert history["average_score"] is None
    assert [u["reason"] for u in history["unscored_rounds"]] == ["execution_unavailable"]
    items = client.get("/learning/item-status/me", headers=headers,
                       params={"item_type": "coding"}).json()
    assert items["states"]["coding_two_sum"]["attempts"] == 0


def test_report_keeps_a_genuinely_scored_zero(durable):
    client, headers = durable
    session_id = _start(client, headers, "verbal")
    body = client.get(f"/session/{session_id}", headers=headers).json()
    questions = body["active_round"]["question_context"]["questions"]
    resp = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answers": [{"question_id": q["id"], "selected_option_ids": []} for q in questions]})
    assert resp.status_code == 200, resp.text

    report = client.get(f"/dashboard/{session_id}", headers=headers).json()
    assert report["averages"]["final_score"] == 0.0
    assert report["breakdown"]["Poor"] == 1
    assert report["coverage"]["unscored_rounds"] == []
    [block] = report["block_results"]
    assert block["average_score"] == 0.0
    assert block["suggestion"] is not None
