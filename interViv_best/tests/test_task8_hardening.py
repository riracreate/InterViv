from __future__ import annotations

import io
import json
import os
import urllib.error

import pytest

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("QUESTION_GENERATION_MODE", "llm_csv_fallback")
os.environ.setdefault("QUESTION_REQUIRE_LLM", "false")
os.environ.setdefault("QUESTION_LLM_RETRY_BASE_SECONDS", "0")

from modules import question_bank as qb  # noqa: E402
from modules import question_runtime as qr  # noqa: E402


@pytest.fixture(autouse=True)
def _task8_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_LIVE_FETCH", "1")
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "llm_csv_fallback")
    monkeypatch.setenv("QUESTION_REQUIRE_LLM", "false")
    monkeypatch.setattr(qr, "_IN_MEMORY_CACHE", {})
    monkeypatch.setattr(qr, "_IN_MEMORY_LIMITS", {})


def test_question_cache_key_uses_target_concepts_tuple() -> None:
    base = qr.QuestionCacheContext("DSA", "general", "medium", ())
    targeted = qr.QuestionCacheContext("DSA", "general", "medium", ("tree",))

    assert qr.question_cache_key(base) != qr.question_cache_key(targeted)
    assert qr.question_cache_key(targeted) == qr.question_cache_key(
        qr.QuestionCacheContext(" dsa ", "GENERAL", "Medium", ("tree",))
    )


def test_question_cache_key_includes_company_and_role() -> None:
    amazon = qr.QuestionCacheContext("DSA", "general", "medium", (), company="Amazon", role="SDE")
    google = qr.QuestionCacheContext("DSA", "general", "medium", (), company="Google", role="SDE")
    none = qr.QuestionCacheContext("DSA", "general", "medium", ())
    assert qr.question_cache_key(amazon).startswith("interviv:question:v2:")
    assert qr.question_cache_key(amazon) != qr.question_cache_key(google)
    assert qr.question_cache_key(amazon) != qr.question_cache_key(none)
    assert qr.question_cache_key(amazon) == qr.question_cache_key(
        qr.QuestionCacheContext("DSA", "general", "medium", (), company=" amazon ", role="SDE")
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


def test_cached_question_is_bypassed_when_already_asked_and_fresh_generated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("QUESTION_LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("QUESTION_LLM_RETRY_BASE_SECONDS", "0")
    monkeypatch.setenv("QUESTION_LLM_RATE_LIMIT_PER_MINUTE", "0")

    context = qr.QuestionCacheContext("DSA", "general", "medium", ("tree",))
    cached_raw = json.dumps({
        "question": "Explain binary search tree insertion.",
        "ideal_answer": "Compare keys at each node and insert at a leaf.",
        "ideal_keywords": ["BST", "insertion", "O(h)"],
    })
    qr._cache_set(context, cached_raw)

    fresh_raw = json.dumps({
        "question": "How do AVL tree rotations maintain balance?",
        "ideal_answer": "Single and double rotations restore height balance after updates.",
        "ideal_keywords": ["AVL", "rotation", "balance factor"],
    })
    calls = {"count": 0}

    class _FakeResp:
        def __init__(self, body: str) -> None:
            self._buf = io.BytesIO(body.encode("utf-8"))

        def read(self) -> bytes:
            return self._buf.read()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, *args, **kwargs):
        calls["count"] += 1
        return _FakeResp(json.dumps({"choices": [{"message": {"content": fresh_raw}}]}))

    monkeypatch.setattr(qr.urllib.request, "urlopen", fake_urlopen)

    # Round 1: empty asked -> uses cached question without dialing urlopen.
    r1 = qr.call_llm_with_cache_retry("prompt", context, asked=[])
    assert r1 == cached_raw
    assert calls["count"] == 0

    # Round 2: asked contains Round 1's question -> bypasses cache and dials LLM for fresh question.
    r2 = qr.call_llm_with_cache_retry(
        "prompt",
        context,
        asked=["Explain binary search tree insertion."],
    )
    assert r2 == fresh_raw
    assert calls["count"] == 1


def test_ollama_auto_provider_when_cloud_keys_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "auto")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("QUESTION_LLM_MODEL", raising=False)
    monkeypatch.setenv("OLLAMA_MODEL", "gemma2:2b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    provider, api_key, model = qb._llm_provider()
    assert provider == "ollama"
    assert api_key == "ollama"
    assert model == "gemma2:2b"
    assert qb._chat_completion_url(provider) == "http://127.0.0.1:11434/v1/chat/completions"

    seen_urls: list[str] = []
    ollama_reply = json.dumps({
        "question": "How does a B-tree index optimize range queries?",
        "ideal_answer": "Keys are sorted in balanced leaf pages linked sequentially.",
        "ideal_keywords": ["B-tree", "range scan", "page", "index", "O(log n)"],
    })

    class _FakeResp:
        def read(self) -> bytes:
            return json.dumps({"choices": [{"message": {"content": ollama_reply}}]}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, *args, **kwargs):
        seen_urls.append(req.full_url)
        return _FakeResp()

    monkeypatch.setattr(qr.urllib.request, "urlopen", fake_urlopen)
    payload = qr.generate_question("DBMS", "indexing", "medium", asked=[])
    assert seen_urls == ["http://127.0.0.1:11434/v1/chat/completions"]
    assert payload["source"] == "llm"
    assert payload["llm_provider"] == "ollama"
    assert payload["llm_model"] == "gemma2:2b"
    assert payload["question"] == "How does a B-tree index optimize range queries?"


def test_ollama_api_generate_fallback_and_coding_coach_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "auto")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("QUESTION_LLM_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("CODING_COACH_MODEL", "gemma2:2b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

    provider, api_key, model = qb._llm_provider()
    assert (provider, api_key, model) == ("ollama", "ollama", "gemma2:2b")

    seen_urls: list[str] = []
    ollama_reply = json.dumps({
        "question": "Explain Python list comprehensions vs generator expressions.",
        "ideal_answer": "List comprehensions materialize elements eagerly in memory while generators yield lazily.",
        "ideal_keywords": ["generator", "list comprehension", "lazy evaluation", "memory", "iterator"],
    })

    class _FakeResp:
        def read(self) -> bytes:
            return json.dumps({"response": ollama_reply}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, *args, **kwargs):
        seen_urls.append(req.full_url)
        if req.full_url.endswith("/v1/chat/completions"):
            raise urllib.error.HTTPError(
                req.full_url, 404, "Not Found", hdrs=None, fp=io.BytesIO(b"not found")
            )
        return _FakeResp()

    monkeypatch.setattr(qr.urllib.request, "urlopen", fake_urlopen)
    payload = qr.generate_question("Python", "python_core", "easy", asked=[])
    assert seen_urls == [
        "http://127.0.0.1:11434/v1/chat/completions",
        "http://127.0.0.1:11434/api/generate",
    ]
    assert payload["source"] == "llm"
    assert payload["llm_provider"] == "ollama"
    assert payload["question"] == "Explain Python list comprehensions vs generator expressions."


def test_call_llm_retries_if_llm_returns_duplicate_question_in_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("QUESTION_LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("QUESTION_LLM_RETRY_BASE_SECONDS", "0")
    monkeypatch.setenv("QUESTION_LLM_RATE_LIMIT_PER_MINUTE", "0")

    dup = json.dumps({
        "question": "What is a deadlock?",
        "ideal_answer": "Circular wait among processes holding resources.",
        "ideal_keywords": ["deadlock", "circular wait", "mutex"],
    })
    fresh = json.dumps({
        "question": "How does banker's algorithm prevent deadlock?",
        "ideal_answer": "Checks resource allocation safety before granting requests.",
        "ideal_keywords": ["banker's algorithm", "safe state", "deadlock avoidance"],
    })
    replies = [dup, fresh]
    idx = {"i": 0}

    class _FakeResp:
        def __init__(self, content: str) -> None:
            self._buf = io.BytesIO(
                json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")
            )

        def read(self) -> bytes:
            return self._buf.read()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, *args, **kwargs):
        current = replies[min(idx["i"], len(replies) - 1)]
        idx["i"] += 1
        return _FakeResp(current)

    monkeypatch.setattr(qr.urllib.request, "urlopen", fake_urlopen)
    context = qr.QuestionCacheContext("OS", "os_core", "medium", ())
    raw = qr.call_llm_with_cache_retry(
        "prompt",
        context,
        asked=["What is a deadlock?"],
    )
    assert raw == fresh
    assert idx["i"] == 2
