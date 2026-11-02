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
    args = parser.parse_args()
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30, trust_env=False) as client:
        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        ready = request("GET", "/ready")
        assert ready["checks"]["database"]["persistent"] is True
        if args.after_restart:
            state = json.loads(STATE.read_text())
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
            STATE.parent.mkdir(exist_ok=True)
            fd = os.open(STATE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as handle:
                json.dump(state, handle)
        progress = request("GET", "/dashboard/progress")
        assert any(row["session_id"] == state["session_id"] for row in progress["history"])
        request("GET", f"/dashboard/{state['session_id']}")
        print("PASS: persistent account → login → practice → submission → progress → report" + (" after restart" if args.after_restart else ""))


if __name__ == "__main__":
    main()
