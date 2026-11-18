"""Offline tests for direct NVIDIA NIM and Groq content/check providers."""
from __future__ import annotations

import io
import json
from dataclasses import replace
from urllib.error import HTTPError

import pytest

from modules import bundle_generator, interview_llm as routing, llm_usage
from modules.interview_llm_budget import DispatchDeferred, RequestBudget
from modules.llm_http_policy import classify_http_error, parse_ratelimit_headers
from tests.test_ai_interview_routing import FREE_A, FREE_B, PAID, Clock, catalog


class _FakeHTTPResponse:
    def __init__(self, payload: dict, *, headers: dict[str, str] | None = None, status: int = 200):
        self._raw = json.dumps(payload).encode("utf-8")
        self.headers = headers or {}
        self.status = status

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _direct_env(monkeypatch, tmp_path, *, content_models=(), check_models=(), allow_paid=False,
                allow_self_check=False, content_provider="nvidia", check_provider="groq",
                groq_model=routing.DEFAULT_GROQ_CHECK_MODEL,
                nvidia_model=routing.DEFAULT_NVIDIA_CONTENT_MODEL):
    monkeypatch.setenv("AI_INTERVIEW_ROUTING_ENABLED", "1")
    monkeypatch.setenv("INTERVIEW_DIRECT_PROVIDERS_ENABLED", "1")
    monkeypatch.setenv("INTERVIEW_CONTENT_PROVIDER", content_provider)
    monkeypatch.setenv("INTERVIEW_CHECK_PROVIDER", check_provider)
    monkeypatch.setenv("NVIDIA_CONTENT_MODEL", nvidia_model)
    monkeypatch.setenv("GROQ_CHECK_MODEL", groq_model)
    monkeypatch.setenv("NVIDIA_API_KEY", "offline-nvidia-fixture")
    monkeypatch.setenv("GROQ_API_KEY", "offline-groq-fixture")
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-openrouter-fixture")
    monkeypatch.setenv("LLM_LIVE_FETCH", "1")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.delenv("LLM_LIVE_CONSUMERS", raising=False)
    from backend.config import get_settings
    get_settings.cache_clear()
    clock = Clock()
    settings = routing.RoutingSettings(
        state_path=tmp_path / "limits.json",
        direct_providers_enabled=True,
        content_provider=content_provider,
        check_provider=check_provider,
        nvidia_content_model=nvidia_model,
        groq_check_model=groq_model,
        content_models=content_models,
        check_models=check_models,
        allow_paid_content=allow_paid,
        allow_self_check=allow_self_check,
    )
    router = routing.InterviewRouter(settings, catalog_source=catalog, clock=clock)
    monkeypatch.setattr(routing, "get_router", lambda: router)
    llm_usage.reset_memory_usage()
    bundle_generator.set_bundle_llm_override(None)
    return router, clock


def test_direct_provider_settings_default_off_and_per_lane_routing(monkeypatch, tmp_path):
    for key in (
        "INTERVIEW_DIRECT_PROVIDERS_ENABLED", "INTERVIEW_CONTENT_PROVIDER",
        "INTERVIEW_CHECK_PROVIDER", "NVIDIA_CONTENT_MODEL", "GROQ_CHECK_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    assert routing.RoutingSettings.from_env() == routing.RoutingSettings()
    assert routing.RoutingSettings.from_env().direct_providers_enabled is False

    router, clock = _direct_env(monkeypatch, tmp_path)
    sent: list[tuple[str, dict]] = []

    def fake_urlopen(req, **kwargs):
        body = json.loads(req.data.decode("utf-8"))
        sent.append((req.full_url, body))
        if req.full_url == routing.NVIDIA_CHAT_URL:
            return _FakeHTTPResponse({
                "model": body["model"],
                "choices": [{"message": {"content": "<think>internal</think>{\"ok\": true}"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            })
        assert req.full_url == routing.GROQ_CHAT_URL
        return _FakeHTTPResponse({
            "model": body["model"],
            "choices": [{"message": {"content": "{\"root_cause\": \"ok\"}"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 6, "total_tokens": 16},
        }, headers={"x-ratelimit-remaining-requests": "99", "x-ratelimit-remaining-tokens": "9000"})

    monkeypatch.setattr(routing.urllib.request, "urlopen", fake_urlopen)
    with routing.interview_scope("per-lane", 2) as scope:
        assert bundle_generator.resolve_generation_provider_and_model() == (
            "nvidia", routing.DEFAULT_NVIDIA_CONTENT_MODEL,
        )
        assert bundle_generator.resolve_checker_provider_and_model() == (
            "groq", routing.DEFAULT_GROQ_CHECK_MODEL,
        )
        gen = router.dispatch(purpose="bundle_generation", messages=[{"role": "user", "content": "Write bundle"}])
        clock.advance(4)
        chk = router.dispatch(purpose="bundle_check_audit", messages=[{"role": "user", "content": "Audit bundle"}])

    assert gen.provider == "nvidia"
    assert gen.model == routing.DEFAULT_NVIDIA_CONTENT_MODEL
    assert gen.text == '{"ok": true}'  # thinking tags stripped
    assert scope.providers["bundle_generation"] == "nvidia"

    assert chk.provider == "groq"
    assert chk.model == routing.DEFAULT_GROQ_CHECK_MODEL
    assert scope.providers["bundle_check_audit"] == "groq"

    assert sent[0][0] == routing.NVIDIA_CHAT_URL
    assert sent[0][1]["messages"][0] == {"role": "system", "content": "detailed thinking off"}
    assert sent[0][1]["response_format"] == {"type": "json_object"}

    assert sent[1][0] == routing.GROQ_CHAT_URL
    assert sent[1][1]["reasoning_effort"] == "low"
    assert sent[1][1]["response_format"]["type"] == "json_schema"
    assert sent[1][1]["response_format"]["json_schema"]["strict"] is True


def test_conversation_lane_stays_locked_to_openrouter_haiku(monkeypatch, tmp_path):
    router, _ = _direct_env(monkeypatch, tmp_path)
    urls: list[str] = []

    def fake_urlopen(req, **kwargs):
        body = json.loads(req.data.decode("utf-8"))
        urls.append(req.full_url)
        return _FakeHTTPResponse({
            "model": PAID,
            "choices": [{"message": {"content": "Follow-up response."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        })

    monkeypatch.setattr(routing.urllib.request, "urlopen", fake_urlopen)
    for purpose in sorted(routing.PERSONAL_PURPOSES):
        with routing.interview_scope(f"conv-{purpose}", 2):
            res = router.dispatch(
                purpose=purpose,
                messages=[{"role": "user", "content": "PRIVATE_CANDIDATE_ANSWER"}],
                expect_json=False,
            )
            assert res.provider == "openrouter"
            assert res.model == PAID
        with pytest.raises(routing.PrivacyViolation):
            routing.enforce_outbound_policy(purpose=purpose, model=routing.DEFAULT_NVIDIA_CONTENT_MODEL, provider="nvidia")
        with routing.interview_scope(f"block-{purpose}", 2), pytest.raises(routing.PrivacyViolation):
            router.dispatch(purpose=purpose, messages=[], provider="groq")

    assert all(u == routing.CHAT_URL for u in urls)


def test_static_capability_table_and_nvidia_json_schema_probe(monkeypatch, tmp_path):
    router, _ = _direct_env(monkeypatch, tmp_path, nvidia_model="nvidia/unknown-unlisted")
    with routing.interview_scope("unknown-direct", 2), pytest.raises(routing.RoutingError, match="DIRECT_PROVIDER_CAPABILITIES"):
        router.dispatch(purpose="bundle_generation", messages=[{"role": "user", "content": "x"}])

    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    with pytest.raises(routing.RoutingError, match="LLM_LIVE_FETCH=1"):
        routing.check_nvidia_json_schema_support()

    ok_probe = routing.check_nvidia_json_schema_support(
        opener=lambda req: _FakeHTTPResponse({"choices": [{"message": {"content": '{"ok": true}'}}]}),
    )
    assert ok_probe["json_schema_supported"] is True

    def fail_opener(req):
        raise HTTPError(routing.NVIDIA_CHAT_URL, 400, "Bad Request", {}, io.BytesIO(b'{"error": "unsupported"}'))

    bad_probe = routing.check_nvidia_json_schema_support(opener=fail_opener)
    assert bad_probe["json_schema_supported"] is False
    assert bad_probe["status"] == 400


@pytest.mark.parametrize("status,expected_kind", [
    (401, "authorization"),
    (402, "credits"),
    (403, "authorization"),
])
def test_direct_provider_401_402_403_abort_without_retry_or_openrouter_fallback(monkeypatch, tmp_path, status, expected_kind):
    router, _ = _direct_env(monkeypatch, tmp_path, content_models=(FREE_A,))
    calls: list[str] = []

    def fail_urlopen(req, **kwargs):
        calls.append(req.full_url)
        body = {"error": {"message": "insufficient credits"}} if status == 402 else {"error": {"message": "unauthorized"}}
        raise HTTPError(req.full_url, status, "err", {}, io.BytesIO(json.dumps(body).encode()))

    monkeypatch.setattr(routing.urllib.request, "urlopen", fail_urlopen)
    with routing.interview_scope(f"abort-{status}", 2), pytest.raises(DispatchDeferred, match=expected_kind):
        router.dispatch(purpose="bundle_generation", messages=[{"role": "user", "content": "hi"}])

    assert calls == [routing.NVIDIA_CHAT_URL]  # Single attempt; no retry, no OpenRouter fallback


def test_direct_provider_429_retries_once_and_falls_back_to_openrouter_free_not_paid(monkeypatch, tmp_path):
    # Case 1: 429 on first attempt, retry succeeds on NVIDIA
    router, clock = _direct_env(monkeypatch, tmp_path, content_models=(FREE_A,), allow_paid=True)
    calls: list[str] = []

    def retry_then_ok(req, **kwargs):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise HTTPError(req.full_url, 429, "rate limit", {"Retry-After": "1"}, io.BytesIO(b'{"error":"rpm"}'))
        return _FakeHTTPResponse({
            "model": routing.DEFAULT_NVIDIA_CONTENT_MODEL,
            "choices": [{"message": {"content": '{"ok": 1}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        })

    monkeypatch.setattr(routing.urllib.request, "urlopen", retry_then_ok)
    with routing.interview_scope("retry-ok", 2):
        res = router.dispatch(purpose="bundle_generation", messages=[{"role": "user", "content": "hi"}])
    assert res.provider == "nvidia"
    assert calls == [routing.NVIDIA_CHAT_URL, routing.NVIDIA_CHAT_URL]

    # Case 2: NVIDIA fails twice -> OpenRouter :free succeeds -> never paid Claude
    router2, _ = _direct_env(monkeypatch, tmp_path / "sub", content_models=(FREE_A,), allow_paid=True)
    fallback_urls: list[tuple[str, str]] = []

    def nvidia_down_or_free_ok(req, **kwargs):
        body = json.loads(req.data.decode("utf-8"))
        fallback_urls.append((req.full_url, body["model"]))
        if req.full_url == routing.NVIDIA_CHAT_URL:
            raise HTTPError(req.full_url, 429, "rate limit", {"Retry-After": "1"}, io.BytesIO(b'{"error":"rpm"}'))
        return _FakeHTTPResponse({
            "model": FREE_A,
            "choices": [{"message": {"content": '{"ok": 2}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        })

    monkeypatch.setattr(routing.urllib.request, "urlopen", nvidia_down_or_free_ok)
    with routing.interview_scope("fallback-free", 2) as scope:
        res2 = router2.dispatch(purpose="bundle_generation", messages=[{"role": "user", "content": "hi"}])
    assert res2.provider == "openrouter"
    assert res2.model == FREE_A
    assert scope.providers["bundle_generation"] == "openrouter"
    assert [u for u, _ in fallback_urls] == [routing.NVIDIA_CHAT_URL, routing.NVIDIA_CHAT_URL, routing.CHAT_URL]
    assert all(m != PAID for _, m in fallback_urls)

    # Case 3: No OpenRouter :free works + allow_paid=True -> stops (never uses paid Claude for content)
    router3, _ = _direct_env(monkeypatch, tmp_path / "sub2", content_models=(FREE_A,), allow_paid=True)
    tried_models: list[str] = []

    def all_content_fail(req, **kwargs):
        body = json.loads(req.data.decode("utf-8"))
        tried_models.append(body["model"])
        raise HTTPError(req.full_url, 503, "down", {}, io.BytesIO(b'{"error":"unavailable"}'))

    monkeypatch.setattr(routing.urllib.request, "urlopen", all_content_fail)
    with routing.interview_scope("stop-no-paid", 4), pytest.raises(DispatchDeferred):
        router3.dispatch(purpose="bundle_generation", messages=[{"role": "user", "content": "hi"}])
    assert PAID not in tried_models
    assert tried_models == [routing.DEFAULT_NVIDIA_CONTENT_MODEL, FREE_A]


def test_nvidia_40_per_minute_groq_headers_and_zero_cost_journal(monkeypatch, tmp_path):
    clock = Clock()
    budget = RequestBudget(tmp_path / "limits.json", clock=clock)
    for i in range(40):
        tok = budget.reserve(
            interview_id=f"nv-{i}", core_count=2, lane="content",
            model=routing.DEFAULT_NVIDIA_CONTENT_MODEL, free=False, provider="nvidia",
        )
        budget.release(tok)
        clock.advance(1)  # 40 calls in 40 seconds (< 60s window)

    with pytest.raises(DispatchDeferred, match="nvidia_minute"):
        budget.reserve(
            interview_id="nv-41", core_count=2, lane="content",
            model=routing.DEFAULT_NVIDIA_CONTENT_MODEL, free=False, provider="nvidia",
        )

    state = budget.snapshot()
    assert state["direct_counts"]["nvidia"] == 40
    assert state["free_count"] == 0
    assert state["cost_usd"] == 0.0

    # Advance past the oldest start -> 41st call admitted cleanly
    clock.advance(25)
    tok41 = budget.reserve(
        interview_id="nv-41", core_count=2, lane="content",
        model=routing.DEFAULT_NVIDIA_CONTENT_MODEL, free=False, provider="nvidia",
    )
    budget.release(tok41)

    # Groq header parsing + blocking
    groq_hdrs = {
        "x-ratelimit-limit-requests": "14400",
        "x-ratelimit-limit-tokens": "18000",
        "x-ratelimit-remaining-requests": "0",
        "x-ratelimit-remaining-tokens": "5000",
        "x-ratelimit-reset-requests": "2m59.56s",
        "x-ratelimit-reset-tokens": "3.44s",
    }
    parsed = parse_ratelimit_headers(groq_hdrs, clock())
    assert parsed["remaining_requests"] == 0
    assert parsed["reset_requests_s"] == pytest.approx(179.56, abs=0.01)

    decision = classify_http_error(429, "rate limited", groq_hdrs, now=clock(), lane="content")
    assert decision.kind == "rpm"
    assert decision.retry_at == pytest.approx(clock() + 179.56, abs=0.01)

    budget.record_groq_headers(groq_hdrs)
    with pytest.raises(DispatchDeferred, match="groq_rate_limit"):
        budget.reserve(
            interview_id="gq-1", core_count=2, lane="content",
            model=routing.DEFAULT_GROQ_CHECK_MODEL, free=False, provider="groq",
        )
    clock.advance(180)
    tok_gq = budget.reserve(
        interview_id="gq-1", core_count=2, lane="content",
        model=routing.DEFAULT_GROQ_CHECK_MODEL, free=False, provider="groq",
    )
    budget.release(tok_gq)
    after = budget.snapshot()
    assert after["direct_counts"]["groq"] == 1
    assert after["cost_usd"] == 0.0
    assert after["groq_limits"]["limit_requests"] == 14400


def test_cross_family_writer_and_checker_enforced(monkeypatch, tmp_path):
    # Nemotron writer rejects an OpenRouter Nemotron checker unless allow_self_check=True
    def nemotron_catalog():
        base = catalog()
        base["data"].append({
            "id": "nvidia/nemotron-checker:free",
            "pricing": {"prompt": "0", "completion": "0"},
            "context_length": 32768,
            "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
            "supported_parameters": ["structured_outputs", "response_format", "max_tokens"],
        })
        return base

    router, _ = _direct_env(
        monkeypatch, tmp_path,
        check_provider="openrouter",
        check_models=("nvidia/nemotron-checker:free", FREE_A),
    )
    router.catalog_source = nemotron_catalog
    assert router.check_candidates_with_providers() == (("openrouter", FREE_A),)

    # Non-Nemotron Groq checker is accepted with NVIDIA Nemotron writer
    router_ok, _ = _direct_env(monkeypatch, tmp_path / "ok", groq_model="openai/gpt-oss-120b")
    assert router_ok.resolve_check_provider_and_model() == ("groq", "openai/gpt-oss-120b")

    # Even if check_provider is forced to nvidia Nemotron, cross-family rule blocks without allow_self_check
    router_same = routing.InterviewRouter(
        replace(router_ok.settings, check_provider="openrouter", check_models=("nvidia/nemotron-checker:free",)),
        catalog_source=nemotron_catalog, clock=Clock(),
    )
    with routing.interview_scope("same-family", 2), pytest.raises(routing.RoutingError, match="matches generator"):
        router_same.check_candidates_with_providers()
