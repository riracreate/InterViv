"""Overhaul Phase 5: curated hints, unrecorded general guidance, editorials."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password  # noqa: E402
from backend.db import get_database  # noqa: E402
from backend.learning_hints import schema_summary, sql_constructs  # noqa: E402
from backend.main import app  # noqa: E402
from backend.db.phase2_content_bank import PHASE2_SQL_BANK  # noqa: E402


def _list_sql_problems():
    return [p for p in PHASE2_SQL_BANK if p.get('reference_query') and p.get('schema_ddl')]

PRIVATE = ("correct_option_ids", "reference_query", "reference_solution", "hidden_tests",
           "checks_json", "mutant", "expected")


def _user(prefix: str):
    user_id = str(uuid4())
    get_database()["users"].insert_one({
        "id": user_id, "email": f"{prefix}-{user_id[:8]}@example.com", "name": prefix,
        "password_hash": hash_password("passw0rd123"),
        "created_at": datetime.now(timezone.utc), "last_active_at": datetime.now(timezone.utc),
    })
    return user_id, {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _events(user_id: str) -> list[dict]:
    return list(get_database()["assistance_events"].find({"user_id": user_id}))


def _seed_round(user_id: str, round_type: str, problem_id: str, *, status: str, score=None,
                session_status: str = "completed") -> str:
    session_id = f"s-{uuid4().hex[:8]}"
    get_database()["sessions"].insert_one({
        "session_id": session_id, "user_id": user_id, "candidate_id": "c", "skills": ["SQL"],
        "status": session_status, "total_rounds": 1, "last_round": 1,
        "rounds": [{"round": 1, "round_type": round_type, "status": status, "final_score": score,
                    "question": "q", "config_json": {"problem_id": problem_id}, "question_context": {}}],
    })
    return session_id


def test_general_guidance_is_never_recorded():
    user_id, headers = _user("guide")
    resp = TestClient(app).get("/learning/guidance", params={"skill": "DBMS"}, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["available"] is True and body["recorded"] is False
    assert body["guidance"]["checklist"]
    unknown = TestClient(app).get("/learning/guidance", params={"skill": "Basket weaving"}, headers=headers).json()
    assert unknown["available"] is False and "dbms" in unknown["known_skills"]
    assert _events(user_id) == []


def test_item_hints_are_curated_safe_and_recorded():
    user_id, headers = _user("hint")
    client = TestClient(app)
    sql = _list_sql_problems()[0]
    sql_hint = client.get("/learning/hint", params={"item_type": "sql", "item_id": sql["id"]}, headers=headers)
    assert sql_hint.status_code == 200, sql_hint.text
    hint = sql_hint.json()["hint"]
    assert {t["name"] for t in hint["tables"]} >= {"customers", "orders"}
    assert hint["relationships"] and hint["constructs"]
    coding = client.get("/learning/hint", params={"item_type": "coding", "item_id": "coding_two_sum"},
                        headers=headers).json()["hint"]
    assert coding["approach"] and coding["constraints"]
    blob = json.dumps([sql_hint.json(), coding]).lower()
    for needle in PRIVATE:
        assert needle not in blob, needle
    kinds = {e.get("kind") for e in _events(user_id)}
    assert kinds == {"hint"}  # question-specific help stays recorded


def test_sql_and_coding_editorials_unlock_after_an_attempt_without_hidden_data():
    user_id, headers = _user("editorial")
    client = TestClient(app)
    sql = _list_sql_problems()[0]
    locked = client.get("/learning/explanation", params={"item_type": "sql", "item_id": sql["id"]},
                        headers=headers)
    assert locked.status_code == 409
    _seed_round(user_id, "sql", sql["id"], status="submitted", score=40.0)
    _seed_round(user_id, "coding", "coding_two_sum", status="submitted", score=60.0)
    sql_ed = client.get("/learning/explanation", params={"item_type": "sql", "item_id": sql["id"]},
                        headers=headers)
    assert sql_ed.status_code == 200, sql_ed.text
    assert sql_ed.json()["editorial"]["solution_query"].lower().startswith("select")
    code_ed = client.get("/learning/explanation", params={"item_type": "coding", "item_id": "coding_two_sum"},
                         headers=headers)
    assert "def two_sum" in code_ed.json()["editorial"]["solution_code"]
    blob = json.dumps([sql_ed.json(), code_ed.json()]).lower()
    for needle in ("hidden_tests", "checks_json", "mutant", "cases"):
        assert needle not in blob, needle
    assert sum(1 for e in _events(user_id) if e.get("kind") == "explanation") == 2


def test_editorial_waits_while_the_item_is_open_in_an_active_session():
    user_id, headers = _user("open")
    sql = _list_sql_problems()[1]
    _seed_round(user_id, "sql", sql["id"], status="submitted", score=55.0)
    _seed_round(user_id, "sql", sql["id"], status="ready", session_status="active")
    resp = TestClient(app).get("/learning/explanation", params={"item_type": "sql", "item_id": sql["id"]},
                               headers=headers)
    assert resp.status_code == 409
    assert "still open" in resp.json()["detail"]


def test_schema_and_construct_helpers():
    ddl = ("CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, total REAL,"
           " FOREIGN KEY (customer_id) REFERENCES customers(id));"
           " CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);")
    summary = schema_summary(ddl)
    assert [t["name"] for t in summary["tables"]] == ["orders", "customers"]
    assert "orders.customer_id → customers.id" in summary["relationships"]
    assert sql_constructs("SELECT c.name, SUM(o.total) FROM orders o JOIN customers c ON c.id = o.customer_id "
                          "GROUP BY c.name HAVING SUM(o.total) > 10 ORDER BY 2 DESC") == [
        "join", "group_by", "having", "aggregate", "order_by"]
