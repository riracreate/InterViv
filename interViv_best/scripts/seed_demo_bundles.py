#!/usr/bin/env python3
"""Seed 3 offline ``Python`` demo fixture bundles for Slice 1 local verification.

Writes strictly to the database configured by ``DATABASE_URL``, refuses the
protected local database (``local-data/interviv-local.sqlite3``) and any
``interviv.db`` file, and marks every bundle's attribution with
``origin="demo_fixture"`` so it can never be mistaken for pilot output.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import get_settings  # noqa: E402
from modules import bundle_store  # noqa: E402
from modules.bundle_store import BundleStoreError  # noqa: E402
from scripts.pregenerate_bundles import (  # noqa: E402
    _protected_local_db_path,
    _resolve_sqlite_db_path,
    protected_local_db_error,
)

DEMO_ORIGIN = "demo_fixture"
DEMO_ACTOR = "demo_fixture:seed_demo_bundles"


def _demo_bundle_docs() -> list[dict[str, Any]]:
    attr = {
        "origin": DEMO_ORIGIN,
        "demo_fixture": True,
        "generated_by_model": None,
        "note": "Offline Slice 1 demo fixture — never treat as live pilot output.",
    }
    rubric = {
        "coverage": "Addresses all required core concepts clearly.",
        "accuracy": "Avoids concurrency or scoping misconceptions.",
        "depth": "Gives concrete mechanism-level explanation.",
        "clarity": "Structured, concise technical explanation.",
    }
    return [
        {
            "bundle_id": "demo.python.01_gil.v1",
            "version": 1,
            "skill": "Python",
            "topic": "Interpreter Mutex",
            "difficulty": "medium",
            "question": (
                "Explain how the CPython Global Interpreter Lock (GIL) affects "
                "CPU-bound threads versus blocking I/O threads."
            ),
            "reference_answer": (
                "In CPython, a mutex ensures only one thread executes Python "
                "bytecode at a time to protect interpreter state and reference "
                "counts. CPU-bound threads serialize on the lock, while blocking "
                "I/O syscalls release the lock so other threads make concurrent progress."
            ),
            "acceptable_variants": [
                "One thread executes bytecode under the GIL while blocking I/O syscalls release it."
            ],
            "keywords": ["gil", "bytecode", "mutex", "blocking io", "syscalls"],
            "required_concepts": [
                {
                    "id": "bytecode_mutex",
                    "descriptor": "Only one thread executes bytecode at a time under the mutex",
                    "aliases": ["bytecode lock", "gil mutex", "single thread bytecode"],
                    "expected_propositions": [
                        "one thread executes bytecode",
                        "mutex serializes bytecode",
                    ],
                },
                {
                    "id": "io_release",
                    "descriptor": "Blocking I/O syscalls release the lock so other threads run",
                    "aliases": ["blocking io", "releases lock", "io syscalls"],
                    "expected_propositions": [
                        "blocking io releases lock",
                        "syscalls release lock",
                    ],
                },
            ],
            "optional_concepts": [
                {
                    "id": "multiprocessing_parallelism",
                    "descriptor": "Use multiprocessing processes for multi-core CPU parallelism",
                    "aliases": ["multiprocessing", "separate processes"],
                    "expected_propositions": ["multiprocessing uses separate processes"],
                }
            ],
            "misconceptions": [
                {
                    "id": "parallel_cpu_threads",
                    "description": "python threads run cpu bytecode simultaneously across cores",
                    "candidate_patterns": [
                        "python threads run bytecode simultaneously across multiple cores"
                    ],
                }
            ],
            "depth_markers": ["reference counts", "syscalls release lock"],
            "rubric_descriptors": rubric,
            "followups": [
                {
                    "prompt": (
                        "Follow-up: Why can blocking I/O threads still overlap cleanly "
                        "even while CPython enforces the GIL?"
                    ),
                    "targets_concept": "io_release",
                },
                {
                    "prompt": (
                        "Follow-up: What runtime state does the CPython bytecode mutex protect?"
                    ),
                    "targets_concept": "bytecode_mutex",
                },
            ],
            "calibration_examples": [
                {
                    "answer": (
                        "Only one thread executes bytecode at once under the GIL mutex, "
                        "while blocking I/O syscalls release the lock cleanly for concurrency."
                    ),
                    "author_level": 3,
                    "expected_band": "Good",
                },
                {
                    "answer": (
                        "Threads always bypass all interpreter synchronization rules and run "
                        "arbitrary Python code in parallel without any runtime lock, "
                        "reference count protection, kernel scheduling overhead, memory "
                        "barriers, process isolation, socket waits, or interpreter checks."
                    ),
                    "author_level": 0,
                    "expected_band": "Poor",
                },
            ],
            "source": "human_authored",
            "author": DEMO_ACTOR,
            "attribution": attr,
        },
        {
            "bundle_id": "demo.python.02_generators.v1",
            "version": 1,
            "skill": "Python",
            "topic": "Generators and Lazy Evaluation",
            "difficulty": "medium",
            "question": (
                "How do Python generators produce values lazily compared to building "
                "a list, and when do they save memory?"
            ),
            "reference_answer": (
                "A generator function yields one item at a time and suspends its "
                "execution frame between next calls instead of materializing every "
                "element in memory upfront, giving O(1) memory per yielded value."
            ),
            "acceptable_variants": [
                "Generators suspend state on yield and produce values one at a time lazily."
            ],
            "keywords": ["yield", "lazy", "generator", "frame", "memory"],
            "required_concepts": [
                {
                    "id": "yield_suspend",
                    "descriptor": "Yield suspends and resumes execution state across iterations",
                    "aliases": ["yield keyword", "suspends frame"],
                    "expected_propositions": ["yield suspends state"],
                },
                {
                    "id": "lazy_memory",
                    "descriptor": "Values are computed lazily one at a time without full list allocation",
                    "aliases": ["one item at a time", "constant memory"],
                    "expected_propositions": ["computes values lazily"],
                },
            ],
            "optional_concepts": [],
            "misconceptions": [],
            "depth_markers": ["execution frame", "single-pass iterator"],
            "rubric_descriptors": rubric,
            "followups": [
                {
                    "prompt": "Follow-up: How does Python preserve local variables between yield steps?",
                    "targets_concept": "yield_suspend",
                },
                {
                    "prompt": "Follow-up: Why does streaming with a generator use less memory than a list?",
                    "targets_concept": "lazy_memory",
                },
            ],
            "calibration_examples": [
                {
                    "answer": (
                        "Yield suspends the generator frame and resumes on the next step, "
                        "so values compute lazily one at a time in constant memory."
                    ),
                    "author_level": 3,
                    "expected_band": "Good",
                },
                {
                    "answer": (
                        "Generators eagerly compute every output into a hidden array on call "
                        "before returning results, using identical peak RAM, copying buffers "
                        "on every iteration, and allocating full list frames repeatedly across "
                        "nested loops and network calls."
                    ),
                    "author_level": 0,
                    "expected_band": "Poor",
                },
            ],
            "source": "human_authored",
            "author": DEMO_ACTOR,
            "attribution": attr,
        },
        {
            "bundle_id": "demo.python.03_closures.v1",
            "version": 1,
            "skill": "Python",
            "topic": "Closures and Late Binding",
            "difficulty": "easy",
            "question": (
                "What causes late-binding bugs in Python loop closures, and how do "
                "default arguments fix them?"
            ),
            "reference_answer": (
                "Python closures look up free variables from the enclosing scope when "
                "called rather than when defined, so loop lambdas share the final loop "
                "value unless a default argument binds the current value at definition time."
            ),
            "acceptable_variants": [
                "Closures resolve enclosing variables lazily at call time; default arguments bind early."
            ],
            "keywords": ["closure", "late binding", "enclosing scope", "default argument"],
            "required_concepts": [
                {
                    "id": "late_lookup",
                    "descriptor": "Free variables in a closure resolve at call time, not definition time",
                    "aliases": ["late binding", "resolved when called"],
                    "expected_propositions": ["resolves variable at call time"],
                },
                {
                    "id": "default_bind",
                    "descriptor": "Default parameter values capture the current iteration value at definition",
                    "aliases": ["default argument", "early bind"],
                    "expected_propositions": ["default parameter captures value"],
                },
            ],
            "optional_concepts": [],
            "misconceptions": [],
            "depth_markers": ["cell object", "__closure__"],
            "rubric_descriptors": rubric,
            "followups": [
                {
                    "prompt": "Follow-up: When does Python resolve free variables inside a nested function?",
                    "targets_concept": "late_lookup",
                },
                {
                    "prompt": "Follow-up: How does binding a default argument change capture timing?",
                    "targets_concept": "default_bind",
                },
            ],
            "calibration_examples": [
                {
                    "answer": (
                        "A closure resolves free variables at call time from the shared "
                        "cell, while a default argument captures each iteration value early."
                    ),
                    "author_level": 3,
                    "expected_band": "Good",
                },
                {
                    "answer": (
                        "Loop closures snapshot every local variable by value as raw bytecode "
                        "constants on creation and never reference enclosing scope cells, making "
                        "default parameters purely syntactic sugar for static loop allocation."
                    ),
                    "author_level": 0,
                    "expected_band": "Poor",
                },
            ],
            "source": "human_authored",
            "author": DEMO_ACTOR,
            "attribution": attr,
        },
    ]


def seed_db_guard_error(database_url: str | None) -> str | None:
    """Refuse unset/memory DBs, protected local DB, and any ``interviv.db``."""
    raw = str(database_url or "").strip()
    if not raw:
        return (
            "Refusing to run: DATABASE_URL is unset or empty. Point DATABASE_URL "
            "to a copy SQLite file (e.g. sqlite:////tmp/interviv-copy.sqlite3)."
        )
    if raw.endswith(":memory:") or ":memory:" in raw:
        return "Refusing to run against in-memory SQLite (:memory:)."

    # Respect pregenerate_bundles' protected-DB check on active settings.
    protected_msg = protected_local_db_error()
    if protected_msg:
        return protected_msg

    resolved = _resolve_sqlite_db_path(raw)
    if resolved is not None:
        protected = _protected_local_db_path()
        if resolved == protected or (
            resolved.exists() and protected.exists() and os.path.samefile(resolved, protected)
        ):
            return (
                f"Refusing to run: DATABASE_URL resolves to the protected local "
                f"database ({protected})."
            )
        if resolved.name.lower() == "interviv.db":
            return (
                f"Refusing to run: target path {resolved} is named interviv.db. "
                "Use an explicit copy file (for example sqlite:////tmp/interviv-copy.sqlite3)."
            )
        repo_interviv_db = (ROOT / "interviv.db").expanduser().resolve(strict=False)
        if resolved == repo_interviv_db or (
            resolved.exists()
            and repo_interviv_db.exists()
            and os.path.samefile(resolved, repo_interviv_db)
        ):
            return (
                f"Refusing to run: DATABASE_URL resolves to {repo_interviv_db}. "
                "Use a separate copy SQLite file."
            )
    return None


def seed_demo_bundles() -> list[dict[str, Any]]:
    """Import and auto-check the 3 ``Python`` ``demo_fixture`` bundles idempotently."""
    settings = get_settings()
    err = seed_db_guard_error(settings.database_url)
    if err:
        raise RuntimeError(err)

    results: list[dict[str, Any]] = []
    for doc in _demo_bundle_docs():
        imported = bundle_store.import_bundle(
            doc,
            actor_id=DEMO_ACTOR,
            initial_status="generated",
            audit_reason="Offline Slice 1 demo fixture import",
        )
        version_doc = imported["version"]
        if version_doc["status"] == "generated":
            version_doc = bundle_store.transition_automated_check(
                version_doc["bundle_id"],
                int(version_doc["version"]),
                to_status="auto_checked",
                reason="demo_fixture offline auto_checked seed",
                check_meta={"origin": DEMO_ORIGIN, "demo_fixture": True},
            )
        elif version_doc["status"] not in {"auto_checked", "reviewed"}:
            raise BundleStoreError(
                "invalid",
                f"Unexpected existing status {version_doc['status']!r} on {version_doc['bundle_id']}",
            )
        results.append(
            {
                "bundle_id": version_doc["bundle_id"],
                "version": int(version_doc["version"]),
                "difficulty": version_doc["difficulty"],
                "topic": (version_doc.get("content_json") or {}).get("topic"),
                "status": version_doc["status"],
                "import_result": imported["result"],
                "origin": (version_doc.get("attribution_json") or {}).get("origin"),
            }
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed 3 Python demo_fixture bundles into DATABASE_URL (refuses protected DB and interviv.db)."
    )
    parser.parse_args(argv)
    try:
        rows = seed_demo_bundles()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for item in rows:
        print(
            f"Seeded {item['bundle_id']} v{item['version']} "
            f"[{item['difficulty']} / {item['topic']}] "
            f"status={item['status']} origin={item['origin']} ({item['import_result']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
