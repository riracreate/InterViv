"""Hard-pair skill merge validation and Prompt A LLM error policy tests."""

from __future__ import annotations

import io
import json
import logging
import os
import urllib.error
from typing import Any
from unittest.mock import patch

import pytest
import torch

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("JOBS_LIVE_FETCH", "0")
os.environ.setdefault("LLM_LIVE_FETCH", "0")

from backend import config as app_config
from backend.db.sqlalchemy_store import _sessionmaker, get_engine, get_sqlalchemy_database
from modules import bundle_jobs, bundle_store, llm_usage, question_bank, role_skills
from modules.llm_errors import LLMCreditExhaustedError
from modules.semantic_scorer import _get_model


def _clear_all_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def clean_skill_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "true")
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    _clear_all_caches()
    bundle_store.reset_memory_store()
    llm_usage.reset_memory_usage()
    bundle_jobs.reset_memory_bundle_jobs()
    role_skills.reset_role_skill_cache(reset_canonicals=True)
    role_skills.set_role_skills_llm_override(None)
    monkeypatch.setattr(role_skills.LOGGER, "disabled", False)
    monkeypatch.setattr(role_skills.LOGGER, "propagate", True)
    yield
    role_skills.set_role_skills_llm_override(None)
    bundle_store.reset_memory_store()
    llm_usage.reset_memory_usage()
    bundle_jobs.reset_memory_bundle_jobs()
    role_skills.reset_role_skill_cache(reset_canonicals=True)
    _clear_all_caches()


NON_MERGE_HARD_PAIRS = [
    ("Java", "JavaScript"),
    ("SQL", "NoSQL"),
    ("React", "React Native"),
    ("C", "C++"),
    ("C", "C#"),
    ("C++", "C#"),
    ("Machine Learning", "Deep Learning"),
    ("Product Management", "Project Management"),
    ("Accounting", "Auditing"),
]

SHOULD_MERGE_HARD_PAIRS = [
    ("Data Analysis", "Data Analytics"),
]


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _http_error(url: str, code: int, body: dict[str, Any] | str) -> urllib.error.HTTPError:
    raw = json.dumps(body) if isinstance(body, dict) else str(body)
    return urllib.error.HTTPError(
        url,
        code,
        f"HTTP {code}",
        hdrs=None,
        fp=io.BytesIO(raw.encode("utf-8")),
    )


@pytest.mark.requires_semantic_model
def test_hard_pairs_raw_minilm_scores_are_reproducible(clean_skill_env) -> None:
    model = _get_model()
    assert model is not None

    scores: dict[tuple[str, str], float] = {}
    for a, b in NON_MERGE_HARD_PAIRS + SHOULD_MERGE_HARD_PAIRS:
        a_sing = role_skills._singularize_phrase(a)
        b_sing = role_skills._singularize_phrase(b)
        embs = model.encode([a, b, a_sing, b_sing], convert_to_tensor=True, normalize_embeddings=True)
        cos_raw = float(torch.dot(embs[0], embs[1]))
        cos_sing = float(torch.dot(embs[2], embs[3]))
        assert cos_raw == pytest.approx(cos_sing, abs=1e-4)
        _, probe_b_on_a = role_skills._minilm_best_match(b, [a])
        _, probe_a_on_b = role_skills._minilm_best_match(a, [b])
        assert probe_b_on_a == pytest.approx(max(0.0, cos_raw), abs=1e-4)
        assert probe_a_on_b == pytest.approx(max(0.0, cos_raw), abs=1e-4)
        scores[(a, b)] = cos_raw

    # Key empirical tension: React/React Native (0.7396) > Data Analysis/Data Analytics (0.7311).
    assert scores[("React", "React Native")] > scores[("Data Analysis", "Data Analytics")]
    assert scores[("Data Analysis", "Data Analytics")] < role_skills.DEFAULT_SIMILARITY_THRESHOLD


@pytest.mark.parametrize("first,second", NON_MERGE_HARD_PAIRS)
def test_non_merge_hard_pairs_stay_separate_both_directions(
    clean_skill_env, first: str, second: str
) -> None:
    # With full base canonicals + registered first -> second stays separate
    res_ab, mt_ab = role_skills.resolve_skill_identity(
        second, extra_canonicals=[first], register=False
    )
    res_ba, mt_ba = role_skills.resolve_skill_identity(
        first, extra_canonicals=[second], register=False
    )
    assert res_ab.lower() != first.lower()
    assert res_ba.lower() != second.lower()
    assert res_ab.lower() != res_ba.lower()
    assert mt_ab in {"exact", "new_canonical"}
    assert mt_ba in {"exact", "new_canonical"}

    # Even in an isolated canonical set (only [first] registered) AND low MiniLM threshold (0.30),
    # never-merge blocks MiniLM / singular / alias cross-merging.
    with patch.object(role_skills, "get_canonical_skills", return_value=[first]):
        iso_ab, iso_mt_ab = role_skills.resolve_skill_identity(
            second, similarity_threshold=0.30, register=False
        )
    with patch.object(role_skills, "get_canonical_skills", return_value=[second]):
        iso_ba, iso_mt_ba = role_skills.resolve_skill_identity(
            first, similarity_threshold=0.30, register=False
        )
    assert iso_ab.lower() != first.lower()
    assert iso_ba.lower() != second.lower()
    if iso_mt_ab == "minilm_match" or iso_mt_ba == "minilm_match":
        pytest.fail(f"Never-merge pair {(first, second)} merged via MiniLM: {iso_ab}/{iso_ba}")


@pytest.mark.parametrize("first,second", NON_MERGE_HARD_PAIRS)
def test_never_merge_checked_before_alias_and_minilm_case_insensitive(
    clean_skill_env, monkeypatch, first: str, second: str
) -> None:
    assert role_skills.is_never_merge_pair(first.lower(), second.upper())
    assert role_skills.is_never_merge_pair(second.lower(), first.upper())

    # Inject a bogus alias and bogus high-score MiniLM match trying to merge second -> first
    monkeypatch.setitem(role_skills._ALIAS_TO_CANONICAL, second.lower(), first)
    monkeypatch.setattr(role_skills, "_minilm_best_match", lambda _raw, _c: (first, 0.99))

    with patch.object(role_skills, "get_canonical_skills", return_value=[first]):
        resolved, match_type = role_skills.resolve_skill_identity(
            second.upper(), register=False
        )
    assert resolved.lower() != first.lower()
    assert match_type == "new_canonical"


def test_never_merge_handles_punctuation_and_spelling_variants(clean_skill_env) -> None:
    with patch.object(role_skills, "get_canonical_skills", return_value=["React"]):
        res, mt = role_skills.resolve_skill_identity(
            "react-native", similarity_threshold=0.50, register=False
        )
        assert res != "React"
        assert mt == "new_canonical"

    with patch.object(role_skills, "get_canonical_skills", return_value=["SQL"]):
        res_nosql, mt_nosql = role_skills.resolve_skill_identity(
            "No-SQL", similarity_threshold=0.30, register=False
        )
        assert res_nosql != "SQL"
        assert mt_nosql == "new_canonical"

    with patch.object(role_skills, "get_canonical_skills", return_value=["C"]):
        res_csharp, mt_csharp = role_skills.resolve_skill_identity(
            "C Sharp", similarity_threshold=0.20, register=False
        )
        assert res_csharp != "C"
        assert mt_csharp != "minilm_match"


@pytest.mark.parametrize("first,second", SHOULD_MERGE_HARD_PAIRS)
def test_should_merge_pairs_merge_symmetrically(
    clean_skill_env, first: str, second: str
) -> None:
    res_ab, mt_ab = role_skills.resolve_skill_identity(
        second, extra_canonicals=[first], register=False
    )
    assert res_ab == first
    assert mt_ab == "alias"

    res_ba, mt_ba = role_skills.resolve_skill_identity(
        first, extra_canonicals=[second], register=False
    )
    assert res_ba == second
    assert mt_ba == "alias"

    # Sequential stateful registration collapses both to one canonical regardless of order
    role_skills.reset_role_skill_cache(reset_canonicals=True)
    c1, _ = role_skills.resolve_skill_identity(first, register=True)
    c2, _ = role_skills.resolve_skill_identity(second, register=True)
    assert c1 == c2 == first

    role_skills.reset_role_skill_cache(reset_canonicals=True)
    d1, _ = role_skills.resolve_skill_identity(second, register=True)
    d2, _ = role_skills.resolve_skill_identity(first, register=True)
    assert d1 == d2 == second


@pytest.mark.requires_semantic_model
def test_original_paraphrases_and_distinct_non_tech_skills_still_pass(clean_skill_env) -> None:
    paraphrases = [
        ("PostgreSQL Databases", "PostgreSQL"),
        ("Docker Containerization", "Docker"),
        ("Machine Learning Models", "Machine Learning"),
        ("Kubernetes Clusters", "Kubernetes"),
        ("Python Programming", "Python"),
        ("SQL Queries", "SQL"),
    ]
    for raw, expected in paraphrases:
        resolved, match_type = role_skills.resolve_skill_identity(raw, register=False)
        assert resolved == expected
        assert match_type == "minilm_match"

    for distinct in (
        "Product Positioning",
        "Go-To-Market Strategy",
        "Cohort Retention Analysis",
        "Financial Modeling",
        "Supply Chain Optimization",
    ):
        resolved, match_type = role_skills.resolve_skill_identity(distinct, register=False)
        assert resolved == distinct
        assert match_type == "new_canonical"


def _enable_live_provider(monkeypatch, provider: str = "openrouter") -> None:
    monkeypatch.setenv("LLM_LIVE_FETCH", "1")
    _clear_all_caches()
    if provider == "ollama":
        monkeypatch.setattr(
            question_bank,
            "_llm_provider",
            lambda: ("ollama", "ollama-local", "gemma2:2b"),
        )
    else:
        monkeypatch.setattr(
            question_bank,
            "_llm_provider",
            lambda: ("openrouter", "sk-test-dummy", "test/model"),
        )


@pytest.mark.parametrize(
    "error_body",
    [
        {"error": {"message": "Insufficient credits"}},
        {"error": {"code": "in_flight_budget_exhausted", "message": "Budget exhausted"}},
    ],
)
def test_dial_prompt_a_402_not_retried_raises_and_logs_usage(
    clean_skill_env, monkeypatch, error_body: dict[str, Any]
) -> None:
    _enable_live_provider(monkeypatch, "openrouter")
    calls = {"n": 0}
    sleeps: list[float] = []

    def fake_urlopen(req, timeout=None, context=None):
        calls["n"] += 1
        raise _http_error(req.full_url, 402, error_body)

    monkeypatch.setattr(role_skills.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(role_skills.time, "sleep", lambda s: sleeps.append(s))

    with pytest.raises(LLMCreditExhaustedError) as exc_info:
        role_skills.extract_role_skills(role="Data Analyst", jd_text="Analyze metrics")

    assert exc_info.value.status_code == 402
    assert calls["n"] == 1
    assert sleeps == []

    events = llm_usage.list_usage_events()
    assert len(events) == 1
    assert events[0]["status"] == "error"
    assert events[0]["purpose"] == "role_skill_extraction"
    assert "402" in (events[0]["error"] or "")


@pytest.mark.parametrize("status_code", [502, 503])
def test_dial_prompt_a_502_503_not_retried_and_logs_usage(
    clean_skill_env, monkeypatch, status_code: int
) -> None:
    _enable_live_provider(monkeypatch, "openrouter")
    calls = {"n": 0}
    sleeps: list[float] = []

    def fake_urlopen(req, timeout=None, context=None):
        calls["n"] += 1
        raise _http_error(req.full_url, status_code, "Upstream error")

    monkeypatch.setattr(role_skills.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(role_skills.time, "sleep", lambda s: sleeps.append(s))

    res = role_skills.extract_role_skills(role="Backend Engineer", jd_text="Build APIs")
    assert res["offline_uncached"] is True
    assert res["mode"] == "offline_uncached"
    assert f"HTTP {status_code}" in (res.get("error") or "")
    assert calls["n"] == 1
    assert sleeps == []

    events = llm_usage.list_usage_events()
    assert len(events) == 1
    assert events[0]["status"] == "error"
    assert f"HTTP {status_code}" in (events[0]["error"] or "")


def test_dial_prompt_a_429_retries_with_backoff_and_succeeds(
    clean_skill_env, monkeypatch
) -> None:
    _enable_live_provider(monkeypatch, "openrouter")
    calls = {"n": 0}
    sleeps: list[float] = []

    ok_payload = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps(
                        {
                            "role_title": "Data Analyst",
                            "domain": "Analytics",
                            "skills": [
                                {
                                    "name": "Data Analytics",
                                    "topics": ["Cohort Analysis", "Funnel Metrics"],
                                    "weight": 0.9,
                                }
                            ],
                        }
                    )
                },
            }
        ],
        "usage": {"prompt_tokens": 40, "completion_tokens": 25, "total_tokens": 65},
    }

    def fake_urlopen(req, timeout=None, context=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _http_error(req.full_url, 429, "Rate limited")
        return _FakeResponse(ok_payload)

    monkeypatch.setattr(role_skills.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(role_skills.time, "sleep", lambda s: sleeps.append(s))

    res = role_skills.extract_role_skills(role="Data Analyst", jd_text="Analyze metrics")
    assert res["mode"] == "llm"
    assert res["skills"] == ["Data Analytics"]
    assert calls["n"] == 3
    assert sleeps == [2, 4]

    events = llm_usage.list_usage_events()
    assert len(events) == 1
    assert events[0]["status"] == "ok"
    assert events[0]["total_tokens"] == 65


def test_dial_prompt_a_429_exhausted_logs_single_error(
    clean_skill_env, monkeypatch
) -> None:
    _enable_live_provider(monkeypatch, "openrouter")
    calls = {"n": 0}
    sleeps: list[float] = []

    def fake_urlopen(req, timeout=None, context=None):
        calls["n"] += 1
        raise _http_error(req.full_url, 429, "Rate limited")

    monkeypatch.setattr(role_skills.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(role_skills.time, "sleep", lambda s: sleeps.append(s))

    res = role_skills.extract_role_skills(role="Data Analyst", jd_text="Analyze metrics")
    assert res["offline_uncached"] is True
    assert "HTTP 429" in (res.get("error") or "")
    assert calls["n"] == 4
    assert sleeps == [2, 4, 8]

    events = llm_usage.list_usage_events()
    assert len(events) == 1
    assert events[0]["status"] == "error"


def test_dial_prompt_a_finish_reason_length_not_parsed_and_logged(
    clean_skill_env, monkeypatch, caplog
) -> None:
    _enable_live_provider(monkeypatch, "openrouter")
    parse_calls = {"n": 0}
    orig_parse = role_skills._parse_json_object

    def spy_parse(raw: str):
        parse_calls["n"] += 1
        return orig_parse(raw)

    monkeypatch.setattr(role_skills, "_parse_json_object", spy_parse)

    # Even if content looks like valid JSON, finish_reason == "length" must NOT parse it.
    truncated_payload = {
        "choices": [
            {
                "finish_reason": "length",
                "message": {
                    "content": '{"role_title": "PM", "skills": [{"name": "Pricing", "topics": ["A", "B"]}]}'
                },
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 700, "total_tokens": 800},
    }
    monkeypatch.setattr(
        role_skills.urllib.request,
        "urlopen",
        lambda req, timeout=None, context=None: _FakeResponse(truncated_payload),
    )

    with caplog.at_level(logging.WARNING, logger="modules.role_skills"):
        res = role_skills.extract_role_skills(role="Product Manager", jd_text="Own roadmap")

    assert parse_calls["n"] == 0
    assert res["offline_uncached"] is True
    assert "truncated" in (res.get("error") or "").lower()
    assert any("truncated" in rec.message.lower() for rec in caplog.records)

    events = llm_usage.list_usage_events()
    assert len(events) == 1
    assert events[0]["status"] == "error"
    assert events[0]["prompt_tokens"] == 100
    assert events[0]["completion_tokens"] == 700
    assert events[0]["total_tokens"] == 800
    assert "truncated" in (events[0]["error"] or "").lower()


def test_dial_prompt_a_ollama_done_reason_length_not_parsed_and_logged(
    clean_skill_env, monkeypatch, caplog
) -> None:
    _enable_live_provider(monkeypatch, "ollama")
    parse_calls = {"n": 0}

    def spy_parse(_raw: str):
        parse_calls["n"] += 1
        return None

    monkeypatch.setattr(role_skills, "_parse_json_object", spy_parse)

    ollama_truncated = {
        "message": {"role": "assistant", "content": '{"role_title": "PM", "skills": ['},
        "done": True,
        "done_reason": "length",
        "prompt_eval_count": 55,
        "eval_count": 700,
    }
    monkeypatch.setattr(
        role_skills.urllib.request,
        "urlopen",
        lambda req, timeout=None, context=None: _FakeResponse(ollama_truncated),
    )

    with caplog.at_level(logging.WARNING, logger="modules.role_skills"):
        res = role_skills.extract_role_skills(role="Product Manager", jd_text="Own roadmap")

    assert parse_calls["n"] == 0
    assert res["offline_uncached"] is True
    assert "truncated" in (res.get("error") or "").lower()
    assert any("truncated" in rec.message.lower() for rec in caplog.records)

    events = llm_usage.list_usage_events()
    assert len(events) == 1
    assert events[0]["status"] == "error"
    assert events[0]["prompt_tokens"] == 55
    assert events[0]["completion_tokens"] == 700
    assert events[0]["total_tokens"] == 755


@pytest.mark.requires_semantic_model
def test_new_canonical_skill_registration_logs_memory_and_jsonl_without_duplicates(
    clean_skill_env, monkeypatch: pytest.MonkeyPatch, tmp_path, caplog
) -> None:
    audit_path = tmp_path / "audit" / "new_canonical_skills.jsonl"
    monkeypatch.setenv("NEW_CANONICAL_SKILLS_AUDIT_PATH", str(audit_path))
    assert role_skills.resolve_new_canonical_audit_path() == audit_path

    # register=False must not emit an audit event or touch the JSONL file.
    with caplog.at_level(logging.INFO, logger="modules.role_skills"):
        canon_ro, mt_ro = role_skills.resolve_skill_identity(
            "quantum supply optimization", register=False
        )
    assert canon_ro == "Quantum Supply Optimization"
    assert mt_ro == "new_canonical"
    assert role_skills.list_new_canonical_skill_events() == []
    assert not audit_path.exists()
    assert not any("new_canonical" in rec.message for rec in caplog.records)

    # First register=True creation emits LOGGER.info, in-memory event, and JSONL line.
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="modules.role_skills"):
        canon1, mt1 = role_skills.resolve_skill_identity(
            "revenue attribution modeling", register=True
        )
    assert canon1 == "Revenue Attribution Modeling"
    assert mt1 == "new_canonical"

    info_msgs = [
        rec.getMessage()
        for rec in caplog.records
        if rec.levelno == logging.INFO and "new_canonical" in rec.getMessage()
    ]
    assert len(info_msgs) == 1
    assert "Revenue Attribution Modeling" in info_msgs[0]

    events = role_skills.list_new_canonical_skill_events()
    assert len(events) == 1
    ev = events[0]
    assert ev["canonical_name"] == "Revenue Attribution Modeling"
    assert ev["raw_name"] == "revenue attribution modeling"
    assert ev["normalized"] == "Revenue Attribution Modeling"
    assert ev["similarity_threshold"] == role_skills.DEFAULT_SIMILARITY_THRESHOLD
    assert isinstance(ev["best_similarity_score"], float)
    assert ev["best_existing_candidate"]
    assert ev["created_at"]

    assert audit_path.exists()
    rows = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["canonical_name"] == "Revenue Attribution Modeling"
    assert rows[0]["raw_name"] == "revenue attribution modeling"
    assert rows[0]["normalized"] == "Revenue Attribution Modeling"
    assert rows[0]["created_at"] == ev["created_at"]

    # Repeat exact / case-insensitive calls and base exact/alias calls must not duplicate logs or JSONL.
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="modules.role_skills"):
        assert role_skills.resolve_skill_identity(
            "revenue attribution modeling", register=True
        ) == ("Revenue Attribution Modeling", "exact")
        assert role_skills.resolve_skill_identity(
            "REVENUE ATTRIBUTION MODELING", register=True
        ) == ("Revenue Attribution Modeling", "exact")
        assert role_skills.resolve_skill_identity("python", register=True) == ("Python", "exact")
        assert role_skills.resolve_skill_identity("golang", register=True) == ("Go", "alias")

    assert not any("new_canonical" in rec.getMessage() for rec in caplog.records)
    assert len(role_skills.list_new_canonical_skill_events()) == 1
    rows_after = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows_after) == 1

    # reset_canonical_registry clears in-memory events cleanly.
    role_skills.reset_canonical_registry()
    assert role_skills.list_new_canonical_skill_events() == []
