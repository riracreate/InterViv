from __future__ import annotations

import json
import os
import urllib.error

import pytest

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("QUESTION_GENERATION_MODE", "llm_csv_fallback")
os.environ.setdefault("QUESTION_REQUIRE_LLM", "false")
os.environ.setdefault("QUESTION_LLM_RETRY_BASE_SECONDS", "0")

from modules import question_runtime as qr  # noqa: E402


def test_question_cache_key_uses_target_concepts_tuple() -> None:
    base = qr.QuestionCacheContext("DSA", "general", "medium", ())
    targeted = qr.QuestionCacheContext("DSA", "general", "medium", ("tree",))

    assert qr.question_cache_key(base) != qr.question_cache_key(targeted)
    assert qr.question_cache_key(targeted) == qr.question_cache_key(
        qr.QuestionCacheContext(" dsa ", "GENERAL", "Medium", ("tree",))
    )


def test_llm_retries_three_times_then_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("QUESTION_LLM_MAX_RETRIES", "3")
    monkeypatch.setenv("QUESTION_LLM_RETRY_BASE_SECONDS", "0")
    monkeypatch.setenv("QUESTION_LLM_RATE_LIMIT_PER_MINUTE", "0")

    def fail_urlopen(*args, **kwargs):
        calls["count"] += 1
        raise urllib.error.URLError("network down")

    monkeypatch.setattr(qr.urllib.request, "urlopen", fail_urlopen)
    raw = qr.call_llm_with_cache_retry(
        "prompt",
        qr.QuestionCacheContext("DSA", "general", "medium", ("tree",)),
    )

    assert raw is None
    assert calls["count"] == 3
    assert "Network error" in (qr.last_runtime_error() or "")


def test_generate_question_falls_back_after_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "llm_csv_fallback")
    monkeypatch.setattr(qr, "call_llm_with_cache_retry", lambda *args, **kwargs: None)

    payload = qr.generate_question(
        "DSA",
        "general",
        "medium",
        asked=[],
        target_concepts=["tree", "dynamic programming"],
    )

    assert payload["question"]
    assert payload["source"] in {"structured_fallback", "csv", "domain_fallback", "template"}
    assert payload["skill"] == "DSA"


def test_market_prompt_enforces_question_only_json_contract() -> None:
    prompt = qr.build_question_prompt(
        skill="DSA",
        sub_domain="trees",
        difficulty="medium",
        asked=[],
        target_concepts=["tree traversal"],
        market_context=qr.MarketQuestionContext(
            company="Amazon",
            role="SDE Intern",
            resume_skills=("Python", "DSA"),
            weak_skills=("trees",),
        ),
    )

    for expected in (
        '"ideal_answer"',
        '"ideal_keywords"',
        '"question_type"',
        '"company"',
        '"role"',
        '"followups"',
        "Do not score, judge, grade, evaluate, or give feedback",
        "Resume skills: Python, DSA",
        "Weak skills/concepts: trees",
    ):
        assert expected in prompt


def test_generate_question_returns_market_metadata_from_llm_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "llm_csv_fallback")
    raw = json.dumps({
        "question": "How would you use a hash map to optimize pair-sum lookup?",
        "ideal_answer": "Use a hash map to store complements while scanning once. This reduces lookup to average O(1).",
        "ideal_keywords": ["hash map", "complement", "O(n)", "lookup", "pair sum"],
        "sub_domain": "hashing",
        "topic": "Pair sum",
        "difficulty": "medium",
        "question_type": "coding",
        "company": "Amazon",
        "role": "SDE Intern",
        "followups": ["What edge case would you test?", "What is the space complexity?"],
    })
    monkeypatch.setattr(qr, "call_llm_with_cache_retry", lambda *args, **kwargs: raw)

    payload = qr.generate_question(
        "DSA",
        "hashing",
        "medium",
        asked=[],
        target_concepts=["hash map"],
        market_context=qr.MarketQuestionContext(
            company="Amazon",
            role="SDE Intern",
            resume_skills=("Python", "DSA"),
            weak_skills=("hashing",),
        ),
    )

    for key in (
        "question",
        "ideal_answer",
        "ideal_keywords",
        "company",
        "role",
        "skill",
        "sub_domain",
        "topic",
        "difficulty",
        "question_type",
        "followups",
    ):
        assert key in payload
    assert payload["source"] == "llm"
    assert payload["company"] == "Amazon"
    assert payload["role"] == "SDE Intern"


def test_cached_raw_response_is_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("QUESTION_LLM_MAX_RETRIES", "1")
    monkeypatch.setenv("QUESTION_LLM_RATE_LIMIT_PER_MINUTE", "0")
    context = qr.QuestionCacheContext("Python", "python_core", "medium", ())
    raw = json.dumps({"question": "Explain Python generators.", "ideal_answer": "", "ideal_keywords": "yield"})

    qr._cache_set(context, raw)
    assert qr.call_llm_with_cache_retry("prompt", context) == raw
