"""Unit tests for WS2 Step 3 (batch robustness) and Step 5 (checker hardening)."""

from __future__ import annotations

import csv
import io
import json
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import dotenv
import httpx
import pytest

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("JOBS_LIVE_FETCH", "0")
os.environ.setdefault("LLM_LIVE_FETCH", "0")

from backend import config as app_config
from backend.db.sqlalchemy_store import _sessionmaker, get_engine, get_sqlalchemy_database
from modules import (
    bundle_generator,
    bundle_jobs,
    bundle_store,
    llm_usage,
    role_skills,
)
from modules.llm_errors import LLMCreditExhaustedError, LLMTruncatedError
from modules.question_bundles import validate_generated_bundle_doc
from scripts import pregenerate_bundles


def _clear_all_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def batch_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # Simulated live runs (fake transport, no real credits) may use memory.
    monkeypatch.setenv("INTERVIV_ALLOW_LIVE_ON_MEMORY_DB", "1")
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "true")
    monkeypatch.setenv("JOBS_LIVE_FETCH", "0")
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-fake-key-do-not-print")
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-haiku-4.5")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("QUESTION_LLM_MODEL", raising=False)
    monkeypatch.delenv("BUNDLE_CHECK_MODEL", raising=False)
    monkeypatch.setenv(
        "REJECTED_BUNDLES_AUDIT_PATH",
        str(tmp_path / "rejected_bundles_audit.jsonl"),
    )
    _clear_all_caches()
    bundle_store.reset_memory_store()
    llm_usage.reset_memory_usage()
    bundle_jobs.reset_memory_bundle_jobs()
    role_skills.reset_role_skill_cache(reset_canonicals=True)
    bundle_generator.set_bundle_llm_override(None)
    role_skills.set_role_skills_llm_override(None)
    yield tmp_path
    bundle_generator.set_bundle_llm_override(None)
    role_skills.set_role_skills_llm_override(None)
    bundle_store.reset_memory_store()
    llm_usage.reset_memory_usage()
    bundle_jobs.reset_memory_bundle_jobs()
    role_skills.reset_role_skill_cache(reset_canonicals=True)
    _clear_all_caches()


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, Any] | str, status: int = 200) -> None:
        self.status = status
        if isinstance(payload, str):
            self._raw = payload.encode("utf-8")
        else:
            self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> "_FakeHTTPResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _http_error(url: str, code: int, body: dict[str, Any] | str) -> urllib.error.HTTPError:
    raw = body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8")
    return urllib.error.HTTPError(url, code, f"HTTP {code}", {}, io.BytesIO(raw))


def _valid_bundle_payload(
    *,
    topic: str = "Rate Limiting",
    three_required: bool = False,
    tight_third: bool = False,
    all_tight: bool = False,
) -> dict[str, Any]:
    req = [
        {
            "id": "token_bucket",
            "descriptor": "Token bucket controls burst and average rate",
            "aliases": ["token bucket", "refill tokens"],
            "expected_propositions": (
                ["nonexistent quantum crystal latch"] if all_tight else ["token bucket refill rate"]
            ),
        },
        {
            "id": "http_429_headers",
            "descriptor": "Return HTTP 429 with Retry-After header",
            "aliases": ["429", "retry after"],
            "expected_propositions": (
                ["nonexistent hyperloop signal"] if all_tight else ["status 429 retry after"]
            ),
        },
    ]
    followups = [
        {"prompt": "How does token bucket allow bounded bursts?", "targets_concept": "token_bucket"},
        {"prompt": "What headers help clients back off on 429?", "targets_concept": "http_429_headers"},
    ]
    if three_required:
        req.append(
            {
                "id": "redis_lua_atomicity",
                "descriptor": "Use Redis Lua script for atomic check-and-decrement",
                "aliases": ["lua script", "atomic redis"],
                "expected_propositions": (
                    ["ephemeral consensus quorum latch"]
                    if (tight_third or all_tight)
                    else ["atomic redis lua script"]
                ),
            }
        )
        followups[1] = {
            "prompt": "Why use an atomic Redis Lua script across workers?",
            "targets_concept": "redis_lua_atomicity",
        }

    return {
        "question": f"How would you implement distributed {topic} across stateless API workers?",
        "reference_answer": (
            "Use a token bucket algorithm backed by centralized state to enforce average "
            "refill rate while allowing bounded bursts. When capacity is exhausted, reject "
            "requests with HTTP status 429 and include a Retry-After header so callers back off."
        ),
        "acceptable_variants": ["Enforce token bucket counters and emit 429 with Retry-After."],
        "keywords": ["rate limiting", "token bucket", "429", "retry-after", "redis"],
        "required_concepts": req,
        "optional_concepts": [
            {
                "id": "sliding_window_log",
                "descriptor": "Sliding window log avoids boundary spikes",
                "aliases": ["sliding window", "window log"],
                "expected_propositions": ["sliding window boundary spikes"],
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
        "followups": followups,
        "calibration_examples": [
            {
                "answer": "Apply a token bucket with steady refill rate and return status 429 with Retry-After.",
                "author_level": 3,
                "expected_band": "Good",
            },
            {
                "answer": (
                    "Rate limiting works automatically when web servers disable TCP keepalive and "
                    "store request timestamps inside local process globals because every worker "
                    "shares local variables across different physical machines over Ethernet. "
                    "Adding more CPU threads eliminates network congestion and prevents abuse "
                    "without tracking client keys, counters, windows, headers, or status codes, "
                    "while database backups synchronize request quotas lazily every midnight "
                    "across regional clusters regardless of incoming traffic bursts or retries."
                ),
                "author_level": 0,
                "expected_band": "Poor",
            },
        ],
    }


def _install_role_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    def _role_override(role: str, jd_text: str):
        if "backend" in role.lower():
            return {
                "role_title": "Backend Engineer",
                "domain": "Engineering",
                "skills": [
                    {
                        "name": "API Design",
                        "topics": ["Rate Limiting", "Idempotency"],
                        "weight": 0.95,
                    }
                ],
            }
        return {
            "role_title": "Data Analyst",
            "domain": "Analytics",
            "skills": [
                {
                    "name": "SQL",
                    "topics": ["Window Functions", "Query Tuning"],
                    "weight": 0.95,
                }
            ],
        }

    role_skills.set_role_skills_llm_override(_role_override)


# ─── Spec 1 & 2: HTTP 402 no-retry, 429 backoff, no 502/503 retry ────────────


def test_post_json_402_not_retried_even_in_flight_budget_exhausted(
    batch_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}
    sleeps: list[float] = []

    def fake_urlopen(req, timeout=0, context=None):
        calls["n"] += 1
        raise _http_error(
            req.full_url,
            402,
            {
                "error": {
                    "message": "in_flight_budget_exhausted: You requested up to 2200 tokens, but can only afford 1049.",
                    "code": 402,
                }
            },
        )

    monkeypatch.setattr(bundle_generator.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(bundle_generator.time, "sleep", sleeps.append)

    with pytest.raises(LLMCreditExhaustedError) as exc_info:
        bundle_generator._post_json(
            "https://openrouter.ai/api/v1/chat/completions",
            body={"model": "test", "messages": []},
            headers={"Authorization": "Bearer secret"},
            timeout_s=10,
            retry_transient=True,
        )

    assert calls["n"] == 1
    assert sleeps == []
    assert exc_info.value.status_code == 402
    assert exc_info.value.credit_info["requested_tokens"] == 2200
    assert exc_info.value.credit_info["affordable_tokens"] == 1049


@pytest.mark.parametrize("status_code", [500, 502, 503])
def test_post_json_5xx_not_retried(
    batch_env, monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    calls = {"n": 0}
    sleeps: list[float] = []

    def fake_urlopen(req, timeout=0, context=None):
        calls["n"] += 1
        raise _http_error(req.full_url, status_code, {"error": "gateway failure"})

    monkeypatch.setattr(bundle_generator.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(bundle_generator.time, "sleep", sleeps.append)

    with pytest.raises(urllib.error.HTTPError) as exc_info:
        bundle_generator._post_json(
            "https://openrouter.ai/api/v1/chat/completions",
            body={"model": "test", "messages": []},
            headers={},
            timeout_s=10,
            retry_transient=True,
        )

    assert exc_info.value.code == status_code
    assert calls["n"] == 1
    assert sleeps == []


def test_post_json_429_exponential_backoff_succeeds_and_exhausts(
    batch_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempts = {"n": 0}
    sleeps: list[float] = []

    def flaky_429(req, timeout=0, context=None):
        attempts["n"] += 1
        if attempts["n"] <= 2:
            raise _http_error(req.full_url, 429, {"error": "rate_limit"})
        return _FakeHTTPResponse({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(bundle_generator.urllib.request, "urlopen", flaky_429)
    monkeypatch.setattr(bundle_generator.time, "sleep", sleeps.append)

    raw = bundle_generator._post_json(
        "https://openrouter.ai/api/v1/chat/completions",
        body={"model": "test", "messages": []},
        headers={},
        timeout_s=10,
        retry_transient=True,
    )
    assert "ok" in raw
    assert attempts["n"] == 3
    assert sleeps == [2, 4]

    # Exhausting all retries raises 429 after exponential backoffs (2, 4, 8, 16)
    attempts["n"] = 0
    sleeps.clear()

    def always_429(req, timeout=0, context=None):
        attempts["n"] += 1
        raise _http_error(req.full_url, 429, {"error": "rate_limit"})

    monkeypatch.setattr(bundle_generator.urllib.request, "urlopen", always_429)
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        bundle_generator._post_json(
            "https://openrouter.ai/api/v1/chat/completions",
            body={"model": "test", "messages": []},
            headers={},
            timeout_s=10,
            retry_transient=True,
        )
    assert exc_info.value.code == 429
    assert attempts["n"] == 5
    assert sleeps == [2, 4, 8, 16]


def test_pregenerate_402_aborts_and_rerun_resumes_from_cache(
    batch_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_role_skills(monkeypatch)
    out_dir = batch_env / "generated_out"
    post_calls: list[dict[str, Any]] = []
    phase = {"allow_second_cell": False}

    def fake_urlopen(req, timeout=0, context=None):
        url = req.full_url
        if url.endswith("/api/v1/key"):
            return _FakeHTTPResponse({"data": {"limit_remaining": 10.0, "usage": 0.0}})
        if url.endswith("/api/v1/credits"):
            return _FakeHTTPResponse({"data": {"total_credits": 10.0, "total_usage": 0.0}})
        if url.endswith("/api/v1/models"):
            return _FakeHTTPResponse(
                {
                    "data": [
                        {
                            "id": "anthropic/claude-haiku-4.5",
                            "pricing": {"prompt": "0.000001", "completion": "0.000005"},
                        }
                    ]
                }
            )
        body = json.loads(req.data.decode("utf-8"))
        user_msg = body["messages"][-1]["content"]
        post_calls.append({"url": url, "user": user_msg})
        # First cell succeeds; second cell hits HTTP 402 during initial run
        if not phase["allow_second_cell"] and len(post_calls) >= 3:
            raise _http_error(
                url,
                402,
                {
                    "error": {
                        "message": "Insufficient credits. You requested up to 2200 tokens, but can only afford 800.",
                        "code": 402,
                    }
                },
            )
        if "Interview Question:" in user_msg:
            return _FakeHTTPResponse(
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": "We apply a token bucket with refill rate and return HTTP status 429 with Retry-After headers."
                            },
                        }
                    ],
                    "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
                }
            )
        topic = "Rate Limiting"
        for line in user_msg.splitlines():
            if line.startswith("- topic:"):
                topic = line.split(":", 1)[1].strip()
                break
        return _FakeHTTPResponse(
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps(_valid_bundle_payload(topic=topic))},
                    }
                ],
                "usage": {"prompt_tokens": 120, "completion_tokens": 250, "total_tokens": 370},
            }
        )

    monkeypatch.setattr(bundle_generator.urllib.request, "urlopen", fake_urlopen)

    exit_code_1 = pregenerate_bundles.main(
        [
            "--roles",
            "Backend Engineer,Data Analyst",
            "--difficulties",
            "easy,medium",
            "--max-bundles",
            "4",
            "--output-dir",
            str(out_dir),
            "--live",
        ]
    )
    out1 = capsys.readouterr().out
    assert exit_code_1 != 0
    assert "ABORTED (credit_exhausted)" in out1
    assert "affordable_tokens" in out1
    assert "rerun the exact same command" in out1
    # Cell 1 used 2 POST calls (generation + blind check), Cell 2 failed on its 1st POST call (402, no retry), Cells 3 & 4 never started
    assert len(post_calls) == 3

    # Top up credits and rerun the EXACT same command -> Cell 1 is cached (0 calls), Cells 2-4 complete (6 POST calls)
    phase["allow_second_cell"] = True
    post_calls.clear()
    exit_code_2 = pregenerate_bundles.main(
        [
            "--roles",
            "Backend Engineer,Data Analyst",
            "--difficulties",
            "easy,medium",
            "--max-bundles",
            "4",
            "--output-dir",
            str(out_dir),
            "--live",
            "--resume",
        ]
    )
    out2 = capsys.readouterr().out
    assert exit_code_2 == 0
    assert "Resume status: 1/4 already cached; 3 remaining before run." in out2
    assert "cache_hits=1" in out2
    assert "generated=3" in out2
    assert "auto_checked=4" in out2 or "auto_checked=3" in out2
    assert len(post_calls) == 6
    assert len(list(out_dir.rglob("*.yaml"))) == 4


def test_bundle_jobs_402_aborts_worker_without_burning_attempts(
    batch_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    j1 = bundle_jobs.enqueue_bundle_job(skill="Python", topic="Asyncio", difficulty="easy")
    j2 = bundle_jobs.enqueue_bundle_job(skill="Python", topic="Locks", difficulty="medium")

    def boom_402(**kwargs):
        raise LLMCreditExhaustedError("HTTP 402 out of credits", status_code=402)

    monkeypatch.setattr(bundle_generator, "generate_and_check_bundle", boom_402)
    summary = bundle_jobs.run_bundle_worker_once(limit=5, allow_live=True)
    assert summary["aborted"] is True
    assert summary["abort_reason"] == "credit_exhausted"
    assert summary["processed"] == 1
    assert bundle_jobs.get_bundle_job(j1["id"])["status"] == "queued"
    assert bundle_jobs.get_bundle_job(j1["id"])["attempts"] == 0
    assert bundle_jobs.get_bundle_job(j2["id"])["status"] == "queued"
    assert bundle_jobs.get_bundle_job(j2["id"])["attempts"] == 0


# ─── Spec 2: Pre-flight credit check & --estimate ────────────────────────────


def test_preflight_refuses_when_cost_exceeds_credit(
    batch_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_role_skills(monkeypatch)
    post_calls = {"n": 0}

    def fake_urlopen(req, timeout=0, context=None):
        url = req.full_url
        if url.endswith("/api/v1/key"):
            return _FakeHTTPResponse({"data": {"limit_remaining": 0.002, "usage": 0.998}})
        if url.endswith("/api/v1/credits"):
            return _FakeHTTPResponse({"data": {"total_credits": 1.0, "total_usage": 0.998}})
        if url.endswith("/api/v1/models"):
            return _FakeHTTPResponse(
                {
                    "data": [
                        {
                            "id": "anthropic/claude-haiku-4.5",
                            "pricing": {"prompt": "0.000001", "completion": "0.000005"},
                        }
                    ]
                }
            )
        post_calls["n"] += 1
        raise AssertionError("POST chat completion must not run when pre-flight refuses")

    monkeypatch.setattr(bundle_generator.urllib.request, "urlopen", fake_urlopen)

    code = pregenerate_bundles.main(
        [
            "--roles",
            "Backend Engineer",
            "--difficulties",
            "easy,medium",
            "--max-bundles",
            "4",
            "--output-dir",
            str(batch_env / "out"),
            "--live",
        ]
    )
    out = capsys.readouterr().out
    assert code != 0
    assert post_calls["n"] == 0
    assert "ABORTED (insufficient_credits)" in out
    assert "remaining_credit=$0.002000" in out


def test_preflight_accounts_for_cached_cells_and_estimate_flag_no_post(
    batch_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install_role_skills(monkeypatch)

    # Pre-populate 3 of 4 planned cells as auto_checked using override
    def seed_override(purpose: str, **kwargs):
        if purpose == "bundle_generation":
            topic = "Rate Limiting"
            for line in kwargs["messages"][-1]["content"].splitlines():
                if line.startswith("- topic:"):
                    topic = line.split(":", 1)[1].strip()
                    break
            return {"content": json.dumps(_valid_bundle_payload(topic=topic))}
        if purpose == "bundle_blind_answer":
            return "Token bucket controls refill rate and HTTP status 429 includes Retry-After."
        raise AssertionError(purpose)

    bundle_generator.set_bundle_llm_override(seed_override)
    seeded = pregenerate_bundles.run_pregeneration(
        roles=["Backend Engineer", "Data Analyst"],
        difficulties=["easy", "medium"],
        max_bundles=3,
        export_yaml=False,
    )
    assert seeded["auto_checked"] == 3
    bundle_generator.set_bundle_llm_override(None)
    llm_usage.reset_memory_usage()

    def fake_get_only(req, timeout=0, context=None):
        url = req.full_url
        if url.endswith("/api/v1/key"):
            return _FakeHTTPResponse({"data": {"limit_remaining": 0.02, "usage": 0.0}})
        if url.endswith("/api/v1/credits"):
            return _FakeHTTPResponse({"data": {"total_credits": 0.02, "total_usage": 0.0}})
        if url.endswith("/api/v1/models"):
            return _FakeHTTPResponse(
                {
                    "data": [
                        {
                            "id": "anthropic/claude-haiku-4.5",
                            "pricing": {"prompt": "0.000001", "completion": "0.000005"},
                        }
                    ]
                }
            )
        raise AssertionError(f"Unexpected non-GET call during --estimate: {url}")

    monkeypatch.setattr(bundle_generator.urllib.request, "urlopen", fake_get_only)

    code = pregenerate_bundles.main(
        [
            "--roles",
            "Backend Engineer,Data Analyst",
            "--difficulties",
            "easy,medium",
            "--max-bundles",
            "4",
            "--estimate",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "planned=4 cached=3 pending_check=0 uncached=1" in out
    assert "fits=True" in out
    assert "SUFFICIENT CREDITS" in out
    assert llm_usage.summarize_usage()["count"] == 0


# ─── Spec 3: Truncation (finish_reason / done_reason == "length") ───────────


def test_http_finish_reason_length_raises_truncated_logs_and_never_parses(
    batch_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    def parse_boom(*args, **kwargs):
        raise AssertionError("_parse_json_object must not be called on truncated output")

    monkeypatch.setattr(bundle_generator, "_parse_json_object", parse_boom)

    def fake_urlopen(req, timeout=0, context=None):
        return _FakeHTTPResponse(
            {
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": '{"question": "partial unclosed json'},
                    }
                ],
                "usage": {"prompt_tokens": 520, "completion_tokens": 2200, "total_tokens": 2720},
            }
        )

    monkeypatch.setattr(bundle_generator.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(LLMTruncatedError):
        bundle_generator.generate_and_check_bundle(
            skill="Python", topic="Asyncio", difficulty="medium", allow_live=True
        )

    events = llm_usage.list_usage_events()
    assert len(events) == 1
    ev = events[0]
    assert ev["status"] == "truncated"
    assert "truncated" in (ev["error"] or "").lower()
    assert ev["prompt_tokens"] == 520
    assert ev["completion_tokens"] == 2200
    assert ev["total_tokens"] == 2720


def test_ollama_done_reason_length_raises_truncated_and_never_parses(
    batch_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "gemma2:2b")

    def parse_boom(*args, **kwargs):
        raise AssertionError("_parse_json_object must not be called on truncated output")

    monkeypatch.setattr(bundle_generator, "_parse_json_object", parse_boom)

    def fake_urlopen(req, timeout=0, context=None):
        return _FakeHTTPResponse(
            {
                "done_reason": "length",
                "message": {"content": '{"question": "partial'},
                "prompt_eval_count": 300,
                "eval_count": 1024,
            }
        )

    monkeypatch.setattr(bundle_generator.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(LLMTruncatedError):
        bundle_generator.generate_and_check_bundle(
            skill="Python", topic="Generators", difficulty="easy", allow_live=True
        )

    events = llm_usage.list_usage_events()
    assert len(events) == 1
    assert events[0]["status"] == "truncated"
    assert events[0]["prompt_tokens"] == 300
    assert events[0]["completion_tokens"] == 1024


def test_override_finish_reason_length_raises_truncated_and_logs(
    batch_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    def parse_boom(*args, **kwargs):
        raise AssertionError("_parse_json_object must not be called on truncated output")

    monkeypatch.setattr(bundle_generator, "_parse_json_object", parse_boom)

    def trunc_override(**kwargs):
        return {
            "choices": [
                {"finish_reason": "length", "message": {"content": '{"question": "cut off'}}
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 2200, "total_tokens": 2300},
        }

    bundle_generator.set_bundle_llm_override(trunc_override)
    with pytest.raises(LLMTruncatedError):
        bundle_generator.generate_and_check_bundle(
            skill="Python", topic="GIL", difficulty="hard"
        )
    events = llm_usage.list_usage_events()
    assert len(events) == 1
    assert events[0]["status"] == "truncated"
    assert events[0]["total_tokens"] == 2300


# ─── Step 5: Blind prompt 120-180w, concept demotion, rejected JSONL audit ───


def test_blind_answer_prompt_targets_120_to_180_words() -> None:
    msgs = bundle_generator._build_blind_answer_messages(
        question="Explain Python GIL.", skill="Python", difficulty="medium"
    )
    joined = "\n".join(m["content"] for m in msgs)
    assert "120-180 words" in joined or "120-180 word" in joined
    assert "strong candidate" in joined.lower()
    assert bundle_generator.DEFAULT_BLIND_CHECK_MAX_TOKENS >= 360


def test_over_specific_concept_demotion_skips_regeneration_and_audit_jsonl(
    batch_env: Path,
) -> None:
    purposes: list[str] = []
    audit_path = batch_env / "demotion_rejected.jsonl"

    def demotion_llm(purpose: str, **kwargs):
        purposes.append(purpose)
        if purpose == "bundle_generation":
            return {
                "content": json.dumps(
                    _valid_bundle_payload(
                        topic="Rate Limiting", three_required=True, tight_third=True
                    )
                ),
                "usage": {"total_tokens": 100},
            }
        if purpose == "bundle_blind_answer":
            return {
                "content": (
                    "We enforce a token bucket with a steady refill rate to absorb short bursts, "
                    "and when tokens run out we return HTTP status 429 with a Retry-After header."
                ),
                "usage": {"total_tokens": 50},
            }
        if purpose == "bundle_check_audit":
            return {
                "content": json.dumps(
                    {
                        "root_cause": "redis_lua_atomicity is too implementation-specific",
                        "issue_type": "over_specific_concept",
                        "missed_concepts": ["redis_lua_atomicity"],
                        "fixes": ["Demote redis_lua_atomicity to optional_concepts"],
                    }
                ),
                "usage": {"total_tokens": 40},
            }
        raise AssertionError(f"Unexpected purpose (should not regenerate): {purpose}")

    bundle_generator.set_bundle_llm_override(demotion_llm)
    res = bundle_generator.generate_and_check_bundle(
        skill="API Design",
        topic="Rate Limiting",
        difficulty="medium",
        rejected_audit_path=audit_path,
    )

    assert purposes == ["bundle_generation", "bundle_blind_answer", "bundle_check_audit"]
    assert res["status"] == "auto_checked"
    assert res["retried"] is False
    assert res["demoted_concept"] == "redis_lua_atomicity"
    assert res["version"] == 2

    versions = {v["version"]: v for v in bundle_store.list_versions(res["bundle_id"])}
    assert versions[1]["status"] == "rejected"
    assert versions[2]["status"] == "auto_checked"

    v2_content = versions[2]["content_json"]
    assert [c["id"] for c in v2_content["required_concepts"]] == [
        "token_bucket",
        "http_429_headers",
    ]
    assert "redis_lua_atomicity" in [c["id"] for c in v2_content["optional_concepts"]]
    # Followup that targeted the demoted concept was retargeted so generated-doc validation passes
    assert all(
        fu["targets_concept"] in {"token_bucket", "http_429_headers"}
        for fu in v2_content["followups"]
    )
    export_doc = {
        **v2_content,
        "version": 2,
        "source": versions[2]["source"],
        "author": versions[2]["author_id"],
        "attribution": versions[2]["attribution_json"],
    }
    assert validate_generated_bundle_doc(export_doc)["content"]["bundle_id"] == res["bundle_id"]
    assert versions[2]["attribution_json"]["auto_check"]["demoted_concept"] == "redis_lua_atomicity"
    assert not audit_path.exists()


def test_demotion_not_applied_when_only_2_required_concepts_and_writes_audit_jsonl(
    batch_env: Path,
) -> None:
    purposes: list[str] = []
    audit_path = batch_env / "nested" / "rejected.jsonl"

    def two_req_fail_llm(purpose: str, **kwargs):
        purposes.append(purpose)
        if purpose == "bundle_generation":
            payload = _valid_bundle_payload(topic="Idempotency", three_required=False)
            payload["required_concepts"][1]["expected_propositions"] = ["nonexistent hyperloop signal"]
            return {"content": json.dumps(payload), "usage": {"total_tokens": 80}}
        if purpose == "bundle_regeneration":
            payload = _valid_bundle_payload(topic="Idempotency", three_required=False, all_tight=True)
            payload["question"] = "[Retry] " + payload["question"]
            return {"content": json.dumps(payload), "usage": {"total_tokens": 80}}
        if purpose == "bundle_blind_answer":
            return {
                "content": "Token bucket controls refill rate accurately.",
                "usage": {"total_tokens": 30},
            }
        if purpose == "bundle_check_audit":
            return {
                "content": json.dumps(
                    {
                        "root_cause": "only 2 required concepts exist so cannot demote",
                        "issue_type": "over_specific_concept",
                        "missed_concepts": ["http_429_headers"],
                        "fixes": ["Broaden proposition"],
                    }
                ),
                "usage": {"total_tokens": 30},
            }
        raise AssertionError(purpose)

    bundle_generator.set_bundle_llm_override(two_req_fail_llm)
    res = bundle_generator.generate_and_check_bundle(
        skill="API Design",
        topic="Idempotency",
        difficulty="hard",
        rejected_audit_path=audit_path,
    )

    assert res["status"] == "rejected"
    assert res["retried"] is True
    assert "bundle_regeneration" in purposes
    assert audit_path.exists()

    lines = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 2
    assert [row["stage"] for row in lines] == ["initial", "regeneration"]
    assert [row["version"] for row in lines] == [1, 2]
    for row in lines:
        assert row["bundle_id"] == res["bundle_id"]
        assert row["skill_slug"] == "api-design"
        assert row["topic_slug"] == "idempotency"
        assert row["difficulty"] == "hard"
        assert row["question"]
        assert row["blind_answer"]
        assert row["failure_reason"]
        assert row["created_at"]
        assert row["missed_concepts"]
        for mc in row["missed_concepts"]:
            assert {"id", "label", "descriptor"} <= set(mc.keys())


def test_step_e_uses_concept_evaluator_v3_and_records_version(batch_env: Path) -> None:
    """Step E.2 runs concept_evaluator_v3 and records evaluator_version in check metadata."""
    audit_path = batch_env / "v3_rejected.jsonl"

    def v3_semantic_override(purpose: str, **kwargs):
        if purpose == "bundle_generation":
            # Propositions alone cannot match (v2 would fail), but v3 semantic/alias tiers match.
            payload = _valid_bundle_payload(topic="Backpressure", all_tight=True)
            return {"content": json.dumps(payload), "usage": {"total_tokens": 90}}
        if purpose == "bundle_blind_answer":
            return {
                "content": (
                    "A token bucket regulates average traffic throughput while smoothing sudden "
                    "traffic spikes cleanly. When capacity empties, servers reject calls with "
                    "status 429 and a Retry-After wait interval so callers throttle cleanly."
                ),
                "usage": {"total_tokens": 55},
            }
        raise AssertionError(purpose)

    bundle_generator.set_bundle_llm_override(v3_semantic_override)
    passed = bundle_generator.generate_and_check_bundle(
        skill="API Design",
        topic="Backpressure",
        difficulty="medium",
        rejected_audit_path=audit_path,
    )
    assert passed["status"] == "auto_checked"
    assert passed["retried"] is False
    assert passed["blind_eval"]["evaluator_version"] == "concept_evaluator_v3.0"
    assert passed["bundle"]["attribution_json"]["auto_check"]["evaluator_version"] == "concept_evaluator_v3.0"
    assert not audit_path.exists()

    # Verify evaluator_version is also persisted on retry/rejection metadata
    bundle_store.reset_memory_store()
    blind_calls = {"n": 0}

    def retry_then_reject_v3(purpose: str, **kwargs):
        if purpose == "bundle_generation":
            return {"content": json.dumps(_valid_bundle_payload(topic="Sharding", all_tight=True)), "usage": {"total_tokens": 80}}
        if purpose == "bundle_regeneration":
            p = _valid_bundle_payload(topic="Sharding", all_tight=True)
            p["question"] = "[Retry] " + p["question"]
            return {"content": json.dumps(p), "usage": {"total_tokens": 80}}
        if purpose == "bundle_blind_answer":
            blind_calls["n"] += 1
            return {"content": "Completely unrelated discussion about DNS TTL records.", "usage": {"total_tokens": 25}}
        if purpose == "bundle_check_audit":
            return {
                "content": json.dumps(
                    {
                        "root_cause": "answer missed everything",
                        "issue_type": "question",
                        "fixes": ["clarify prompt"],
                    }
                ),
                "usage": {"total_tokens": 25},
            }
        raise AssertionError(purpose)

    bundle_generator.set_bundle_llm_override(retry_then_reject_v3)
    rejected = bundle_generator.generate_and_check_bundle(
        skill="API Design",
        topic="Sharding",
        difficulty="hard",
        rejected_audit_path=audit_path,
    )
    assert rejected["status"] == "rejected"
    versions = {v["version"]: v for v in bundle_store.list_versions(rejected["bundle_id"])}
    assert versions[1]["attribution_json"]["auto_check"]["evaluator_version"] == "concept_evaluator_v3.0"
    assert versions[2]["attribution_json"]["auto_check"]["evaluator_version"] == "concept_evaluator_v3.0"


# ─── Item A: Calibration length clamp removed + usable flag ───────────────────


def test_prompt_b_requires_concept_specific_propositions() -> None:
    prompt_b = "\n".join(
        m["content"]
        for m in bundle_generator._build_prompt_b_messages(
            skill="Python", topic="GIL", difficulty="medium"
        )
    )
    regen = "\n".join(
        m["content"]
        for m in bundle_generator._build_regeneration_messages(
            skill="Python",
            topic="GIL",
            difficulty="medium",
            previous_content={},
            blind_answer="short",
            eval_res={},
            audit_diagnosis={},
        )
    )
    for text in (prompt_b, regen):
        assert "at least one term specific to its own concept" in text
        assert "vague or off-topic answer would not contain it" in text
        assert 'No proposition may consist only of generic words (for example "the code", "an error occurs", "returns true")' in text
        assert "No proposition may repeat across concepts" in text
        assert "<= 35" in text and ">= 90" in text


def test_normalize_calibration_examples_preserves_text_and_length_bias() -> None:
    assert not hasattr(bundle_generator, "_POOR_CALIBRATION_PADDING")

    prompt_b = "\n".join(
        m["content"]
        for m in bundle_generator._build_prompt_b_messages(
            skill="Python", topic="GIL", difficulty="medium"
        )
    )
    assert "<= 35" in prompt_b and ">= 90" in prompt_b

    regen = "\n".join(
        m["content"]
        for m in bundle_generator._build_regeneration_messages(
            skill="Python",
            topic="GIL",
            difficulty="medium",
            previous_content={},
            blind_answer="short",
            eval_res={},
            audit_diagnosis={},
        )
    )
    assert "<= 35" in regen and ">= 90" in regen

    good_35 = " ".join(f"g{i}" for i in range(35))
    good_48 = " ".join(f"g{i}" for i in range(48))
    poor_90 = " ".join(f"p{i}" for i in range(90))
    poor_14 = " ".join(f"p{i}" for i in range(14))
    partial_20 = " ".join(f"m{i}" for i in range(20))

    normalized = bundle_generator._normalize_calibration_examples(
        [
            {"answer": good_35, "author_level": 3, "expected_band": "Good"},
            {"answer": good_48, "author_level": 3, "expected_band": "Good"},
            {"answer": poor_90, "author_level": 0, "expected_band": "Poor"},
            {"answer": poor_14, "author_level": 0, "expected_band": "Poor"},
            {"answer": partial_20, "author_level": 1, "expected_band": "Partial"},
        ]
    )
    assert len(normalized) == 5

    # Exact boundaries: Good <= 35 and Poor >= 90 -> length_bias_usable=True
    assert normalized[0]["answer"] == good_35
    assert normalized[0]["word_count"] == 35
    assert normalized[0]["length_bias_usable"] is True
    assert "length_bias_unusable_reason" not in normalized[0]

    assert normalized[2]["answer"] == poor_90
    assert normalized[2]["word_count"] == 90
    assert normalized[2]["length_bias_usable"] is True
    assert "length_bias_unusable_reason" not in normalized[2]

    # Out-of-range answers are NEVER truncated or padded; real word_count stored & marked False
    assert normalized[1]["answer"] == good_48
    assert normalized[1]["word_count"] == 48
    assert normalized[1]["length_bias_usable"] is False
    assert normalized[1]["length_bias_unusable_reason"] == "good_exceeded_35_words"

    assert normalized[3]["answer"] == poor_14
    assert normalized[3]["word_count"] == 14
    assert normalized[3]["length_bias_usable"] is False
    assert normalized[3]["length_bias_unusable_reason"] == "poor_under_90_words"

    # Other band/level omits length_bias_usable
    assert normalized[4]["answer"] == partial_20
    assert normalized[4]["word_count"] == 20
    assert "length_bias_usable" not in normalized[4]


def test_generate_and_check_bundle_succeeds_without_regen_when_calibration_out_of_range(
    batch_env: Path,
) -> None:
    long_good = " ".join(f"goodtok{i}" for i in range(52))
    short_poor = " ".join(f"poortok{i}" for i in range(18))
    purposes: list[str] = []

    def out_of_range_cal_llm(purpose: str, **kwargs):
        purposes.append(purpose)
        if purpose == "bundle_generation":
            payload = _valid_bundle_payload(topic="Circuit Breakers")
            payload["calibration_examples"] = [
                {"answer": long_good, "author_level": 3, "expected_band": "Good"},
                {"answer": short_poor, "author_level": 0, "expected_band": "Poor"},
            ]
            return {"content": json.dumps(payload), "usage": {"total_tokens": 120}}
        if purpose == "bundle_blind_answer":
            return {
                "content": (
                    "We apply a token bucket with steady refill rate and return HTTP status "
                    "429 with a Retry-After header when limits are exceeded."
                ),
                "usage": {"total_tokens": 60},
            }
        raise AssertionError(f"Unexpected regeneration/audit call: {purpose}")

    bundle_generator.set_bundle_llm_override(out_of_range_cal_llm)
    res = bundle_generator.generate_and_check_bundle(
        skill="API Design",
        topic="Circuit Breakers",
        difficulty="medium",
    )

    assert purposes == ["bundle_generation", "bundle_blind_answer"]
    assert res["status"] == "auto_checked"
    assert res["retried"] is False
    cals = res["bundle"]["content_json"]["calibration_examples"]
    assert cals[0]["answer"] == long_good
    assert cals[0]["word_count"] == 52
    assert cals[0]["length_bias_usable"] is False
    assert cals[0]["length_bias_unusable_reason"] == "good_exceeded_35_words"
    assert cals[1]["answer"] == short_poor
    assert cals[1]["word_count"] == 18
    assert cals[1]["length_bias_usable"] is False
    assert cals[1]["length_bias_unusable_reason"] == "poor_under_90_words"


# ─── Item D: Root conftest isolation (dotenv & outbound network) ─────────────


def test_conftest_blocks_dotenv_and_unmocked_network_calls() -> None:
    repo_env = Path(__file__).resolve().parents[1] / ".env"

    with pytest.raises(AssertionError, match="real .env"):
        dotenv.load_dotenv()
    with pytest.raises(AssertionError, match="real .env"):
        dotenv.load_dotenv(repo_env)
    with pytest.raises(AssertionError, match="real .env"):
        app_config.load_dotenv()
    with pytest.raises(AssertionError, match="real .env"):
        dotenv.dotenv_values()

    with pytest.raises(AssertionError, match="Unmocked outbound network call blocked"):
        urllib.request.urlopen("https://example.com")
    with pytest.raises(AssertionError, match="Unmocked outbound network call blocked"):
        socket.create_connection(("example.com", 80), timeout=1)
    with httpx.Client() as client:
        with pytest.raises(AssertionError, match="Unmocked outbound network call blocked"):
            client.get("https://example.com")


# ─── Item E & Pilot Reporting: Demoted JSONL, Pilot Metrics, Review CSV ───────


def test_demoted_concept_exports_jsonl_to_demoted_bundles_audit_path(
    batch_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    demoted_path = batch_env / "audit_out" / "demoted_concepts.jsonl"
    monkeypatch.setenv("DEMOTED_BUNDLES_AUDIT_PATH", str(demoted_path))

    blind_text = (
        "We enforce a token bucket with a steady refill rate to smooth traffic bursts, "
        "and return HTTP status 429 with a Retry-After header when exhausted."
    )

    def demote_llm(purpose: str, **kwargs):
        if purpose == "bundle_generation":
            return {
                "content": json.dumps(
                    _valid_bundle_payload(
                        topic="Quota Demotion", three_required=True, tight_third=True
                    )
                ),
                "usage": {"total_tokens": 100},
            }
        if purpose == "bundle_blind_answer":
            return {"content": blind_text, "usage": {"total_tokens": 50}}
        if purpose == "bundle_check_audit":
            return {
                "content": json.dumps(
                    {
                        "root_cause": "redis_lua_atomicity is implementation-specific",
                        "issue_type": "over_specific_concept",
                        "missed_concepts": ["redis_lua_atomicity"],
                        "fixes": ["Move redis_lua_atomicity to optional_concepts"],
                    }
                ),
                "usage": {"total_tokens": 40},
            }
        raise AssertionError(f"Unexpected purpose: {purpose}")

    bundle_generator.set_bundle_llm_override(demote_llm)
    res = bundle_generator.generate_and_check_bundle(
        skill="API Design",
        topic="Quota Demotion",
        difficulty="medium",
    )

    assert res["status"] == "auto_checked"
    assert res["demoted_concept"] == "redis_lua_atomicity"
    assert demoted_path.exists()

    rows = [
        json.loads(line)
        for line in demoted_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["question"] == res["bundle"]["content_json"]["question"]
    assert row["demoted_concept"] == "redis_lua_atomicity"
    assert row["blind_answer"] == blind_text
    assert "redis_lua_atomicity" in row["audit_reason"]
    assert row["bundle_id"] == res["bundle_id"]
    assert row["from_version"] == 1
    assert row["to_version"] == 2
    assert row["missed_concept_details"]["id"] == "redis_lua_atomicity"
    assert row["audit"]["issue_type"] == "over_specific_concept"


@pytest.mark.requires_semantic_model
def test_pregenerate_pilot_metrics_and_export_bundles_review_csv(
    batch_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def multi_topic_role_override(role: str, jd_text: str):
        return {
            "role_title": "Backend Engineer",
            "domain": "Engineering",
            "skills": [
                {
                    "name": "API Design",
                    "topics": ["Pass Flow", "Demote Flow", "Reject Flow"],
                    "weight": 0.95,
                }
            ],
        }

    role_skills.set_role_skills_llm_override(multi_topic_role_override)

    demoted_audit = batch_env / "pilot_demoted.jsonl"
    rejected_audit = batch_env / "pilot_rejected.jsonl"
    csv_path = batch_env / "pilot_review.csv"

    def _pass_flow_payload() -> dict[str, Any]:
        payload = _valid_bundle_payload(topic="Pass Flow")
        payload["required_concepts"] = [
            {
                "id": "token_bucket",
                "descriptor": "Token bucket controls burst and average rate",
                "aliases": ["token bucket"],
                "expected_propositions": ["token bucket refill rate"],
            },
            {
                "id": "http_429_headers",
                "descriptor": "Return HTTP 429 with Retry-After header",
                "aliases": ["retry after"],
                "expected_propositions": ["nonexistent hyperloop signal"],
            },
            {
                "id": "burst_smoothing",
                "descriptor": "Burst traffic is smoothed by refilling capacity gradually over time.",
                "aliases": ["zyx_unused_alias"],
                "expected_propositions": ["zyx nonexistent prop"],
            },
        ]
        return payload

    def pilot_llm(purpose: str, messages: list[dict[str, str]], **kwargs):
        joined = "\n".join(m["content"] for m in messages)
        if purpose == "bundle_generation":
            if "Pass Flow" in joined:
                payload = _pass_flow_payload()
            elif "Demote Flow" in joined:
                payload = _valid_bundle_payload(
                    topic="Demote Flow", three_required=True, tight_third=True
                )
            else:
                payload = _valid_bundle_payload(topic="Reject Flow", all_tight=True)
                for rc in payload["required_concepts"]:
                    rc["aliases"] = [f"zyx_{rc['id']}"]
            return {
                "content": json.dumps(payload),
                "usage": {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
            }
        if purpose == "bundle_regeneration":
            payload = _valid_bundle_payload(topic="Reject Flow", all_tight=True)
            payload["question"] = "[Retry] " + payload["question"]
            for rc in payload["required_concepts"]:
                rc["aliases"] = [f"zyx_{rc['id']}"]
            return {
                "content": json.dumps(payload),
                "usage": {"prompt_tokens": 110, "completion_tokens": 210, "total_tokens": 320},
            }
        if purpose == "bundle_blind_answer":
            if "Pass Flow" in joined:
                text = (
                    "Apply a token bucket with steady refill rate and include Retry After headers. "
                    "Burst traffic is smoothed by refilling capacity gradually over time."
                )
            elif "Demote Flow" in joined:
                text = (
                    "Use a token bucket with steady refill rate and return HTTP status 429 "
                    "with a Retry-After header."
                )
            else:
                text = "Gardening soil moisture requires watering tomatoes regularly each morning."
            return {
                "content": text,
                "usage": {"prompt_tokens": 40, "completion_tokens": 60, "total_tokens": 100},
            }
        if purpose == "bundle_check_audit":
            if "Demote Flow" in joined:
                diag = {
                    "root_cause": "redis_lua_atomicity too specific",
                    "issue_type": "over_specific_concept",
                    "missed_concepts": ["redis_lua_atomicity"],
                    "fixes": ["Demote to optional"],
                }
            else:
                diag = {
                    "root_cause": "question unclear",
                    "issue_type": "question",
                    "missed_concepts": ["token_bucket", "http_429_headers"],
                    "fixes": ["Rewrite question"],
                }
            return {
                "content": json.dumps(diag),
                "usage": {"prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50},
            }
        raise AssertionError(f"Unexpected purpose: {purpose}")

    bundle_generator.set_bundle_llm_override(pilot_llm)
    pricing = {
        "anthropic/claude-haiku-4.5": {
            "prompt_per_token": 0.000001,
            "completion_per_token": 0.000005,
            "request_cost": 0.0,
        }
    }

    report = pregenerate_bundles.run_pregeneration(
        roles=["Backend Engineer"],
        difficulties=["medium"],
        max_bundles=3,
        export_yaml=False,
        rejected_audit_path=rejected_audit,
        demoted_audit_path=demoted_audit,
        export_review_csv=csv_path,
        pricing_by_model=pricing,
    )

    assert report["planned_count"] == 3
    assert report["evaluated"] == 3
    assert report["first_time_pass_count"] == 1
    assert report["first_time_pass_rate"] == pytest.approx(round(1 / 3, 4))
    assert report["demoted"] == 1
    assert report["demotion_rate"] == pytest.approx(round(1 / 3, 4))
    assert report["rejected"] == 1
    assert len(report["rejected_reasons"]) == 1
    rr = report["rejected_reasons"][0]
    assert rr["bundle_id"] == "api-design.reject-flow-medium"
    assert rr["version"] == 2
    assert rr["issue_type"] == "question"
    assert rr["reason"]
    assert rr["missed_concepts"] == ["token_bucket", "http_429_headers"]

    # Pass Flow: 1 proposition + 1 alias + 1 semantic; Demote Flow: 2 propositions; Reject Flow: 0
    assert report["blind_match_tier_counts"] == {
        "proposition": 3,
        "alias": 1,
        "semantic": 1,
    }

    # Exact token and cost accounting across all 3 cells
    assert report["actual_tokens"] == {
        "prompt_tokens": 630,
        "completion_tokens": 1090,
        "total_tokens": 1720,
        "per_bundle": round(1720 / 3, 2),
    }
    expected_cost = round(630 * 0.000001 + 1090 * 0.000005, 6)
    assert report["actual_cost_usd"] == pytest.approx(expected_cost)
    assert report["cost_per_bundle_usd"] == pytest.approx(round(expected_cost / 3, 6))

    assert demoted_audit.exists()
    assert len([ln for ln in demoted_audit.read_text(encoding="utf-8").splitlines() if ln.strip()]) == 1
    assert rejected_audit.exists()
    assert len([ln for ln in rejected_audit.read_text(encoding="utf-8").splitlines() if ln.strip()]) == 2

    assert report["review_csv_path"] == str(csv_path)
    assert csv_path.exists()
    expected_review_cols = [
        "reference correct (y/n)",
        "question clear (y/n)",
        "difficulty right (y/n)",
        "concepts sensible (y/n)",
        "notes",
    ]
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == list(pregenerate_bundles.REVIEW_CSV_COLUMNS)
        assert reader.fieldnames[-5:] == expected_review_cols
        csv_rows = list(reader)

    assert len(csv_rows) == 3
    for row in csv_rows:
        for col in expected_review_cols:
            assert row[col] == ""
        assert row["bundle_id"]
        assert row["question"]
        assert row["reference_answer"]
        assert int(row["calibration_good_words"]) > 0
        assert int(row["calibration_poor_words"]) > 0

    assert [row["status"] for row in csv_rows] == ["auto_checked", "auto_checked", "rejected"]
    assert csv_rows[0]["demoted_concept"] == ""
    assert csv_rows[1]["demoted_concept"] == "redis_lua_atomicity"

    # Also verify CLI flags --demoted-audit-path and --export-review-csv wire cleanly in main()
    bundle_store.reset_memory_store()
    cli_demoted = batch_env / "cli_demoted.jsonl"
    cli_csv = batch_env / "cli_review.csv"
    exit_code = pregenerate_bundles.main(
        [
            "--roles",
            "Backend Engineer",
            "--difficulties",
            "medium",
            "--max-bundles",
            "2",
            "--no-export-yaml",
            "--demoted-audit-path",
            str(cli_demoted),
            "--export-review-csv",
            str(cli_csv),
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Pilot metrics:" in out
    assert "Blind match tiers:" in out
    assert f"Review CSV: {cli_csv}" in out
    assert cli_demoted.exists()
    assert cli_csv.exists()
