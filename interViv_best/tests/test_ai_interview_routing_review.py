"""Offline regressions for the seven step-1b reviewer probes."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import replace
from pathlib import Path
from urllib.error import URLError

import pytest

from modules import bundle_generator, interview_llm as routing, llm_usage, role_skills
from modules.interview_llm_budget import BudgetUnavailable, DispatchDeferred, RequestBudget
from modules.llm_http_policy import LimitDecision, classify_http_error
from scripts import interview_llm_status, list_interview_content_models, pregenerate_bundles
from tests.test_ai_interview_routing import FREE_A, FREE_B, PAID, catalog, env, http_error, send


def model_row(model="mid/good-27b:free", *, context=32768, inputs=None, outputs=None):
    return {"id": model, "context_length": context,
            "architecture": {"input_modalities": inputs or ["text"], "output_modalities": outputs or ["text"]},
            "pricing": {"prompt": "0", "completion": "0"},
            "supported_parameters": ["structured_outputs", "response_format", "max_tokens"]}


def pinned_router(env, **changes):
    router, _ = env
    router.settings = replace(router.settings, content_models=(FREE_A, FREE_B), **changes)
    return router


class Response:
    def __init__(self, data):
        self.data = data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps(self.data).encode()


def mock_completion(monkeypatch, returned_model, *, calls=None):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture-key-never-live")
    def urlopen(request, **kwargs):
        assert request.full_url == routing.CHAT_URL
        if calls is not None:
            calls.append(json.loads(request.data))
        return Response({"model": returned_model,
                         "choices": [{"message": {"content": "fixture answer"}, "finish_reason": "stop"}],
                         "usage": {"prompt_tokens": 7, "completion_tokens": 11}})
    monkeypatch.setattr(routing.urllib.request, "urlopen", urlopen)


def test_catalog_probe_filters_tiny_reranker_router_and_keeps_chat_models(env):
    router, _ = env
    rows = [model_row("aaa/tiny-1b:free", context=8192), model_row("aab/reranker:free"),
            model_row("mid/good-27b:free"), model_row("zeta/strong-70b:free"), model_row("openrouter/free")]
    router.catalog_source = lambda: {"data": rows}
    assert router.content_candidates() == ("mid/good-27b:free", "zeta/strong-70b:free")


@pytest.mark.parametrize("change", [
    {"architecture": {"input_modalities": ["image"], "output_modalities": ["text"]}},
    {"architecture": {"input_modalities": ["text"], "output_modalities": ["embedding"]}},
    {"architecture": {"input_modalities": ["text"], "output_modalities": ["image"]}},
    {"architecture": {}}, {"type": "reranker"}, {"model_type": "embedding"}, {"type": []},
    {"context_length": None}, {"context_length": 8192}, {"context_length": True},
    {"top_provider": {"context_length": 8192}},
    {"supported_parameters": ["structured_outputs", "max_tokens"]},
    {"supported_parameters": ["response_format", "max_tokens"]},
    {"supported_parameters": ["response_format", "structured_outputs"]},
    {"supported_parameters": ["response_format", "structured_outputs", "max_tokens", {}]},
])
def test_content_catalog_requires_text_chat_context_and_both_json_capabilities(change):
    assert not routing._free_structured({**model_row(), **change})


def test_configured_context_minimum_and_text_capable_input(env):
    router, _ = env
    row = model_row(inputs=["text", "image"])
    assert routing._free_structured(row)
    assert not routing._free_structured(row, min_context=65536)
    with pytest.raises(routing.RoutingError, match="context"):
        routing.InterviewRouter(replace(router.settings, min_content_context=0), catalog_source=catalog)


def test_real_content_dispatch_requires_owner_order_before_catalog_or_transport(env):
    router, _ = env
    router.catalog_source = lambda: pytest.fail("Unapproved discovery must not fetch even the catalog")
    with routing.interview_scope("no-owner-order", 2), pytest.raises(routing.RoutingError, match="INTERVIEW_CONTENT_MODELS"):
        router.dispatch(purpose="bundle_generation", messages=[])
    assert not router.settings.state_path.exists()


@pytest.mark.parametrize("discovery", [False, True])
def test_real_content_dispatch_accepts_pinned_order_or_explicit_discovery(env, monkeypatch, discovery):
    router, _ = env
    router.settings = replace(router.settings, content_models=() if discovery else (FREE_A,), allow_content_discovery=discovery)
    calls = []
    mock_completion(monkeypatch, FREE_A, calls=calls)
    with routing.interview_scope("approved-model-order", 2):
        result = router.dispatch(purpose="bundle_generation", messages=[])
    assert result.model == FREE_A
    assert len(calls) == 1
    assert calls[0]["response_format"] == {"type": "json_object"}


def test_discovery_is_default_off_and_env_can_explicitly_enable_it(monkeypatch):
    monkeypatch.delenv("INTERVIEW_ALLOW_CONTENT_DISCOVERY", raising=False)
    assert routing.RoutingSettings.from_env().allow_content_discovery is False
    monkeypatch.setenv("INTERVIEW_ALLOW_CONTENT_DISCOVERY", "true")
    monkeypatch.setenv("INTERVIEW_CONTENT_MIN_CONTEXT", "65536")
    settings = routing.RoutingSettings.from_env()
    assert settings.allow_content_discovery is True
    assert settings.min_content_context == 65536


def test_catalog_script_is_read_only_and_never_calls_completion(env, monkeypatch, capsys):
    router, _ = env
    monkeypatch.setattr(routing.InterviewRouter, "_chat_once", lambda *a: pytest.fail("No completion is permitted"))
    assert list_interview_content_models.main([], catalog_source=catalog) == 0
    output = capsys.readouterr().out
    assert "id\tcontext_length\tparameters" in output
    assert f"{FREE_A}\t32768\t" in output and "response_format" in output
    assert PAID not in output and "not-structured" not in output
    assert not router.settings.state_path.exists()


@pytest.mark.parametrize("live,consumers", [("0", "questions"), ("1", "coach")])
def test_catalog_script_requires_live_flag_and_questions_consumer(env, monkeypatch, live, consumers):
    monkeypatch.setenv("LLM_LIVE_FETCH", live)
    monkeypatch.setenv("LLM_LIVE_CONSUMERS", consumers)
    with pytest.raises(SystemExit) as error:
        list_interview_content_models.main([], catalog_source=lambda: pytest.fail("No catalog fetch"))
    assert error.value.code == 2


@pytest.mark.parametrize("status,kind", [(400, "model_unavailable"), (401, "authorization"), (403, "authorization"),
                                        (408, "model_unavailable"), (422, "model_unavailable"),
                                        (500, "model_unavailable"), (504, "model_unavailable"), (529, "model_unavailable")])
def test_reviewed_http_statuses_have_backoff_or_operator_stop(status, kind):
    decision = classify_http_error(status, "fixture", {}, now=1000)
    assert decision.kind == kind
    assert decision.retry_at is not None if kind == "model_unavailable" else decision.retry_at is None


@pytest.mark.parametrize("status", [400, 422])
def test_rejected_content_model_does_not_repeat_for_fourteen_more_admissions(env, status):
    router, clock = env
    calls = []
    def transport(model):
        calls.append(model)
        if model == FREE_A:
            raise http_error(status)
        return "next candidate", (1, 1, 2)
    with routing.interview_scope("fourteen-probe", 4), pytest.raises(DispatchDeferred, match="model_unavailable"):
        send(router, override=transport)
    for _ in range(14):
        clock.advance()
        with routing.interview_scope("fourteen-probe", 4):
            assert send(router, override=transport).model == FREE_B
    assert calls == [FREE_A] + [FREE_B] * 14
    assert router.budget.snapshot()["interviews"]["fourteen-probe"]["content"] == 15


@pytest.mark.parametrize("status", [401, 403])
def test_authorization_stop_survives_restart_days_and_credit_clear(env, status):
    router, clock = env
    with routing.interview_scope("access", 2), pytest.raises(DispatchDeferred, match="authorization"):
        send(router, override=lambda model: (_ for _ in ()).throw(http_error(status)))
    clock.advance(86400)
    restarted = RequestBudget(router.settings.state_path, clock=clock)
    restarted.clear_credit_block()
    with routing.interview_scope("new-access", 2), pytest.raises(DispatchDeferred, match="authorization"):
        send(router)
    assert restarted.snapshot()["total_count"] == 1
    restarted.clear_access_block()
    with routing.interview_scope("new-access", 2):
        assert send(router).model == FREE_A


@pytest.mark.parametrize("reason,kind", [(TimeoutError("connect timed out"), "timeout"),
                                        (OSError("network down"), "network_unavailable")])
def test_urlerror_is_a_typed_deferral_and_logs_once(env, monkeypatch, caplog, reason, kind):
    router, clock = env
    monkeypatch.setenv("OPENROUTER_API_KEY", "fixture-only")
    monkeypatch.setattr(routing.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(URLError(reason)))
    with caplog.at_level(logging.INFO, logger=routing.LOGGER.name):
        with routing.interview_scope("network", 2), pytest.raises(DispatchDeferred) as error:
            router.dispatch(purpose="role_skill_extraction", messages=[])
    assert error.value.reason == kind
    assert error.value.retry_at == clock() + 4
    events = llm_usage.list_usage_events()
    assert len(events) == 1 and events[0]["error"] == kind
    records = [record for record in caplog.records if record.name == routing.LOGGER.name]
    assert len(records) == 1 and records[0].returned_model is None
    assert router.budget.snapshot()["leases"] == {}


@pytest.mark.parametrize("returned,accepted", [
    (PAID, True), (PAID + "-20251001", True), (PAID + "-2025-10-01", True),
    (PAID + "-20250230", False), (PAID + ":free", False),
    (PAID + "-20251001:free", False), (PAID + "-extra", False),
    ("anthropic/claude-haiku-4.6", False), ("another/claude-haiku-4.5", False), (None, False),
])
def test_returned_model_family_rule_is_explicit(returned, accepted):
    assert routing.same_model_family(PAID, returned) is accepted


def test_free_request_may_report_its_same_base_or_dated_family():
    assert routing.same_model_family(FREE_A, "fixture/alpha")
    assert routing.same_model_family(FREE_A, "fixture/alpha-20251001:free")
    assert not routing.same_model_family(FREE_A, "fixture/alpha-70b:free")


def test_dated_provider_slug_is_accepted_and_logged_with_requested_id(env, monkeypatch, caplog):
    router, _ = env
    returned = PAID + "-20251001"
    calls = []
    mock_completion(monkeypatch, returned, calls=calls)
    with caplog.at_level(logging.INFO, logger=routing.LOGGER.name), routing.interview_scope("dated-provider", 2) as scope:
        result = router.dispatch(purpose="role_skill_extraction", messages=[{"role": "user", "content": "PRIVATE_INPUT"}])
    assert result.model == returned and result.requested_model == PAID
    assert result.usage == (7, 11, 18)
    assert scope.models["role_skill_extraction"] == returned
    assert len(calls) == 1
    events = llm_usage.list_usage_events()
    assert len(events) == 1 and events[0]["model"] == returned and events[0]["status"] == "ok"
    records = [record for record in caplog.records if record.name == routing.LOGGER.name]
    assert len(records) == 1 and records[0].requested_model == PAID and records[0].returned_model == returned
    assert "PRIVATE_INPUT" not in caplog.text


def test_wrong_provider_family_still_logs_returned_id_and_billed_usage(env, monkeypatch, caplog):
    router, _ = env
    returned = "another/unapproved-model"
    mock_completion(monkeypatch, returned)
    with caplog.at_level(logging.INFO, logger=routing.LOGGER.name), routing.interview_scope("wrong-family", 2):
        with pytest.raises(routing.PrivacyViolation):
            router.dispatch(purpose="role_skill_extraction", messages=[])
    event, = llm_usage.list_usage_events()
    assert event["model"] == returned and event["total_tokens"] == 18 and event["status"] == "error"
    assert [record.returned_model for record in caplog.records if record.name == routing.LOGGER.name] == [returned]


def test_status_script_default_is_byte_read_only_and_clear_is_explicit(env, capsys):
    router, _ = env
    router.budget.record_failure(PAID, LimitDecision("credits"), free=False)
    before = router.settings.state_path.read_bytes()
    assert interview_llm_status.main(["--journal", str(router.settings.state_path)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["state"]["credit_block"] is True
    assert all(key in status["state"] for key in ("total_count", "free_count", "models", "leases", "all_until"))
    assert router.settings.state_path.read_bytes() == before
    assert interview_llm_status.main(["--journal", str(router.settings.state_path), "--clear-credit-block"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["state"]["credit_block"] is False
    assert status["state"]["total_count"] == 0


def test_status_script_access_clear_is_separate_from_credit_clear(env, capsys):
    router, _ = env
    router.budget.record_failure(PAID, LimitDecision("authorization"), free=False)
    args = ["--journal", str(router.settings.state_path)]
    interview_llm_status.main(args + ["--clear-credit-block"])
    assert json.loads(capsys.readouterr().out)["state"]["operator_block"] == "authorization"
    interview_llm_status.main(args + ["--clear-access-block"])
    assert json.loads(capsys.readouterr().out)["state"]["operator_block"] is None


def test_status_script_does_not_create_a_missing_journal(env, tmp_path, capsys):
    path = tmp_path / "missing-directory" / "missing.json"
    interview_llm_status.main(["--journal", str(path)])
    assert json.loads(capsys.readouterr().out)["exists"] is False
    assert not path.parent.exists()
    with pytest.raises(SystemExit):
        interview_llm_status.main(["--journal", str(path), "--clear-credit-block"])
    assert not path.parent.exists()


def test_batch_scope_exceeds_interview_cap_but_obeys_explicit_budget_and_restart(env):
    router, clock = env
    with routing.batch_scope("thirty", max_requests=30):
        for _ in range(30):
            send(router)
            clock.advance()
    with routing.batch_scope("thirty", max_requests=30), pytest.raises(DispatchDeferred, match="content_batch_cap"):
        send(router)
    with routing.batch_scope("thirty", max_requests=31), pytest.raises(BudgetUnavailable, match="resized"):
        send(router)
    state = RequestBudget(router.settings.state_path, clock=clock).snapshot()
    assert state["batches"]["thirty"]["content"] == 30
    assert state["free_count"] == 30 and state["interviews"] == {}


@pytest.mark.parametrize("purpose", sorted(routing.PERSONAL_PURPOSES))
def test_batch_scope_never_admits_conversation_purposes(env, purpose):
    router, _ = env
    with routing.batch_scope("content-only", max_requests=100), pytest.raises(routing.PrivacyViolation, match="content-only"):
        send(router, purpose=purpose)
    assert not router.settings.state_path.exists()


def test_batch_and_interview_share_daily_and_concurrency_limits(env):
    router, clock = env
    for identity, count in (("first", 30), ("second", 20)):
        with routing.batch_scope(identity, max_requests=30):
            for _ in range(count):
                send(router)
                clock.advance()
    with routing.batch_scope("second", max_requests=30), pytest.raises(DispatchDeferred, match="free_daily"):
        send(router)
    assert router.budget.snapshot()["free_count"] == 50
    # Paid slots share the same global concurrency count with batch slots.
    one = router.budget.reserve(interview_id="paid", core_count=2, lane="conversation", model=PAID, free=False)
    two = router.budget.reserve_batch(batch_id="paid-batch", max_requests=3, lane="content", model=PAID, free=False)
    with pytest.raises(DispatchDeferred, match="concurrency"):
        router.budget.reserve_batch(batch_id="third", max_requests=3, lane="content", model=PAID, free=False)
    router.budget.release(one)
    router.budget.release(two)


@pytest.mark.parametrize("maximum", [None, 0, -1, True])
def test_batch_scope_requires_a_positive_explicit_request_budget(maximum):
    with pytest.raises(routing.RoutingError):
        with routing.batch_scope("bad-budget", max_requests=maximum):
            pytest.fail("Invalid scope entered")


def test_pregeneration_uses_content_batch_scope_and_stops_at_request_cap(env, monkeypatch):
    router, clock = env
    monkeypatch.setattr(pregenerate_bundles, "protected_local_db_error", lambda: None)
    monkeypatch.setattr(pregenerate_bundles, "_cached_role_profile", lambda role: {
        "skill_specs": [{"name": "Python", "topics": [f"Topic {i}" for i in range(31)], "weight": 1}],
    })
    monkeypatch.setattr(role_skills, "extract_role_skills", lambda **kw: pytest.fail("Batch must not call conversation extraction"))
    bundle_generator.set_bundle_llm_override(lambda **kw: "fixture bundle")
    def generate(**kwargs):
        assert isinstance(routing._SCOPE.get(), routing.BatchScope)
        bundle_generator._call_bundle_llm(purpose="bundle_generation", provider="openrouter", model=FREE_A,
                                         messages=[{"role": "user", "content": "generic content"}])
        clock.advance()
        return {"status": "auto_checked", "cache_hit": False}
    monkeypatch.setattr(bundle_generator, "generate_and_check_bundle", generate)
    result = pregenerate_bundles.run_pregeneration(roles=["Generic engineer"], difficulties=["medium"],
        max_bundles=31, export_yaml=False, max_requests=30, batch_id="script-batch")
    assert result["generated"] == 30 and result["completed_cells"] == 30
    assert result["abort_reason"] == "content_batch_cap" and len(result["remaining_cells"]) == 1
    assert router.budget.snapshot()["batches"]["script-batch"]["content"] == 30


@pytest.mark.parametrize("maximum,cached,reason", [(None, True, "routing_budget_required"),
                                                  (5, False, "cached_roles_required")])
def test_routed_pregeneration_requires_budget_and_cached_roles_before_dispatch(env, monkeypatch, maximum, cached, reason):
    router, _ = env
    router.catalog_source = lambda: pytest.fail("No metadata fetch before validation")
    monkeypatch.setattr(pregenerate_bundles, "protected_local_db_error", lambda: None)
    monkeypatch.setattr(pregenerate_bundles, "_cached_role_profile", lambda role: {} if cached else None)
    result = pregenerate_bundles.run_pregeneration(roles=["Generic engineer"], max_requests=maximum)
    assert result["aborted"] is True and result["abort_reason"] == reason
    assert not router.settings.state_path.exists()


def test_pregeneration_cli_forwards_explicit_batch_arguments(monkeypatch, capsys):
    received = []
    monkeypatch.setattr(pregenerate_bundles, "apply_runtime_env", lambda: None)
    monkeypatch.setattr(pregenerate_bundles, "run_pregeneration", lambda **kw: received.append(kw) or {
        "dry_run": True, "planned_count": 0, "cache_hits": 0, "planned": []})
    assert pregenerate_bundles.main(["--dry-run", "--max-requests", "80", "--batch-id", "chosen-batch"]) == 0
    assert received[0]["max_requests"] == 80 and received[0]["batch_id"] == "chosen-batch"


def test_lease_expiry_exceeds_request_timeout_and_expired_slot_is_reclaimed(env):
    router, clock = env
    token = router.budget.reserve(interview_id="lease", core_count=2, lane="conversation", model=PAID, free=False, timeout_s=180)
    lease = router.budget.inspect()["state"]["leases"][token]
    assert lease["started_at"] == clock()
    assert lease["expires_at"] - lease["started_at"] > 180
    clock.advance(lease["expires_at"] - clock() + 1)
    state = router.budget.snapshot()
    assert token not in state["leases"] and state["total_count"] == 1


def test_finished_interview_is_pruned_without_refund_or_id_reuse(env):
    router, clock = env
    token = router.budget.reserve(interview_id="finished", core_count=2, lane="conversation", model=PAID, free=False)
    router.budget.finish_interview("finished")
    assert "finished" in router.budget.inspect()["state"]["interviews"]  # waits for its active lease
    router.budget.release(token)
    restarted = RequestBudget(router.settings.state_path, clock=clock)
    state = restarted.snapshot()
    assert "finished" not in state["interviews"] and "finished" in state["closed_interviews"]
    assert state["total_count"] == 1
    with pytest.raises(DispatchDeferred, match="interview_finished"):
        restarted.reserve(interview_id="finished", core_count=2, lane="conversation", model=PAID, free=False)


def test_flag_off_fixture_remains_byte_identical():
    fixture = Path(__file__).with_name("fixtures") / "ai_routing_flag_off.json"
    assert hashlib.sha256(fixture.read_bytes()).hexdigest() == "c7bd7382554fd751b3c8b83986b18fa2ba73250629d4d5e33538e4ff1d6ead1f"
