"""Generate the brief's skill and scenario bundles into the demo database.

Content lane: nvidia/nemotron-3.5-super-vl:free
Check lane: inclusionai/ling-3.2-flash:free
No paid calls. Free-cap budget is 50 requests unless the owner confirms the $10 purchase.
"""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import dotenv_values

DEMO = Path.home() / "interviv-demo" / "interviv-demo.sqlite3"
vals = dotenv_values(Path.home() / "Downloads/mega 2 copy/interViv_best/.env") or {}
if not (Path.home() / "Downloads/mega 2 copy/interViv_best/.env").is_file():
    vals = dotenv_values("/Users/praneetsharma/Downloads/mega 2 copy/interViv_best/.env") or {}
for key, value in vals.items():
    if key and value and key not in os.environ and key != "OPENROUTER_FREE_HIGH_LIMIT_CONFIRMED":
        os.environ[key] = value
os.environ["DATABASE_URL"] = "sqlite:///" + str(DEMO.resolve())
os.environ["AI_INTERVIEW_ROUTING_ENABLED"] = "1"
os.environ["LLM_LIVE_FETCH"] = "1"
os.environ["LLM_LIVE_CONSUMERS"] = "questions"
os.environ["INTERVIEW_CONTENT_MODELS"] = "nvidia/nemotron-3.5-super-vl:free"
os.environ["INTERVIEW_CHECK_MODELS"] = "inclusionai/ling-3.2-flash:free"
os.environ["INTERVIEW_ALLOW_SELF_CHECK"] = "false"
os.environ["ALLOW_PAID_CONTENT_FALLBACK"] = "false"
os.environ["OPENROUTER_FREE_HIGH_LIMIT_CONFIRMED"] = "false"
os.environ.setdefault("NEW_CANONICAL_SKILLS_AUDIT_PATH", str(ROOT / "artifacts" / "new_canonical_skills_audit.jsonl"))

from backend.config import get_settings
get_settings.cache_clear()

from modules import bundle_store, interview_llm
from modules.bundle_generator import generate_and_check_bundle
from modules.interview_llm_budget import DispatchDeferred
from modules.role_blueprints import load_blueprints, question_speech_issues, register_unresolved_skills
from scripts.pregenerate_bundles import protected_local_db_error

CELLS = [
    ("SQL", "Joins", "easy", None),
    ("Product Metrics", "Metric definitions", "easy", None),
    ("SQL", "Indexing", "medium", None),
    ("SQL", "Transactions", "medium", None),
    ("SQL", "Query plans", "medium", None),
    ("SQL", "Isolation", "medium", None),
    ("JavaScript", "Event loop", "medium", None),
    ("JavaScript", "Closures", "medium", None),
    ("JavaScript", "Promises", "medium", None),
    ("REST", "Idempotency", "medium", None),
    ("REST", "Pagination", "medium", None),
    ("REST", "Authentication", "medium", None),
    ("Statistics", "Distributions", "medium", None),
    ("Statistics", "Hypothesis testing", "medium", None),
    ("DBMS", "Normalization", "medium", None),
    ("DBMS", "Indexes", "medium", None),
    ("Product Metrics", "Funnels", "medium", None),
    ("Product Metrics", "Guardrail metrics", "medium", None),
    ("Production Debugging", "Latency spike", "medium", "Backend Engineer"),
    ("Production Debugging", "Safe rollback", "medium", "Backend Engineer"),
    ("Disputed Metrics", "Signup gap", "medium", "Data Analyst"),
    ("Data Quality", "Metric drop", "medium", "Data Analyst"),
    ("Feature Tradeoffs", "Constrained capacity", "medium", "Associate Product Manager"),
    ("Feature Tradeoffs", "Phased rollout", "medium", "Associate Product Manager"),
]

SCHEMA_KEYS = ("reference_answer", "acceptable_variants", "required_concepts", "followups", "calibration_examples")
PROMPT_PHRASES = ("1-3 interview", "matching the schema", "json skeleton")


def defects(question: str, reference: str) -> list[str]:
    found = question_speech_issues(question)
    blob = f"{question}\n{reference}".lower()
    for key in SCHEMA_KEYS:
        if key in blob:
            found.append(key)
    for phrase in PROMPT_PHRASES:
        if phrase in blob:
            found.append(phrase)
    sentences = [part.strip().lower() for part in re.split(r"[.!?]+", question) if part.strip()]
    if len(sentences) != len(set(sentences)):
        found.append("repeated sentence")
    return found


def reject(result: dict, reason: str) -> None:
    version = bundle_store.get_version(result["bundle_id"], int(result["version"]))
    bundle_store._transition(
        bundle_store._backend(), version, "rejected", "content_review", reason,
        datetime.now(timezone.utc),
    )


def main() -> int:
    blocked = protected_local_db_error()
    if blocked:
        print("ABORTED", blocked)
        return 1
    registered = register_unresolved_skills(load_blueprints())
    print("REGISTERED", ", ".join(registered))
    print("CELLS", len(CELLS), "MAX_REQUESTS 50")
    with interview_llm.batch_scope("brief-role-content-2026-11-17", max_requests=50):
        for index, (skill, topic, difficulty, role) in enumerate(CELLS, start=1):
            label = f"{index:02d} {skill} | {topic} | {difficulty} | {role or '-'}"
            result = None
            for attempt in range(6):
                try:
                    result = generate_and_check_bundle(
                        skill=skill, topic=topic, difficulty=difficulty, role=role, allow_live=True,
                    )
                    break
                except DispatchDeferred as exc:
                    wait = 5
                    if getattr(exc, "retry_at", None):
                        wait = max(1, min(30, float(exc.retry_at) - time.time()))
                    print(f"{label} WAIT {exc.reason} {wait:.0f}s")
                    time.sleep(wait)
                except Exception as exc:
                    message = str(exc)
                    if any(token in message for token in ("content_pacing", "model_backoff", "upstream", "free_minute")):
                        print(f"{label} WAIT {message.split(':')[-1].strip()[:80]}")
                        time.sleep(6)
                        continue
                    print(f"{label} ERROR {type(exc).__name__}: {exc}")
                    result = None
                    break
            if result is None:
                continue
            status = result.get("status")
            bundle = result.get("bundle") or {}
            content = bundle.get("content_json") or bundle
            question = str(content.get("question") or "")
            reference = str(content.get("reference_answer") or "")
            problems = defects(question, reference)
            if problems and status in {"auto_checked", "generated", "reviewed"}:
                reject(result, "presentation defect: " + ", ".join(problems))
                status = "rejected"
            print(f"{label} STATUS {status} WORDS {len(question.split())} DEFECTS {problems or '-'}")
            print("  Q:", question[:220])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
