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
