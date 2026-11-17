"""Step 1: offline model privacy, catalog selection, durable limits and gates."""
from __future__ import annotations

import copy
import io
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.error import HTTPError

import pytest

from modules import bundle_generator, interview_llm as routing, role_skills
from modules.interview_llm_budget import BudgetUnavailable, DispatchDeferred, RequestBudget
from modules.llm_http_policy import classify_http_error, next_utc_day

FREE_A, FREE_B = "fixture/alpha:free", "fixture/beta:free"
PAID = routing.PAID_CONVERSATION_MODEL


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 17, 10, tzinfo=timezone.utc).timestamp()

    def __call__(self):
        return self.now

    def advance(self, seconds=4):
        self.now += seconds


def catalog():
    def row(model, prompt="0", completion="0", parameters=None):
        return {"id": model, "pricing": {"prompt": prompt, "completion": completion},
                "context_length": 32768,
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
                "supported_parameters": parameters if parameters is not None else ["structured_outputs", "response_format", "max_tokens"]}
    return {"data": [row(FREE_B), row(FREE_A), row("fixture/not-structured", parameters=["response_format"]),
                     row("fixture/missing-price", prompt=None), row("fixture/negative", prompt="-1"),
                     row(PAID, "0.000001", "0.000005")]}


def http_error(status, *, source="", message="", headers=None):
    body = {"error": {"metadata": {"limit_source": source}, "message": message}}
    return HTTPError(routing.CHAT_URL, status, "fixture error", headers or {}, io.BytesIO(json.dumps(body).encode()))


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_INTERVIEW_ROUTING_ENABLED", "1")
    monkeypatch.setenv("LLM_LIVE_FETCH", "1")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.delenv("LLM_LIVE_CONSUMERS", raising=False)
    from backend.config import get_settings
    get_settings.cache_clear()
    clock = Clock()
    settings = routing.RoutingSettings(state_path=tmp_path / "limits.json")
    router = routing.InterviewRouter(settings, catalog_source=catalog, clock=clock)
    monkeypatch.setattr(routing, "get_router", lambda: router)
    role_skills.reset_role_skill_cache()
    from modules import llm_usage
    llm_usage.reset_memory_usage()
    bundle_generator.set_bundle_llm_override(None)
    role_skills.set_role_skills_llm_override(None)
    yield router, clock
    bundle_generator.set_bundle_llm_override(None)
    role_skills.set_role_skills_llm_override(None)
    role_skills.reset_role_skill_cache()
    routing._router.cache_clear()
    get_settings.cache_clear()


def send(router, *, purpose="bundle_generation", model=None, personal_text=False, override=None):
    return router.dispatch(purpose=purpose, model=model, personal_text=personal_text,
                          messages=[{"role": "user", "content": "fixture prompt"}],
                          override=override or (lambda model: ("completion", (2, 3, 5))))


def test_settings_are_separate_default_off_and_have_no_fixed_free_ids(monkeypatch):
    for key in ("AI_INTERVIEW_ROUTING_ENABLED", "INTERVIEW_CONTENT_MODELS", "INTERVIEW_CONVERSATION_MODEL",
                "ALLOW_PAID_CONTENT_FALLBACK", "OPENROUTER_FREE_HIGH_LIMIT_CONFIRMED"):
        monkeypatch.delenv(key, raising=False)
    assert not routing.enabled()
    settings = routing.RoutingSettings.from_env()
    assert settings.content_models == ()
    assert settings.conversation_model == PAID
    assert settings.allow_paid_content is False
    assert settings.high_free_limit is False
    monkeypatch.setenv("INTERVIEW_LLM_STATE_PATH", "")
    assert routing.RoutingSettings.from_env().state_path == routing.RoutingSettings.state_path
    monkeypatch.setenv("OPENROUTER_MODEL", "irrelevant/legacy")
    monkeypatch.setenv("QUESTION_LLM_MODEL", "irrelevant/question")
    monkeypatch.setenv("BUNDLE_CHECK_MODEL", "irrelevant/check")
    assert routing.RoutingSettings.from_env() == settings


def test_catalog_discovery_and_owner_order_are_validated(env):
    router, clock = env
    assert router.content_candidates() == (FREE_A, FREE_B)
    ordered = routing.InterviewRouter(replace(router.settings, content_models=(FREE_B, FREE_A)), catalog_source=catalog, clock=clock)
    assert ordered.content_candidates() == (FREE_B, FREE_A)


@pytest.mark.parametrize("model", ["fixture/unknown", PAID, "fixture/not-structured", "fixture/missing-price", "fixture/negative"])
def test_invalid_owner_id_anywhere_in_order_blocks_before_dispatch(env, model):
    router, clock = env
    invalid = routing.InterviewRouter(replace(router.settings, content_models=(FREE_A, model)), catalog_source=catalog, clock=clock)
    calls = []
    with routing.interview_scope("invalid-model", 2), pytest.raises(routing.RoutingError):
        send(invalid, override=lambda model: calls.append(model))
    assert calls == []
    assert not router.settings.state_path.exists()


@pytest.mark.parametrize("bad_price", [None, "NaN", "Infinity", "invalid", "-1", "0.01"])
def test_only_actual_zero_prices_qualify(env, bad_price):
    router, clock = env
    rows = catalog()
    for row in rows["data"]:
        if row["id"] == FREE_A:
            row["pricing"]["completion"] = bad_price
    changed = routing.InterviewRouter(router.settings, catalog_source=lambda: rows, clock=clock)
    assert changed.content_candidates() == (FREE_B,)


def test_catalog_is_lazy_refreshed_and_fails_closed(env):
    router, clock = env
    calls = []
    rows = catalog()
    router.catalog_source = lambda: calls.append(True) or copy.deepcopy(rows)
    assert calls == []
    assert router.content_candidates() == (FREE_A, FREE_B)
    router.content_candidates()
    assert len(calls) == 1
    rows["data"] = [row for row in rows["data"] if row["id"] != FREE_A]
    clock.advance(301)
    assert router.content_candidates() == (FREE_B,)
    router.catalog_source = lambda: {"data": "invalid"}
    clock.advance(301)
    with pytest.raises(routing.RoutingError, match="catalog"):
        router.content_candidates()


@pytest.mark.parametrize("parameters", ["structured_outputs", {"structured_outputs": True}])
def test_catalog_requires_a_structured_output_capability_list(env, parameters):
    router, clock = env
    rows = catalog()
    rows["data"][1]["supported_parameters"] = parameters
    changed = routing.InterviewRouter(router.settings, catalog_source=lambda: rows, clock=clock)
    assert changed.content_candidates() == (FREE_B,)


@pytest.mark.parametrize("purpose", sorted(routing.PERSONAL_PURPOSES))
@pytest.mark.parametrize("model", [FREE_A, "other/paid-model", PAID + ":free"])
def test_answer_and_resume_purposes_refuse_every_nonpaid_conversation_id(env, purpose, model):
    router, _ = env
    calls = []
    with routing.interview_scope("private", 2), pytest.raises(routing.PrivacyViolation):
        router.dispatch(purpose=purpose, model=model, personal_text=False,
                        messages=[{"role": "user", "content": "PRIVATE_ANSWER PRIVATE_RESUME"}],
                        override=lambda model: calls.append(model))
    assert calls == []
    assert not router.settings.state_path.exists()


def test_personal_content_cannot_be_relabelled_as_generic_purpose(env):
    router, _ = env
    with routing.interview_scope("private-content", 2), pytest.raises(routing.PrivacyViolation, match="content lane"):
        send(router, personal_text=True)
    assert not router.settings.state_path.exists()


def test_explicit_personal_marker_refuses_free_content_before_transport(env):
    router, _ = env
    with routing.interview_scope("free-content-answer", 2), pytest.raises(routing.PrivacyViolation, match=":free"):
        send(router, personal_text=True, model=FREE_A)


def test_unknown_purpose_cannot_default_to_content_lane(env):
    router, _ = env
    with routing.interview_scope("unknown", 2), pytest.raises(routing.RoutingError, match="Unclassified"):
        send(router, purpose="raw_resume_chat")


def test_conversation_config_is_guarded_before_catalog(env):
    router, clock = env
    invalid = routing.InterviewRouter(replace(router.settings, conversation_model=FREE_A),
                                     catalog_source=lambda: pytest.fail("Catalog must not be touched"), clock=clock)
    with routing.interview_scope("invalid-paid-setting", 2), pytest.raises(routing.PrivacyViolation):
        send(invalid, purpose="interviewer_turn")


def test_actual_http_is_gated_even_with_key_and_explicit_override_id(env, monkeypatch):
    router, _ = env
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture-key")
    with routing.interview_scope("gate", 2), pytest.raises(routing.RoutingError, match="live fetch"):
        router.dispatch(purpose="role_skill_extraction", messages=[], model=PAID)
    assert not router.settings.state_path.exists()


def test_offline_overrides_cannot_enable_catalog_network(env, monkeypatch):
    router, clock = env
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    no_catalog = routing.InterviewRouter(router.settings, clock=clock)
    with routing.interview_scope("offline-catalog", 2), pytest.raises(routing.RoutingError, match="injected"):
        send(no_catalog)


def test_interviewer_consumer_global_and_selection_gates(env, monkeypatch):
    from modules.llm_outbound_gate import LLM_CONSUMERS, llm_consumer_enabled
    router, _ = env
    assert "interviewer" in LLM_CONSUMERS
    monkeypatch.setenv("LLM_LIVE_CONSUMERS", "questions")
    assert not llm_consumer_enabled("interviewer")
    with routing.interview_scope("consumer", 2), pytest.raises(routing.RoutingError, match="consumer"):
        send(router, purpose="interviewer_turn")
    monkeypatch.setenv("LLM_LIVE_CONSUMERS", "interviewer")
    with routing.interview_scope("consumer", 2):
        assert send(router, purpose="interviewer_turn").model == PAID


def test_gate_rechecked_after_admission(env, monkeypatch):
    router, _ = env
    reserve = router.budget.reserve
    def close_gate(**kwargs):
        token = reserve(**kwargs)
        monkeypatch.setenv("LLM_LIVE_CONSUMERS", "coach")
        return token
    monkeypatch.setattr(router.budget, "reserve", close_gate)
    calls = []
    with routing.interview_scope("gate-race", 2), pytest.raises(routing.RoutingError, match="consumer"):
        send(router, override=lambda model: calls.append(model))
    assert calls == []
    assert router.budget.snapshot()["leases"] == {}


@pytest.mark.parametrize("n,lane,limit", [(2, "content", 13), (4, "content", 25), (2, "conversation", 4), (4, "conversation", 6)])
def test_per_interview_caps_persist_on_reconstruction(env, n, lane, limit):
    router, clock = env
    for _ in range(limit):
        budget = RequestBudget(router.settings.state_path, clock=clock)
        token = budget.reserve(interview_id="durable", core_count=n, lane=lane, model=PAID, free=False)
        budget.release(token)
        clock.advance()
    with pytest.raises(DispatchDeferred, match=f"{lane}_interview_cap"):
        RequestBudget(router.settings.state_path, clock=clock).reserve(
            interview_id="durable", core_count=n, lane=lane, model=PAID, free=False)


def test_daily_limit_shared_across_models_and_restart(env):
    router, clock = env
    for index in range(50):
        budget = RequestBudget(router.settings.state_path, clock=clock)
        token = budget.reserve(interview_id=f"daily-{index}", core_count=2, lane="content",
                               model=FREE_A if index % 2 else FREE_B, free=True)
        budget.release(token)
        clock.advance()
    with pytest.raises(DispatchDeferred, match="free_daily"):
        router.budget.reserve(interview_id="daily-next", core_count=2, lane="content", model=FREE_B, free=True)
    higher = RequestBudget(router.settings.state_path, high_free_limit=True, clock=clock)
    token = higher.reserve(interview_id="daily-next", core_count=2, lane="content", model=FREE_B, free=True)
    higher.release(token)
    assert higher.daily_limit == 1000
    assert higher.snapshot()["free_count"] == 51


def test_sliding_minute_counter_is_durable_not_a_fixed_bucket(env):
    router, clock = env
    # Exercise the quota counter independently of the stricter content pacer.
    for index in range(20):
        token = router.budget.reserve(interview_id=f"minute-{index}", core_count=2,
                                      lane="conversation", model=FREE_A, free=True)
        router.budget.release(token)
    reloaded = RequestBudget(router.settings.state_path, clock=clock)
    with pytest.raises(DispatchDeferred, match="free_minute"):
        reloaded.reserve(interview_id="minute-over", core_count=2, lane="conversation", model=FREE_B, free=True)
    clock.advance(60)
    token = reloaded.reserve(interview_id="minute-over", core_count=2, lane="conversation", model=FREE_B, free=True)
    reloaded.release(token)


def test_pacing_and_clock_rollback_cannot_reset_admission(env):
    router, clock = env
    token = router.budget.reserve(interview_id="clock", core_count=2, lane="content", model=FREE_A, free=True)
    router.budget.release(token)
    for delta in (1, -86400):
        clock.advance(delta)
        with pytest.raises(DispatchDeferred, match="content_pacing"):
            router.budget.reserve(interview_id="clock", core_count=2, lane="content", model=FREE_A, free=True)
    assert router.budget.snapshot()["free_count"] == 1
    clock.now = next_utc_day(clock.now + 86400) + 1
    state = router.budget.snapshot()
    assert state["free_count"] == 0
    assert state["interviews"]["clock"]["content"] == 1


def test_two_concurrent_reservations_across_independent_instances(env):
    router, clock = env
    barrier = threading.Barrier(3)
    release = threading.Event()
    def hold(index):
        budget = RequestBudget(router.settings.state_path, clock=clock)
        token = budget.reserve(interview_id=f"parallel-{index}", core_count=2, lane="conversation", model=PAID, free=False)
        barrier.wait(timeout=10)
        assert release.wait(timeout=10)
        budget.release(token)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(hold, i) for i in range(2)]
        try:
            barrier.wait(timeout=10)
            with pytest.raises(DispatchDeferred, match="concurrency"):
                router.budget.reserve(interview_id="third", core_count=2, lane="conversation", model=PAID, free=False)
        finally:
            release.set()
        for future in futures:
            future.result(timeout=10)
    assert router.budget.snapshot()["total_count"] == 2


def test_restart_reclaims_a_dead_process_without_refunding_its_attempt(env):
    router, clock = env
    code = """import sys
from pathlib import Path
from modules.interview_llm_budget import RequestBudget
b = RequestBudget(Path(sys.argv[1]), clock=lambda: float(sys.argv[2]))
b.reserve(interview_id='crashed', core_count=2, lane='conversation', model='paid', free=False)
"""
    subprocess.run([sys.executable, "-c", code, str(router.settings.state_path), str(clock())], check=True, timeout=20)
    state = router.budget.snapshot()
    assert state["leases"] == {}
    assert state["interviews"]["crashed"]["conversation"] == 1


@pytest.mark.parametrize("invalid", ["not json", "{}", '{"version": 1, "host": "another-host", "accounts": {}}'])
def test_corrupt_or_foreign_journal_fails_closed(env, invalid):
    router, _ = env
    router.settings.state_path.write_text(invalid)
    with routing.interview_scope("corrupt", 2), pytest.raises(BudgetUnavailable):
        send(router)
    assert router.settings.state_path.read_text() == invalid


def test_state_write_failure_prevents_transport(env, monkeypatch):
    router, _ = env
    monkeypatch.setattr(os, "replace", lambda *a: (_ for _ in ()).throw(OSError("unavailable disk")))
    calls = []
    with routing.interview_scope("disk", 2), pytest.raises(BudgetUnavailable):
        send(router, override=lambda model: calls.append(model))
    assert calls == []


def test_scope_and_core_budget_cannot_be_missing_or_resized(env):
    router, _ = env
    with pytest.raises(routing.RoutingError, match="Missing interview_scope"):
        send(router)
    with routing.interview_scope("same-id", 2):
        send(router, purpose="role_skill_extraction")
    with routing.interview_scope("same-id", 4), pytest.raises(BudgetUnavailable, match="resized"):
        send(router, purpose="role_skill_extraction")


@pytest.mark.parametrize("status", [402, 429])
def test_daily_errors_stop_all_free_fallbacks_and_persist(env, status):
    router, clock = env
    calls = []
    def capped(model):
        calls.append(model)
        raise http_error(status, source="openrouter_free_tier_daily")
    with routing.interview_scope("daily-error", 2), pytest.raises(DispatchDeferred, match="free_daily"):
        send(router, override=capped)
    clock.advance()
    rebuilt = routing.InterviewRouter(router.settings, catalog_source=catalog, clock=clock)
    with routing.interview_scope("new-interview", 2), pytest.raises(DispatchDeferred, match="free_daily"):
        send(rebuilt, override=lambda model: calls.append(model))
    assert calls == [FREE_A]
    assert rebuilt.budget.snapshot()["free_count"] == 1


def test_paid_content_fallback_requires_explicit_flag_and_guard(env):
    router, clock = env
    with routing.interview_scope("paid-fallback", 2), pytest.raises(DispatchDeferred):
        send(router, override=lambda model: (_ for _ in ()).throw(http_error(429, source="openrouter_free_tier_daily")))
    clock.advance()
    opted_in = routing.InterviewRouter(replace(router.settings, allow_paid_content=True), catalog_source=catalog, clock=clock)
    with routing.interview_scope("paid-fallback", 2) as scope:
        assert send(opted_in).model == PAID
        assert scope.models["bundle_generation"] == PAID
    with routing.interview_scope("private-fallback", 2), pytest.raises(routing.PrivacyViolation):
        send(opted_in, personal_text=True)
    assert opted_in.budget.snapshot()["total_count"] == 2


def test_provider_unavailability_uses_next_validated_model_on_retry(env):
    router, clock = env
    with routing.interview_scope("fallback", 2), pytest.raises(DispatchDeferred, match="model_unavailable"):
        send(router, override=lambda model: (_ for _ in ()).throw(http_error(503)))
    clock.advance()
    with routing.interview_scope("fallback", 2):
        assert send(router).model == FREE_B
    assert router.budget.snapshot()["interviews"]["fallback"]["content"] == 2


def test_retry_rechecks_privacy_without_spending_another_attempt(env):
    router, clock = env
    with routing.interview_scope("retry", 2), pytest.raises(DispatchDeferred, match="rpm"):
        send(router, override=lambda model: (_ for _ in ()).throw(http_error(429, headers={"Retry-After": "4"})))
    clock.advance()
    with routing.interview_scope("retry", 2), pytest.raises(routing.PrivacyViolation):
        send(router, personal_text=True)
    assert router.budget.snapshot()["total_count"] == 1


def test_credit_exhaustion_does_not_retry_or_use_paid_content(env):
    router, clock = env
    opted_in = routing.InterviewRouter(replace(router.settings, allow_paid_content=True), catalog_source=catalog, clock=clock)
    with routing.interview_scope("credits", 2), pytest.raises(DispatchDeferred, match="credits"):
        send(opted_in, override=lambda model: (_ for _ in ()).throw(http_error(402, source="openrouter_credits")))
    clock.advance(86400)
    with routing.interview_scope("credits-next", 2), pytest.raises(DispatchDeferred, match="credits"):
        send(opted_in)
    opted_in.budget.clear_credit_block()
    with routing.interview_scope("credits-next", 2):
        assert send(opted_in).model == FREE_A
    assert opted_in.budget.snapshot()["total_count"] == 2


def test_timeout_spends_one_attempt_and_releases_capacity(env):
    router, _ = env
    with routing.interview_scope("timeout", 2), pytest.raises(DispatchDeferred, match="timeout"):
        send(router, override=lambda model: (_ for _ in ()).throw(TimeoutError()))
    state = router.budget.snapshot()
    assert state["total_count"] == 1
    assert state["leases"] == {}


def test_usage_logs_actual_failed_model_once_without_private_error_body(env):
    from modules import llm_usage
    router, _ = env
    with routing.interview_scope("private-errors", 2), pytest.raises(DispatchDeferred):
        send(router, purpose="resume_extraction", override=lambda model: (_ for _ in ()).throw(
            http_error(429, message="PRIVATE_RESUME_TOKEN")))
    events = llm_usage.list_usage_events()
    assert len(events) == 1
    assert events[0]["model"] == PAID
    assert events[0]["status"] == "error"
    assert events[0]["error"] == "unknown_quota"
    assert "PRIVATE_RESUME_TOKEN" not in json.dumps(events, default=str)
    assert "PRIVATE_RESUME_TOKEN" not in router.settings.state_path.read_text()


def test_new_bundle_boundary_cannot_bypass_closed_global_flag_with_allow_live(env, monkeypatch):
    router, _ = env
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    with routing.interview_scope("global-bypass", 2), pytest.raises(bundle_generator.BundleGenerationError, match="disabled"):
        bundle_generator._call_bundle_llm(purpose="bundle_generation", provider="openrouter", model=PAID,
                                        messages=[], allow_live=True)
    assert not router.settings.state_path.exists()


@pytest.mark.parametrize("status,source,kind", [
    (402, "openrouter_free_tier_daily", "free_daily"), (429, "openrouter_free_tier_daily", "free_daily"),
    (402, "openrouter_in_flight_budget", "in_flight"), (429, "openrouter_free_tier_per_minute", "rpm"),
    (429, "upstream_provider_shared_pool", "upstream"), (402, "openrouter_key_limit", "credits"),
    (429, "openrouter_credits", "credits"), (429, "", "unknown_quota"), (404, "", "model_unavailable"),
])
def test_http_classification_uses_body_not_status_alone(status, source, kind):
    error = http_error(status, source=source)
    decision = classify_http_error(status, error.read(), error.headers, now=1000)
    assert decision.kind == kind


@pytest.mark.parametrize("header", [
    {"Retry-After": "12"},
    {"Retry-After": format_datetime(datetime.fromtimestamp(1700000012, timezone.utc))},
    {"X-RateLimit-Reset": "1700000012"},
    {"x-ratelimit-reset": "1700000012000"},
])
def test_retry_reset_headers_are_parsed_conservatively(header):
    decision = classify_http_error(429, "rate limited", header, now=1700000000)
    assert decision.kind == "rpm"
    assert decision.retry_at == 1700000012


def test_plain_text_daily_402_and_unknown_429_never_spin():
    assert classify_http_error(402, "Free daily quota reached", {}, now=1000).kind == "free_daily"
    assert classify_http_error(429, "something unknown", {}, now=1000).kind == "unknown_quota"


def test_bundle_and_role_existing_override_hooks_use_separate_models(env, monkeypatch):
    router, clock = env
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")  # explicit offline hooks, injected catalog
    seen = []
    bundle_generator.set_bundle_llm_override(lambda **kwargs: seen.append(kwargs) or {"content": "bundle result"})
    role_skills.set_role_skills_llm_override(lambda **kwargs: {
        "role_title": "Backend engineer", "domain": "Software",
        "skills": [{"name": "Python", "topics": ["Concurrency"], "weight": 0.8}],
    })
    with routing.interview_scope("adapters", 2):
        assert bundle_generator.resolve_generation_provider_and_model() == ("openrouter", FREE_A)
        assert bundle_generator.resolve_checker_provider_and_model() == ("openrouter", FREE_A)
        assert bundle_generator._call_bundle_llm(purpose="bundle_generation", provider="legacy", model="legacy",
                                                messages=[{"role": "user", "content": "generic"}]) == "bundle result"
        role = role_skills.extract_role_skills(role="Backend engineer", jd_text="PRIVATE_RESUME_MARKER")
    assert seen[0]["model"] == FREE_A
    assert "PRIVATE_RESUME_MARKER" not in json.dumps(seen)
    assert role["model"] == PAID
    from modules import llm_usage
    events = llm_usage.list_usage_events()
    assert any(event["purpose"] == "bundle_generation" and event["model"] == FREE_A for event in events)
    assert any(event["purpose"] == "role_skill_extraction" and event["model"] == PAID for event in events)


@pytest.mark.parametrize("shape", ["dict", "json", "list"])
def test_paid_role_adapter_preserves_existing_override_return_formats(env, monkeypatch, shape):
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    payload = {"role_title": "Engineer", "domain": "Software",
               "skills": [{"name": "Python", "topics": ["Concurrency"], "weight": 0.8}]}
    raw = payload if shape == "dict" else json.dumps(payload) if shape == "json" else ["Python"]
    role_skills.set_role_skills_llm_override(lambda **kwargs: raw)
    with routing.interview_scope("override-shape", 2):
        result = role_skills.extract_role_skills(role="Engineer")
    assert result["skills"] == ["Python"]
    assert result["model"] == PAID
    assert result["offline_uncached"] is False


@pytest.mark.parametrize("routing_on", [False, True])
def test_bundle_and_role_dispatch_honor_consumer_denial_including_overrides(env, monkeypatch, routing_on):
    monkeypatch.setenv("AI_INTERVIEW_ROUTING_ENABLED", str(int(routing_on)))
    monkeypatch.setenv("LLM_LIVE_CONSUMERS", "coach,narration")
    calls = []
    bundle_generator.set_bundle_llm_override(lambda **kw: calls.append(kw))
    role_skills.set_role_skills_llm_override(lambda **kw: calls.append(kw))
    with pytest.raises(bundle_generator.BundleGenerationError, match="consumer"):
        bundle_generator._call_bundle_llm(purpose="bundle_generation", provider="openrouter", model=PAID, messages=[])
    assert role_skills.extract_role_skills(role="No cached role")["offline_uncached"] is True
    assert calls == []


def test_flag_off_transcript_matches_pre_step1_capture(monkeypatch, tmp_path):
    from tests.ai_routing_harness import capture
    expected = json.loads(Path(__file__).with_name("fixtures").joinpath("ai_routing_flag_off.json").read_text())
    assert capture(monkeypatch, tmp_path) == expected
