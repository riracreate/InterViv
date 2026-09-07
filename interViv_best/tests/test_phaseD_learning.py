"""Phase D: target context, notebook, retry, bookmarks, assistance, honesty.

Evidence rule: every statistic traces to recorded attempts. Coding
attempts produce no scored evidence and appear as unavailable, never
as zeros and never silently omitted. Assisted and unassisted attempts
stay separated. No answer keys, restricted explanations, reference
solutions, hidden tests, or private execution metadata leak.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password
from backend.db import get_database
from backend.db.phase2_content_bank import PHASE2_MCQ_BANK, PHASE2_SQL_BANK
from backend.main import app

PRIVATE_SUBSTRINGS = (
    "correct_option_ids",
    "reference_query",
    "reference_solution",
    "hidden_tests",
    "hidden_stdout",
    "hidden_stderr",
    "mutant",
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _make_user(prefix: str) -> dict[str, str]:
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


@pytest.fixture
def test_user() -> dict[str, str]:
    return _make_user("phased")


@pytest.fixture
def second_user() -> dict[str, str]:
    return _make_user("phased-other")


def _auth(user: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {user['token']}"}


def _start(client: TestClient, user: dict[str, str], body: dict) -> dict:
    resp = client.post("/session/start", json=body, headers=_auth(user))
    assert resp.status_code == 200, resp.text
    return resp.json()


def _start_mcq(client, user, question_ids, skill="DBMS"):
    return _start(client, user, {
        "candidate_id": "",
        "skills": [skill],
        "rounds_per_skill": 1,
        "round_type": "mcq",
        "round_config": {
            "question_ids": question_ids,
            "count": len(question_ids),
            "duration_minutes": 20,
        },
    })


def _options(question: dict) -> list[dict]:
    return list(question.get("options") or question.get("options_json") or [])


def _wrong_option(question: dict) -> str:
    correct = set(question.get("correct_option_ids") or [])
    for option in _options(question):
        if option["id"] not in correct:
            return option["id"]
    raise AssertionError("no wrong option available")


def _right_option(question: dict) -> str:
    return list(question["correct_option_ids"])[0]


def _submit_mcq(client, user, session_id, answers):
    resp = client.post(
        "/session/answer",
        json={"session_id": session_id, "round": 1, "answers": answers},
        headers=_auth(user),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _assert_no_private_material(blob: str) -> None:
    lowered = blob.lower()
    for needle in PRIVATE_SUBSTRINGS:
        assert needle not in lowered, f"leaked: {needle}"


def _seed_candidate(user_id: str, skills: list[str] | None = None) -> str:
    db = get_database()
    candidate_id = str(uuid4())
    db["candidates"].insert_one({
        "candidate_id": candidate_id,
        "user_id": user_id,
        "resume_skills": skills or ["Python", "SQL"],
        "created_at": datetime.now(timezone.utc),
    })
    return candidate_id


# Target context ------------------------------------------------------------


def test_target_context_round_trip_and_mirror(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    assert client.get("/target-context/me", headers=headers).json() == {"target": None}

    resp = client.put(
        "/target-context/me",
        json={"company_id": "tcs", "role_id": "tcs_swe"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    target = resp.json()["target"]
    assert target["company_name"] == "TCS"
    assert target["role_title"] == "Software Engineer"
    assert "DSA" in target["required_skills"]

    # Existing readiness consumers read the users-row mirror. The mirror
    # uses the same slug→db-id conversion as the legacy target endpoint
    # (integer id after a SQL seed, slug in pure memory mode).
    from backend.db.company_seed import role_slug_to_db_id

    user = get_database()["users"].find_one({"id": test_user["id"]})
    assert user["target_role_id"] == (role_slug_to_db_id("tcs_swe") or "tcs_swe")
    progress = client.get("/dashboard/progress", headers=headers)
    assert progress.status_code == 200

    # Partial update preserves; explicit null clears.
    resp = client.put(
        "/target-context/me", json={"jd_text": "Build APIs."}, headers=headers
    )
    assert resp.status_code == 200
    target = resp.json()["target"]
    assert target["role_id"] == "tcs_swe"
    assert target["jd_text"] == "Build APIs."
    assert target["jd_source"] == "paste"

    resp = client.put(
        "/target-context/me", json={"company_id": None, "role_id": None},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["target"]["company_id"] is None
    assert resp.json()["target"]["jd_text"] == "Build APIs."

    assert client.delete("/target-context/me", headers=headers).status_code == 200
    assert client.get("/target-context/me", headers=headers).json() == {"target": None}


def test_target_context_validation(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    assert client.get("/target-context/me").status_code == 401

    resp = client.put("/target-context/me", json={"company_id": "nope"}, headers=headers)
    assert resp.status_code == 404
    resp = client.put(
        "/target-context/me",
        json={"company_id": "tcs", "role_id": "nope"},
        headers=headers,
    )
    assert resp.status_code == 404
    resp = client.put("/target-context/me", json={"role_id": "tcs_swe"}, headers=headers)
    assert resp.status_code == 422
    resp = client.put("/target-context/me", json={"job_id": "nope"}, headers=headers)
    assert resp.status_code == 404
    resp = client.put(
        "/target-context/me", json={"jd_source": "carrier-pigeon"}, headers=headers
    )
    assert resp.status_code == 422
    resp = client.put(
        "/target-context/me", json={"jd_text": "x" * 9000}, headers=headers
    )
    assert resp.status_code == 422
    resp = client.put(
        "/target-context/me", json={"resume_ref": "missing"}, headers=headers
    )
    assert resp.status_code == 404


def test_target_context_job_and_resume_links(
    client: TestClient, test_user: dict[str, str]
) -> None:
    from modules.jobs_explorer import load_fixture_jobs

    headers = _auth(test_user)
    job_id = load_fixture_jobs()[0]["id"]
    candidate_id = _seed_candidate(test_user["id"], ["Python", "SQL"])

    resp = client.put(
        "/target-context/me",
        json={"company_id": "tcs", "role_id": "tcs_swe", "job_id": job_id,
              "resume_ref": candidate_id},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    target = resp.json()["target"]
    assert target["job_title"]
    assert "SQL" in (target["resume_skills"] or [])


def test_target_context_isolated_per_user(
    client: TestClient, test_user: dict[str, str], second_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    client.put(
        "/target-context/me",
        json={"company_id": "tcs", "role_id": "tcs_swe"}, headers=headers
    )
    other = _auth(second_user)
    assert client.get("/target-context/me", headers=other).json() == {"target": None}
    client.put("/target-context/me", json={"jd_text": "Other."}, headers=other)
    mine = client.get("/target-context/me", headers=headers).json()["target"]
    assert mine["role_id"] == "tcs_swe"
    assert mine["jd_text"] is None


def test_legacy_target_patch_syncs_context(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    client.put("/target-context/me", json={"jd_text": "Keep me."}, headers=headers)
    resp = client.patch(
        "/auth/me/target",
        json={"target_company_id": "tcs", "target_role_id": "tcs_swe"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    target = client.get("/target-context/me", headers=headers).json()["target"]
    assert target["company_id"] == "tcs"
    assert target["role_id"] == "tcs_swe"
    assert target["jd_text"] == "Keep me."


def test_preferences_do_not_change_measured_mastery(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    _seed_candidate(test_user["id"], ["Python", "SQL"])
    from modules.skill_graph import StudentSkillGraph

    StudentSkillGraph(test_user["id"]).initialize_from_resume(["Python", "SQL"])
    before_mastery = client.get("/mastery/me", headers=headers).json()["details"]
    before_graph = {
        node["name"]: node["attempts"]
        for node in client.get("/skill-graph/me", headers=headers).json()["skills"]
    }
    before_readiness = client.get("/dashboard/progress", headers=headers).json()["readiness"]

    client.put(
        "/target-context/me",
        json={"company_id": "tcs", "role_id": "tcs_swe"}, headers=headers
    )
    after_mastery = client.get("/mastery/me", headers=headers).json()["details"]
    after_graph = {
        node["name"]: node["attempts"]
        for node in client.get("/skill-graph/me", headers=headers).json()["skills"]
    }
    after_readiness = client.get("/dashboard/progress", headers=headers).json()["readiness"]
    assert after_mastery == before_mastery
    assert after_graph == before_graph
    assert after_readiness == before_readiness

    # A scored round is evidence and DOES register (differs from a preference).
    questions = [q for q in PHASE2_MCQ_BANK if q.get("skill") == "DBMS"][:2]
    started = _start_mcq(client, test_user, [q["id"] for q in questions])
    _submit_mcq(client, test_user, started["session_id"], [
        {"question_id": q["id"], "selected_option_ids": [_wrong_option(q)]}
        for q in questions
    ])
    graph = client.get("/skill-graph/me", headers=headers).json()
    dbms = next(node for node in graph["skills"] if node["name"] == "DBMS")
    assert dbms["attempts"] >= 1


def test_target_does_not_override_explicit_topic(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    client.put(
        "/target-context/me",
        json={"company_id": "tcs", "role_id": "tcs_swe"},
        headers=headers,
    )
    questions = [q for q in PHASE2_MCQ_BANK if q.get("skill") == "OOP"][:2]
    started = _start_mcq(client, test_user, [q["id"] for q in questions], skill="OOP")
    served = started.get("questions") or []
    assert served
    assert all(q.get("skill") == "OOP" for q in served)


def test_empty_notebook_is_absence_not_zeros(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    notebook = client.get("/learning/notebook/me", headers=headers).json()
    assert notebook["entries"] == []
    assert notebook["counts"] is None
    assert notebook["empty_reason"] == "no_scored_attempts"
    assert "0" not in json.dumps(notebook["counts"])


def test_notebook_only_contains_recorded_misses(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    questions = [q for q in PHASE2_MCQ_BANK if q.get("skill") == "DBMS"][:3]
    started = _start_mcq(client, test_user, [q["id"] for q in questions])
    _submit_mcq(client, test_user, started["session_id"], [
        {"question_id": questions[0]["id"], "selected_option_ids": [_wrong_option(questions[0])]},
        {"question_id": questions[1]["id"], "selected_option_ids": [_right_option(questions[1])]},
        {"question_id": questions[2]["id"], "selected_option_ids": [_wrong_option(questions[2])]},
    ])
    notebook = client.get("/learning/notebook/me", headers=headers).json()
    ids = {e["item_id"] for e in notebook["entries"]}
    assert questions[0]["id"] in ids
    assert questions[2]["id"] in ids
    assert questions[1]["id"] not in ids
    assert all(e["kind"] == "mcq_miss" for e in notebook["entries"])
    assert notebook["counts"]["total"] == 2
    assert notebook["counts"]["unassisted"] == 2


def test_retry_sets_draw_only_from_missed_topics(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    empty = client.post("/learning/retry-sets", json={}, headers=headers)
    assert empty.status_code == 409

    dbms = [q for q in PHASE2_MCQ_BANK if q.get("skill") == "DBMS"][:2]
    started = _start_mcq(client, test_user, [q["id"] for q in dbms])
    _submit_mcq(client, test_user, started["session_id"], [
        {"question_id": q["id"], "selected_option_ids": [_wrong_option(q)]}
        for q in dbms
    ])
    created = client.post(
        "/learning/retry-sets",
        json={"name": "DBMS misses", "max_items": 5},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    items = created.json()["retry_set"]["items"]
    assert items
    assert all(i["skill"] == "DBMS" for i in items)
    assert all(i["item_type"] == "mcq" for i in items)
    listed = client.get("/learning/retry-sets/me", headers=headers).json()
    assert listed["retry_sets"][0]["id"] == created.json()["retry_set"]["id"]


def test_assisted_and_unassisted_attempts_stay_separated(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    questions = [q for q in PHASE2_MCQ_BANK if q.get("skill") == "DBMS"][:2]

    assisted_start = _start_mcq(client, test_user, [questions[0]["id"]])
    hint = client.get(
        "/learning/hint",
        params={"item_type": "mcq", "item_id": questions[0]["id"]},
        headers=headers,
    )
    assert hint.status_code == 200, hint.text
    assert "correct_option_ids" not in hint.text
    assert "explanation" not in json.dumps(hint.json().get("hint") or {})
    _submit_mcq(client, test_user, assisted_start["session_id"], [
        {"question_id": questions[0]["id"], "selected_option_ids": [_wrong_option(questions[0])]},
    ])

    unassisted_start = _start_mcq(client, test_user, [questions[1]["id"]])
    unassisted = _submit_mcq(client, test_user, unassisted_start["session_id"], [
        {"question_id": questions[1]["id"], "selected_option_ids": [_wrong_option(questions[1])]},
    ])
    assert unassisted["assisted"] is False

    notebook = client.get("/learning/notebook/me", headers=headers).json()
    by_id = {e["item_id"]: e for e in notebook["entries"]}
    assert by_id[questions[0]["id"]]["assisted"] is True
    assert "hint" in by_id[questions[0]["id"]]["assistance_kinds"]
    assert by_id[questions[1]["id"]]["assisted"] is False

    mastery = client.get("/mastery/me", headers=headers).json()
    split = mastery["assistance"]
    assert split["assisted_rounds"] >= 1
    assert split["unassisted_rounds"] >= 1
    progress = client.get("/dashboard/progress", headers=headers).json()
    assert progress["readiness_assistance"]["assisted_rounds"] >= 1
    assert progress["readiness_assistance"]["unassisted_rounds"] >= 1


def test_hint_metadata_does_not_leak_answers(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    question = next(q for q in PHASE2_MCQ_BANK if q.get("skill") == "DBMS")
    started = _start_mcq(client, test_user, [question["id"]])
    locked = client.get(
        "/learning/explanation",
        params={"item_type": "mcq", "item_id": question["id"]},
        headers=headers,
    )
    assert locked.status_code == 409
    _submit_mcq(client, test_user, started["session_id"], [
        {"question_id": question["id"], "selected_option_ids": [_wrong_option(question)]},
    ])
    hint = client.get(
        "/learning/hint",
        params={"item_type": "mcq", "item_id": question["id"]},
        headers=headers,
    ).json()
    blob = json.dumps(hint)
    _assert_no_private_material(blob)
    assert question["id"] not in (hint.get("hint") or {}).get("guidance", "")
    notebook = client.get("/learning/notebook/me", headers=headers).json()
    _assert_no_private_material(json.dumps(notebook))
    assert all("correct_option_ids" not in e for e in notebook["entries"])


def test_coding_contributes_no_scored_evidence(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    started = client.post("/session/start", json={
        "candidate_id": "",
        "skills": ["DSA"],
        "rounds_per_skill": 1,
        "round_type": "coding",
        "round_config": {"problem_id": "coding_two_sum", "duration_minutes": 30},
    }, headers=headers)
    assert started.status_code == 200, started.text
    session_id = started.json()["session_id"]
    submitted = client.post("/session/answer", json={
        "session_id": session_id,
        "round": 1,
        "answer_text": "def two_sum(nums, target):\n    return []\n",
    }, headers=headers)
    assert submitted.status_code == 503, submitted.text

    notebook = client.get("/learning/notebook/me", headers=headers).json()
    assert notebook["entries"] == []
    assert notebook["empty_reason"] == "no_scored_attempts"
    assert notebook["coverage"]["excluded_coding_rounds"] >= 1
    assert notebook["coverage"]["excluded_coding_reason"]

    status = client.get(
        "/learning/item-status/me",
        params={"item_type": "coding"},
        headers=headers,
    ).json()
    state = status["states"]["coding_two_sum"]
    assert state["state"] == "attempted_unscored"
    assert state["reason"] == "execution_unavailable"
    assert "solved" not in state["state"]

    progress = client.get("/dashboard/progress", headers=headers).json()
    assert progress["coding_coverage"]["unscored_coding_rounds"] >= 1
    assert progress["coding_coverage"]["scored_coding_rounds"] == 0
    coding_rows = [
        row for row in progress["history"]
        if "coding" in (row.get("round_types") or [])
    ]
    assert coding_rows
    assert coding_rows[0]["average_score"] is None
    reasons = {u["reason"] for u in coding_rows[0]["unscored_rounds"]}
    assert "execution_unavailable" in reasons

    report = client.get(f"/dashboard/{session_id}", headers=headers).json()
    assert report["coverage"]["scored_rounds"] == 0
    assert any(u["reason"] == "execution_unavailable" for u in report["coverage"]["unscored_rounds"])
    _assert_no_private_material(json.dumps(report))


def test_ownership_of_learning_surfaces(
    client: TestClient, test_user: dict[str, str], second_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    other = _auth(second_user)
    questions = [q for q in PHASE2_MCQ_BANK if q.get("skill") == "DBMS"][:1]
    started = _start_mcq(client, test_user, [q["id"] for q in questions])
    _submit_mcq(client, test_user, started["session_id"], [
        {"question_id": questions[0]["id"], "selected_option_ids": [_wrong_option(questions[0])]},
    ])
    created = client.post("/learning/retry-sets", json={"max_items": 3}, headers=headers)
    assert created.status_code == 200, created.text
    set_id = created.json()["retry_set"]["id"]
    bookmark = client.put(
        "/learning/bookmarks",
        json={"item_type": "mcq", "item_id": questions[0]["id"]},
        headers=headers,
    )
    assert bookmark.status_code == 200, bookmark.text

    assert client.get("/learning/notebook/me", headers=other).json()["entries"] == []
    assert client.get("/learning/retry-sets/me", headers=other).json()["retry_sets"] == []
    assert client.get("/learning/bookmarks/me", headers=other).json()["bookmarks"] == []
    assert client.get(f"/learning/retry-sets/{set_id}", headers=other).status_code == 404
    assert client.delete(f"/learning/retry-sets/{set_id}", headers=other).status_code == 404
    assert client.post(
        "/learning/assistance",
        json={
            "item_type": "mcq",
            "item_id": questions[0]["id"],
            "kind": "hint",
            "session_id": started["session_id"],
        },
        headers=other,
    ).status_code == 403
    mine = client.get("/learning/retry-sets/me", headers=headers).json()
    assert mine["retry_sets"][0]["id"] == set_id


def test_leakage_scan_across_connected_surfaces(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    candidate_id = _seed_candidate(test_user["id"], ["Python", "SQL"])
    client.put(
        "/target-context/me",
        json={
            "company_id": "tcs",
            "role_id": "tcs_swe",
            "resume_ref": candidate_id,
            "jd_text": "Build APIs in Python.",
        },
        headers=headers,
    )
    questions = [q for q in PHASE2_MCQ_BANK if q.get("skill") == "DBMS"][:2]
    started = _start_mcq(client, test_user, [q["id"] for q in questions])
    submitted = _submit_mcq(client, test_user, started["session_id"], [
        {"question_id": q["id"], "selected_option_ids": [_wrong_option(q)]}
        for q in questions
    ])
    retry = client.post("/learning/retry-sets", json={"max_items": 4}, headers=headers)
    blobs = [
        client.get("/target-context/me", headers=headers).text,
        client.get("/gap-analysis/me/tcs_swe", headers=headers).text,
        client.get("/learning/notebook/me", headers=headers).text,
        retry.text,
        client.get("/learning/retry-sets/me", headers=headers).text,
        client.get("/resources", params={"skill_id": "DBMS"}, headers=headers).text,
        client.get(f"/dashboard/{started['session_id']}", headers=headers).text,
        client.get("/dashboard/progress", headers=headers).text,
        json.dumps(submitted),
    ]
    for blob in blobs:
        _assert_no_private_material(blob)


def test_phase_b_and_c_contracts_still_hold(
    client: TestClient, test_user: dict[str, str]
) -> None:
    headers = _auth(test_user)
    mixed = client.post("/session/start", json={
        "blocks": [
            {"round_type": "mcq", "category": "verbal", "skills": ["Verbal Ability"],
             "count": 2, "duration_minutes": 10},
            {"round_type": "mcq", "category": "oa", "skills": ["DBMS"],
             "count": 2, "duration_minutes": 10},
        ],
    }, headers=headers)
    assert mixed.status_code == 200, mixed.text
    body = mixed.json()
    assert body["block_plan"][0]["category"] == "verbal"
    assert body["questions"]
    assert all(q.get("skill") == "Verbal Ability" for q in body["questions"])
    refresh = client.get(f"/session/{body['session_id']}", headers=headers)
    assert refresh.status_code == 200
    started_ids = [q["id"] for q in (body.get("questions") or body.get("question_context", {}).get("questions") or [])]
    refreshed = refresh.json()
    active = refreshed.get("active_round") or refreshed
    refreshed_ids = [
        q["id"]
        for q in (
            active.get("questions")
            or (active.get("question_context") or {}).get("questions")
            or refreshed.get("questions")
            or []
        )
    ]
    assert started_ids
    assert refreshed_ids == started_ids

    oop = client.post("/session/start", json={
        "blocks": [
            {"round_type": "mcq", "category": "oa", "skills": ["OOP"],
             "count": 15, "duration_minutes": 20},
        ],
    }, headers=headers)
    assert oop.status_code == 422
    assert "found 10" in oop.text and "need 15" in oop.text

    answers = [
        {"question_id": q["id"], "selected_option_ids": [q["options"][0]["id"]]}
        for q in body["questions"]
    ]
    first = client.post("/session/answer", json={
        "session_id": body["session_id"], "round": 1, "answers": answers,
    }, headers=headers)
    assert first.status_code == 200, first.text
    dup = client.post("/session/answer", json={
        "session_id": body["session_id"], "round": 1, "answers": answers,
    }, headers=headers)
    assert dup.status_code == 409

    coding = client.post("/session/start", json={
        "blocks": [
            {"round_type": "coding", "category": "coding", "skills": ["arrays"],
             "count": 1, "duration_minutes": 30, "problem_ids": ["coding_two_sum"]},
        ],
    }, headers=headers)
    assert coding.status_code == 200, coding.text
    unavailable = client.post("/session/answer", json={
        "session_id": coding.json()["session_id"],
        "round": 1,
        "answer_text": "def two_sum(nums, target): pass",
    }, headers=headers)
    assert unavailable.status_code == 503
