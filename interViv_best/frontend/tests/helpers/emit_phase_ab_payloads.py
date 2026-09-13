"""Emit real Phase AB payloads for the Node tests.

Runs the API against a migrated disposable SQLite file — the durable store
the Z-F01/Z-F02 browser defects were observed on — and prints fresh and
expired GET /session payloads per category plus two session reports.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORK = Path(tempfile.mkdtemp(prefix="interviv-phase-ab-"))
URL = f"sqlite:///{WORK / 'phase-ab.db'}"
os.environ.update(DATABASE_URL=URL, INTERVIV_USE_MEMORY_DB="false")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

from fastapi.testclient import TestClient  # noqa: E402

from backend.db.sqlalchemy_store import get_engine  # noqa: E402
from backend.main import app  # noqa: E402
from tests.test_phaseE_system_design import _run_alembic  # noqa: E402
from tests.test_phaseY_expiry import (  # noqa: E402
    BLOCKS,
    SUBMITS,
    _force_expiry,
    _headers,
    _make_user,
    _start,
)


def main() -> None:
    _run_alembic(URL, "upgrade", "head")
    client = TestClient(app)
    headers = _headers(_make_user("phaseab-node"))

    def fetch(session_id: str) -> dict:
        return client.get(f"/session/{session_id}", headers=headers).json()

    fresh = {category: fetch(_start(client, headers, category)) for category in BLOCKS}

    expired = {}
    for category in ("ml_primitives", "coding"):
        session_id = _start(client, headers, category)
        _force_expiry(session_id)
        expired[category] = fetch(session_id)

    session_id = _start(client, headers, "coding")
    _force_expiry(session_id)
    submit = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1, **SUBMITS["coding"]})
    assert submit.status_code == 400, submit.text
    report_unscored = client.get(f"/dashboard/{session_id}", headers=headers).json()

    session_id = _start(client, headers, "verbal")
    questions = fetch(session_id)["active_round"]["question_context"]["questions"]
    submit = client.post("/session/answer", headers=headers, json={
        "session_id": session_id, "round": 1,
        "answers": [{"question_id": q["id"], "selected_option_ids": []} for q in questions]})
    assert submit.status_code == 200, submit.text
    report_zero = client.get(f"/dashboard/{session_id}", headers=headers).json()
    assert report_zero["averages"]["final_score"] == 0.0, report_zero["averages"]

    print(json.dumps({
        "durations": {category: block["duration_minutes"] for category, block in BLOCKS.items()},
        "fresh": fresh,
        "expired": expired,
        "report_unscored": report_unscored,
        "report_zero": report_zero,
    }, separators=(",", ":"), default=str))


if __name__ == "__main__":
    try:
        main()
    finally:
        get_engine().dispose()
        shutil.rmtree(WORK, ignore_errors=True)
