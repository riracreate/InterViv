"""--live runs must refuse the in-memory database and name their DB target."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("LLM_LIVE_FETCH", "0")

from backend import config as app_config
from backend.db.sqlalchemy_store import _sessionmaker, get_engine, get_sqlalchemy_database
from modules import bundle_generator, bundle_store, llm_usage, role_skills
from scripts import pregenerate_bundles


def _clear_all_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def guard_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("INTERVIV_ALLOW_LIVE_ON_MEMORY_DB", raising=False)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "true")
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    _clear_all_caches()
    bundle_store.reset_memory_store()
    llm_usage.reset_memory_usage()
    role_skills.reset_role_skill_cache(reset_canonicals=True)
    bundle_generator.set_bundle_llm_override(None)
    role_skills.set_role_skills_llm_override(None)
    yield tmp_path
    bundle_generator.set_bundle_llm_override(None)
    role_skills.set_role_skills_llm_override(None)
    bundle_store.reset_memory_store()
    llm_usage.reset_memory_usage()
    role_skills.reset_role_skill_cache(reset_canonicals=True)
    _clear_all_caches()


def _counting_overrides(calls: dict[str, int]) -> None:
    def role_override(role: str, jd_text: str):
        calls["role"] = calls.get("role", 0) + 1
        return {
            "role_title": role,
            "domain": "Engineering",
            "skills": [{"name": "API Design", "topics": ["Rate Limiting"], "weight": 1.0}],
        }

    def bundle_override(purpose: str, **kwargs: Any):
        calls[purpose] = calls.get(purpose, 0) + 1
        if purpose == "bundle_blind_answer":
            return {
                "content": (
                    "We apply a token bucket with refill rate and return HTTP "
                    "status 429 with Retry-After headers."
                )
            }
        payload = {
            "question": "How should an API enforce rate limits fairly?",
            "reference_answer": (
                "Use a token bucket per client with a steady refill rate; "
                "reject excess requests with HTTP 429 and a Retry-After header."
            ),
            "acceptable_variants": ["Enforce token bucket counters and emit 429 with Retry-After."],
            "keywords": ["rate limiting", "token bucket", "429", "retry-after", "redis"],
            "required_concepts": [
                {
                    "id": "token_bucket",
                    "descriptor": "Token bucket controls burst and average rate",
                    "aliases": ["token bucket"],
                    "expected_propositions": ["token bucket", "refill rate"],
                },
                {
                    "id": "http_429_headers",
                    "descriptor": "Return HTTP 429 with Retry-After header",
                    "aliases": ["retry after"],
                    "expected_propositions": ["status 429", "retry after"],
                },
            ],
            "optional_concepts": [
                {
                    "id": "burst_smoothing",
                    "descriptor": "Burst traffic is smoothed by refilling capacity gradually over time",
                    "aliases": ["burst"],
                    "expected_propositions": ["burst"],
                }
            ],
            "misconceptions": [
                {
                    "id": "local_memory_only",
                    "description": "per-process python dictionaries synchronize global limits across machines",
                    "candidate_patterns": ["in-memory dict shares rate limits across nodes"],
                }
            ],
            "depth_markers": ["burst tolerance", "clock skew", "atomic increment"],
            "rubric_descriptors": {
                "coverage": "Covers algorithm and client backoff signaling.",
                "accuracy": "Avoids claiming process-local state works across nodes.",
                "depth": "Explains atomicity and burst behavior.",
                "clarity": "Clear and structured.",
            },
            "followups": [
                {"prompt": "How does token bucket allow bounded bursts?", "targets_concept": "token_bucket"},
                {"prompt": "What headers help clients back off on 429?", "targets_concept": "http_429_headers"},
            ],
            "calibration_examples": [
                {
                    "answer": "Token bucket refills steadily; excess gets 429 with Retry-After.",
                    "author_level": 3,
                    "expected_band": "Good",
                },
                {
                    "answer": " ".join(["filler"] * 95),
                    "author_level": 0,
                    "expected_band": "Poor",
                },
            ],
        }
        return {"content": json.dumps(payload)}

    role_skills.set_role_skills_llm_override(role_override)
    bundle_generator.set_bundle_llm_override(bundle_override)


def test_live_run_refuses_in_memory_database_before_any_llm_call(guard_env: Path) -> None:
    calls: dict[str, int] = {}
    _counting_overrides(calls)

    report = pregenerate_bundles.run_pregeneration(
        roles=["Backend Engineer"], max_bundles=1, allow_live=True, export_yaml=False
    )

    assert report["aborted"] is True
    assert report["abort_reason"] == "in_memory_database"
    assert "DATABASE_URL is unset" in (report["abort_error"] or "")
    assert calls == {}
    assert llm_usage.summarize_usage()["count"] == 0


def test_live_cli_refuses_and_prints_memory_target(
    guard_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = pregenerate_bundles.main(
        ["--roles", "Backend Engineer", "--max-bundles", "1", "--live", "--no-export-yaml"]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "Database: in-memory (DATABASE_URL unset" in out
    assert "ABORTED (in_memory_database)" in out


def test_live_cli_with_sqlite_database_prints_path_and_runs(
    guard_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = guard_env / "pilot.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    _clear_all_caches()

    from backend.db.sqlalchemy_models import Base

    Base.metadata.create_all(get_engine())

    calls: dict[str, int] = {}
    _counting_overrides(calls)

    code = pregenerate_bundles.main(
        [
            "--roles", "Backend Engineer",
            "--max-bundles", "1",
            "--live",
            "--no-export-yaml",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert f"Database: {db_path}" in out
    assert calls.get("bundle_generation", 0) >= 1
    assert db_path.exists()


def test_refuses_protected_db_in_every_mode_absolute_relative_and_symlink(
    guard_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    protected_dir = guard_env / "protected_dir"
    protected_dir.mkdir(parents=True, exist_ok=True)
    protected_db = protected_dir / "protected.sqlite3"
    protected_db.write_bytes(b"original-protected-bytes")
    symlink_db = guard_env / "alias_link.sqlite3"
    symlink_db.symlink_to(protected_db)

    monkeypatch.setattr(pregenerate_bundles, "_PROTECTED_LOCAL_DB_PATH", protected_db)
    monkeypatch.setenv("INTERVIV_ALLOW_LIVE_ON_MEMORY_DB", "1")
    monkeypatch.chdir(guard_env)

    calls: dict[str, int] = {}
    _counting_overrides(calls)

    candidate_urls = [
        f"sqlite:///{protected_db}",
        "sqlite:///protected_dir/protected.sqlite3",
        f"sqlite:///{symlink_db}",
        "sqlite:///alias_link.sqlite3",
    ]

    for url in candidate_urls:
        monkeypatch.setenv("DATABASE_URL", url)
        _clear_all_caches()

        for mode_kwargs in (
            {"dry_run": True},
            {"estimate_only": True},
            {"allow_live": False},
            {"allow_live": True},
        ):
            report = pregenerate_bundles.run_pregeneration(
                roles=["Backend Engineer"],
                max_bundles=1,
                export_yaml=False,
                **mode_kwargs,
            )
            assert report["aborted"] is True
            assert report["abort_reason"] == "protected_local_database"
            assert "Refusing to run" in (report["abort_error"] or "")

        for cli_args in (
            ["--roles", "Backend Engineer", "--max-bundles", "1", "--dry-run", "--no-export-yaml"],
            ["--roles", "Backend Engineer", "--max-bundles", "1", "--estimate", "--no-export-yaml"],
            ["--roles", "Backend Engineer", "--max-bundles", "1", "--no-export-yaml"],
            ["--roles", "Backend Engineer", "--max-bundles", "1", "--live", "--no-export-yaml"],
        ):
            code = pregenerate_bundles.main(cli_args)
            out = capsys.readouterr().out
            assert code == 1
            assert "ABORTED (protected_local_database)" in out

    assert calls == {}
    assert protected_db.read_bytes() == b"original-protected-bytes"

