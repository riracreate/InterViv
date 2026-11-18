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
        "GROQ_CONTENT_BACKUP_MODEL", "INTERVIEW_ALLOW_SELF_CHECK",
    ):
        monkeypatch.delenv(key, raising=False)
    defaults = routing.RoutingSettings.from_env()
    assert defaults == routing.RoutingSettings()
    assert defaults.direct_providers_enabled is False
    assert defaults.allow_self_check is False
    assert defaults.nvidia_content_model == "nvidia/nemotron-3.5-super-vl-120b-a12b"
    assert defaults.groq_content_backup_model == "qwen/qwen3.8-27b"
    assert defaults.groq_check_model == "openai/gpt-oss-120b"

    router, clock = _direct_env(monkeypatch, tmp_path)
    sent: list[tuple[str, dict, dict]] = []

    def fake_urlopen(req, **kwargs):
        body = json.loads(req.data.decode("utf-8"))
        hdrs = {k.lower(): v for k, v in req.header_items()}
        sent.append((req.full_url, body, hdrs))
        if req.full_url == routing.NVIDIA_CHAT_URL:
            return _FakeHTTPResponse({
                "model": "private/nvidia/nemotron-3.5-super-120b-a12b",
                "choices": [{"message": {"content": "<think>internal</think>{\"ok\": true}"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            })
        assert req.full_url == routing.GROQ_CHAT_URL
        content = "Candidate answer text." if body.get("response_format") is None else "{\"root_cause\": \"ok\"}"
        return _FakeHTTPResponse({
            "model": body["model"],
            "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 6, "total_tokens": 16},
        }, headers={"x-ratelimit-remaining-requests": "99", "x-ratelimit-remaining-tokens": "9000"})

    monkeypatch.setattr(routing.urllib.request, "urlopen", fake_urlopen)
    with routing.interview_scope("per-lane", 2) as scope:
        assert bundle_generator.resolve_generation_provider_and_model() == (
            "nvidia", "nvidia/nemotron-3.5-super-vl-120b-a12b",
        )
        assert bundle_generator.resolve_checker_provider_and_model() == (
            "groq", "openai/gpt-oss-120b",
        )
        gen = router.dispatch(purpose="bundle_generation", messages=[{"role": "user", "content": "Write bundle"}])
        clock.advance(4)
        blind = router.dispatch(
            purpose="bundle_blind_answer",
            messages=[{"role": "user", "content": "Answer question"}],
            max_tokens=380,
            expect_json=False,
        )
        clock.advance(4)
        chk = router.dispatch(
            purpose="bundle_check_audit",
            messages=[{"role": "user", "content": "Audit bundle"}],
            max_tokens=400,
        )

    assert gen.provider == "nvidia"
    assert gen.requested_model == "nvidia/nemotron-3.5-super-vl-120b-a12b"
    assert gen.model == "private/nvidia/nemotron-3.5-super-120b-a12b"
    assert gen.text == '{"ok": true}'  # thinking tags safety-net stripped
    assert scope.providers["bundle_generation"] == "nvidia"
    assert scope.models["bundle_generation"] == "private/nvidia/nemotron-3.5-super-120b-a12b"

    assert blind.provider == "groq"
    assert chk.provider == "groq"
    assert chk.model == "openai/gpt-oss-120b"
    assert scope.providers["bundle_check_audit"] == "groq"

    # NVIDIA writer: strict json_schema, chat_template_kwargs, no system prompt switch, User-Agent
    assert sent[0][0] == routing.NVIDIA_CHAT_URL
    assert sent[0][1]["messages"] == [{"role": "user", "content": "Write bundle"}]
    assert sent[0][1]["chat_template_kwargs"] == {"enable_thinking": False}
    assert sent[0][1]["response_format"]["type"] == "json_schema"
    assert sent[0][1]["response_format"]["json_schema"]["strict"] is True
    assert sent[0][2]["user-agent"] == routing.DIRECT_PROVIDER_USER_AGENT

    # Groq checker blind answer: reasoning_effort low, max_tokens sized above answer budget, User-Agent
    assert sent[1][0] == routing.GROQ_CHAT_URL
    assert sent[1][1]["reasoning_effort"] == "low"
    assert sent[1][1]["max_tokens"] == 380 + routing.DEFAULT_CONTENT_REASONING_MAX_TOKENS
    assert "response_format" not in sent[1][1]
    assert sent[1][2]["user-agent"] == routing.DIRECT_PROVIDER_USER_AGENT

    # Groq checker audit: strict json_schema, reasoning_effort low, max_tokens sized, User-Agent
    assert sent[2][0] == routing.GROQ_CHAT_URL
    assert sent[2][1]["reasoning_effort"] == "low"
    assert sent[2][1]["max_tokens"] == 400 + routing.DEFAULT_CONTENT_REASONING_MAX_TOKENS
    assert sent[2][1]["response_format"]["type"] == "json_schema"
    assert sent[2][1]["response_format"]["json_schema"]["strict"] is True
    assert sent[2][2]["user-agent"] == routing.DIRECT_PROVIDER_USER_AGENT

    # Budget journal records served model name next to requested ID
    journal_state = router.budget.snapshot()
    served = journal_state["served_models"]["nvidia/nemotron-3.5-super-vl-120b-a12b"]
    assert served == {
        "requested_model": "nvidia/nemotron-3.5-super-vl-120b-a12b",
        "served_model": "private/nvidia/nemotron-3.5-super-120b-a12b",
        "provider": "nvidia",
    }


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

    # Writer without strict json_schema support is refused
    router_no_schema, _ = _direct_env(
        monkeypatch, tmp_path / "noschema", nvidia_model="nvidia/llama-3.3-nemotron-super-49b-v1.5"
    )
    with routing.interview_scope("no-schema", 2), pytest.raises(routing.RoutingError, match="json_schema"):
        router_no_schema.dispatch(purpose="bundle_generation", messages=[{"role": "user", "content": "x"}])

    # Content lane never emits json_object
    for purpose in ("bundle_generation", "bundle_regeneration", "bundle_check_audit"):
        fmt = routing.response_format_for(purpose, "content", True)
        assert fmt is not None and fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True
    assert routing.response_format_for("bundle_blind_answer", "content", True) is None
    with pytest.raises(routing.RoutingError, match="json_object"):
        routing.response_format_for("unexpected_json_purpose", "content", True)
    with pytest.raises(routing.RoutingError, match="json_object"):
        routing.InterviewRouter._chat_direct_once(
            "nvidia", routing.DEFAULT_NVIDIA_CONTENT_MODEL, [{"role": "user", "content": "x"}],
            100, 0.1, 10, True, response_format={"type": "json_object"},
        )

    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    with pytest.raises(routing.RoutingError, match="LLM_LIVE_FETCH=1"):
        routing.check_nvidia_json_schema_support()

    probe_requests = []

    def ok_opener(req):
        probe_requests.append((json.loads(req.data.decode("utf-8")), {k.lower(): v for k, v in req.header_items()}))
        return _FakeHTTPResponse({"choices": [{"message": {"content": '{"ok": true}'}}]})

    ok_probe = routing.check_nvidia_json_schema_support(opener=ok_opener)
    assert ok_probe["json_schema_supported"] is True
    assert probe_requests[0][0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert probe_requests[0][1]["user-agent"] == routing.DIRECT_PROVIDER_USER_AGENT

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


def test_direct_provider_429_retries_once_and_falls_back_through_qwen_then_openrouter_free_not_paid(
    monkeypatch, tmp_path, caplog
):
    # Case 1: 429 on first attempt, retry succeeds on NVIDIA (backup Qwen is NOT called)
    router, clock = _direct_env(monkeypatch, tmp_path, content_models=(FREE_A,), allow_paid=True)
    calls: list[str] = []

    def retry_then_ok(req, **kwargs):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise HTTPError(req.full_url, 429, "rate limit", {"Retry-After": "1"}, io.BytesIO(b'{"error":"rpm"}'))
        return _FakeHTTPResponse({
            "model": "private/nvidia/nemotron-3.5-super-120b-a12b",
            "choices": [{"message": {"content": '{"ok": 1}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
        })

    monkeypatch.setattr(routing.urllib.request, "urlopen", retry_then_ok)
    with routing.interview_scope("retry-ok", 2):
        res = router.dispatch(purpose="bundle_generation", messages=[{"role": "user", "content": "hi"}])
    assert res.provider == "nvidia"
    assert calls == [routing.NVIDIA_CHAT_URL, routing.NVIDIA_CHAT_URL]

    # Case 2: NVIDIA fails (503 model_unavailable) -> logs fallback and uses Groq qwen/qwen3.8-27b backup writer with effort=none
    router_qwen, _ = _direct_env(monkeypatch, tmp_path / "qwen_backup", content_models=(FREE_A,), allow_paid=True)
    qwen_calls: list[tuple[str, dict, dict]] = []

    def nvidia_fails_qwen_ok(req, **kwargs):
        body = json.loads(req.data.decode("utf-8"))
        hdrs = {k.lower(): v for k, v in req.header_items()}
        qwen_calls.append((req.full_url, body, hdrs))
        if req.full_url == routing.NVIDIA_CHAT_URL:
            raise HTTPError(req.full_url, 503, "unavailable", {}, io.BytesIO(b'{"error":"upstream"}'))
        return _FakeHTTPResponse({
            "model": "qwen/qwen3.8-27b",
            "choices": [{"message": {"content": '{"ok": "qwen"}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10},
        })

    monkeypatch.setattr(routing.urllib.request, "urlopen", nvidia_fails_qwen_ok)
    import logging
    with caplog.at_level(logging.WARNING, logger=routing.LOGGER.name), routing.interview_scope("nv-to-qwen", 2) as scope:
        res_q = router_qwen.dispatch(purpose="bundle_generation", messages=[{"role": "user", "content": "hi"}])
    assert res_q.provider == "groq"
    assert res_q.model == "qwen/qwen3.8-27b"
    assert scope.providers["bundle_generation"] == "groq"
    assert [u for u, _, _ in qwen_calls] == [routing.NVIDIA_CHAT_URL, routing.GROQ_CHAT_URL]
    assert qwen_calls[1][1]["model"] == "qwen/qwen3.8-27b"
    assert qwen_calls[1][1]["reasoning_effort"] == "none"
    assert qwen_calls[1][1]["response_format"]["type"] == "json_schema"
    assert qwen_calls[1][2]["user-agent"] == routing.DIRECT_PROVIDER_USER_AGENT
    assert any("interview_llm_writer_fallback" in r.message and "qwen/qwen3.8-27b" in r.message for r in caplog.records)

    # Case 3: NVIDIA and Groq backup fail -> OpenRouter :free succeeds -> never paid Claude
    router2, _ = _direct_env(monkeypatch, tmp_path / "sub", content_models=(FREE_A,), allow_paid=True)
    fallback_urls: list[tuple[str, str]] = []

    def direct_down_free_ok(req, **kwargs):
        body = json.loads(req.data.decode("utf-8"))
        fallback_urls.append((req.full_url, body["model"]))
        if req.full_url in {routing.NVIDIA_CHAT_URL, routing.GROQ_CHAT_URL}:
            raise HTTPError(req.full_url, 429, "rate limit", {"Retry-After": "1"}, io.BytesIO(b'{"error":"rpm"}'))
        return _FakeHTTPResponse({
            "model": FREE_A,
            "choices": [{"message": {"content": '{"ok": 2}'}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        })

    monkeypatch.setattr(routing.urllib.request, "urlopen", direct_down_free_ok)
    with routing.interview_scope("fallback-free", 2) as scope:
        res2 = router2.dispatch(purpose="bundle_generation", messages=[{"role": "user", "content": "hi"}])
    assert res2.provider == "openrouter"
    assert res2.model == FREE_A
    assert scope.providers["bundle_generation"] == "openrouter"
    assert [u for u, _ in fallback_urls] == [
        routing.NVIDIA_CHAT_URL, routing.NVIDIA_CHAT_URL,
        routing.GROQ_CHAT_URL, routing.GROQ_CHAT_URL,
        routing.CHAT_URL,
    ]
    assert all(m != PAID for _, m in fallback_urls)

    # Case 4: No OpenRouter :free works + allow_paid=True -> stops (never uses paid Claude for content)
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
    assert tried_models == [routing.DEFAULT_NVIDIA_CONTENT_MODEL, routing.DEFAULT_GROQ_CONTENT_BACKUP_MODEL, FREE_A]


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

    # Served private/nvidia/... identifier still counts as nvidia/nemotron family
    assert routing._same_writer_family(
        "openrouter", "nvidia/nemotron-checker:free", "nvidia", "private/nvidia/nemotron-3.5-super-120b-a12b"
    ) is True

    # Qwen backup writer and gpt-oss checker are different families (allowed even on same Groq provider)
    assert routing.model_family("qwen/qwen3.8-27b", "groq") == "qwen"
    assert routing.model_family("openai/gpt-oss-120b", "groq") == "gpt-oss"
    assert routing._same_writer_family("groq", "openai/gpt-oss-120b", "groq", "qwen/qwen3.8-27b") is False
    assert router_ok.check_candidates_with_providers(
        generator_provider="groq", generator_model="qwen/qwen3.8-27b",
    ) == (("groq", "openai/gpt-oss-120b"),)


@pytest.mark.parametrize("provider,model", [
    ("nvidia", "nvidia/nemotron-3.5-super-vl-120b-a12b"),
    ("groq", "openai/gpt-oss-120b"),
    ("openrouter", FREE_A),
])
def test_privacy_lock_allowlist_and_env_example(monkeypatch, tmp_path, provider, model):
    assert routing.ALLOWED_BUNDLE_PURPOSES == frozenset({
        "bundle_generation", "bundle_regeneration", "bundle_blind_answer", "bundle_check_audit",
    })
    for allowed_purpose in sorted(routing.ALLOWED_BUNDLE_PURPOSES):
        routing.enforce_outbound_policy(purpose=allowed_purpose, model=model, personal_text=False, provider=provider)
        with pytest.raises(routing.PrivacyViolation):
            routing.enforce_outbound_policy(purpose=allowed_purpose, model=model, personal_text=True, provider=provider)

    for forbidden in ("unknown_future_task", "custom_summary", "raw_resume_chat", *sorted(routing.PERSONAL_PURPOSES)):
        with pytest.raises(routing.PrivacyViolation):
            routing.enforce_outbound_policy(purpose=forbidden, model=model, personal_text=False, provider=provider)

    router, _ = _direct_env(
        monkeypatch, tmp_path,
        content_provider="groq" if provider == "groq" else "nvidia",
        content_models=(FREE_A,) if provider == "openrouter" else (),
        nvidia_model="nvidia/nemotron-3.5-super-vl-120b-a12b",
    )
    with routing.interview_scope("unknown-allowlist", 2), pytest.raises(routing.PrivacyViolation):
        router.dispatch(purpose="unknown_future_task", messages=[{"role": "user", "content": "hi"}], provider=provider, model=model)

    from pathlib import Path
    env_example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "# INTERVIEW_ALLOW_SELF_CHECK=false" in env_example
    assert "\nINTERVIEW_ALLOW_SELF_CHECK=" not in env_example
