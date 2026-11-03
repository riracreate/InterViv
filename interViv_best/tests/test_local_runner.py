"""Overhaul Phase 3: trusted local runner and Docker-free coding execution.

The runner is a convenience for a trusted local demo, not a sandbox; these
tests pin its limits and its opt-in gate, and that coding scoring through it
keeps the existing scorer contract (hidden details stay aggregate).
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend import execution  # noqa: E402
from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.db.phase_c_coding_bank import get_coding_problem  # noqa: E402
from backend.local_runner import (  # noqa: E402
    LocalRunnerUnavailable,
    run_python_job,
    trusted_local_execution_enabled,
)
from backend.main import app  # noqa: E402
from tests.round_helpers import activate  # noqa: E402

TWO_SUM = '''def two_sum(nums, target):
    seen = {}
    for i, x in enumerate(nums):
        if target - x in seen:
            return [seen[target - x], i]
        seen[x] = i
    return []
'''


@pytest.fixture
def trusted_local(monkeypatch):
    monkeypatch.delenv("CODING_EXECUTOR_URL", raising=False)
    monkeypatch.setenv("INTERVIV_TRUSTED_LOCAL_EXECUTION", "1")
    monkeypatch.setenv("INTERVIV_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    from backend import config

    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


# ── gate ────────────────────────────────────────────────────────────────


def test_gate_requires_flag_development_and_loopback(monkeypatch):
    from backend import config

    monkeypatch.delenv("INTERVIV_TRUSTED_LOCAL_EXECUTION", raising=False)
    monkeypatch.setenv("INTERVIV_BIND_HOST", "127.0.0.1")
    config.get_settings.cache_clear()
    assert trusted_local_execution_enabled() is False

    monkeypatch.setenv("INTERVIV_TRUSTED_LOCAL_EXECUTION", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    config.get_settings.cache_clear()
    assert trusted_local_execution_enabled() is True

    monkeypatch.setenv("INTERVIV_BIND_HOST", "0.0.0.0")
    assert trusted_local_execution_enabled() is False
    monkeypatch.delenv("INTERVIV_BIND_HOST")
    assert trusted_local_execution_enabled() is False

    monkeypatch.setenv("INTERVIV_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("ENVIRONMENT", "staging")  # any non-development environment
    config.get_settings.cache_clear()
    assert trusted_local_execution_enabled() is False
    config.get_settings.cache_clear()


# ── worker limits ───────────────────────────────────────────────────────


def test_worker_runs_code_and_reports_ok():
    result = run_python_job({"main.py": "print(sum(range(10)))"})
    assert result.status == "ok"
    assert result.stdout.strip() == "45"


@pytest.mark.parametrize("source, status", [
    ("while True:\n    pass\n", "timeout"),
    ("import time\ntime.sleep(30)\n", "timeout"),
    ("x = []\nwhile True:\n    x.append(bytearray(8_000_000))\n", "memory"),
    ("while True:\n    print('x' * 4096)\n", "output_limit"),
    ("raise RuntimeError('boom')\n", "runtime"),
])
def test_worker_enforces_limits(source, status):
    started = time.monotonic()
    result = run_python_job({"main.py": source})
    assert result.status == status, (result.status, result.stderr[-300:])
    assert time.monotonic() - started < 8


def test_candidate_imports_and_file_access_are_refused():
    driver = (
        "import importlib.util\n"
        "spec = importlib.util.spec_from_file_location('solution', 'solution.py')\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
    )
    for candidate, message in (
        ("import os\n", "Import of 'os' is not allowed"),
        ("import subprocess\n", "Import of 'subprocess' is not allowed"),
        ("from socket import socket\n", "Import of 'socket' is not allowed"),
        ("open('/etc/hosts').read()\n", "open() is not available"),
    ):
        result = run_python_job({"main.py": driver, "solution.py": candidate})
        assert result.status == "runtime"
        assert message in result.stderr


def test_allowed_stdlib_and_numpy_work():
    ok = run_python_job({"main.py": "import heapq, collections\nprint(heapq.nsmallest(1, [3, 1]))"})
    assert ok.stdout.strip() == "[1]"
    np_job = run_python_job({"main.py": "import numpy as np\nprint(int(np.arange(4).sum()))"}, numpy=True)
    assert np_job.status == "ok" and np_job.stdout.strip() == "6"


def test_startup_failure_is_infrastructure_not_candidate(monkeypatch):
    import backend.local_runner as runner

    monkeypatch.setattr(runner.sys, "executable", "/nonexistent/python")
    with pytest.raises(LocalRunnerUnavailable):
        run_python_job({"main.py": "print(1)"})


# ── execute_tests through the trusted local backend ─────────────────────


def _two_sum_tests():
    problem = get_coding_problem("coding_two_sum")
    return problem, list(problem["visible_tests"]), list(problem["hidden_tests"])


def test_correct_solution_passes_visible_and_hidden(trusted_local):
    problem, visible, hidden = _two_sum_tests()
    result = execution.execute_tests(source=TWO_SUM, function="two_sum",
                                     visible_tests=visible, hidden_tests=hidden,
                                     problem=problem)
    assert result["mode"] == "trusted_local"
    assert all(o["passed"] for o in result["visible"])
    assert all(o["passed"] for o in result["hidden"])
    # Visible cases carry actual values; hidden ones only pass/error.
    assert "actual" in result["visible"][0]
    assert set(result["hidden"][0]) == {"passed", "error"}


@pytest.mark.parametrize("source, error", [
    ("def two_sum(nums, target):\n    return [0, 0]\n", "mismatch"),
    ("def two_sum(nums, target):\n    raise ValueError('x')\n", "runtime"),
    ("def two_sum(nums, target):\n    while True:\n        pass\n", "timeout"),
    ("def two_sum(nums, target)\n    return []\n", "compile"),
])
def test_candidate_failures_are_scored_outcomes(trusted_local, source, error):
    problem, visible, hidden = _two_sum_tests()
    result = execution.execute_tests(source=source, function="two_sum",
                                     visible_tests=visible, hidden_tests=hidden,
                                     problem=problem)
    assert not any(o["passed"] for o in result["visible"])
    assert result["visible"][0]["error"] == error


def test_other_languages_stay_unavailable_without_piston(trusted_local):
    problem, visible, hidden = _two_sum_tests()
    with pytest.raises(execution.ExecutionUnavailableError):
        execution.execute_tests(source="function two_sum(a,b){return []}", function="two_sum",
                                visible_tests=visible, hidden_tests=hidden,
                                language="javascript", problem=problem)


def test_disabled_runner_keeps_the_unavailable_contract(monkeypatch):
    monkeypatch.delenv("CODING_EXECUTOR_URL", raising=False)
    monkeypatch.delenv("INTERVIV_TRUSTED_LOCAL_EXECUTION", raising=False)
    problem, visible, hidden = _two_sum_tests()
    with pytest.raises(execution.ExecutionUnavailableError):
        execution.execute_tests(source=TWO_SUM, function="two_sum",
                                visible_tests=visible, hidden_tests=hidden, problem=problem)


def test_status_reports_per_language_mode(trusted_local):
    status = execution.get_execution_status()
    modes = {item["id"]: item["mode"] for item in status["languages"]}
    assert modes["python"] == "trusted_local"
    assert modes["javascript"] == modes["java"] == modes["cpp"] == "unavailable"
    assert status["available"] is True
    assert status["provider"] == "trusted_local"
    assert "not a security sandbox" in status["trusted_local"]["label"]
    assert {"id", "label", "runtime", "version", "editor", "available"} <= set(status["languages"][0])


# ── API: coding round without Docker ────────────────────────────────────


def _make_user(prefix: str) -> dict[str, str]:
    user_id = str(uuid4())
    get_database()["users"].insert_one({
        "id": user_id, "email": f"{prefix}-{user_id[:8]}@example.com", "name": prefix,
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc), "last_active_at": datetime.now(timezone.utc),
    })
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _coding_session(client, headers, rounds=1):
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "coding", "category": "coding", "problem_ids": ["coding_two_sum"],
         "duration_minutes": 30, "count": rounds},
    ]})
    assert start.status_code == 200, start.text
    return start.json()["session_id"]


def test_coding_round_runs_and_scores_without_docker(trusted_local):
    client = TestClient(app)
    headers = _make_user("local-code")
    session_id = _coding_session(client, headers)
    run = client.post("/session/coding/run", headers=headers, json={
        "session_id": session_id, "round": 1, "source": TWO_SUM, "language": "python"})
    assert run.status_code == 200, run.text
    assert run.json()["visible_passed"] == run.json()["visible_total"] > 0

    submit = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1, "answer_text": TWO_SUM, "language": "python"})
    assert submit.status_code == 200, submit.text
    assert submit.json()["final_score"] == 100.0
    assert "hidden_tests" not in submit.text and "expected" not in submit.text


def test_run_quota_is_released_when_nothing_ran(monkeypatch):
    monkeypatch.delenv("CODING_EXECUTOR_URL", raising=False)
    monkeypatch.delenv("INTERVIV_TRUSTED_LOCAL_EXECUTION", raising=False)
    client = TestClient(app)
    headers = _make_user("local-quota")
    session_id = _coding_session(client, headers)
    for _ in range(2):
        run = client.post("/session/coding/run", headers=headers, json={
            "session_id": session_id, "round": 1, "source": TWO_SUM, "language": "python"})
        assert run.status_code == 503
    stored = get_database()["sessions"].find_one({"session_id": session_id})
    assert int(stored["rounds"][0].get("coding_exec_count") or 0) == 0


def test_candidate_errors_consume_quota(trusted_local):
    client = TestClient(app)
    headers = _make_user("local-quota-used")
    session_id = _coding_session(client, headers)
    bad = "def two_sum(nums, target):\n    raise ValueError('no')\n"
    run = client.post("/session/coding/run", headers=headers, json={
        "session_id": session_id, "round": 1, "source": bad, "language": "python"})
    assert run.status_code == 200
    assert run.json()["visible"][0]["error"] == "runtime"
    stored = get_database()["sessions"].find_one({"session_id": session_id})
    assert stored["rounds"][0]["coding_exec_count"] == 1


def test_mixed_session_advances_past_coding(trusted_local):
    client = TestClient(app)
    headers = _make_user("local-mixed")
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "coding", "category": "coding", "problem_ids": ["coding_two_sum"],
         "duration_minutes": 30},
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 1},
    ]})
    session_id = start.json()["session_id"]
    first = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1, "answer_text": TWO_SUM, "language": "python"})
    assert first.status_code == 200, first.text
    assert first.json()["next_round_status"] == "ready"
    activate(client, headers, session_id, 2)
    second = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 2,
        "answer_text": "An index speeds up lookups on a column."})
    assert second.status_code == 200, second.text
    assert second.json()["session_complete"] is True
