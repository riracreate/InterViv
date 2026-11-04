"""Overhaul Phase 3: ML primitives executed by the trusted local runner.

Every pack reference must score 100 through the real worker; executable
buggy variants must fail the numerical property they were written to
violate; ``execute: false`` variants (prohibited imports) are rejected
without running. Scores follow v1-ml-primitives.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.main import app  # noqa: E402
from backend.ml_primitives.evaluate import evaluate_ml_submission  # noqa: E402
from backend.ml_primitives.packs import (  # noqa: E402
    decode_value,
    encode_value,
    load_pack,
    pack_roots,
)
from modules.scoring.ml_primitives import score_ml_primitives_round  # noqa: E402
from tests.round_helpers import activate  # noqa: E402

PACKS = [f"{root.parent.name}.{root.name}" for root in pack_roots()]


@pytest.fixture
def trusted_local(monkeypatch):
    monkeypatch.setenv("INTERVIV_TRUSTED_LOCAL_EXECUTION", "1")
    monkeypatch.setenv("INTERVIV_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    from backend import config

    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def _root(problem_id):
    name, _, version = problem_id.partition(".")
    return next(r for r in pack_roots() if r.parent.name == name and r.name == version)


def test_six_packs_are_loaded_deterministically():
    assert len(PACKS) == 6
    for problem_id in PACKS:
        first, second = load_pack(problem_id), load_pack(problem_id)
        assert first is second  # cached
        assert first.suite.cases and first.import_rule_name


@pytest.mark.parametrize("problem_id", PACKS)
def test_reference_scores_100_through_the_worker(trusted_local, problem_id):
    source = (_root(problem_id) / "reference.py").read_text(encoding="utf-8")
    result = score_ml_primitives_round(candidate_source=source, config={"problem_id": problem_id})
    assert result["final_score"] == 100.0, result["artifact_json"]
    assert result["scoring_schema_version"] == "v1-ml-primitives"
    assert result["artifact_json"]["execution_status"] == "ok"


BUGS = [
    (problem_id, path)
    for problem_id in PACKS
    for path in sorted((_root(problem_id) / "bugs").glob("*.py"))
]


@pytest.mark.parametrize("problem_id, bug", BUGS, ids=[f"{p}:{b.stem}" for p, b in BUGS])
def test_buggy_variants_through_the_worker(trusted_local, problem_id, bug):
    meta = yaml.safe_load(bug.with_suffix(".meta.yaml").read_text(encoding="utf-8"))
    evaluation = evaluate_ml_submission(problem_id=problem_id, source=bug.read_text(encoding="utf-8"))
    if not meta.get("execute", True):
        assert evaluation["status"] == "candidate_error"
        assert evaluation["error"] == "prohibited_import"
        assert evaluation["execution"]["status"] == "not_run"
        assert not any(c["passed"] for c in evaluation["cases"])
        return
    assert evaluation["status"] == "graded"
    if meta.get("violates_property"):
        failed = {p["name"] for p in evaluation["properties"] if not p["passed"]}
        assert meta["violates_property"] in failed
        assert not all(c["passed"] for c in evaluation["cases"])
    if meta.get("violates_static"):
        names = {f["name"] for f in evaluation["static"]["findings"]}
        assert meta["violates_static"] in names


def test_style_findings_are_reported_but_not_scored(trusted_local):
    problem_id = "softmax_stable.v1"
    loop = (_root(problem_id) / "bugs" / "batch_loop.py").read_text(encoding="utf-8")
    result = score_ml_primitives_round(candidate_source=loop, config={"problem_id": problem_id})
    assert result["final_score"] == 100.0
    assert any("batch axis loop" in line for line in result["feedback"]["content"])


@pytest.mark.parametrize("source, error", [
    ("import numpy as np\ndef softmax(logits)\n    return logits\n", "syntax"),
    ("import numpy as np\nimport os\ndef softmax(logits):\n    return logits\n", "prohibited_import"),
    ("import numpy as np\ndef softmax(logits):\n    raise ValueError('nope')\n", "runtime"),
    ("import numpy as np\ndef softmax(logits):\n    while True:\n        pass\n", "timeout"),
    ("import numpy as np\ndef softmax(logits):\n    return [str(x) for x in logits]\n", "invalid_output"),
    ("import numpy as np\nraise RuntimeError('top level')\n", "load"),
])
def test_candidate_errors_score_zero_with_a_kind(trusted_local, source, error):
    result = score_ml_primitives_round(candidate_source=source, config={"problem_id": "softmax_stable.v1"})
    assert result["final_score"] == 0.0
    kinds = {c["error"] for c in result["artifact_json"]["cases"]}
    assert error in kinds, result["artifact_json"]
    assert "nope" not in str(result) and "top level" not in str(result)  # no echoed messages


def test_unavailable_runner_never_scores(monkeypatch):
    from backend.execution import ExecutionUnavailableError

    monkeypatch.delenv("INTERVIV_TRUSTED_LOCAL_EXECUTION", raising=False)
    with pytest.raises(ExecutionUnavailableError):
        evaluate_ml_submission(problem_id="softmax_stable.v1", source="import numpy as np\n")


def test_envelopes_round_trip_and_reject_bad_shapes():
    value = {"a": np.arange(6, dtype=np.int64).reshape(2, 3), "b": np.array(0.5)}
    decoded = decode_value(encode_value(value))
    assert decoded["a"].dtype == np.int64 and decoded["a"].shape == (2, 3)
    assert decoded["b"].shape == () and float(decoded["b"]) == 0.5
    for bad in (
        {"kind": "ndarray", "dtype": "object", "shape": [1], "data": [1]},
        {"kind": "ndarray", "dtype": "float64", "shape": [3], "data": [1.0]},
        {"kind": "ndarray", "dtype": "float64", "shape": [-1], "data": []},
        {"kind": "ndarray", "dtype": "float64", "shape": [1], "data": ["x"]},
        {"kind": "pickle", "data": "gASV"},
    ):
        with pytest.raises(ValueError):
            decode_value(bad)


# ── API: ML round through the shared session path ───────────────────────


def _headers(prefix: str) -> dict[str, str]:
    user_id = str(uuid4())
    get_database()["users"].insert_one({
        "id": user_id, "email": f"{prefix}-{user_id[:8]}@example.com", "name": prefix,
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc), "last_active_at": datetime.now(timezone.utc),
    })
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def test_ml_round_is_graded_and_session_advances(trusted_local):
    client = TestClient(app)
    headers = _headers("ml-api")
    start = client.post("/session/start", headers=headers, json={"blocks": [
        {"round_type": "ml_primitives", "category": "ml_primitives",
         "problem_ids": ["minmax_normalize.v1"], "duration_minutes": 30},
        {"round_type": "technical_short_answer", "category": "interview",
         "skills": ["DBMS"], "count": 1},
    ]})
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    view = client.get(f"/session/{session_id}", headers=headers).json()
    assert view["active_round"]["config_json"]["scoring_available"] is True

    source = (_root("minmax_normalize.v1") / "reference.py").read_text(encoding="utf-8")
    wrong_problem = client.post("/ml-primitives/softmax_stable.v1/submit", headers=headers, json={
        "session_id": session_id, "round": 1, "source": source})
    assert wrong_problem.status_code == 409

    graded = client.post("/ml-primitives/minmax_normalize.v1/submit", headers=headers, json={
        "session_id": session_id, "round": 1, "source": source})
    assert graded.status_code == 200, graded.text
    body = graded.json()
    assert body["final_score"] == 100.0
    assert body["evidence_kind"] == "measured"
    assert body["next_round_status"] == "ready"
    for leaked in ("reference_output", "PHASEX_", "generate_cases", "inputs"):
        assert leaked not in graded.text

    attempts = client.get("/ml-primitives/attempts", headers=headers).json()["attempts"]
    mine = [a for a in attempts if a["session_id"] == session_id]
    assert mine and mine[-1]["score"] == 100.0 and mine[-1]["grader_version"] == "v1-ml-primitives"

    history = client.get(f"/session/{session_id}", headers=headers).json()["round_history"]
    assert history[0]["final_score"] == 100.0
    assert history[0]["artifact_json"]["cases_passed"] == history[0]["artifact_json"]["cases_total"]

    activate(client, headers, session_id, 2)
    done = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 2,
        "answer_text": "Normalization reduces redundancy."})
    assert done.status_code == 200, done.text
    assert done.json()["session_complete"] is True
