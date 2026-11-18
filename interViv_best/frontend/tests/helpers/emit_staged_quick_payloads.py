"""Real staged Quick payloads for Node contracts; disposable SQLite, no network."""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import urllib.request
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(tempfile.mkdtemp(prefix="interviv-staged-ui-"))
sys.path.insert(0, str(ROOT))
os.environ.update({
    "INTERVIV_DISABLE_DOTENV": "1", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
    "DATABASE_URL": f"sqlite:///{WORK / 'quick.sqlite3'}", "INTERVIV_USE_MEMORY_DB": "false",
    "JWT_SECRET_KEY": "staged-ui-test-secret-with-at-least-32-bytes",
    "LLM_LIVE_FETCH": "0", "JOBS_LIVE_FETCH": "0", "SCORER_VERSION": "v3",
    "STAGED_INLINE_FOLLOW_UPS": "1", "REVIEWED_BUNDLES_ONLY": "false",
    "FOLLOWUP_DECISIONS_AUDIT_PATH": str(WORK / "followups.jsonl"),
    "REJECTED_BUNDLES_AUDIT_PATH": str(WORK / "rejected.jsonl"),
    "DEMOTED_BUNDLES_AUDIT_PATH": str(WORK / "demoted.jsonl"),
    "NEW_CANONICAL_SKILLS_AUDIT_PATH": str(WORK / "canonical.jsonl"),
})
for name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "OLLAMA_API_KEY"):
    os.environ.pop(name, None)

import dotenv
import httpx


def blocked(*args, **kwargs):
    raise AssertionError("Staged UI payload fixtures forbid dotenv and outbound network")


async def blocked_async(*args, **kwargs):
    return blocked()


with ExitStack() as guards:
    for target, name in ((dotenv, "load_dotenv"), (dotenv, "dotenv_values"),
                         (socket, "create_connection"), (urllib.request, "urlopen"),
                         (httpx.HTTPTransport, "handle_request")):
        guards.enter_context(patch.object(target, name, blocked))
    guards.enter_context(patch.object(httpx.AsyncHTTPTransport, "handle_async_request", blocked_async))
    from fastapi.testclient import TestClient
    from backend.auth.security import create_access_token, hash_password
    from backend.db import get_database
    from backend.db.sqlalchemy_store import create_all_for_smoke, get_engine
    from backend.main import app
    from scripts.seed_demo_bundles import seed_demo_bundles

    create_all_for_smoke()
    seed_demo_bundles()
    user_id = "staged-ui-" + uuid4().hex
    now = datetime.now(timezone.utc)
    get_database()["users"].insert_one({
        "id": user_id, "name": "Staged UI fixture", "email": user_id + "@example.com",
        "password_hash": hash_password("FixtureOnly123!"), "created_at": now, "last_active_at": now,
    })
    headers = {"Authorization": "Bearer " + create_access_token(user_id)}
    client = TestClient(app)

    def body(response):
        assert response.status_code == 200, response.text
        return response.json()

    start = body(client.post("/session/start", headers=headers, json={
        "flow_version": "staged_v1", "preset": "quick", "skills": ["Python"],
        "practice_mode": "coached_practice", "allow_optional_follow_ups": True,
    }))
    sid = start["session_id"]
    states = [body(client.get(f"/session/{sid}", headers=headers))]
    operations = []
    for _ in range(12):
        current = states[-1]
        if current["status"] == "completed":
            break
        if current.get("pending_round"):
            rn = current["pending_round"]["round"]
            response = body(client.post(f"/session/{sid}/rounds/{rn}/activate", headers=headers))
            operations.append({"kind": "activateRound", "round": rn, "response": response})
        else:
            active = current["active_round"]
            if active.get("is_follow_up"):
                answer = "During socket reads or disk waits, blocking I/O syscalls release lock so another runnable thread can acquire the interpreter."
            elif active.get("stage") == "warm_up":
                answer = "Python uses dynamic typing and automatic reference counting."
            else:
                answer = "In CPython only one thread executes bytecode at once under the GIL mutex. Generators yield one item at a time and suspend frame state in constant memory instead of building a list."
            response = body(client.post("/session/answer", headers=headers, json={
                "session_id": sid, "round": active["round"], "answer_text": answer,
            }))
            operations.append({"kind": "submitAnswer", "round": active["round"], "response": response})
        states.append(body(client.get(f"/session/{sid}", headers=headers)))
    assert states[-1]["status"] == "completed"
    assert any(r.get("is_follow_up") for r in states[-1]["round_history"])
    print(json.dumps({"start": start, "states": states, "operations": operations}, default=str))
    get_engine().dispose()
