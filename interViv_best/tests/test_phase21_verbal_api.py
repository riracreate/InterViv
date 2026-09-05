"""API coverage for standalone Verbal Ability MCQ practice (Phase 2.1).

Covers: standalone session validation, category-specific selection on both
the database and fallback paths, scoring, completion, ownership, refresh
stability, key/explanation leakage, and separation from technical reporting.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.db.phase21_verbal_bank import (  # noqa: E402
    PHASE21_VERBAL_BANK,
    VERBAL_SKILL,
    seed_verbal_bank,
)
from backend.main import app  # noqa: E402

VERBAL_START = {
    "candidate_id": "",
    "skills": [VERBAL_SKILL],
    "rounds_per_skill": 1,
    "round_type": "mcq",
    "round_config": {"count": 15, "duration_minutes": 20, "negative_marking": 0.25},
}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _make_user(prefix: str) -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one(
        {
            "id": user_id,
            "email": f"{prefix}-{user_id[:8]}@example.com",
            "name": f"Test {prefix}",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    return {"id": user_id, "token": create_access_token(user_id)}


def _headers(user: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def _start(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    payload = deepcopy(VERBAL_START)
    payload.update(overrides)
    resp = client.post("/session/start", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _submit_all(client: TestClient, headers: dict[str, str], session_id: str, questions: list[dict]) -> dict:
    answers = [
        {"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}
        for q in questions
    ]
    resp = client.post(
        "/session/answer",
        json={"session_id": session_id, "round": 1, "answers": answers},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Standalone validation ────────────────────────────────────────────────

def test_verbal_rejects_mixed_skills(client: TestClient) -> None:
    user = _make_user("verbal-mixed")
    db = get_database()
    before = len(list(db["sessions"].find({})))
    resp = client.post(
        "/session/start",
        json={**VERBAL_START, "skills": [VERBAL_SKILL, "DBMS"]},
        headers=_headers(user),
    )
    assert resp.status_code == 422, resp.text
    assert "cannot be combined" in resp.text
    assert len(list(db["sessions"].find({}))) == before


def test_verbal_rejects_other_round_types(client: TestClient) -> None:
    user = _make_user("verbal-roundtype")
    for round_type in ("technical_short_answer", "sql"):
        resp = client.post(
            "/session/start",
            json={**VERBAL_START, "round_type": round_type},
            headers=_headers(user),
        )
        assert resp.status_code == 422, resp.text
        assert "round_type=" in resp.text and "mcq" in resp.text


def test_verbal_rejects_multiple_rounds(client: TestClient) -> None:
    user = _make_user("verbal-rounds")
    resp = client.post(
        "/session/start",
        json={**VERBAL_START, "rounds_per_skill": 3},
        headers=_headers(user),
    )
    assert resp.status_code == 422, resp.text
    assert "rounds_per_skill=1" in resp.text


# ── Category-specific selection (fallback path) ──────────────────────────

def test_verbal_start_assigns_verbal_only(client: TestClient) -> None:
    user = _make_user("verbal-assign")
    started = _start(client, _headers(user))
    assert started["total_rounds"] == 1
    questions = started["questions"]
    assert len(questions) == 15
    assert all(q["skill"] == VERBAL_SKILL for q in questions)
    assert all(q["id"].startswith("mcq_verbal_") for q in questions)
    assert len({q["id"] for q in questions}) == 15
    blob = json.dumps(started, default=str)
    assert '"correct_option_ids"' not in blob
    assert '"explanation"' not in blob


def test_technical_start_excludes_verbal(client: TestClient) -> None:
    user = _make_user("verbal-excl")
    resp = client.post(
        "/session/start",
        json={
            "candidate_id": "",
            "skills": ["DBMS", "Python"],
            "rounds_per_skill": 1,
            "round_type": "mcq",
            "round_config": {"count": 15, "duration_minutes": 20, "negative_marking": 0.25},
        },
        headers=_headers(user),
    )
    assert resp.status_code == 200, resp.text
    questions = resp.json()["questions"]
    assert len(questions) == 15
    assert all(q["skill"] != VERBAL_SKILL for q in questions)


def test_insufficient_bank_returns_clear_error(client: TestClient) -> None:
    user = _make_user("verbal-short")
    resp = client.post(
        "/session/start",
        json={**VERBAL_START, "round_config": {"count": 31, "duration_minutes": 20}},
        headers=_headers(user),
    )
    assert resp.status_code == 422, resp.text
    assert "Not enough Verbal Ability MCQ questions" in resp.text


def test_partially_seeded_bank_errors_without_mixing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.db import phase21_verbal_bank

    monkeypatch.setattr(phase21_verbal_bank, "PHASE21_VERBAL_BANK", PHASE21_VERBAL_BANK[:10])
    user = _make_user("verbal-partial")
    resp = client.post("/session/start", json=VERBAL_START, headers=_headers(user))
    assert resp.status_code == 422, resp.text
    assert "found 10, need 15" in resp.text


# ── Database paths ───────────────────────────────────────────────────────

def _clear_database_caches() -> None:
    from backend import config
    from backend.db import sqlalchemy_store

    config.get_settings.cache_clear()
    sqlalchemy_store.get_engine.cache_clear()
    sqlalchemy_store._sessionmaker.cache_clear()
    sqlalchemy_store.get_sqlalchemy_database.cache_clear()


@pytest.fixture()
def sqlite_db(tmp_path, monkeypatch):
    from backend.db import sqlalchemy_store

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'verbal_e2e.db'}")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "false")
    _clear_database_caches()
    sqlalchemy_store.create_all_for_smoke()
    try:
        yield
    finally:
        _clear_database_caches()


def test_verbal_works_with_technical_only_database(
    client: TestClient, sqlite_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.db.phase2_content_bank import seed_phase2_content_bank
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        seed_phase2_content_bank(session)
    user = _make_user("verbal-techodb")
    started = _start(client, _headers(user))
    assert len(started["questions"]) == 15
    assert all(q["skill"] == VERBAL_SKILL for q in started["questions"])


def test_verbal_served_from_database_when_seeded(
    client: TestClient, sqlite_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.db import phase21_verbal_bank
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        assert seed_verbal_bank(session) == 30
    # Empty module bank proves the rows came from the database, not fallback.
    monkeypatch.setattr(phase21_verbal_bank, "PHASE21_VERBAL_BANK", [])
    user = _make_user("verbal-dbseed")
    started = _start(client, _headers(user))
    assert len(started["questions"]) == 15
    assert all(q["skill"] == VERBAL_SKILL for q in started["questions"])


def test_technical_db_selection_excludes_verbal(
    client: TestClient, sqlite_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.db.phase2_content_bank import seed_phase2_content_bank
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        seed_phase2_content_bank(session)
        assert seed_verbal_bank(session) == 30
    user = _make_user("verbal-dbexcl")
    resp = client.post(
        "/session/start",
        json={
            "candidate_id": "",
            "skills": ["DBMS"],
            "rounds_per_skill": 1,
            "round_type": "mcq",
            "round_config": {"count": 15, "duration_minutes": 20},
        },
        headers=_headers(user),
    )
    assert resp.status_code == 200, resp.text
    assert all(q["skill"] != VERBAL_SKILL for q in resp.json()["questions"])


# ── Scoring, completion, ownership, refresh ──────────────────────────────

def _assigned(count: int = 4) -> list[dict]:
    return deepcopy(PHASE21_VERBAL_BANK[:count])


def test_verbal_scoring_matrix() -> None:
    from modules.scoring import score_round

    assigned = _assigned()
    keys = {q["id"]: q["correct_option_ids"] for q in assigned}
    wrong = {
        q["id"]: [o["id"] for o in q["options_json"] if o["id"] not in keys[q["id"]]][:1]
        for q in assigned
    }

    def answers(mapping: dict, skip: set[str] | None = None) -> list[dict]:
        skip = skip or set()
        return [
            {"question_id": qid, "selected_option_ids": [] if qid in skip else sel}
            for qid, sel in mapping.items()
        ]

    all_correct = score_round(
        round_type="mcq", answers=answers(keys),
        question_context={"questions": assigned}, config={"negative_marking": 0.25},
    )
    assert all_correct["final_score"] == 100.0

    all_wrong = score_round(
        round_type="mcq", answers=answers(wrong),
        question_context={"questions": assigned}, config={"negative_marking": 0.25},
    )
    assert all_wrong["final_score"] == 0.0

    mixed = dict(keys)
    first = assigned[0]["id"]
    mixed[first] = wrong[first]
    mixed_score = score_round(
        round_type="mcq", answers=answers(mixed),
        question_context={"questions": assigned}, config={"negative_marking": 0.25},
    )
    assert mixed_score["final_score"] == round((3 - 0.25) / 4 * 100, 2)

    skipped_score = score_round(
        round_type="mcq", answers=answers(keys, skip={first}),
        question_context={"questions": assigned}, config={"negative_marking": 0.25},
    )
    assert skipped_score["final_score"] == 75.0
    assert skipped_score["artifact_json"]["unanswered_count"] == 1


def test_verbal_submit_completes_session(client: TestClient) -> None:
    user = _make_user("verbal-complete")
    started = _start(client, _headers(user))
    body = _submit_all(client, _headers(user), started["session_id"], started["questions"])
    assert body["session_complete"] is True
    assert body["next_question"] is None
    fetched = client.get(f"/session/{started['session_id']}", headers=_headers(user))
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["status"] == "completed"


def test_verbal_cross_user_access_rejected(client: TestClient) -> None:
    owner = _make_user("verbal-owner")
    other = _make_user("verbal-other")
    started = _start(client, _headers(owner))
    session_id = started["session_id"]

    fetched = client.get(f"/session/{session_id}", headers=_headers(other))
    assert fetched.status_code == 403, fetched.text

    submit = client.post(
        "/session/answer",
        json={"session_id": session_id, "round": 1, "answers": []},
        headers=_headers(other),
    )
    assert submit.status_code == 403, submit.text


def test_verbal_refresh_preserves_ids_order_expiry(client: TestClient) -> None:
    user = _make_user("verbal-refresh")
    started = _start(client, _headers(user))
    session_id = started["session_id"]
    first_ids = [q["id"] for q in started["questions"]]
    first_opts = [[o["id"] for o in q["options"]] for q in started["questions"]]

    snapshots = []
    for _ in range(2):
        resp = client.get(f"/session/{session_id}", headers=_headers(user))
        assert resp.status_code == 200, resp.text
        snapshots.append(resp.json()["active_round"])
    for snap in snapshots:
        assert [q["id"] for q in snap["question_context"]["questions"]] == first_ids
        assert [[o["id"] for o in q["options"]] for q in snap["question_context"]["questions"]] == first_opts
        assert snap["expires_at"] == started["expires_at"]


# ── Leakage ──────────────────────────────────────────────────────────────

KEY_SENTINEL = "SECRET_VERBAL_KEY_SENTINEL"
EXP_SENTINEL = "SECRET_VERBAL_EXPLANATION_SENTINEL"


def _seed_key_sentinels(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.db import phase21_verbal_bank

    seeded = deepcopy(PHASE21_VERBAL_BANK)
    seeded[0]["correct_option_ids"] = [KEY_SENTINEL]
    seeded[0]["explanation"] = EXP_SENTINEL
    monkeypatch.setattr(phase21_verbal_bank, "PHASE21_VERBAL_BANK", seeded)


def _assert_no_verbal_leak(payload: object, surface: str) -> None:
    blob = json.dumps(payload, default=str)
    assert KEY_SENTINEL not in blob, f"{surface} leaked key sentinel"
    assert EXP_SENTINEL not in blob, f"{surface} leaked explanation sentinel"
    assert '"correct_option_ids"' not in blob, f"{surface} exposed correct_option_ids"
    assert '"explanation"' not in blob, f"{surface} exposed explanation"


def test_verbal_key_leak_probe_fails_closed() -> None:
    with pytest.raises(AssertionError, match="probe leaked key sentinel"):
        _assert_no_verbal_leak({"k": KEY_SENTINEL}, "probe")


def test_verbal_surfaces_hide_keys_and_explanations(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _make_user("verbal-leak")
    headers = _headers(user)
    _seed_key_sentinels(monkeypatch)
    started = _start(client, headers)
    session_id = started["session_id"]

    stored = get_database()["sessions"].find_one({"session_id": session_id})["rounds"][0]
    assert KEY_SENTINEL in json.dumps(stored["question_context"], default=str)

    _assert_no_verbal_leak(started, "start")

    resume = client.get(f"/session/{session_id}", headers=headers)
    assert resume.status_code == 200, resume.text
    _assert_no_verbal_leak(resume.json(), "resume")

    body = _submit_all(client, headers, session_id, started["questions"])
    _assert_no_verbal_leak(body, "submit")

    dash = client.get(f"/dashboard/{session_id}", headers=headers)
    assert dash.status_code == 200, dash.text
    _assert_no_verbal_leak(dash.json(), "dashboard")


# ── Separation from technical reporting ──────────────────────────────────

def test_verbal_ignored_by_role_readiness() -> None:
    from modules.company_graph import get_company_graph
    from modules.gap_analysis import compute_gap_for_levels

    _, role = get_company_graph().find_role("amazon_sde_intern")
    levels = {"DSA": (45.0, 3), "DBMS": (60.0, 3)}
    base = compute_gap_for_levels(role, levels).overall_readiness_percentage
    with_verbal = compute_gap_for_levels(
        role, {**levels, VERBAL_SKILL: (100.0, 5)}
    ).overall_readiness_percentage
    assert with_verbal == base


def test_verbal_results_reported_separately(client: TestClient) -> None:
    from modules.skill_graph import StudentSkillGraph

    user = _make_user("verbal-separate")
    headers = _headers(user)
    started = _start(client, headers)
    _submit_all(client, headers, started["session_id"], started["questions"])

    state = StudentSkillGraph(user["id"]).get_current_state()
    assert VERBAL_SKILL in state
    assert state[VERBAL_SKILL].attempts == 1

    dash = client.get(f"/dashboard/{started['session_id']}", headers=headers)
    assert dash.status_code == 200, dash.text
    body = dash.json()
    assert list(body["topic_scores"]) == [VERBAL_SKILL]
    assert body["averages"]["final_score"] == body["rounds"][0]["final_score"]
