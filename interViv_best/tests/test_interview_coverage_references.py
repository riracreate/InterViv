"""Interview skill coverage and reference-answer completeness.

Observed: a resume-driven Interview block with five confirmed skills asked
ten questions that were all recorded against the first skill. Eight of them
were generic templates about one other skill, with no reference answer to
score against or to show in the report.

Covered here: the per-question skill plan; the content rules on every served
question (bounded retries, a fallback that is about the requested skill,
otherwise "content unavailable"); one eligibility rule for the pre-start
check and for serving; the planned scope shown before a start, including
Jobs and Coach launches; and the launcher switch that lets the provider
configured in .env generate questions and nothing else.
"""

from __future__ import annotations

import json
import os
import urllib.request
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
from modules import question_content  # noqa: E402
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
    every test here states its own. A provider request that a test does not
    stub is blocked by the suite's network guard and fails that test.
    """
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "csv")
    monkeypatch.setenv("QUESTION_REQUIRE_LLM", "false")
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("QUESTION_LLM_RETRY_BASE_SECONDS", "0")
    monkeypatch.setenv("QUESTION_LLM_RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.delenv("LLM_LIVE_CONSUMERS", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    qr._IN_MEMORY_CACHE.clear()
    yield
    qr._IN_MEMORY_CACHE.clear()


def _generation(index: int, *, complete: bool = True) -> str:
    body: dict[str, object] = {"question": f"Generated question {index}: how would you apply it?"}
    if complete:
        body["ideal_answer"] = (
            "A strong answer states the goal first, then walks through the "
            "steps that were taken in order. It names one trade-off that was "
            "accepted and explains how the result was checked afterwards."
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


# ── The content rules: a scored question carries what it is scored against ───

REFERENCE = (
    "An index keeps the indexed keys sorted in a separate structure, so a "
    "lookup walks a few pages instead of scanning every row of the table."
)
KEYWORDS = ["index", "sorted keys", "lookup", "full table scan"]


def test_content_rules_need_a_substantial_reference_and_keywords() -> None:
    valid = {"question": "How does an index speed up a query?", "ideal_answer": REFERENCE,
             "ideal_keywords": KEYWORDS}
    assert question_content.reference_issues(valid) == []
    # The same rule whatever the source, and whichever key names are used.
    for source in ("llm", "llm-adaptive", "csv", "structured_fallback"):
        assert qr.reference_gap({**valid, "source": source}) is None
    assert qr.reference_gap({"question": "Q?", "reference_answer": REFERENCE,
                             "keywords": "index | sorted keys | lookup | scan"}) is None

    assert qr.reference_gap({**valid, "ideal_answer": " "}) == "no reference answer"
    # Present is not enough: a one-line reference is too weak to score against.
    assert qr.reference_gap({**valid, "ideal_answer": "An index makes lookups faster."}) == (
        f"reference answer under {question_content.MIN_REFERENCE_WORDS} words")
    assert qr.reference_gap({**valid, "ideal_keywords": ""}) == "no keywords"
    assert qr.reference_gap({**valid, "ideal_keywords": []}) == "no keywords"
    assert qr.reference_gap({**valid, "ideal_keywords": ["index", "lookup"]}) == (
        f"fewer than {question_content.MIN_KEYWORDS} keywords")
    # Repeats and punctuation are not keywords the scorer can match.
    assert qr.reference_gap({**valid, "ideal_keywords": "index, Index, INDEX, lookup, --, ??"}) == (
        f"fewer than {question_content.MIN_KEYWORDS} keywords")
    assert question_content.reference_issues({**valid, "ideal_answer": "", "ideal_keywords": ""}) == [
        "no reference answer", "no keywords"]
    assert qr.reference_gap({**valid, "question": " "}) == "no question text"
    assert qr.reference_gap(None) == "no question text"


def test_the_bank_audit_and_serving_share_one_set_of_content_rules() -> None:
    from scripts import question_audit

    assert question_audit.MIN_KEYWORDS is question_content.MIN_KEYWORDS
    assert question_audit.MIN_REFERENCE_WORDS is question_content.MIN_REFERENCE_WORDS
    assert question_audit.VALID_DIFFICULTIES is question_content.VALID_DIFFICULTIES
    assert question_audit._split_multi is question_content.split_keywords
    report = question_audit.audit_question_bank(
        question_audit.PROJECT_ROOT / "data" / "fallback_question_bank.csv")
    assert report.schema_ok and not report.errors
    assert not [issue for issue in report.warnings
                if "keywords" in issue.message or "Ideal answer" in issue.message]


def test_every_offline_question_passes_the_content_rules() -> None:
    pool = qr.offline_pool()
    assert pool
    for entry in pool:
        assert question_content.reference_issues(entry) == [], entry["question"]
        assert entry["source"] in OFFLINE_SOURCES
        assert entry["skill"] and entry["sub_domain"]
    questions = [entry["question"].lower() for entry in pool]
    assert len(questions) == len(set(questions))
    # Legacy bank rows that have a reference but no keywords are not served.
    assert "what is kubernetes?" not in questions
    assert "what is ci/cd?" not in questions


# ── relevance: a skill is covered only by questions about it ────────────────

def _entry(skill: str, sub_domain: str, question: str, **extra) -> dict:
    return {"question": question, "ideal_answer": REFERENCE, "ideal_keywords": list(KEYWORDS),
            "source": "csv", "company": "", "role": "", "skill": skill, "sub_domain": sub_domain,
            "topic": sub_domain, "difficulty": "medium", "question_type": "conceptual",
            "followups": [], **extra}


def _questions(skill: str) -> list[str]:
    return [entry["question"] for entry in qr.eligible_offline_questions(skill)]


def test_a_tool_is_covered_only_by_questions_tagged_with_it() -> None:
    """CI/CD used to be 'covered' by any System Design question, Kubernetes included."""
    for skill, tag in (("CI/CD", "ci/cd"), ("cicd", "ci/cd"), ("Docker", "docker"),
                       ("Kubernetes", "kubernetes"), ("AWS", "aws"), ("Azure", "azure")):
        eligible = qr.eligible_offline_questions(skill)
        assert eligible, skill
        assert {entry["sub_domain"] for entry in eligible} == {tag}, skill
    assert not set(_questions("CI/CD")) & set(_questions("Kubernetes"))
    assert not set(_questions("CI/CD")) & set(_questions("Docker"))
    # The alias table files these under System Design / devops or cloud, but
    # no question is tagged with them: nothing offline is about them.
    for skill in ("Git", "GitHub Actions", "Terraform", "k8s", "GCP", "DynamoDB", "NLP", "Agile"):
        assert qr.eligible_offline_questions(skill) == [], skill


def test_a_skill_named_in_the_question_text_is_not_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    kubernetes = _entry("System Design", "kubernetes",
                        "How would a Kubernetes rollout fit into a CI/CD pipeline?")
    devops = _entry("System Design", "devops", "What is Kubernetes and why do CI/CD teams use it?")
    tagged = _entry("System Design", "ci/cd", "When does a pipeline stage block a release?")
    monkeypatch.setattr(qr, "_OFFLINE_POOL", [kubernetes, devops, tagged])

    # Both other questions say "CI/CD"; only the one tagged ci/cd is about it.
    assert _questions("CI/CD") == [tagged["question"]]
    assert _questions("Kubernetes") == [kubernetes["question"]]
    served = qr.fallback_question("CI/CD", "devops", "medium", [])
    assert served["question"] == tagged["question"]
    with pytest.raises(qr.QuestionContentUnavailable, match="'CI/CD' that has not been asked already"):
        qr.fallback_question("CI/CD", "devops", "medium", [tagged["question"]])


def test_whole_skill_aliases_follow_the_alias_table_and_names_match_exactly() -> None:
    assert _questions("Operating Systems") == _questions("OS") != []
    assert _questions("Computer Networks") == _questions("CN") != []
    # SQL is served from DBMS, except the questions tagged as another named
    # part of it (MongoDB, Cassandra).
    sql, dbms = _questions("SQL"), _questions("DBMS")
    assert set(sql) < set(dbms)
    assert {entry["sub_domain"] for entry in qr.eligible_offline_questions("DBMS")
            if entry["question"] not in sql} == {"mongodb", "cassandra"}
    assert _questions("MongoDB") and set(_questions("MongoDB")) <= set(dbms) - set(sql)
    # Java gets its own questions first, then OOP's. JavaScript's are not
    # Java's because the name starts the same way.
    java = qr.eligible_offline_questions("Java")
    own = [entry for entry in java if entry["skill"] == "Java"]
    assert own and java[:len(own)] == own
    assert {entry["skill"] for entry in java} == {"Java", "OOP"}
    assert not set(_questions("Java")) & set(_questions("JavaScript"))
    assert qr.eligible_offline_questions("R") == []
    # A broad skill keeps its general questions ahead of the named parts.
    design = qr.eligible_offline_questions("System Design")
    named = [qr._named_part(entry) for entry in design]
    assert True in named and named == sorted(named)


@pytest.mark.parametrize("skill", ["HR", "SQL", "Java", "CI/CD", "System Design", "Python", "Agile"])
def test_serving_draws_on_exactly_the_questions_the_pre_start_check_counts(skill: str) -> None:
    """One eligibility rule: never a template, never another skill's question."""
    eligible = _questions(skill)
    assert qr.offline_reference_count(skill) == len(eligible)
    asked: list[str] = []
    while True:
        try:
            row = qr.fallback_question(skill, None, "medium", asked)
        except qr.QuestionContentUnavailable as exc:
            assert f"'{skill}'" in str(exc)
            break
        assert row["source"] in OFFLINE_SOURCES
        assert qr.reference_gap(row) is None
        assert row["question"] in eligible and row["question"] not in asked
        asked.append(row["question"])
        assert len(asked) <= len(eligible)
    assert sorted(asked) == sorted(eligible)


def test_planned_counts_cannot_run_short_whichever_questions_other_skills_take() -> None:
    def scope(*planned: tuple[str, int]) -> dict[str, dict]:
        items = qr.scope_sources([{"skill": skill, "questions": n} for skill, n in planned])
        return {item["skill"]: item for item in items}

    oop, java = len(_questions("OOP")), len(_questions("Java"))
    assert oop == 7 and java == 12
    fits = scope(("OOP", 3), ("Java", 3))
    assert fits["OOP"]["available"] and fits["Java"]["available"]
    assert fits["OOP"]["shared_with"] == ["Java"] and fits["OOP"]["offline_needed"] == 6

    # Each fits alone, but Java may be given four of OOP's seven questions.
    short = scope(("OOP", 4), ("Java", 4))
    assert short["OOP"]["available"] is False
    assert (short["OOP"]["offline_questions"], short["OOP"]["offline_needed"]) == (7, 8)
    assert short["Java"]["available"] is True
    assert scope(("OOP", 4))["OOP"]["available"] is True

    # A skill planned in two blocks is counted once, for both.
    twice = qr.scope_sources([{"skill": "DBMS", "questions": 5}, {"skill": "DBMS", "questions": 5}])
    assert [item["planned_total"] for item in twice] == [10, 10]
    assert [item["available"] for item in twice] == [False, False]
    assert scope(("SQL", 3))["SQL"]["served_as"] == "DBMS"
    assert scope(("Java", 3))["Java"]["served_as"] is None


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


def test_a_generation_with_thin_reference_material_is_not_served(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fields that are merely filled in do not make a scorable question."""
    thin = json.dumps({
        "question": "What is a sprint?",
        "ideal_answer": "A sprint is a short, fixed period of work.",
        "ideal_keywords": ["sprint", "iteration"],
    })
    prompts = _live(monkeypatch, lambda n: thin)
    with pytest.raises(qr.QuestionContentUnavailable) as raised:
        qr.generate_question("Agile", None, "medium", [])
    assert len(prompts) == qr.MAX_GENERATION_ATTEMPTS
    assert f"reference answer under {question_content.MIN_REFERENCE_WORDS} words" in str(raised.value)

    # With bank content for the skill, the valid bank question is served.
    row = qr.generate_question("DBMS", None, "medium", [])
    assert row["source"] in OFFLINE_SOURCES and qr.reference_gap(row) is None


def test_fallback_after_a_failed_generation_is_about_the_confirmed_skill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _live(monkeypatch, lambda n: None)
    row = qr.generate_question("CI/CD", None, "medium", [])
    assert row["source"] in OFFLINE_SOURCES
    assert row["sub_domain"] == "ci/cd"
    assert row["question"] in _questions("CI/CD")
    # Nothing offline is about Terraform, although the alias table files it
    # under the same bank skill and sub-domain as CI/CD.
    with pytest.raises(qr.QuestionContentUnavailable, match="'Terraform'"):
        qr.generate_question("Terraform", None, "medium", [])


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
        "skill": "Agile", "questions": 3, "planned_total": 3, "served_as": None,
        "offline_questions": 0, "offline_needed": 3, "shared_with": [],
        "source": "bank", "available": False,
    }]
    # Nothing offline is about Agile: the advice is to remove it or generate
    # live, not to lower the count.
    no_content = ("No offline questions for 'Agile' (3 planned): remove it, or use live "
                  "question generation where it is configured.")
    assert no_content in block["reason"]
    assert "lower the question count" not in block["reason"]

    start = client.post("/session/start", headers=headers, json=body)
    assert start.status_code == 422, start.text
    assert no_content in start.json()["detail"]
    assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None


def test_the_observed_five_skill_plan_is_reported_short_not_filled_from_other_skills() -> None:
    """Offline there is one question each about AWS, Azure, CI/CD and Docker
    and none about Agile. Two each used to be 'covered' by whatever System
    Design questions came next."""
    client = TestClient(app)
    user = _make_user("cov-observed")
    headers = _headers(user)
    body = {"blocks": [_interview(["AWS", "Agile", "Azure", "CI/CD", "Docker"], 10)]}

    availability = client.post("/session/availability", headers=headers, json=body)
    assert availability.json()["available"] is False
    scope = availability.json()["blocks"][0]["planned_scope"]
    assert [(item["skill"], item["questions"], item["offline_questions"], item["available"])
            for item in scope["skills"]] == [
        ("AWS", 2, 1, False), ("Agile", 2, 0, False), ("Azure", 2, 1, False),
        ("CI/CD", 2, 1, False), ("Docker", 2, 1, False),
    ]
    start = client.post("/session/start", headers=headers, json=body)
    assert start.status_code == 422, start.text
    detail = start.json()["detail"]
    # Two problems, each with its own remedy.
    assert ("No offline questions for 'Agile' (2 planned): remove it, or use live question "
            "generation where it is configured.") in detail
    assert ("Fewer than planned for 'AWS' (2 planned, 1 available), 'Azure' (2 planned, 1 available), "
            "'CI/CD' (2 planned, 1 available), 'Docker' (2 planned, 1 available): lower the question "
            "count or remove them.") in detail
    assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None


def test_each_round_asks_a_question_about_its_own_skill() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("cov-relevance"))
    skills = ["AWS", "Azure", "CI/CD", "Docker"]
    body = {"blocks": [_interview(skills, 4)]}
    assert client.post("/session/availability", headers=headers, json=body).json()["available"] is True

    start = client.post("/session/start", headers=headers, json=body)
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    number = 1
    while True:
        answered = _answer(client, headers, session_id, number)
        if answered["session_complete"]:
            break
        assert answered["progression_blocked"] is False
        number = answered["next_round"]
        activate(client, headers, session_id, number)

    stored = _stored(session_id)
    assert [r["skill"] for r in stored["rounds"]] == skills
    for round_doc, skill in zip(stored["rounds"], skills):
        context = _context(round_doc)
        # The served question's own tag names the round's skill.
        assert qr._name_key(context["sub_domain"]) == qr._name_key(skill)
        assert round_doc["question"] in _questions(skill)
        assert qr.reference_gap(context) is None
    assert "kubernetes" not in " ".join(r["question"] for r in stored["rounds"]).lower()


def test_offline_questions_are_counted_across_the_whole_plan() -> None:
    client = TestClient(app)
    user = _make_user("cov-pool")
    headers = _headers(user)
    # Java is served from its own questions and from OOP's seven.
    body = {"blocks": [_interview(["OOP"], 4), _interview(["Java"], 4)]}

    availability = client.post("/session/availability", headers=headers, json=body)
    assert availability.status_code == 200, availability.text
    assert availability.json()["available"] is False
    oop, java = availability.json()["blocks"]
    assert oop["available"] is False and java["available"] is True
    insufficient = ("Fewer than planned for 'OOP' (4 planned, 7 available, shared with Java): "
                    "lower the question count or remove it.")
    assert insufficient in oop["reason"]
    assert "live question generation" not in oop["reason"]

    start = client.post("/session/start", headers=headers, json=body)
    assert start.status_code == 422, start.text
    assert insufficient in start.json()["detail"]
    assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None

    fits = client.post("/session/availability", headers=headers, json={
        "blocks": [_interview(["OOP"], 3), _interview(["Java"], 3)],
    })
    assert fits.json()["available"] is True

    # One skill planned in two blocks is one demand on its questions.
    twice = client.post("/session/start", headers=headers, json={
        "blocks": [_interview(["DBMS"], 5), _interview(["DBMS"], 5)],
    })
    assert twice.status_code == 422, twice.text
    assert "Fewer than planned for 'DBMS' (10 planned, 9 available)" in twice.json()["detail"]


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
        "skill": "Agile", "questions": 3, "planned_total": 3, "served_as": None,
        "offline_questions": 0, "offline_needed": 3, "shared_with": [],
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
    assert ("No scored question with a reference answer and keywords is available "
            "for skill 'Agile'") in start.json()["detail"]
    assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None


# ── Jobs and Coach launches: the plan is built on the server ────────────────

def test_job_practice_draft_shows_its_planned_scope_before_confirming() -> None:
    from modules.jobs_explorer import load_fixture_jobs, reset_memory_store, set_fetch_override

    reset_memory_store()
    set_fetch_override(lambda **kwargs: load_fixture_jobs()[:3])
    try:
        client = TestClient(app)
        user = _make_user("cov-jobs-scope")
        headers = _headers(user)
        jobs = {job["title"]: job["id"]
                for job in client.get("/jobs?q=intern&where=Pune&page=1", headers=headers).json()["jobs"]}

        # Five skills, three free-text questions: the limit is kept and the
        # two skills that get none are named.
        full_stack = client.post(f"/jobs/{jobs['SDE Intern — Full Stack']}/prepare", headers=headers)
        assert full_stack.status_code == 200, full_stack.text
        draft = full_stack.json()
        assert draft["proposed_skills"] == ["JavaScript", "Node.js", "OOP", "React", "System Design"]
        scope = draft["planned_scope"]
        assert scope["questions"] == 3
        assert [(item["skill"], item["questions"], item["available"]) for item in scope["skills"]] == [
            ("JavaScript", 1, True), ("Node.js", 1, True), ("OOP", 1, True)]
        assert scope["not_covered"] == ["React", "System Design"]

        # A proposed skill with nothing scored offline is flagged in the
        # draft, and confirming it is refused with the reason.
        backend = client.post(f"/jobs/{jobs['Software Development Intern — Backend']}/prepare", headers=headers)
        scope = backend.json()["planned_scope"]
        assert [(item["skill"], item["available"]) for item in scope["skills"]] == [
            ("DBMS", True), ("DSA", True), ("Django", False)]
        job_id = jobs["Software Development Intern — Backend"]
        refused = client.post(f"/jobs/{job_id}/practice", headers=headers, json={
            "confirm": True, "blocks": backend.json()["proposed_blocks"]})
        assert refused.status_code == 422, refused.text
        assert "No offline questions for 'Django' (1 planned)" in refused.json()["detail"]
        assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None

        # With the skills edited, the server plans from the confirmed list:
        # still at most three free-text questions, one per skill.
        started = client.post(f"/jobs/{job_id}/practice", headers=headers, json={
            "confirm": True, "skills": ["DBMS", "DSA", "Python", "OOP"]})
        assert started.status_code == 200, started.text
        body = started.json()
        assert body["round_plan"] == ["technical_short_answer"] * 3 + ["mcq"]
        assert [(item["skill"], item["questions"]) for item in body["planned_scope"]["skills"]] == [
            ("DBMS", 1), ("DSA", 1), ("Python", 1)]
        assert body["planned_scope"]["not_covered"] == ["OOP"]
        stored = _stored(body["session_id"])
        assert [spec["skills"] for spec in stored["expanded_plan"][:3]] == [["DBMS"], ["DSA"], ["Python"]]
    finally:
        set_fetch_override(None)
        reset_memory_store()


def test_job_practice_preview_is_rebuilt_for_edited_skills_and_the_start_uses_it() -> None:
    """Editing the skills in the confirm dialog must change what is previewed
    and what is started, together."""
    from modules.jobs_explorer import load_fixture_jobs, reset_memory_store, set_fetch_override

    reset_memory_store()
    set_fetch_override(lambda **kwargs: load_fixture_jobs()[:3])
    try:
        client = TestClient(app)
        user = _make_user("cov-jobs-refresh")
        headers = _headers(user)
        jobs = {job["title"]: job["id"]
                for job in client.get("/jobs?q=intern&where=Pune&page=1", headers=headers).json()["jobs"]}
        job_id = jobs["Software Development Intern — Backend"]
        proposed = client.post(f"/jobs/{job_id}/prepare", headers=headers).json()
        assert [block["skills"] for block in proposed["proposed_blocks"][:3]] == [["DBMS"], ["DSA"], ["Django"]]

        # The candidate replaces Django. The draft is rebuilt for that list:
        # blocks and scope both describe the edited skills.
        edited = ["DBMS", "DSA", "Python", "OOP"]
        refreshed = client.post(f"/jobs/{job_id}/prepare", headers=headers, json={"skills": edited})
        assert refreshed.status_code == 200, refreshed.text
        draft = refreshed.json()
        assert draft["proposed_skills"] == edited
        assert [block["skills"] for block in draft["proposed_blocks"][:3]] == [["DBMS"], ["DSA"], ["Python"]]
        assert [(item["skill"], item["questions"], item["available"])
                for item in draft["planned_scope"]["skills"]] == [
            ("DBMS", 1, True), ("DSA", 1, True), ("Python", 1, True)]
        assert draft["planned_scope"]["not_covered"] == ["OOP"]

        # The typed list is cleaned, never reinterpreted or padded.
        cleaned = client.post(f"/jobs/{job_id}/prepare", headers=headers,
                              json={"skills": ["  DBMS ", "dbms", "", "DSA"]}).json()
        assert cleaned["proposed_skills"] == ["DBMS", "DSA"]
        empty = client.post(f"/jobs/{job_id}/prepare", headers=headers, json={"skills": []}).json()
        assert empty["proposed_skills"] == [] and empty["proposed_blocks"] == []
        assert empty["planned_scope"] is None
        # A skill with nothing offline is still flagged after an edit.
        flagged = client.post(f"/jobs/{job_id}/prepare", headers=headers,
                              json={"skills": ["DBMS", "Agile"]}).json()
        assert [(item["skill"], item["available"]) for item in flagged["planned_scope"]["skills"]] == [
            ("DBMS", True), ("Agile", False)]

        # Blocks left over from the first proposal are not the edited plan.
        stale = client.post(f"/jobs/{job_id}/practice", headers=headers, json={
            "confirm": True, "skills": edited, "blocks": proposed["proposed_blocks"]})
        assert stale.status_code == 422, stale.text
        assert "does not match the confirmed skills (not in the list: Django)" in stale.json()["detail"]
        assert get_database()["sessions"].find_one({"user_id": user["id"]}) is None

        # The refreshed draft is what starts, and it passes the same checks.
        started = client.post(f"/jobs/{job_id}/practice", headers=headers, json={
            "confirm": True, "skills": draft["proposed_skills"], "blocks": draft["proposed_blocks"]})
        assert started.status_code == 200, started.text
        body = started.json()
        assert body["planned_scope"] == draft["planned_scope"]
        stored = _stored(body["session_id"])
        assert [spec["skills"] for spec in stored["expanded_plan"][:3]] == [["DBMS"], ["DSA"], ["Python"]]
        assert _context(stored["rounds"][0])["skill"] == "DBMS"
    finally:
        set_fetch_override(None)
        reset_memory_store()


def test_coach_plan_shows_the_planned_scope_of_its_practice_launch() -> None:
    client = TestClient(app)
    headers = _headers(_make_user("cov-coach-scope"))
    plan = client.post("/coach/plan", headers=headers, json={
        "goal_text": "Backend intern role: I need DBMS, OOP, DSA, operating systems and Python.",
        "include_dashboard": False,
    })
    assert plan.status_code == 200, plan.text
    preview = plan.json()["practice_preview"]
    assert len(preview["skills"]) > 3
    assert preview["round_plan"][:3] == ["technical_short_answer"] * 3
    scope = preview["planned_scope"]
    assert scope["questions"] == 3
    assert [item["skill"] for item in scope["skills"]] == preview["skills"][:3]
    assert all(item["questions"] == 1 and item["available"] for item in scope["skills"])
    assert scope["not_covered"] == preview["skills"][3:]

    started = client.post("/coach/start-practice", headers=headers, json={
        "skills": preview["skills"], "round_plan": preview["round_plan"]})
    assert started.status_code == 200, started.text
    assert started.json()["planned_scope"]["not_covered"] == scope["not_covered"]
    stored = _stored(started.json()["session_id"])
    assert [spec["skills"] for spec in stored["expanded_plan"][:3]] == [[s] for s in preview["skills"][:3]]


# ── The live gate: question generation is one consumer of it ────────────────

def test_the_live_gate_can_be_limited_to_question_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    from modules import guidance_coach
    from modules.llm_outbound_gate import (
        llm_consumer_enabled,
        question_llm_outbound_allowed,
        question_source_health,
    )

    monkeypatch.setenv("QUESTION_GENERATION_MODE", "llm_csv_fallback")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    assert [llm_consumer_enabled(c) for c in ("questions", "coach", "narration")] == [False] * 3

    # Open and unrestricted, as before the consumer list existed.
    monkeypatch.setenv("LLM_LIVE_FETCH", "1")
    assert [llm_consumer_enabled(c) for c in ("questions", "coach", "narration")] == [True] * 3
    assert question_source_health()["llm_live_consumers"] == "all"

    # What ``run_local.py --live-questions`` sets.
    monkeypatch.setenv("LLM_LIVE_CONSUMERS", "questions")
    assert [llm_consumer_enabled(c) for c in ("questions", "coach", "narration")] == [True, False, False]
    assert question_llm_outbound_allowed() is True
    assert qr.live_generation_available() is True
    assert question_source_health()["llm_live_consumers"] == ["questions"]
    # The coach has a key and an open gate, and still sends nothing: the
    # autouse network guard would fail this test on any request.
    assert guidance_coach._llm_extract_phrases("I know Python, SQL and some React.") is None

    monkeypatch.setenv("LLM_LIVE_CONSUMERS", "coach")
    assert question_llm_outbound_allowed() is False
    assert qr.live_generation_available() is False


def test_live_questions_leave_narration_rendered_at_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    from modules import narration_provider
    from modules.narration_jobs import narration_job_id

    _live(monkeypatch, _generation)
    monkeypatch.setenv("LLM_LIVE_CONSUMERS", "questions")
    # Even with a provider installed, narration is not a consumer of this gate.
    fake = narration_provider.FakeNarrationProvider()
    monkeypatch.setattr(narration_provider, "_PROVIDER", fake)
    client = TestClient(app)
    headers = _headers(_make_user("cov-narration"))
    start = client.post("/session/start", headers=headers, json={"blocks": [_interview(["Agile"], 1)]})
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    assert _context(_stored(session_id)["rounds"][0])["source"] in qr.GENERATED_SOURCES

    answered = _answer(client, headers, session_id, 1)
    assert answered["narration_status"] == "skipped"
    assert fake.calls == 0
    job = get_database()["narration_jobs"].find_one({"id": narration_job_id(session_id, 1)})
    assert job["artifact"]["source"] == "rules_feedback"
    assert job["artifact"]["metadata"]["validation"] == "generation_disabled"


# ── The launcher ─────────────────────────────────────────────────────────────

def test_local_launcher_generates_questions_only_when_asked(tmp_path, monkeypatch) -> None:
    from scripts.run_local import _runtime_environment

    # A key in .env (or the shell) is not consent to dial the provider.
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("LLM_LIVE_FETCH", "1")
    monkeypatch.setenv("LLM_LIVE_CONSUMERS", "coach,narration")  # stale shell value
    off = _runtime_environment(tmp_path, executor_on=False, live_jobs=False)
    assert (off["LLM_LIVE_FETCH"], off["QUESTION_GENERATION_MODE"]) == ("0", "csv")
    assert off["LLM_LIVE_CONSUMERS"] == ""

    on = _runtime_environment(tmp_path, executor_on=False, live_jobs=False, live_questions=True)
    assert (on["LLM_LIVE_FETCH"], on["QUESTION_GENERATION_MODE"]) == ("1", "llm_csv_fallback")
    # Questions only: the guidance coach and narration do not get the gate.
    assert on["LLM_LIVE_CONSUMERS"] == "questions"
    assert on["QUESTION_REQUIRE_LLM"] == "false"
    assert on["JOBS_LIVE_FETCH"] == "0"


# ── The suite itself: offline, whatever .env holds ───────────────────────────

def test_the_project_dotenv_is_not_loaded_under_tests(tmp_path, monkeypatch) -> None:
    from backend.runtime_env import dotenv_enabled, load_project_dotenv

    (tmp_path / ".env").write_text("INTERVIV_DOTENV_PROBE=from-dotenv\nLLM_LIVE_FETCH=1\n")
    monkeypatch.delenv("INTERVIV_DOTENV_PROBE", raising=False)
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")

    # conftest sets the switch before the backend is imported.
    assert os.environ["INTERVIV_SKIP_DOTENV"] == "1" and dotenv_enabled() is False
    load_project_dotenv(tmp_path)
    assert "INTERVIV_DOTENV_PROBE" not in os.environ
    assert os.environ["LLM_LIVE_FETCH"] == "0"
    for credential in ("OPENAI_API_KEY", "ADZUNA_APP_ID", "ADZUNA_APP_KEY"):
        assert os.environ[credential] == ""

    # Outside the suite the file is read, without overriding the environment.
    monkeypatch.setenv("INTERVIV_SKIP_DOTENV", "0")
    assert dotenv_enabled() is True
    try:
        load_project_dotenv(tmp_path)
        assert os.environ["INTERVIV_DOTENV_PROBE"] == "from-dotenv"
        assert os.environ["LLM_LIVE_FETCH"] == "0"
    finally:
        os.environ.pop("INTERVIV_DOTENV_PROBE", None)


def test_a_test_cannot_reach_the_network(no_external_network) -> None:
    import socket

    with pytest.raises(ConnectionRefusedError, match="tests are offline"):
        socket.create_connection(("192.0.2.10", 443), timeout=1)
    with pytest.raises(OSError, match="tests are offline"):
        urllib.request.urlopen("https://openrouter.ai/api/v1/chat/completions", timeout=1)
    assert set(no_external_network) == {"192.0.2.10", "openrouter.ai"}
    # Loopback stays reachable (local executor, opt-in Postgres).
    assert socket.getaddrinfo("127.0.0.1", 80)
    # This test tried on purpose; clear the record so its teardown passes.
    no_external_network.clear()
