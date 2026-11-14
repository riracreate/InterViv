"""Interview skill coverage and reference-answer completeness.

Observed: a resume-driven Interview block with five confirmed skills asked
ten questions that were all recorded against the first skill. Eight of them
were generic templates about one other skill, with no reference answer to
score against or to show in the report.

Covered here: the per-question skill plan, the reference check on every
served question (bounded retries, same-skill bank fallback, otherwise
"content unavailable"), the planned scope shown before the start, and the
launcher switch that lets the provider configured in .env be used at all.
"""

from __future__ import annotations

import json
import os
import urllib.error
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models.blocks import (  # noqa: E402
    distribute_skills,
    expand_blocks,
    interview_scope,
    legacy_to_blocks,
    normalize_blocks,
)
from modules import adaptive_question_selector as aqs  # noqa: E402
from modules import question_runtime as qr  # noqa: E402
from modules.concept_mastery import ConceptMastery  # noqa: E402
from modules.skill_graph import StudentSkillGraph  # noqa: E402
from tests.round_helpers import activate  # noqa: E402

OFFLINE_SOURCES = {"structured_fallback", "csv"}
ANSWER = (
    "It depends on the workload. I would measure first, pick the simplest "
    "option that meets the requirement, and add monitoring so that "
    "regressions are visible."
)


@pytest.fixture(autouse=True)
def offline_question_source(monkeypatch: pytest.MonkeyPatch):
    """The backend as scripts/run_local.py starts it by default.

    Other test modules leave live-generation settings in ``os.environ``, so
    every test here states its own. Any provider request that is not
    stubbed by the test is recorded and fails it.
    """
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "csv")
    monkeypatch.setenv("QUESTION_REQUIRE_LLM", "false")
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("QUESTION_LLM_RETRY_BASE_SECONDS", "0")
    monkeypatch.setenv("QUESTION_LLM_RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.delenv("REDIS_URL", raising=False)
    qr._IN_MEMORY_CACHE.clear()
    dialed: list[object] = []

    def refuse(request, *args, **kwargs):
        dialed.append(request)
        raise urllib.error.URLError("no provider requests in tests")

    monkeypatch.setattr(qr.urllib.request, "urlopen", refuse)
    yield
    qr._IN_MEMORY_CACHE.clear()
    assert not dialed, "a test reached the provider without stubbing it"


def _generation(index: int, *, complete: bool = True) -> str:
    body: dict[str, object] = {"question": f"Generated question {index}: how would you apply it?"}
    if complete:
        body["ideal_answer"] = (
            "A strong answer states the goal, the steps taken, one trade-off "
            "and how the result is checked."
        )
        body["ideal_keywords"] = ["goal", "steps", "trade-off", "feedback", "review"]
    return json.dumps(body)


def _live(monkeypatch: pytest.MonkeyPatch, respond) -> list[str]:
    """Turn live generation on with a stubbed provider.

    ``respond(call_number)`` returns the provider's raw content, or ``None``
    for a failed request. Returns the prompts that were sent.
    """
    monkeypatch.setenv("LLM_LIVE_FETCH", "1")
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "llm_csv_fallback")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    prompts: list[str] = []

    def call(prompt, context=None, *, asked=None):
        prompts.append(prompt)
        return respond(len(prompts))

    monkeypatch.setattr(qr, "call_llm_with_cache_retry", call)
    monkeypatch.setattr(aqs, "_call_llm", call)
    return prompts


def _make_user(prefix: str) -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    now = datetime.now(timezone.utc)
    db["users"].insert_one({
        "id": user_id,
        "email": f"{prefix}-{user_id[:8]}@example.com",
        "name": f"Test {prefix}",
        "password_hash": hash_password("passw0rd123"),
        "created_at": now,
        "last_active_at": now,
    })
    return {"id": user_id, "token": create_access_token(user_id)}


def _headers(user: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def _interview(skills: list[str], count: int) -> dict[str, object]:
    return {"round_type": "technical_short_answer", "category": "interview",
            "skills": list(skills), "count": count}


def _answer(client: TestClient, headers: dict[str, str], session_id: str, number: int) -> dict:
    resp = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": number, "answer_text": ANSWER,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def _stored(session_id: str) -> dict:
    return get_database()["sessions"].find_one({"session_id": session_id})


def _context(round_doc: dict) -> dict:
    return round_doc.get("question_context") or {}


# ── The plan: one confirmed skill per question ───────────────────────────────

def test_questions_are_shared_across_confirmed_skills_in_order() -> None:
    assert distribute_skills(["A", "B", "C"], 5) == ["A", "A", "B", "B", "C"]
    assert distribute_skills(["A", "B", "C"], 3) == ["A", "B", "C"]
    assert distribute_skills(["A", "B"], 10) == ["A"] * 5 + ["B"] * 5
    # An intentional single-skill session keeps every question.
    assert distribute_skills(["A"], 4) == ["A"] * 4
    assert distribute_skills([], 3) == []


def test_skills_beyond_the_question_budget_are_reported_not_dropped_silently() -> None:
    scope = interview_scope({"skills": ["A", "B", "C", "D", "E"], "count": 3})
    assert scope["questions"] == 3
    assert scope["planned"] == [
        {"skill": "A", "questions": 1},
        {"skill": "B", "questions": 1},
        {"skill": "C", "questions": 1},
    ]
    assert scope["not_covered"] == ["D", "E"]
    assert interview_scope({"skills": ["A", "B"], "count": 5})["not_covered"] == []


def test_block_expansion_plans_one_skill_per_question_and_keeps_counts() -> None:
    plan = normalize_blocks([_interview(["AWS", "Agile", "Azure", "CI/CD", "Docker"], 10)])
    expanded = expand_blocks(plan)
    assert [spec["skills"] for spec in expanded] == [
        ["AWS"], ["AWS"], ["Agile"], ["Agile"], ["Azure"], ["Azure"],
        ["CI/CD"], ["CI/CD"], ["Docker"], ["Docker"],
    ]
    assert [spec["block_index"] for spec in expanded] == list(range(1, 11))
    assert {spec["block_total"] for spec in expanded} == {10}
    assert len({spec["block_id"] for spec in expanded}) == 1

    single = expand_blocks(normalize_blocks([_interview(["Agile"], 4)]))
    assert [spec["skills"] for spec in single] == [["Agile"]] * 4

    # The Full Interview launch (skills x rounds per skill) is unchanged.
    legacy = expand_blocks(legacy_to_blocks(skills=["DBMS", "OOP"], rounds_per_skill=2))
    assert [spec["skills"] for spec in legacy] == [["DBMS"], ["DBMS"], ["OOP"], ["OOP"]]


def test_legacy_round_plan_gives_each_free_text_round_its_own_skill() -> None:
    """Jobs and Coach practice launches send skills plus a round plan."""
    plan = legacy_to_blocks(
        skills=["DBMS", "OOP", "DSA"],
        round_plan=["technical_short_answer"] * 3 + ["mcq"],
        round_config={"count": 8, "duration_minutes": 30},
    )
    expanded = expand_blocks(plan)
    assert [spec["round_type"] for spec in expanded] == ["technical_short_answer"] * 3 + ["mcq"]
    assert [spec["skills"] for spec in expanded[:3]] == [["DBMS"], ["OOP"], ["DSA"]]
    assert expanded[3]["skills"] == ["DBMS", "OOP", "DSA"]

    # More rounds than skills: shared in order. Fewer: the first skills.
    more = expand_blocks(legacy_to_blocks(
        skills=["DBMS", "OOP"], round_plan=["technical_short_answer"] * 3))
    assert [spec["skills"] for spec in more] == [["DBMS"], ["DBMS"], ["OOP"]]
    fewer = expand_blocks(legacy_to_blocks(
        skills=["SQL", "React"], round_plan=["technical_short_answer", "mcq"]))
    assert fewer[0]["skills"] == ["SQL"]


# ── The content contract: a scored question carries its reference ────────────

def test_reference_contract() -> None:
    bank_row = {"question": "Q?", "ideal_answer": "A.", "source": "csv"}
    generated = {"question": "Q?", "ideal_answer": "A.", "ideal_keywords": ["k"], "source": "llm"}
    assert qr.reference_gap(bank_row) is None
    assert qr.reference_gap(generated) is None
    assert qr.reference_gap({**generated, "ideal_keywords": ""}) == "no keywords"
    assert qr.reference_gap({**generated, "source": "llm-adaptive", "ideal_keywords": []}) == "no keywords"
    assert qr.reference_gap({"question": "Q?", "ideal_answer": " ", "source": "template"}) == "no reference answer"
    assert qr.reference_gap({"question": " ", "ideal_answer": "A."}) == "no question text"
    assert qr.reference_gap(None) == "no question text"


def test_offline_fallback_serves_references_until_the_pool_is_spent() -> None:
    """Never a template: the pool the start check counts is the pool served."""
    asked: list[str] = []
    while True:
        try:
            row = qr.fallback_question("HR", None, "medium", asked)
        except qr.QuestionContentUnavailable:
            break
        assert row["source"] in OFFLINE_SOURCES
        assert qr.reference_gap(row) is None
        assert row["question"] not in asked
        asked.append(row["question"])
        assert len(asked) <= 500
    assert len(asked) == qr.offline_reference_count("HR") > 0


def test_a_skill_without_bank_content_is_unavailable_offline() -> None:
    assert qr.offline_reference_count("Agile") == 0
    with pytest.raises(qr.QuestionContentUnavailable, match="'Agile'"):
        qr.fallback_question("Agile", None, "medium", [])
    with pytest.raises(qr.QuestionContentUnavailable, match="'Agile'"):
        qr.generate_question("Agile", None, "medium", [])


def test_incomplete_generation_is_retried_once_then_served(monkeypatch: pytest.MonkeyPatch) -> None:
    prompts = _live(monkeypatch, lambda n: _generation(n, complete=n > 1))
    row = qr.generate_question("Agile", None, "medium", [])
    assert len(prompts) == 2
    assert row["source"] == "llm"
    assert row["llm_provider"] == "openrouter"
    assert row["question"].startswith("Generated question 2")
    assert qr.reference_gap(row) is None
    # The question is about the skill the candidate confirmed.
    assert "question for skill 'Agile'" in prompts[0]


def test_generated_question_is_about_the_confirmed_skill_not_its_bank_alias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts = _live(monkeypatch, _generation)
    row = qr.generate_question("AWS", None, "medium", [])
    assert "question for skill 'AWS'" in prompts[0]
    assert "question for skill 'System Design'" not in prompts[0]
    # Stored under the bank skill, as before, so scoring is unchanged.
    assert row["skill"] == "System Design"


def test_repeated_incomplete_generations_fall_back_to_the_same_skills_bank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts = _live(monkeypatch, lambda n: _generation(n, complete=False))
    row = qr.generate_question("DBMS", None, "medium", [])
    assert len(prompts) == qr.MAX_GENERATION_ATTEMPTS
    assert row["source"] in OFFLINE_SOURCES
    assert row["skill"].lower() == "dbms"
    assert qr.reference_gap(row) is None
    assert "no reference answer" in row["llm_fallback_reason"]


def test_incomplete_generation_with_no_bank_content_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts = _live(monkeypatch, lambda n: _generation(n, complete=False))
    with pytest.raises(qr.QuestionContentUnavailable) as raised:
        qr.generate_question("Agile", None, "medium", [])
    assert len(prompts) == qr.MAX_GENERATION_ATTEMPTS
    assert "'Agile'" in str(raised.value)
    assert "no reference answer" in str(raised.value)


def test_rejected_generation_is_dropped_from_the_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Through the real client: a cached incomplete answer must not be re-served."""
    monkeypatch.setenv("LLM_LIVE_FETCH", "1")
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "llm_csv_fallback")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    requests: list[object] = []

    class Response:
        def __init__(self, content: str) -> None:
            self._raw = json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")

        def read(self) -> bytes:
            return self._raw

        def __enter__(self):
            return self

        def __exit__(self, *exc) -> bool:
            return False

    def urlopen(request, *args, **kwargs):
        requests.append(request)
        return Response(_generation(len(requests), complete=len(requests) > 1))

    monkeypatch.setattr(qr.urllib.request, "urlopen", urlopen)

    row = qr.generate_question("Agile", None, "medium", [])
    assert len(requests) == 2
    assert row["source"] == "llm" and row["llm_provider"] == "openrouter"
    assert row["question"].startswith("Generated question 2")
    # The complete generation is what stays cached.
    again = qr.generate_question("Agile", None, "medium", [])
    assert len(requests) == 2
    assert again["question"] == row["question"]


# ── Adaptation stays inside the caller's scope ───────────────────────────────

def test_gap_analysis_target_stays_inside_the_callers_skills() -> None:
    user_id = f"u-scope-{uuid4().hex[:8]}"
    graph = StudentSkillGraph(user_id)
    graph.initialize_from_resume(["Python", "DSA", "DBMS", "OOP", "HR", "System Design"])
    graph.update_after_round("Python", 90, "medium")
    graph.update_after_round("DSA", 20, "medium")

    unscoped = aqs.choose_adaptive_target(
        user_id=user_id, fallback_skill="Python", fallback_difficulty="medium",
        session_skills=["Python", "DSA", "DBMS", "OOP", "HR", "System Design"],
        target_role_id="amazon_sde_intern",
    )
    assert unscoped.skill == "DSA"

    scoped = aqs.choose_adaptive_target(
        user_id=user_id, fallback_skill="Python", fallback_difficulty="medium",
        session_skills=["Python"], target_role_id="amazon_sde_intern",
    )
    assert scoped.skill == "Python"


def test_targeted_generation_without_a_reference_is_not_served(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = f"u-targeted-{uuid4().hex[:8]}"
    ConceptMastery().update_from_round(
        user_id=user_id, skill="DSA",
        covered_concepts=["array"], missing_concepts=["tree"],
    )
    prompts = _live(monkeypatch, lambda n: _generation(n, complete=False))
    question = aqs.select_next_question(
        user_id=user_id, skill="DSA", sub_domain="general",
        difficulty="medium", asked=[],
    )
    assert "ADDITIONAL TARGETING" in prompts[0]
    assert question["adaptive_selected"] is False
    assert question["source"] in OFFLINE_SOURCES
    assert qr.reference_gap(question) is None


# ── Through the routes ───────────────────────────────────────────────────────

def test_multi_skill_interview_covers_every_confirmed_skill_with_references() -> None:
    client = TestClient(app)
    user = _make_user("cov-multi")
    headers = _headers(user)
    # The weakest skill used to pull every later question towards itself.
    graph = StudentSkillGraph(user["id"])
    graph.initialize_from_resume(["DBMS", "OOP", "DSA"])
    graph.update_after_round("DBMS", 90, "medium")
    graph.update_after_round("OOP", 85, "medium")
    graph.update_after_round("DSA", 20, "medium")
    body = {"blocks": [_interview(["DBMS", "OOP", "DSA"], 5)]}
    planned = ["DBMS", "DBMS", "OOP", "OOP", "DSA"]

    availability = client.post("/session/availability", headers=headers, json=body)
    assert availability.status_code == 200, availability.text
    block = availability.json()["blocks"][0]
    assert availability.json()["available"] is True
    assert block["planned_scope"]["questions"] == 5
    assert [(item["skill"], item["questions"], item["source"], item["available"])
            for item in block["planned_scope"]["skills"]] == [
        ("DBMS", 2, "bank", True), ("OOP", 2, "bank", True), ("DSA", 1, "bank", True),
    ]
    assert block["planned_scope"]["not_covered"] == []

    start = client.post("/session/start", headers=headers, json=body)
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    assert start.json()["total_rounds"] == 5
    # Reference material never rides on the candidate's question payload.
    assert "ideal_answer" not in json.dumps(start.json())

    number = 1
    while True:
        answered = _answer(client, headers, session_id, number)
        assert "ideal_answer" not in json.dumps(answered)
        if answered["session_complete"]:
            break
        assert answered["progression_blocked"] is False
        number = answered["next_round"]
        assert answered["next_skill"] == planned[number - 1]
        # Resuming mid-session lands on the planned skill.
        resumed = client.get(f"/session/{session_id}", headers=headers)
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["current_skill"] == planned[number - 1]
        activate(client, headers, session_id, number)

    stored = _stored(session_id)
    assert stored["status"] == "completed"
    assert [spec["skills"] for spec in stored["expanded_plan"]] == [[s] for s in planned]
    assert [r["skill"] for r in stored["rounds"]] == planned
    for round_doc, skill in zip(stored["rounds"], planned):
        context = _context(round_doc)
        assert context["skill"].lower() == skill.lower()
        assert context["source"] in OFFLINE_SOURCES
        assert context["ideal_answer"].strip()
        assert round_doc["final_score"] is not None
    assert len({r["question"] for r in stored["rounds"]}) == 5
    ratings = get_database()["candidates"].find_one(
        {"candidate_id": stored["candidate_id"]})["elo_ratings"]
    assert {"DBMS", "OOP", "DSA"} <= set(ratings)

    # The stored reference is shown in the report once the session is done.
    report = client.get(f"/dashboard/{session_id}", headers=headers)
    assert report.status_code == 200, report.text
    rounds = report.json()["rounds"]
    assert len(rounds) == 5
    for shown, round_doc in zip(rounds, stored["rounds"]):
        assert shown["ideal_answer"] == _context(round_doc)["ideal_answer"]


def test_job_practice_launch_asks_one_free_text_question_per_skill() -> None:
    from modules.jobs_explorer import build_practice_start_payload

    client = TestClient(app)
    headers = _headers(_make_user("cov-jobs"))
    payload = build_practice_start_payload(skills=["DBMS", "OOP", "DSA"])
    assert payload["round_plan"] == ["technical_short_answer"] * 3 + ["mcq"]
    start = client.post("/session/start", headers=headers, json=payload)
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    assert start.json()["total_rounds"] == 4

    for number in (1, 2, 3):
        answered = _answer(client, headers, session_id, number)
        assert answered["progression_blocked"] is False
        activate(client, headers, session_id, number + 1)

    stored = _stored(session_id)
    assert [r["skill"] for r in stored["rounds"][:3]] == ["DBMS", "OOP", "DSA"]
    for round_doc, skill in zip(stored["rounds"][:3], ["DBMS", "OOP", "DSA"]):
        assert _context(round_doc)["skill"].lower() == skill.lower()
        assert _context(round_doc)["ideal_answer"].strip()
    assert stored["rounds"][3]["round_type"] == "mcq"


def test_scope_discloses_skills_the_question_budget_cannot_reach() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("cov-budget"))
    body = {"blocks": [_interview(["DBMS", "OOP", "DSA", "OS", "CN"], 3)]}
    availability = client.post("/session/availability", headers=headers, json=body)
    assert availability.status_code == 200, availability.text
    assert availability.json()["available"] is True
    scope = availability.json()["blocks"][0]["planned_scope"]
    assert scope["questions"] == 3
    assert [item["skill"] for item in scope["skills"]] == ["DBMS", "OOP", "DSA"]
    assert scope["not_covered"] == ["OS", "CN"]


def test_offline_skill_without_scored_content_is_refused_before_any_session() -> None:
    client = TestClient(app)
    user = _make_user("cov-agile-offline")
    headers = _headers(user)
    body = {"blocks": [_interview(["Agile"], 3)]}

    availability = client.post("/session/availability", headers=headers, json=body)
    assert availability.status_code == 200, availability.text
    assert availability.json()["available"] is False
    block = availability.json()["blocks"][0]
    assert block["planned_scope"]["skills"] == [{
        "skill": "Agile", "questions": 3, "served_as": None,
        "offline_questions": 0, "offline_needed": 3,
        "source": "bank", "available": False,
    }]
    assert "'Agile' (3 planned, none in the offline bank)" in block["reason"]

    start = client.post("/session/start", headers=headers, json=body)
    assert start.status_code == 422, start.text
    assert "'Agile' (3 planned, none in the offline bank)" in start.json()["detail"]
    assert "turn on live question generation" in start.json()["detail"]
    assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None

    # The same skill beside covered ones is named, not silently replaced.
    mixed = client.post("/session/start", headers=headers, json={
        "blocks": [_interview(["AWS", "Agile", "Azure", "CI/CD", "Docker"], 10)],
    })
    assert mixed.status_code == 422, mixed.text
    assert "'Agile' (2 planned, none in the offline bank)" in mixed.json()["detail"]
    assert "'AWS'" not in mixed.json()["detail"]


def test_offline_pool_is_counted_across_the_whole_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qr, "offline_reference_count", lambda skill: 3)
    client = TestClient(app)
    user = _make_user("cov-pool")
    headers = _headers(user)
    # AWS and Docker are both served from the System Design bank.
    body = {"blocks": [_interview(["AWS"], 2), _interview(["Docker"], 2)]}

    availability = client.post("/session/availability", headers=headers, json=body)
    assert availability.status_code == 200, availability.text
    assert availability.json()["available"] is False
    for block in availability.json()["blocks"]:
        assert block["available"] is False
        assert "this plan needs 4 from the System Design bank, which has 3" in block["reason"]
        assert block["planned_scope"]["skills"][0]["served_as"] == "System Design"

    start = client.post("/session/start", headers=headers, json=body)
    assert start.status_code == 422, start.text
    assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None

    fits = client.post("/session/availability", headers=headers, json={
        "blocks": [_interview(["AWS"], 2), _interview(["Docker"], 1)],
    })
    assert fits.json()["available"] is True


def test_single_skill_session_with_live_generation_stays_on_that_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts = _live(monkeypatch, _generation)
    client = TestClient(app)
    headers = _headers(_make_user("cov-agile-live"))
    body = {"blocks": [_interview(["Agile"], 3)]}

    availability = client.post("/session/availability", headers=headers, json=body)
    assert availability.json()["available"] is True
    assert availability.json()["blocks"][0]["planned_scope"]["skills"] == [{
        "skill": "Agile", "questions": 3, "served_as": None,
        "offline_questions": 0, "offline_needed": 3,
        "source": "generated", "available": True,
    }]
    assert prompts == [], "the scope preview must not generate anything"

    start = client.post("/session/start", headers=headers, json=body)
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    number = 1
    while True:
        answered = _answer(client, headers, session_id, number)
        if answered["session_complete"]:
            break
        number = answered["next_round"]
        activate(client, headers, session_id, number)

    stored = _stored(session_id)
    assert stored["status"] == "completed"
    assert [r["skill"] for r in stored["rounds"]] == ["Agile"] * 3
    for round_doc in stored["rounds"]:
        context = _context(round_doc)
        assert context["source"] in qr.GENERATED_SOURCES
        assert context["ideal_answer"].strip()
        assert context["ideal_keywords_list"]
    assert len(prompts) == 3
    assert all("question for skill 'Agile'" in prompt for prompt in prompts)


def test_incomplete_generations_mid_session_are_replaced_from_the_same_skills_bank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts = _live(monkeypatch, lambda n: _generation(n, complete=False))
    client = TestClient(app)
    headers = _headers(_make_user("cov-missing-ref"))
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview(["DBMS"], 2)],
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    assert len(prompts) == qr.MAX_GENERATION_ATTEMPTS

    answered = _answer(client, headers, session_id, 1)
    assert answered["progression_blocked"] is False
    activate(client, headers, session_id, 2)
    assert _answer(client, headers, session_id, 2)["session_complete"] is True

    stored = _stored(session_id)
    for round_doc in stored["rounds"]:
        context = _context(round_doc)
        assert round_doc["skill"] == "DBMS"
        assert context["source"] in OFFLINE_SOURCES
        assert context["ideal_answer"].strip()


def test_provider_failure_blocks_the_session_and_continue_resumes_the_planned_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = {"up": True}
    _live(monkeypatch, lambda n: _generation(n) if provider["up"] else None)
    client = TestClient(app)
    headers = _headers(_make_user("cov-provider-down"))
    start = client.post("/session/start", headers=headers, json={
        "blocks": [_interview(["Agile"], 2)],
    })
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]

    # Agile has no offline content, so a failed provider leaves nothing valid
    # to ask. The scored answer is kept and the session waits.
    provider["up"] = False
    answered = _answer(client, headers, session_id, 1)
    assert answered["final_score"] is not None
    assert answered["progression_blocked"] is True
    assert answered["session_status"] == "content_blocked"
    assert answered["session_complete"] is False
    assert answered["next_round"] is None
    assert "'Agile'" in answered["progression_blocked_reason"]
    stored = _stored(session_id)
    assert stored["status"] == "content_blocked"
    assert [r["round"] for r in stored["rounds"]] == [1]

    still_down = client.post(f"/session/{session_id}/continue", headers=headers)
    assert still_down.status_code == 200, still_down.text
    assert still_down.json()["continued"] is False
    assert still_down.json()["progression_blocked"] is True
    assert [r["round"] for r in _stored(session_id)["rounds"]] == [1]

    provider["up"] = True
    resumed = client.post(f"/session/{session_id}/continue", headers=headers)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["continued"] is True
    assert resumed.json()["round"] == 2
    assert resumed.json()["current_skill"] == "Agile"
    assert "ideal_answer" not in json.dumps(resumed.json())

    assert _answer(client, headers, session_id, 2)["session_complete"] is True
    stored = _stored(session_id)
    assert stored["status"] == "completed"
    assert [r["skill"] for r in stored["rounds"]] == ["Agile", "Agile"]
    assert all(_context(r)["ideal_answer"].strip() for r in stored["rounds"])


def test_start_reports_unavailable_content_when_the_provider_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _live(monkeypatch, lambda n: None)
    client = TestClient(app)
    user = _make_user("cov-start-down")
    start = client.post("/session/start", headers=_headers(user), json={
        "blocks": [_interview(["Agile"], 2)],
    })
    assert start.status_code == 503, start.text
    assert "No scored question with a reference answer is available for skill 'Agile'" in start.json()["detail"]
    assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None


# ── The launcher ─────────────────────────────────────────────────────────────

def test_local_launcher_generates_questions_only_when_asked(tmp_path, monkeypatch) -> None:
    from scripts.run_local import _runtime_environment

    # A key in .env (or the shell) is not consent to dial the provider.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("LLM_LIVE_FETCH", "1")
    off = _runtime_environment(tmp_path, executor_on=False, live_jobs=False)
    assert (off["LLM_LIVE_FETCH"], off["QUESTION_GENERATION_MODE"]) == ("0", "csv")

    on = _runtime_environment(tmp_path, executor_on=False, live_jobs=False, live_llm=True)
    assert (on["LLM_LIVE_FETCH"], on["QUESTION_GENERATION_MODE"]) == ("1", "llm_csv_fallback")
    assert on["QUESTION_REQUIRE_LLM"] == "false"
    assert on["JOBS_LIVE_FETCH"] == "0"
