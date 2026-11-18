"""S2b: staged reference-free Core turns are unmeasured; legacy is unchanged."""
from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from backend import config as app_config
from backend.evidence_kind import assessment_eligible_scores
from backend.main import app
from backend.routes import answer as answer_routes
from backend.routes import session as session_routes
from tests.round_helpers import activate
from tests.test_slice2_staged_flow import _create_user_headers, staged_sql_env


ANSWER = (
    "Generators yield one value at a time and suspend their execution frame. "
    "For example, streaming a large log file avoids allocating a complete list "
    "because only the current record is needed. The trade-off is that a generator "
    "is consumed after iteration, whereas a list supports repeated indexed access. "
    "In production I would test empty input, close resources with a context manager, "
    "and profile memory usage before choosing the implementation."
)


def _question(*, referenced=False, required=False):
    payload = {
        "question": "Explain Python generators and when you would choose one over a list.",
        "skill": "Python", "sub_domain": "general", "difficulty": "medium",
        "source": "csv" if referenced else "template",
        "ideal_answer": (
            "Generators lazily yield one item at a time and suspend execution state, "
            "saving memory compared with allocating a complete list."
        ) if referenced else "",
        "ideal_keywords": "generator, yield, lazy, memory" if referenced else "",
        "followups": [],
    }
    if required:
        payload["required_concepts"] = [{
            "id": "lazy_generation", "descriptor": "Generators yield values lazily",
            "aliases": ["yield", "lazily"],
            "expected_propositions": ["generators yield values lazily"],
        }]
    return payload


def _install_questions(monkeypatch, *payloads):
    pending = iter(payloads)

    def choose(**kwargs):
        return deepcopy(next(pending))

    monkeypatch.setattr(session_routes, "_get_next_question", choose)
    monkeypatch.setattr(answer_routes, "_get_next_question", choose)
    monkeypatch.setenv("STAGED_INLINE_FOLLOW_UPS", "0")
    app_config.get_settings.cache_clear()


def _start(client, headers, *, staged=True):
    payload = {"skills": ["Python"], "practice_mode": "coached_practice"}
    payload.update({"flow_version": "staged_v1", "preset": "quick"} if staged else {"rounds_per_skill": 1})
    response = client.post("/session/start", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    sid = response.json()["session_id"]
    if staged:
        _answer(client, headers, sid, 1)
        activate(client, headers, sid, 2)
    return sid


def _answer(client, headers, sid, number):
    response = client.post("/session/answer", headers=headers, json={
        "session_id": sid, "round": number, "answer_text": ANSWER,
    })
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("staged", [True, False], ids=["staged", "legacy"])
def test_same_template_core_is_unscored_only_in_staged(staged_sql_env, monkeypatch, staged):
    db = staged_sql_env["db"]
    _, headers = _create_user_headers(db)
    _install_questions(monkeypatch, _question(), _question())
    client = TestClient(app)
    sid = _start(client, headers, staged=staged)
    number = 2 if staged else 1
    response = _answer(client, headers, sid, number)
    stored = db["sessions"].find_one({"session_id": sid})
    core = next(r for r in stored["rounds"] if r["round"] == number)
    if staged:
        assert core["final_score"] is None
        assert core["scoring_breakdown"]["unscored_reason"] == "no_reference_unscored"
        assert core["elo_after"] == core["elo_before"]
        candidate = db["candidates"].find_one({"candidate_id": stored["candidate_id"]})
        assert candidate["elo_ratings"]["Python"] == core["elo_before"]
        assert assessment_eligible_scores(stored["rounds"]) == []
        assert response["feedback_deferred"] is True
    else:
        assert isinstance(core["final_score"], (float, int))
        assert core["final_score"] > 0
        assert response["final_score"] == core["final_score"]
        dashboard = client.get(f"/dashboard/{sid}", headers=headers).json()
        assert "content_source" not in dashboard["rounds"][0]


def test_quick_all_template_core_has_no_average_and_honest_coverage(staged_sql_env, monkeypatch):
    db = staged_sql_env["db"]
    _, headers = _create_user_headers(db)
    whitespace_reference = _question()
    whitespace_reference["ideal_answer"] = " \n "
    _install_questions(monkeypatch, _question(), whitespace_reference)
    client = TestClient(app)
    sid = _start(client, headers)
    _answer(client, headers, sid, 2)
    activate(client, headers, sid, 3)
    assert _answer(client, headers, sid, 3)["session_complete"] is True
    dashboard = client.get(f"/dashboard/{sid}", headers=headers).json()
    assert dashboard["averages"]["final_score"] is None
    assert dashboard["overall_readiness_score"] is None
    assert dashboard["coverage"]["scored_rounds"] == 0
    assert {u["round"]: u["reason"] for u in dashboard["coverage"]["unscored_rounds"]} == {
        1: "warm_up_unscored", 2: "no_reference_unscored", 3: "no_reference_unscored",
    }
    assert [r["content_source"] for r in dashboard["rounds"][1:]] == ["template", "template"]


def test_mixed_core_average_uses_only_referenced_rounds(staged_sql_env, monkeypatch):
    db = staged_sql_env["db"]
    _, headers = _create_user_headers(db)
    _install_questions(monkeypatch, _question(referenced=True), _question())
    client = TestClient(app)
    sid = _start(client, headers)
    _answer(client, headers, sid, 2)
    activate(client, headers, sid, 3)
    _answer(client, headers, sid, 3)
    stored = db["sessions"].find_one({"session_id": sid})
    referenced, generic = stored["rounds"][1:]
    assert referenced["final_score"] is not None
    assert generic["final_score"] is None
    assert generic["elo_after"] == generic["elo_before"]
    assert assessment_eligible_scores(stored["rounds"]) == [referenced["final_score"]]
    dashboard = client.get(f"/dashboard/{sid}", headers=headers).json()
    assert dashboard["averages"]["final_score"] == referenced["final_score"]
    assert dashboard["overall_readiness_score"] == referenced["final_score"]
    assert dashboard["coverage"]["scored_rounds"] == 1
    assert [r["content_source"] for r in dashboard["rounds"][1:]] == ["csv", "template"]


def test_empty_reference_with_required_concepts_remains_measured(staged_sql_env, monkeypatch):
    db = staged_sql_env["db"]
    _, headers = _create_user_headers(db)
    _install_questions(monkeypatch, _question(required=True), _question())
    client = TestClient(app)
    sid = _start(client, headers)
    _answer(client, headers, sid, 2)
    stored = db["sessions"].find_one({"session_id": sid})
    assert stored["rounds"][1]["final_score"] is not None
    assert stored["rounds"][1]["scoring_breakdown"].get("unscored_reason") is None
