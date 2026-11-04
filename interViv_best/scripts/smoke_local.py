"""Exercise the running local app, then verify the same data after a restart.

Creates an explicitly named local smoke-test account; never contacts an
external host. Test credentials remain in a private, ignored local file.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "local-data" / "smoke-check.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--after-restart", action="store_true")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000",
                        help="backend to check (loopback only)")
    parser.add_argument("--state-file", type=Path, default=STATE,
                        help="where the smoke account is kept between runs")
    args = parser.parse_args()
    state_file = args.state_file
    if not args.base_url.startswith(("http://127.0.0.1:", "http://localhost:")):
        raise SystemExit("Refusing a non-loopback backend URL.")
    with httpx.Client(base_url=args.base_url, timeout=60, trust_env=False) as client:
        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        ready = request("GET", "/ready")
        assert ready["checks"]["database"]["persistent"] is True
        if args.after_restart:
            state = json.loads(state_file.read_text())
        else:
            state = {"email": f"local-check-{uuid4().hex[:10]}@example.test", "password": secrets.token_urlsafe(32) + "1a"}
            request("POST", "/auth/signup", json={**state, "name": "Local Test"})
        login = request("POST", "/auth/login", json={k: state[k] for k in ("email", "password")})
        client.headers["Authorization"] = "Bearer " + login["access_token"]
        if not args.after_restart:
            session = request("POST", "/session/start", json={
                "skills": ["DBMS"], "round_type": "mcq", "rounds_per_skill": 1,
                "round_config": {"count": 1, "duration_minutes": 20},
            })
            state["session_id"] = session["session_id"]
            question = session["question_context"]["questions"][0]
            result = request("POST", "/session/answer", json={
                "session_id": state["session_id"], "round": 1,
                "answers": [{"question_id": question["id"], "selected_option_ids": []}],
            })
            assert result["session_complete"] is True
            state_file.parent.mkdir(exist_ok=True)
            fd = os.open(state_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as handle:
                json.dump(state, handle)
        progress = request("GET", "/dashboard/progress")
        assert any(row["session_id"] == state["session_id"] for row in progress["history"])
        request("GET", f"/dashboard/{state['session_id']}")
        if not args.after_restart:
            check_round_lifecycle(request)
        print("PASS: persistent account → login → practice → submission → progress → report" + (" after restart" if args.after_restart else ""))


def check_round_lifecycle(request):
    """Two-round session: the next question opens only on activation."""
    session = request("POST", "/session/start", json={"blocks": [
        {"round_type": "mcq", "category": "oa", "skills": ["DBMS"], "count": 1, "duration_minutes": 10},
        {"round_type": "technical_short_answer", "category": "interview", "skills": ["DBMS"], "count": 1},
    ]})
    sid = session["session_id"]
    question = session["question_context"]["questions"][0]
    first = request("POST", "/session/answer", json={
        "session_id": sid, "round": 1,
        "answers": [{"question_id": question["id"], "selected_option_ids": []}],
    })
    assert first["next_round"] == 2 and first["next_round_status"] == "ready", first
    assert first["next_question"] is None
    review = request("GET", f"/session/{sid}")
    assert review["active_round"] is None and review["review_round"] == 1
    assert review["pending_round"]["round"] == 2
    opened = request("POST", f"/session/{sid}/rounds/2/activate")["active_round"]
    again = request("POST", f"/session/{sid}/rounds/2/activate")["active_round"]
    assert opened["started_at"] == again["started_at"], "activation must be idempotent"
    final = request("POST", "/session/answer", json={
        "session_id": sid, "round": 2,
        "answer_text": "An index keeps keys sorted so lookups avoid scanning the whole table.",
    })
    assert final["session_complete"] is True
    print("PASS: submit → review → activate → submit (round lifecycle)")


if __name__ == "__main__":
    main()
