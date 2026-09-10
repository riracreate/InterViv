"""Security gates for the local coding executor (no Docker required)."""

from __future__ import annotations

import os

import pytest

from backend.execution import (
    ALLOWED_EXECUTOR_URL,
    CodingLimits,
    CodingRateLimitedError,
    ExecutionUnavailableError,
    assert_coding_exec_allowed,
    coding_user_rate_ok,
    consume_round_exec_slot,
    executor_url_is_allowed,
    _configured_executor_url,
    _USER_RATE,
)


@pytest.fixture(autouse=True)
def _clear_rate_buckets():
    _USER_RATE.clear()
    yield
    _USER_RATE.clear()


def test_only_loopback_piston_url_is_allowed() -> None:
    assert executor_url_is_allowed(ALLOWED_EXECUTOR_URL) is True
    assert executor_url_is_allowed("http://127.0.0.1:19000/") is True
    rejected = [
        "",
        "http://emkc.org/api/v2/piston/execute",
        "https://emkc.org/api/v2/piston/execute",
        "http://localhost:19000",
        "http://0.0.0.0:19000",
        "http://127.0.0.1:2000",
        "https://127.0.0.1:19000",
        "http://127.0.0.1:19000/evil",
        "http://user@127.0.0.1:19000",
        "http://127.0.0.1:19000?x=1",
    ]
    for url in rejected:
        assert executor_url_is_allowed(url) is False, url


def test_configured_executor_rejects_public_and_unset(monkeypatch) -> None:
    monkeypatch.delenv("CODING_EXECUTOR_URL", raising=False)
    with pytest.raises(ExecutionUnavailableError):
        _configured_executor_url()
    monkeypatch.setenv("CODING_EXECUTOR_URL", "http://emkc.org/api/v2/piston")
    with pytest.raises(ExecutionUnavailableError):
        _configured_executor_url()
    monkeypatch.setenv("CODING_EXECUTOR_URL", ALLOWED_EXECUTOR_URL)
    assert _configured_executor_url() == ALLOWED_EXECUTOR_URL


def test_per_user_rate_limit_window() -> None:
    assert coding_user_rate_ok("u1", per_minute=2) is True
    assert coding_user_rate_ok("u1", per_minute=2) is True
    assert coding_user_rate_ok("u1", per_minute=2) is False
    assert coding_user_rate_ok("u2", per_minute=2) is True


def test_per_round_exec_slot_cap() -> None:
    round_row: dict = {}
    limits = CodingLimits(max_requests_per_round=3)
    assert consume_round_exec_slot(round_row, limits=limits) == 1
    assert consume_round_exec_slot(round_row, limits=limits) == 2
    assert consume_round_exec_slot(round_row, limits=limits) == 3
    with pytest.raises(CodingRateLimitedError):
        consume_round_exec_slot(round_row, limits=limits)
    assert round_row["coding_exec_count"] == 3


def test_assert_coding_exec_allowed_combines_gates(monkeypatch) -> None:
    monkeypatch.setenv("CODING_RATE_LIMIT_PER_MINUTE", "1")
    round_row: dict = {}
    assert_coding_exec_allowed("alice", round_row)
    with pytest.raises(CodingRateLimitedError):
        assert_coding_exec_allowed("alice", round_row)
