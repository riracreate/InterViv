"""Phase E: system-design persistence, AV capabilities, ownership, leakage."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

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
from backend.db.phase_e_system_design_bank import SYSTEM_DESIGN_RUBRIC
from modules.scoring.system_design import score_system_design_round
from modules.av_capabilities import av_capability_report
from tests.alembic_helpers import parent_revision

PHASE_E_REVISION = "20260907_0007"


def _clear_db_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def sa_url(tmp_path, monkeypatch):
    db_file = tmp_path / "phasee.db"
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


def _make_user(prefix="e1"):
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


def _headers(user):
    return {"Authorization": f"Bearer {user['token']}"}


def _full_ratings():
    return {c["id"]: 4 for c in SYSTEM_DESIGN_RUBRIC}


LEAK_KEYS = (
    "correct_option_ids",
    "reference_solution",
    "reference_query",
    "hidden_tests",
    "hidden_cases",
    "storage_path",
    "artifact_path",
    "raw_blob",
)


def _walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k).lower()
            yield from _walk(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def _assert_no_leakage(payload) -> None:
    keys = set(_walk(payload))
    for key in LEAK_KEYS:
        assert key not in keys, key
    # Stronger: only flag structured restricted fields (stems may say "explanation").
    if isinstance(payload, dict):
        for item in (payload.get("mcq") or []) + (payload.get("verbal") or []):
            assert "explanation" not in item
            assert "correct_option_ids" not in item
        for item in payload.get("coding") or []:
            assert "hidden_tests" not in item
            assert "reference_solution" not in item
        for item in payload.get("system_design") or []:
            assert "reference_outline" not in item
            assert "answer_key" not in item
        ctx = payload.get("question_context")
        if isinstance(ctx, dict):
            assert "reference_outline" not in ctx
            assert "hidden_tests" not in ctx
            assert "correct_option_ids" not in ctx


def test_system_design_attempt_round_trips_on_sqlalchemy_store(sa_url) -> None:
    db = get_database()
    doc = {
        "id": str(uuid4()),
        "user_id": "u1",
        "session_id": "s1",
        "round": 1,
        "prompt_id": "sd_url_shortener",
        "answer_text": "CDN + key-value store",
        "rubric_json": {"ratings": _full_ratings()},
        "evaluation_mode": "structured_self_assessment",
        "status": "scored",
        "score": 75.0,
        "incomplete": False,
        "created_at": datetime.now(timezone.utc),
    }
    db["system_design_attempts"].insert_one(doc)
    found = db["system_design_attempts"].find_one({"id": doc["id"]})
    assert found is not None
    for key in (
        "user_id", "session_id", "round", "prompt_id", "answer_text",
        "evaluation_mode", "status", "score", "incomplete",
    ):
        assert found[key] == doc[key], key
    assert found["rubric_json"]["ratings"]["requirements"] == 4

    get_engine().dispose()
    _clear_db_caches()
    reopened = get_database()
    again = reopened["system_design_attempts"].find_one({"id": doc["id"]})
    assert again is not None
    assert again["score"] == 75.0
    assert again["rubric_json"]["ratings"]["scale"] == 4


def test_alembic_system_design_up_down_up(tmp_path) -> None:
    db_file = tmp_path / "phasee_mig.db"
    url = f"sqlite:///{db_file}"
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    tables = sa_inspect(engine).get_table_names()
    assert "system_design_attempts" in tables
    cols = {c["name"] for c in sa_inspect(engine).get_columns("system_design_attempts")}
    for col in (
        "id", "user_id", "session_id", "round_number", "prompt_id",
        "answer_text", "rubric_json", "evaluation_mode", "status",
        "score", "incomplete", "created_at",
    ):
        assert col in cols, col
    engine.dispose()

    _run_alembic(url, "downgrade", parent_revision(PHASE_E_REVISION))
    engine = create_engine(url)
    try:
        assert "system_design_attempts" not in sa_inspect(engine).get_table_names()
    finally:
        engine.dispose()

    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    try:
        assert "system_design_attempts" in sa_inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_rubric_boundary_no_diagram_verdict() -> None:
    incomplete = score_system_design_round(answer="notes", rubric_ratings={"requirements": 3})
    assert incomplete["final_score"] is None
    assert incomplete["incomplete"] is True
    assert "diagram" in incomplete["boundary"].lower()

    complete = score_system_design_round(answer="notes", rubric_ratings=_full_ratings())
    assert complete["final_score"] is not None
    assert complete["evaluation_mode"] == "structured_self_assessment"
    assert "not auto" in complete["boundary"].lower() or "self-assessment" in complete["boundary"].lower()
    assert "correctness verdict" in complete["boundary"].lower() or "diagram" in complete["boundary"].lower()


def test_system_design_compose_with_other_blocks(sa_url) -> None:
    client = TestClient(app)
    user = _make_user("compose")
    headers = _headers(user)
    started = client.post(
        "/session/start",
        headers=headers,
        json={
            "blocks": [
                {
                    "round_type": "system_design",
                    "category": "system_design",
                    "skills": ["System Design"],
                    "count": 1,
                    "duration_minutes": 25,
                    "problem_ids": ["sd_rate_limiter"],
                },
                {
                    "round_type": "coding",
                    "category": "coding",
                    "skills": [],
                    "count": 1,
                    "duration_minutes": 30,
                    "problem_ids": ["coding_two_sum"],
                },
                {
                    "round_type": "technical_short_answer",
                    "category": "interview",
                    "skills": ["DBMS"],
                    "count": 1,
                },
            ]
        },
    )
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["round_type"] == "system_design"
    assert body["total_rounds"] == 3
    plan = body["block_plan"]
    assert [b["category"] for b in plan] == ["system_design", "coding", "interview"]
    assert plan[0]["id"]
    ctx = body.get("question_context") or {}
    assert ctx.get("id") == "sd_rate_limiter"
    assert ctx.get("rubric")
    assert "evaluation_boundary" in ctx
    _assert_no_leakage(body)

    submit = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": body["session_id"],
            "round": 1,
            "answer_text": "Token bucket in Redis with local fallback.",
            "rubric_ratings": _full_ratings(),
        },
    )
    assert submit.status_code == 200, submit.text
    scored = submit.json()
    assert scored["evaluation_mode"] == "structured_self_assessment"
    assert scored["final_score"] is not None
    assert "diagram" in (scored.get("evaluation_boundary") or "").lower()
    _assert_no_leakage(scored)

    rows = list(get_database()["system_design_attempts"].find(
        {"session_id": body["session_id"]}
    ))
    assert len(rows) == 1
    assert rows[0]["user_id"] == user["id"]
    assert rows[0]["status"] == "scored"


def test_incomplete_rubric_no_zero_score(sa_url) -> None:
    client = TestClient(app)
    user = _make_user("incomplete")
    headers = _headers(user)
    started = client.post(
        "/session/start",
        headers=headers,
        json={
            "blocks": [{
                "round_type": "system_design",
                "category": "system_design",
                "count": 1,
                "problem_ids": ["sd_url_shortener"],
            }]
        },
    )
    assert started.status_code == 200, started.text
    sid = started.json()["session_id"]
    resp = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": sid,
            "round": 1,
            "answer_text": "partial",
            "rubric_ratings": {"requirements": 2},
        },
    )
    assert resp.status_code == 422
    rows = list(get_database()["system_design_attempts"].find({"session_id": sid}))
    assert len(rows) == 1
    assert rows[0]["incomplete"] is True
    assert rows[0]["score"] is None
    assert rows[0]["status"] == "incomplete"


def test_av_capabilities_distinct_states_and_no_speech_score() -> None:
    report = av_capability_report()
    states = report["unavailable_states"]
    for needed in (
        "permission_not_requested",
        "permission_denied",
        "no_device",
        "unsupported_browser",
        "service_unavailable",
        "capture_failed",
        "interrupted_recoverable",
    ):
        assert needed in states
    assert report["speech_scoring"]["available"] is False
    assert report["video_recording"]["available"] is False

    client = TestClient(app)
    resp = client.get("/av/capabilities", headers=_headers(_make_user("av")))
    assert resp.status_code == 200
    body = resp.json()
    assert "retention" in body
    assert body["speech_scoring"]["available"] is False
    _assert_no_leakage(body)


def test_system_design_ownership(sa_url) -> None:
    client = TestClient(app)
    owner = _make_user("owner")
    stranger = _make_user("stranger")
    db = get_database()
    attempt_id = str(uuid4())
    db["system_design_attempts"].insert_one({
        "id": attempt_id,
        "user_id": owner["id"],
        "session_id": "s-own",
        "round": 1,
        "prompt_id": "sd_chat",
        "answer_text": "private notes",
        "rubric_json": {},
        "evaluation_mode": "structured_self_assessment",
        "status": "scored",
        "score": 50.0,
        "incomplete": False,
        "created_at": datetime.now(timezone.utc),
    })

    listed = client.get("/av/system-design-attempts", headers=_headers(owner))
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["attempts"][0]["answer_text"] == "private notes"

    other_list = client.get("/av/system-design-attempts", headers=_headers(stranger))
    assert other_list.status_code == 200
    assert other_list.json()["count"] == 0

    denied = client.delete(
        f"/av/system-design-attempts/{attempt_id}",
        headers=_headers(stranger),
    )
    assert denied.status_code == 403

    deleted = client.delete(
        f"/av/system-design-attempts/{attempt_id}",
        headers=_headers(owner),
    )
    assert deleted.status_code == 200
    assert get_database()["system_design_attempts"].find_one({"id": attempt_id}) is None


def test_practice_bank_includes_system_design_public_only(sa_url) -> None:
    client = TestClient(app)
    user = _make_user("bank")
    resp = client.get("/session/practice-bank", headers=_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["counts"]["system_design"] >= 1
    for item in body["system_design"]:
        assert "rubric" in item
        assert "evaluation_boundary" in item
    _assert_no_leakage(body)


def test_self_assessment_does_not_raise_measured_mastery(sa_url) -> None:
    """Self-reported system-design scores stay out of skill-graph mastery."""
    from modules.skill_graph import StudentSkillGraph

    client = TestClient(app)
    user = _make_user("selfrep")
    headers = _headers(user)
    StudentSkillGraph(user["id"]).initialize_from_resume(["System Design", "DBMS"])
    before = {
        node["name"]: (node.get("attempts") or 0, node.get("score"))
        for node in client.get("/skill-graph/me", headers=headers).json()["skills"]
    }
    started = client.post(
        "/session/start",
        headers=headers,
        json={
            "blocks": [{
                "round_type": "system_design",
                "category": "system_design",
                "count": 1,
                "problem_ids": ["sd_url_shortener"],
            }]
        },
    )
    assert started.status_code == 200, started.text
    submit = client.post(
        "/session/answer",
        headers=headers,
        json={
            "session_id": started.json()["session_id"],
            "round": 1,
            "answer_text": "Self-rated perfect design.",
            "rubric_ratings": _full_ratings(),
        },
    )
    assert submit.status_code == 200, submit.text
    assert submit.json()["evidence_kind"] == "self_reported"
    assert submit.json()["final_score"] == 75.0  # all ratings=4 → (4-1)/4*100
    after = {
        node["name"]: (node.get("attempts") or 0, node.get("score"))
        for node in client.get("/skill-graph/me", headers=headers).json()["skills"]
    }
    assert after == before
    notebook = client.get("/learning/notebook/me", headers=headers).json()
    assert all(
        e.get("round_type") != "system_design"
        for e in notebook.get("entries") or []
    )
    progress = client.get("/dashboard/progress", headers=headers).json()
    for row in progress.get("history") or []:
        if row.get("session_id") == started.json()["session_id"]:
            assert row.get("average_score") is None
            assert row.get("self_reported_rounds", 0) >= 1


# ── Calibration: self-rating vs what the design notes mention (advisory) ─────

from backend.db.phase_e_system_design_bank import (  # noqa: E402
    SYSTEM_DESIGN_EVIDENCE,
    get_system_design_prompt,
    public_system_design_prompt,
)
from modules.scoring.system_design import (  # noqa: E402
    evidence_coverage,
    score_system_design_round,
)

_LIMITER_THIN = (
    "I would put a rate limiter in front of the API and return 429 when a client "
    "sends too many requests per second. Each API key gets its own limit and the "
    "service should be distributed across several nodes."
)
_LIMITER_RICH = (
    _LIMITER_THIN + " Use a token bucket in Redis with an atomic INCR via a Lua "
    "script and a TTL on each key; send Retry-After headers. Race conditions are "
    "avoided by the atomic update, keys are sharded with consistent hashing, and a "
    "local in-memory counter covers a Redis outage. If the store is down we fail "
    "open for reads; we accept approximate accuracy to save memory and note clock skew."
)
_ALL_FIVES = {"requirements": 5, "api_data": 5, "scale": 5, "tradeoffs": 5}


def _limiter_ctx() -> dict:
    return public_system_design_prompt(get_system_design_prompt("sd_rate_limiter"))


def test_evidence_concepts_stay_server_side() -> None:
    public = _limiter_ctx()
    public_text = str(public).lower()
    prompt_text = public["prompt"].lower()
    for concepts in SYSTEM_DESIGN_EVIDENCE["sd_rate_limiter"].values():
        for label, _ in concepts:
            if label.lower() not in prompt_text:  # the prompt itself may name a concept
                assert label.lower() not in public_text, label
    assert set(SYSTEM_DESIGN_EVIDENCE["sd_rate_limiter"]) == {"requirements", "api_data", "scale", "tradeoffs"}


def test_overconfident_ratings_are_flagged_without_changing_score() -> None:
    result = score_system_design_round(answer=_LIMITER_THIN, rubric_ratings=_ALL_FIVES, question_context=_limiter_ctx())
    assert result["final_score"] == 100.0  # score is still the self-assessment
    calibration = result["artifact_json"]["calibration"]
    assert calibration["available"] is True
    rows = {row["id"]: row for row in calibration["criteria"]}
    assert rows["requirements"]["overconfident"] is False  # 429, per second, API key, distributed
    assert rows["scale"]["overconfident"] is True
    assert rows["tradeoffs"]["overconfident"] is True
    assert "fail open vs closed" in rows["tradeoffs"]["not_mentioned"]


def test_rich_notes_back_the_ratings() -> None:
    result = score_system_design_round(answer=_LIMITER_RICH, rubric_ratings=_ALL_FIVES, question_context=_limiter_ctx())
    rows = result["artifact_json"]["calibration"]["criteria"]
    assert not any(row["overconfident"] for row in rows), rows


def test_short_notes_give_no_calibration() -> None:
    coverage = evidence_coverage("token bucket redis", "sd_rate_limiter")
    assert coverage["available"] is False
    result = score_system_design_round(answer="", rubric_ratings=_ALL_FIVES, question_context=_limiter_ctx())
    assert result["artifact_json"]["calibration"]["available"] is False
    assert result["final_score"] == 100.0


def test_unknown_prompt_gives_no_calibration() -> None:
    assert evidence_coverage(_LIMITER_RICH, "sd_unknown")["available"] is False
