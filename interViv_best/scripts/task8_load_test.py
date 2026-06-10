from __future__ import annotations

import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("QUESTION_GENERATION_MODE", "csv")
os.environ.setdefault("QUESTION_REQUIRE_LLM", "false")
os.environ.setdefault("DISABLE_SEMANTIC_SCORING", "true")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402


ANSWER = (
    "I would clarify requirements, choose a suitable data structure, explain "
    "the algorithm, discuss time complexity, and cover an edge case."
)


def run_user(index: int) -> dict[str, object]:
    client = TestClient(app)
    email = f"task8-load-{index}-{uuid4().hex[:8]}@example.com"
    signup = client.post(
        "/auth/signup",
        json={"email": email, "password": "Secret123!", "name": f"Load User {index}"},
    )
    signup.raise_for_status()
    token = signup.json()["access_token"]
    user_id = signup.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    start = client.post(
        "/session/start",
        json={
            "candidate_id": user_id,
            "skills": ["DSA"],
            "rounds_per_skill": 3,
            "sub_domain": "dsa_core",
        },
        headers=headers,
    )
    start.raise_for_status()
    session_id = start.json()["session_id"]

    latencies: list[float] = []
    for round_number in range(1, 4):
        started = time.perf_counter()
        response = client.post(
            "/session/answer",
            json={
                "session_id": session_id,
                "round": round_number,
                "answer_text": ANSWER,
                "word_count": len(ANSWER.split()),
            },
            headers=headers,
        )
        elapsed = time.perf_counter() - started
        if response.status_code >= 400:
            return {
                "user": index,
                "latencies": latencies,
                "errors": [
                    f"round {round_number} status={response.status_code} body={response.text[:500]}"
                ],
            }
        latencies.append(elapsed)
    return {"user": index, "latencies": latencies, "errors": []}


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * p)))
    return ordered[index]


def main() -> int:
    total_users = int(os.getenv("TASK8_LOAD_USERS", "10"))
    errors: list[str] = []
    all_latencies: list[float] = []
    wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=total_users) as pool:
        futures = [pool.submit(run_user, i + 1) for i in range(total_users)]
        for future in as_completed(futures):
            try:
                result = future.result()
                all_latencies.extend(result["latencies"])
                errors.extend(result["errors"])
            except Exception as exc:
                errors.append(str(exc))
    wall_time = time.perf_counter() - wall_start
    p95 = percentile(all_latencies, 0.95)
    payload = {
        "users": total_users,
        "rounds_per_user": 3,
        "answer_calls": len(all_latencies),
        "errors": errors,
        "mean_latency_seconds": round(statistics.mean(all_latencies), 4) if all_latencies else None,
        "p95_latency_seconds": round(p95, 4),
        "wall_time_seconds": round(wall_time, 4),
        "passed": not errors and len(all_latencies) == total_users * 3 and p95 < 3.0,
    }
    print(json.dumps(payload, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
