"""Offline transport, response validation and catalog regressions for step 1c."""
from __future__ import annotations

import http.client
import json
import logging
import ssl
from dataclasses import replace

import pytest

from modules import interview_llm as routing, llm_usage
from modules.interview_llm_budget import DispatchDeferred
from scripts import list_interview_content_models
from tests.test_ai_interview_routing import FREE_A, FREE_B, PAID, catalog, env, send

PAID_CANONICAL = "anthropic/claude-4.5-haiku-20251001"
FREE_CANONICAL = "fixture/renamed-alpha-20261117:free"
BILLED = {"prompt_tokens": 7, "completion_tokens": 11, "total_tokens": 23}


class Response:
    def __init__(self, body, *, headers=None, error=None):
        self.body, self.headers, self.error = body, headers or {}, error

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        if self.error is not None:
            raise self.error
        return self.body


def fake_response(monkeypatch, body, *, headers=None, read_error=None):
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-fixture-only")
    raw = body if isinstance(body, bytes) else json.dumps(body).encode()
    monkeypatch.setattr(routing.urllib.request, "urlopen",
                        lambda *a, **kw: Response(raw, headers=headers, error=read_error))


def content_router(env):
    router, clock = env
    router.settings = replace(router.settings, content_models=(FREE_A, FREE_B))
    return router, clock


def completion_body(model=FREE_A, content="fixture text"):
    return {"model": model, "choices": [{"message": {"content": content}, "finish_reason": "stop"}], "usage": BILLED}


def call_failure(router, caplog, *, purpose="bundle_generation"):
    with caplog.at_level(logging.INFO, logger=routing.LOGGER.name), routing.interview_scope("step1c", 4):
        with pytest.raises(DispatchDeferred) as error:
            router.dispatch(purpose=purpose, messages=[{"role": "user", "content": "PRIVATE_PROMPT_MARKER"}])
    return error.value


def assert_single_failure(router, caplog, reason, *, returned=None, usage=(0, 0, 0)):
    event, = llm_usage.list_usage_events()
    assert event["status"] == "error" and event["error"] == reason
    assert (event["prompt_tokens"], event["completion_tokens"], event["total_tokens"]) == usage
    records = [record for record in caplog.records if record.name == routing.LOGGER.name]
    assert len(records) == 1 and records[0].returned_model == returned
    assert "PRIVATE_PROMPT_MARKER" not in caplog.text
    state = router.budget.inspect()["state"]
    assert state["total_count"] == 1 and state["leases"] == {}
    return state


@pytest.mark.parametrize("error", [http.client.RemoteDisconnected("closed"), ConnectionResetError("reset"),
                                  http.client.IncompleteRead(b"partial", 10), ssl.SSLError("TLS failed")],
                         ids=["remote_disconnected", "connection_reset", "incomplete_read", "ssl_error"])
@pytest.mark.parametrize("source", ["chat_once", "response_read"])
def test_transport_disconnects_are_typed_network_deferrals_once(env, monkeypatch, caplog, error, source):
    router, clock = env
    if source == "chat_once":
        def failed_chat(*args):
            raise error
        monkeypatch.setattr(router, "_chat_once", failed_chat)
    else:
        fake_response(monkeypatch, b"unused", read_error=error)
    deferred = call_failure(router, caplog, purpose="role_skill_extraction")
    assert deferred.reason == "network_unavailable" and deferred.retry_at == clock() + 4
    state = assert_single_failure(router, caplog, "network_unavailable")
    assert state["all_until"] == clock() + 4


@pytest.mark.parametrize("code,kind", [(400, "model_unavailable"), (402, "credits"), (403, "authorization"),
                                      (429, "rpm"), (503, "model_unavailable"), ("422", "model_unavailable"),
                                      (None, "provider_error"), (999, "provider_error")])
def test_http_200_provider_error_uses_embedded_code_and_preserves_billing(env, monkeypatch, caplog, code, kind):
    router, clock = content_router(env)
    body = {"model": FREE_A, "usage": BILLED, "error": {"message": "PRIVATE_PROVIDER_MARKER"}}
    if code is not None:
        body["error"]["code"] = code
    fake_response(monkeypatch, body, headers={"Retry-After": "9"})
    deferred = call_failure(router, caplog)
    assert deferred.reason == kind
    state = assert_single_failure(router, caplog, kind, returned=FREE_A, usage=(7, 11, 23))
    if kind in {"model_unavailable", "provider_error"}:
        assert state["models"][FREE_A] > clock()
    elif kind == "credits":
        assert state["credit_block"] is True
    elif kind == "authorization":
        assert state["operator_block"] == "authorization"
    else:
        assert deferred.retry_at == clock() + 9 and state["all_until"] == clock() + 9
    assert "PRIVATE_PROVIDER_MARKER" not in caplog.text


@pytest.mark.parametrize("body", [b"not JSON", b"", b"\xff", [], None, "scalar"])
def test_non_json_or_non_object_200_response_is_typed_and_backed_off(env, monkeypatch, caplog, body):
    router, clock = content_router(env)
    fake_response(monkeypatch, body)
    deferred = call_failure(router, caplog)
    assert deferred.reason == "invalid_response" and deferred.retry_at == clock() + 300
    state = assert_single_failure(router, caplog, "invalid_response")
    assert state["models"][FREE_A] == clock() + 300


@pytest.mark.parametrize("choices", [None, [], {}, [None], [{}], [{"message": None}],
                                   [{"message": {"content": ["not plain text"]}}]])
def test_malformed_200_choices_preserve_billed_usage(env, monkeypatch, caplog, choices):
    router, _ = content_router(env)
    fake_response(monkeypatch, {**completion_body(), "choices": choices})
    assert call_failure(router, caplog).reason == "invalid_response"
    assert_single_failure(router, caplog, "invalid_response", returned=FREE_A, usage=(7, 11, 23))


@pytest.mark.parametrize("content", [None, "", "  \n\t"])
def test_empty_200_content_backs_off_model_and_never_returns_none_text(env, monkeypatch, caplog, content):
    router, clock = content_router(env)
    fake_response(monkeypatch, completion_body(content=content))
    deferred = call_failure(router, caplog)
    assert deferred.reason == "empty_response" and deferred.retry_at == clock() + 300
    state = assert_single_failure(router, caplog, "empty_response", returned=FREE_A, usage=(7, 11, 23))
    assert state["models"][FREE_A] == clock() + 300
    clock.advance()
    with routing.interview_scope("step1c", 4):
        assert send(router).model == FREE_B


def test_response_validation_itself_returns_typed_error_with_usage(env, monkeypatch):
    fake_response(monkeypatch, completion_body(content=None))
    with pytest.raises(DispatchDeferred) as error:
        routing.InterviewRouter._chat_once(FREE_A, [], 100, 0.1, 20, True)
    assert error.value.reason == "empty_response" and error.value.usage == (7, 11, 23)
    assert error.value.model == FREE_A


def canonical_catalog():
    payload = catalog()
    for row in payload["data"]:
        if row["id"] == PAID:
            row["canonical_slug"] = PAID_CANONICAL
        elif row["id"] == FREE_A:
            row["canonical_slug"] = FREE_CANONICAL
        elif row["id"] == FREE_B:
            row["canonical_slug"] = "fixture/beta-renamed-20261117:free"
    return payload


@pytest.mark.parametrize("returned,accepted", [(PAID_CANONICAL, True),
    ("anthropic/claude-4.5-haiku-20251002", False), ("anthropic/claude-4.5-haiku", False),
    (PAID_CANONICAL + ":free", False), ("fixture/beta-renamed-20261117:free", False)])
def test_paid_dispatch_accepts_only_its_exact_catalog_canonical_slug(env, monkeypatch, caplog, returned, accepted):
    router, _ = env
    router.catalog_source = canonical_catalog
    fake_response(monkeypatch, completion_body(model=returned))
    with caplog.at_level(logging.INFO, logger=routing.LOGGER.name), routing.interview_scope("canonical", 2):
        if accepted:
            result = router.dispatch(purpose="role_skill_extraction", messages=[])
            assert result.model == PAID_CANONICAL and result.requested_model == PAID
        else:
            with pytest.raises(routing.PrivacyViolation):
                router.dispatch(purpose="role_skill_extraction", messages=[])
    event, = llm_usage.list_usage_events()
    assert event["model"] == returned and event["total_tokens"] == 23
    assert event["status"] == ("ok" if accepted else "error")
    records = [record for record in caplog.records if record.name == routing.LOGGER.name]
    assert len(records) == 1 and records[0].returned_model == returned and records[0].requested_model == PAID


@pytest.mark.parametrize("returned", [FREE_CANONICAL, FREE_CANONICAL.removesuffix(":free")])
def test_free_dispatch_accepts_canonical_slug_and_its_free_stripped_form(env, monkeypatch, returned):
    router, _ = content_router(env)
    router.catalog_source = canonical_catalog
    fake_response(monkeypatch, completion_body(model=returned))
    with routing.interview_scope("free-canonical", 2):
        result = router.dispatch(purpose="bundle_generation", messages=[])
    assert result.model == returned and result.requested_model == FREE_A


def test_canonical_slug_does_not_enable_extra_aliases_or_cross_entry_matching():
    assert not routing.same_model_family(PAID, PAID_CANONICAL)
    assert not routing.same_model_family(PAID, PAID_CANONICAL, canonical_slug="another/model")
    assert not routing.same_model_family(PAID, PAID_CANONICAL, canonical_slug=[PAID_CANONICAL])
    assert not routing.same_model_family(FREE_A, "fixture/renamed:free", canonical_slug="fixture/renamed")


@pytest.mark.parametrize("provider", [{}, {"context_length": None}])
def test_null_provider_context_uses_model_context_and_remains_eligible(provider):
    row = next(row for row in catalog()["data"] if row["id"] == FREE_A)
    row["top_provider"] = provider
    assert routing.content_context_length(row) == 32768
    assert routing._free_structured(row)


@pytest.mark.parametrize("context", ["32768", 32768.0, True, [], 0, -1])
def test_non_integer_or_nonpositive_provider_context_is_still_rejected(context):
    row = next(row for row in catalog()["data"] if row["id"] == FREE_A)
    row["top_provider"] = {"context_length": context}
    assert routing.content_context_length(row) == 0
    assert not routing._free_structured(row)


@pytest.mark.parametrize("next_link", ["https://example.invalid/models?page=2", None, ""])
def test_catalog_fetch_fails_closed_on_links_next_without_following_it(env, monkeypatch, next_link):
    payload = {**catalog(), "links": {"next": next_link}}
    calls = []
    def get(request, **kwargs):
        calls.append(request)
        return Response(json.dumps(payload).encode())
    monkeypatch.setattr(routing.urllib.request, "urlopen", get)
    if next_link in (None, ""):
        assert routing._fetch_catalog() == payload
    else:
        with pytest.raises(routing.RoutingError, match=r"pagination unsupported.*total_rows_received=6.*links.next present"):
            routing._fetch_catalog()
    assert len(calls) == 1 and calls[0].full_url == routing.CATALOG_URL and calls[0].data is None


def test_paginated_injected_catalog_blocks_dispatch_before_admission(env, monkeypatch):
    router, _ = env
    router.catalog_source = lambda: {**catalog(), "links": {"next": "/next"}}
    monkeypatch.setattr(router, "_chat_once", lambda *a: pytest.fail("Incomplete catalogs cannot dispatch"))
    with routing.interview_scope("incomplete-catalog", 2), pytest.raises(routing.RoutingError, match="pagination unsupported"):
        router.dispatch(purpose="role_skill_extraction", messages=[])
    assert not router.settings.state_path.exists() and llm_usage.list_usage_events() == []


def test_catalog_script_reports_pagination_failure_without_eligible_output(env, capsys):
    with pytest.raises(SystemExit) as error:
        list_interview_content_models.main(["--diagnostics"], catalog_source=lambda: {**catalog(), "links": {"next": "/next"}})
    captured = capsys.readouterr()
    assert error.value.code == 1 and "total_rows_received=6" in captured.err and "links.next present" in captured.err
    assert "id\tcontext_length" not in captured.out


def test_catalog_diagnostics_report_row_count_pagination_and_haiku_identity_without_completion(env, monkeypatch, capsys):
    router, _ = env
    calls = []
    def source():
        calls.append("catalog only")
        return canonical_catalog()
    monkeypatch.setattr(router, "dispatch", lambda **kw: pytest.fail("No completion in catalog inspection"))
    assert list_interview_content_models.main(["--diagnostics"], catalog_source=source) == 0
    output = capsys.readouterr().out
    assert "total_rows_received\t6" in output and "links_next_present\tfalse" in output
    assert f"conversation_model_id\t{PAID}" in output and f"conversation_canonical_slug\t{PAID_CANONICAL}" in output
    assert f"{FREE_A}\t32768\t" in output and f"{FREE_B}\t32768\t" in output
    assert calls == ["catalog only"] and not router.settings.state_path.exists()


@pytest.mark.parametrize("links", [[], False, {"next": []}, {"next": False}])
def test_malformed_links_still_fail_closed(links):
    with pytest.raises(routing.RoutingError):
        routing.catalog_rows({**catalog(), "links": links})


@pytest.mark.parametrize("links_fields,object_present,next_present,next_value", [
    ({}, False, False, None), ({"links": {}}, True, False, None),
    ({"links": {"next": None}}, True, True, None), ({"links": {"next": ""}}, True, True, ""),
])
def test_catalog_diagnostics_report_link_presence_and_values(env, capsys, links_fields, object_present, next_present, next_value):
    assert list_interview_content_models.main(["--diagnostics"], catalog_source=lambda: {**catalog(), **links_fields}) == 0
    output = capsys.readouterr().out
    assert f"links_present\t{str('links' in links_fields).lower()}" in output
    assert f"links_object_present\t{str(object_present).lower()}" in output
    assert f"links_value\t{json.dumps(links_fields.get('links'), sort_keys=True)}" in output
    assert f"links_next_present\t{str(next_present).lower()}" in output
    assert f"links_next_value\t{json.dumps(next_value)}" in output
    assert not env[0].settings.state_path.exists()


def test_routed_boundary_uses_shared_certifi_ssl_context(env, monkeypatch):
    assert isinstance(routing._SSL_CTX, ssl.SSLContext)
    assert routing._SSL_CTX.cert_store_stats()["x509_ca"] > 0
    monkeypatch.setattr(routing.ssl, "create_default_context",
                        lambda *a, **kw: pytest.fail("must reuse module certifi context"))
    contexts = []
    def fake_urlopen(request, **kwargs):
        contexts.append((request.full_url, kwargs.get("context")))
        payload = catalog() if request.full_url == routing.CATALOG_URL else completion_body(model=PAID)
        return Response(json.dumps(payload).encode())
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-fixture-only")
    monkeypatch.setattr(routing.urllib.request, "urlopen", fake_urlopen)
    router = routing.InterviewRouter(env[0].settings, clock=env[1])
    with routing.interview_scope("ssl-ctx", 2):
        result = router.dispatch(purpose="role_skill_extraction", messages=[])
    assert result.model == PAID
    assert contexts == [(routing.CATALOG_URL, routing._SSL_CTX),
                        (routing.CHAT_URL, routing._SSL_CTX)]


@pytest.mark.parametrize("kind,expected", [
    ("ssl_verify", ("URLError", "SSLCertVerificationError", "errno=1",
                    "ssl_reason=CERTIFICATE_VERIFY_FAILED", "verify_code=20")),
    ("dns", ("URLError", "gaierror", "errno=8")),
    ("timeout", ("URLError", "TimeoutError")),
    ("string_reason", ("URLError", "non_exception_reason")),
    ("http_error", ("HTTPError", "status=403")),
])
def test_catalog_script_prints_urlerror_reason_and_codes_without_secrets(env, monkeypatch, capsys, kind, expected):
    import io
    import socket
    from urllib.error import HTTPError, URLError

    if kind == "ssl_verify":
        reason = ssl.SSLCertVerificationError(1, "PRIVATE_KEY_MARKER")
        reason.reason = "CERTIFICATE_VERIFY_FAILED"
        reason.verify_code = 20
        raised = URLError(reason)
    elif kind == "dns":
        raised = URLError(socket.gaierror(8, "PRIVATE_HOST_MARKER"))
    elif kind == "timeout":
        raised = URLError(TimeoutError("PRIVATE_KEY_MARKER"))
    elif kind == "string_reason":
        raised = URLError("Authorization: Bearer PRIVATE_KEY_MARKER")
    else:
        raised = HTTPError(routing.CATALOG_URL, 403, "Forbidden PRIVATE_KEY_MARKER",
                           {"Authorization": "Bearer PRIVATE_KEY_MARKER"}, io.BytesIO(b"PRIVATE_BODY_MARKER"))
    monkeypatch.setattr(routing.urllib.request, "urlopen", lambda *a, **kw: (_ for _ in ()).throw(raised))
    with pytest.raises(SystemExit) as error:
        list_interview_content_models.main(["--diagnostics"])
    captured = capsys.readouterr()
    assert error.value.code == 1 and captured.out == ""
    for token in expected:
        assert token in captured.err
    for marker in ("PRIVATE_KEY_MARKER", "PRIVATE_HOST_MARKER", "PRIVATE_BODY_MARKER", "Authorization"):
        assert marker not in captured.err
    assert not env[0].settings.state_path.exists()


STEP1E_NEMOTRON_PARAMS = [
    "include_reasoning", "max_tokens", "reasoning", "response_format", "seed",
    "structured_outputs", "temperature", "tool_choice", "tools", "top_p",
]
STEP1E_EFFORT_PARAMS = [
    "include_reasoning", "max_tokens", "reasoning", "reasoning_effort",
    "response_format", "structured_outputs", "temperature", "tool_choice", "tools", "top_p",
]


@pytest.mark.parametrize("case,params,meta,ctx,budget_tokens,cap,expected_reasoning,expected_max", [
    ("step1e_nemotron_not_mandatory", STEP1E_NEMOTRON_PARAMS, None, 1000000, 2200, 1024,
     {"enabled": False, "exclude": True}, 2200),
    ("explicit_not_mandatory", STEP1E_NEMOTRON_PARAMS,
     {"mandatory": False, "default_enabled": True, "supports_max_tokens": True}, 1000000, 2200, 1024,
     {"enabled": False, "exclude": True}, 2200),
    ("mandatory_supports_max_tokens", STEP1E_NEMOTRON_PARAMS,
     {"mandatory": True, "supports_max_tokens": True}, 1000000, 2200, 768,
     {"max_tokens": 768, "exclude": True}, 2968),
    ("mandatory_clamped_below_context", STEP1E_NEMOTRON_PARAMS,
     {"mandatory": True, "supports_max_tokens": True}, 16384, 15800, 1024,
     {"max_tokens": 1024, "exclude": True}, None),
    ("mandatory_effort_low", STEP1E_EFFORT_PARAMS,
     {"mandatory": True, "supports_max_tokens": False}, 1024000, 2200, 1024,
     {"effort": "low", "exclude": True}, 3224),
    ("mandatory_without_budget_or_effort", STEP1E_NEMOTRON_PARAMS,
     {"mandatory": True, "supports_max_tokens": False}, 1000000, 2200, 1024,
     {"exclude": True}, 3224),
    ("no_reasoning_parameter", ["structured_outputs", "response_format", "max_tokens"],
     {"mandatory": True, "supports_max_tokens": True}, 32768, 2200, 1024,
     None, 2200),
    ("no_reasoning_metadata", ["structured_outputs", "response_format", "max_tokens", "reasoning"],
     None, 32768, 2200, 1024,
     None, 2200),
])
def test_content_reasoning_control_follows_catalog_metadata_and_clamps_headroom(
    env, monkeypatch, case, params, meta, ctx, budget_tokens, cap, expected_reasoning, expected_max
):
    payload = catalog()
    for row in payload["data"]:
        if row["id"] == FREE_A:
            row["context_length"] = ctx
            row["supported_parameters"] = list(params)
            if meta is not None:
                row["reasoning"] = dict(meta)
    sent_bodies = []
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-fixture-only")
    monkeypatch.setenv("INTERVIEW_CONTENT_REASONING_MAX_TOKENS", str(cap))
    def capture_post(request, **kwargs):
        sent_bodies.append(json.loads(request.data.decode()))
        return Response(json.dumps(completion_body(model=FREE_A)).encode())
    monkeypatch.setattr(routing.urllib.request, "urlopen", capture_post)
    settings = replace(routing.RoutingSettings.from_env(),
                       content_models=(FREE_A,), state_path=env[0].settings.state_path)
    router = routing.InterviewRouter(settings, catalog_source=lambda: payload, clock=env[1])
    messages = [{"role": "user", "content": "x" * 600}]
    with routing.interview_scope(f"reasoning-{case}", 2):
        result = router.dispatch(purpose="bundle_generation", messages=messages, max_tokens=budget_tokens)
    assert result.model == FREE_A and len(sent_bodies) == 1
    sent = sent_bodies[0]
    assert sent.get("reasoning") == expected_reasoning
    if expected_reasoning is None:
        assert "reasoning" not in sent
    if expected_max is None:
        assert sent["max_tokens"] < ctx - routing._estimate_prompt_tokens(messages)
        assert sent["max_tokens"] == ctx - routing._estimate_prompt_tokens(messages) - 1
    else:
        assert sent["max_tokens"] == expected_max


@pytest.mark.parametrize("purpose", sorted(routing.PERSONAL_PURPOSES))
def test_conversation_lane_never_sends_reasoning_or_adds_headroom(env, monkeypatch, purpose):
    monkeypatch.setenv("LLM_LIVE_CONSUMERS", "questions,interviewer")
    monkeypatch.setenv("OPENROUTER_API_KEY", "offline-fixture-only")
    payload = catalog()
    for row in payload["data"]:
        if row["id"] == PAID:
            row["supported_parameters"] = list(STEP1E_EFFORT_PARAMS)
            row["reasoning"] = {"mandatory": True, "supports_max_tokens": True}
    sent_bodies = []
    def capture_post(request, **kwargs):
        sent_bodies.append(json.loads(request.data.decode()))
        return Response(json.dumps({
            **completion_body(model=PAID),
            "usage": {**BILLED, "completion_tokens_details": {"reasoning_tokens": 0}},
        }).encode())
    monkeypatch.setattr(routing.urllib.request, "urlopen", capture_post)
    router = routing.InterviewRouter(env[0].settings, catalog_source=lambda: payload, clock=env[1])
    with caplog_for(routing.LOGGER.name) as records, routing.interview_scope(f"conv-{purpose}", 2):
        result = router.dispatch(purpose=purpose, messages=[{"role": "user", "content": "PRIVATE_TEXT"}], max_tokens=700)
    assert result.model == PAID and result.reasoning_tokens == 0
    assert len(sent_bodies) == 1 and "reasoning" not in sent_bodies[0] and sent_bodies[0]["max_tokens"] == 700
    assert len(records) == 1 and records[0].reasoning_tokens == 0


from contextlib import contextmanager as _cm


@_cm
def caplog_for(logger_name):
    records = []
    class Handler(logging.Handler):
        def emit(self, record):
            records.append(record)
    handler = Handler(level=logging.INFO)
    target = logging.getLogger(logger_name)
    old_level = target.level
    target.setLevel(logging.INFO)
    target.addHandler(handler)
    try:
        yield records
    finally:
        target.removeHandler(handler)
        target.setLevel(old_level)


@pytest.mark.parametrize("content", [None, "", "  \n\t", '{"question": "cut off'])
def test_finish_reason_length_precedes_empty_content_and_logs_reasoning_tokens(env, monkeypatch, caplog, content):
    router, clock = content_router(env)
    truncated_body = {
        "model": FREE_A,
        "choices": [{"message": {"content": content, "reasoning": "SECRET_REASONING_TRACE"}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 735, "completion_tokens": 2200, "total_tokens": 2935,
                  "completion_tokens_details": {"reasoning_tokens": 2200}},
    }
    fake_response(monkeypatch, truncated_body)
    with pytest.raises(routing.ProviderResponseDeferred) as direct_err:
        routing.InterviewRouter._chat_once(FREE_A, [], 2200, 0.25, 45, True)
    assert direct_err.value.reason == "truncated"
    assert direct_err.value.usage == (735, 2200, 2935)
    assert direct_err.value.reasoning_tokens == 2200

    deferred = call_failure(router, caplog)
    assert deferred.reason == "truncated" and deferred.reasoning_tokens == 2200
    assert deferred.retry_at == clock() + 300
    event, = llm_usage.list_usage_events()
    assert event["status"] == "truncated" and event["error"] == "truncated"
    assert (event["prompt_tokens"], event["completion_tokens"], event["total_tokens"]) == (735, 2200, 2935)
    records = [r for r in caplog.records if r.name == routing.LOGGER.name]
    assert len(records) == 1 and records[0].returned_model == FREE_A and records[0].reasoning_tokens == 2200
    assert "SECRET_REASONING_TRACE" not in caplog.text and "PRIVATE_PROMPT_MARKER" not in caplog.text
    state = router.budget.inspect()["state"]
    assert state["models"][FREE_A] == clock() + 300 and state["leases"] == {}
    clock.advance()
    with routing.interview_scope("step1c", 4):
        assert send(router).model == FREE_B


def test_owner_content_order_skips_ineligible_with_fixed_reasons_and_fails_closed_when_empty(env, caplog):
    _, clock = env
    payload = catalog()
    payload["data"].extend([
        {"id": "openrouter/auto", "pricing": {"prompt": "0", "completion": "0"}, "context_length": 32768,
         "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
         "supported_parameters": ["structured_outputs", "response_format", "max_tokens"]},
        {"id": "fixture/vision-out:free", "pricing": {"prompt": "0", "completion": "0"}, "context_length": 32768,
         "architecture": {"input_modalities": ["text"], "output_modalities": ["image"]},
         "supported_parameters": ["structured_outputs", "response_format", "max_tokens"]},
        {"id": "fixture/short-ctx:free", "pricing": {"prompt": "0", "completion": "0"}, "context_length": 8192,
         "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
         "supported_parameters": ["structured_outputs", "response_format", "max_tokens"]},
    ])
    bad_order = (
        "fixture/missing-from-catalog:free",
        "openrouter/auto",
        "fixture/vision-out:free",
        "fixture/short-ctx:free",
        PAID,
        "fixture/not-structured",
    )
    expected_reasons = [
        ("fixture/missing-from-catalog:free", "absent_from_catalog"),
        ("openrouter/auto", "disallowed_model_kind"),
        ("fixture/vision-out:free", "unsupported_modalities"),
        ("fixture/short-ctx:free", "insufficient_context"),
        (PAID, "nonzero_or_missing_price"),
        ("fixture/not-structured", "missing_structured_params"),
    ]
    mixed_state = env[0].settings.state_path.with_name("mixed-skip.json")
    mixed = routing.InterviewRouter(
        replace(env[0].settings, content_models=(*bad_order, FREE_B), state_path=mixed_state),
        catalog_source=lambda: payload, clock=clock,
    )
    with caplog.at_level(logging.WARNING, logger=routing.LOGGER.name), routing.interview_scope("skip-six", 2):
        assert send(mixed).model == FREE_B
    warnings = [(r.requested_model, r.reason) for r in caplog.records
                if r.name == routing.LOGGER.name and r.levelname == "WARNING"]
    assert warnings == expected_reasons
    assert mixed.budget.inspect()["state"]["total_count"] == 1

    caplog.clear()
    empty_state = env[0].settings.state_path.with_name("all-skipped.json")
    all_bad = routing.InterviewRouter(
        replace(env[0].settings, content_models=bad_order, state_path=empty_state),
        catalog_source=lambda: payload, clock=clock,
    )
    with caplog.at_level(logging.WARNING, logger=routing.LOGGER.name), routing.interview_scope("none-left", 2):
        with pytest.raises(routing.RoutingError):
            send(all_bad)
    assert not empty_state.exists()

    paid_state = env[0].settings.state_path.with_name("paid-fallback.json")
    paid_fallback = routing.InterviewRouter(
        replace(env[0].settings, content_models=("fixture/missing-from-catalog:free",),
                allow_paid_content=True, state_path=paid_state),
        catalog_source=lambda: payload, clock=clock,
    )
    with routing.interview_scope("paid-when-enabled", 2):
        assert send(paid_fallback).model == PAID

    dup_state = env[0].settings.state_path.with_name("dup.json")
    dup = routing.InterviewRouter(
        replace(env[0].settings, content_models=(FREE_A, FREE_A), state_path=dup_state),
        catalog_source=lambda: pytest.fail("Duplicates fail before catalog"), clock=clock,
    )
    with routing.interview_scope("dup", 2), pytest.raises(routing.RoutingError, match="Duplicate"):
        send(dup)
    assert not dup_state.exists()
