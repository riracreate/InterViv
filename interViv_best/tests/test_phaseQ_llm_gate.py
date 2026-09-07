"""Phase Q — LLM_LIVE_FETCH gate and adaptive mode enforcement at the client boundary."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.runtime_env import apply_runtime_env

apply_runtime_env()

from modules import adaptive_question_selector as aqs
from modules import guidance_coach as coach
from modules import question_bank as qb
from modules import question_runtime as qr
from modules.llm_outbound_gate import llm_live_fetch_enabled, question_llm_outbound_allowed


class BoomUrlopen:
    def __call__(self, *args, **kwargs):
        raise AssertionError("LLM urlopen must not run under this configuration")


def test_runtime_env_defaults_llm_live_fetch_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_LIVE_FETCH", raising=False)
    apply_runtime_env()
    assert os.environ.get("LLM_LIVE_FETCH") == "0"
    assert llm_live_fetch_enabled() is False


def test_default_gate_blocks_call_llm_even_with_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Credentials alone are not a gate — default LLM_LIVE_FETCH=0 blocks dial."""
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "llm")
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-used")
    monkeypatch.setattr(qr.urllib.request, "urlopen", BoomUrlopen())

    ctx = qr.QuestionCacheContext("DSA", "general", "medium", ())
    assert qr.call_llm_with_cache_retry("prompt", ctx) is None
    assert "gated" in (qr.last_runtime_error() or "").lower() or "LLM" in (qr.last_runtime_error() or "")


def test_keys_plus_csv_cannot_bypass_via_adaptive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase P hole: keys + csv + target_concepts must not dial after Phase Q."""
    monkeypatch.setenv("LLM_LIVE_FETCH", "1")  # deliberately on
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "csv")
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-used")
    monkeypatch.setattr(qr.urllib.request, "urlopen", BoomUrlopen())

    assert question_llm_outbound_allowed() is False

    # Call through the real adaptive → call_llm_with_cache_retry path (no _call_llm mock).
    payload = aqs.select_next_question(
        user_id=None,
        skill="DSA",
        sub_domain="general",
        difficulty="medium",
        asked=[],
        target_concepts=["trees", "dynamic programming"],
    )
    assert isinstance(payload, dict)
    assert payload.get("adaptive_selected") is False
    assert payload.get("question")
    assert payload.get("source") != "llm-adaptive"


def test_adaptive_default_config_no_urlopen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "csv")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-used")
    monkeypatch.setattr(qr.urllib.request, "urlopen", BoomUrlopen())

    payload = aqs.select_next_question(
        user_id=None,
        skill="Python",
        sub_domain="general",
        difficulty="easy",
        asked=[],
        target_concepts=["decorators"],
    )
    assert isinstance(payload, dict)
    assert payload.get("question")


def test_generate_question_and_bank_paths_no_urlopen_under_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "llm")  # would dial if only mode mattered
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-used")
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(qr.urllib.request, "urlopen", BoomUrlopen())
    monkeypatch.setattr(qb.urllib.request, "urlopen", BoomUrlopen())

    gen = qr.generate_question("DSA", "general", "medium", [])
    assert gen.get("question")
    assert gen.get("source") != "llm" or gen.get("llm_fallback_reason")

    bank = qb._generate_via_llm("DSA", "general", "medium", [])
    assert bank is None


def test_coach_no_urlopen_under_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-used")
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(coach.urllib.request, "urlopen", BoomUrlopen())
    coach.set_llm_override(None)

    plan = coach.build_coach_plan(
        user_id="phase-q-coach",
        jd_text="Need a Python backend engineer with Django and SQL experience for Pune.",
        goal_text="",
    )
    assert plan.get("mode") in {"fallback", "ok", "llm", "lexicon"} or "steps" in plan or "recognized" in plan


def test_gate_on_without_credentials_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM_LIVE_FETCH=1 + empty keys → soft None / fixtures, no urlopen."""
    monkeypatch.setenv("LLM_LIVE_FETCH", "1")
    monkeypatch.setenv("QUESTION_GENERATION_MODE", "llm_csv_fallback")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("QUESTION_LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(qr.urllib.request, "urlopen", BoomUrlopen())

    ctx = qr.QuestionCacheContext("DSA", "general", "medium", ())
    assert qr.call_llm_with_cache_retry("prompt", ctx) is None
    assert "provider" in (qr.last_runtime_error() or "").lower() or "key" in (qr.last_runtime_error() or "").lower()

    gen = qr.generate_question("DSA", "general", "medium", [])
    assert gen.get("question")
    assert gen.get("source") != "llm"
