"""Phase A: owned, candidate-safe Home/Progress summaries and resume decisions."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.auth.security import create_access_token
from backend.db import get_database
from backend.main import app
from modules.skill_graph import StudentSkillGraph


def make_user(target=False):
    uid = str(uuid4())
    get_database()["users"].insert_one({"id": uid, "name": "Phase A Test", "email": f"{uid}@example.test", "password_hash": "test-only-not-a-password", "target_role_id": "tcs_swe" if target else None})
    return uid, {"Authorization": f"Bearer {create_access_token(uid)}"}


def add_session(uid, *, kind="mcq", score=None, deadline=20, status="active", round_status="in_progress"):
    sid = str(uuid4())
    now = datetime.now(timezone.utc)
    get_database()["sessions"].insert_one({
        "session_id": sid, "candidate_id": str(uuid4()), "user_id": uid,
        "skill": "DBMS", "skills": ["DBMS"], "status": status,
        "created_at": now, "total_rounds": 1,
        "private_secret": "NEVER-PUBLIC",
        "rounds": [{"round": 1, "round_type": kind, "status": round_status, "final_score": score,
                    "question": "private question", "answer_text": "private candidate answer",
                    "question_context": {"correct_option_ids": ["secret"], "explanation": "NEVER-PUBLIC"},
                    "artifact_json": {"hidden_cases": ["NEVER-PUBLIC"]},
                    "expires_at": now + timedelta(minutes=deadline) if deadline is not None else None}],
    })
    return sid


def test_progress_requires_authentication():
    response = TestClient(app).get("/dashboard/progress")
    assert response.status_code == 401


def test_new_user_has_no_invented_scores_or_resume():
    _, headers = make_user()
    response = TestClient(app).get("/dashboard/progress", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["readiness"] is None
    assert data["history"] == []
    assert data["scored_session_count"] == 0
    assert data["resumable_session"] is None


def test_history_is_owned_and_zero_is_a_measured_score():
    uid, headers = make_user()
    other, _ = make_user()
    mine = add_session(uid, score=0, status="completed", round_status="submitted")
    add_session(other, score=100, status="completed", round_status="submitted")
    response = TestClient(app).get("/dashboard/progress", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert [row["session_id"] for row in data["history"]] == [mine]
    assert data["history"][0]["average_score"] == 0
    assert data["scored_session_count"] == 1
    assert data["resumable_session"] is None
    for private in ("correct_option_ids", "explanation", "hidden_cases", "question_context", "artifact_json", "answer_text", "password_hash", "NEVER-PUBLIC"):
        assert private not in response.text


def test_resume_requires_owned_unsubmitted_supported_round_inside_stored_window():
    uid, headers = make_user()
    other, _ = make_user()
    mine = add_session(uid)
    add_session(other)
    add_session(uid, deadline=-1)
    add_session(uid, deadline=None)
    add_session(uid, kind="coding")
    add_session(uid, status="completed")
    add_session(uid, round_status="finalizing")
    add_session(uid, score=0)
    client = TestClient(app)
    first = client.get("/dashboard/progress", headers=headers).json()["resumable_session"]
    again = client.get("/dashboard/progress", headers=headers).json()["resumable_session"]
    assert first["session_id"] == mine
    assert first == again


def test_legacy_technical_resume_does_not_invent_a_deadline():
    uid, headers = make_user()
    sid = add_session(uid, kind="technical_short_answer", deadline=None)
    row = TestClient(app).get("/dashboard/progress", headers=headers).json()["resumable_session"]
    assert row["session_id"] == sid
    assert row["expires_at"] is None


def test_profile_preferences_do_not_count_as_mastery_but_measured_zero_does():
    uid, headers = make_user(target=True)
    graph = StudentSkillGraph(uid)
    graph.initialize_from_resume(["DBMS"])
    client = TestClient(app)
    before = client.get("/dashboard/progress", headers=headers).json()
    assert before["readiness"] is None
    assert before["target"]["tested_skill_count"] == 0
    graph.update_after_round("DBMS", 0, "easy")
    after = client.get("/dashboard/progress", headers=headers).json()
    assert after["readiness"] == 0
    assert after["target"]["tested_skill_count"] == 1
    assert next(skill for skill in after["skills"] if skill["name"] == "DBMS")["attempts"] == 1


def test_signup_login_practice_completion_updates_progress_without_a_fake_resume():
    client = TestClient(app)
    credentials = {"email": f"phase-a-{uuid4()}@example.test", "password": "LocalPhaseA123"}
    signup = client.post("/auth/signup", json={**credentials, "name": "Journey Test"})
    assert signup.status_code == 200, signup.text
    login = client.post("/auth/login", json=credentials)
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    start = client.post("/session/start", headers=headers, json={"skills": ["DBMS"], "round_type": "mcq", "rounds_per_skill": 1, "round_config": {"count": 1, "duration_minutes": 20}})
    assert start.status_code == 200, start.text
    session_id = start.json()["session_id"]
    active = client.get("/dashboard/progress", headers=headers).json()
    assert active["resumable_session"]["session_id"] == session_id
    question = start.json()["question_context"]["questions"][0]
    submission = client.post("/session/answer", headers=headers, json={"session_id": session_id, "round": 1, "answers": [{"question_id": question["id"], "selected_option_ids": []}]})
    assert submission.status_code == 200, submission.text
    assert submission.json()["session_complete"] is True
    completed = client.get("/dashboard/progress", headers=headers).json()
    assert completed["resumable_session"] is None
    assert completed["scored_session_count"] == 1
    assert completed["history"][0]["average_score"] == 0
    assert client.get(f"/dashboard/{session_id}", headers=headers).status_code == 200
