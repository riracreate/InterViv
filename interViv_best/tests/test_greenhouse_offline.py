"""Overhaul Phase 5: JOBS_LIVE_FETCH=0 keeps Greenhouse search fully offline."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend import config  # noqa: E402
from modules import jobs_explorer  # noqa: E402


def _no_network(*args, **kwargs):
    raise AssertionError("Greenhouse network request made while JOBS_LIVE_FETCH=0")


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setenv("JOBS_LIVE_FETCH", "0")
    config.get_settings.cache_clear()
    monkeypatch.setattr(jobs_explorer, "load_board_jobs", _no_network)
    monkeypatch.setattr(jobs_explorer, "attach_descriptions", _no_network)
    jobs_explorer._SEARCH_MEMORY.clear()
    yield monkeypatch
    jobs_explorer._SEARCH_MEMORY.clear()
    config.get_settings.cache_clear()


def test_offline_search_serves_labeled_samples_without_network(offline):
    result = jobs_explorer.search_greenhouse_jobs(q="python", where="", page=1, user_id="u-offline")
    assert result["provenance"] == "sample" and result["sample"] is True
    assert "not real openings" in result["disclaimer"]
    assert result["jobs"], "filtered sample listings expected"
    for card in result["jobs"]:
        assert card["provenance"] == "sample"
        assert card["attribution"]["label"] == "Sample listing"
        assert "(sample)" in card["title"]
        assert "python" in (card["title"] + " " + (card["snippet"] or "")).lower()


def test_offline_and_live_results_use_separate_cache_keys(offline):
    offline_result = jobs_explorer.search_greenhouse_jobs(q="", where="", page=1, user_id="u-cache")
    assert offline_result["provenance"] == "sample"

    live_job = {"token": "acme", "company": "Acme", "external_id": "1", "title": "Backend Engineer",
                "location": "Remote", "redirect_url": "", "snippet": "Python services.",
                "updated_at": None}
    offline.setenv("JOBS_LIVE_FETCH", "1")
    config.get_settings.cache_clear()
    offline.setattr(jobs_explorer, "load_board_jobs", lambda: [live_job])
    offline.setattr(jobs_explorer, "attach_descriptions", lambda jobs: jobs)
    live_result = jobs_explorer.search_greenhouse_jobs(q="", where="", page=1, user_id="u-cache")
    assert live_result["provenance"] == "greenhouse" and live_result["sample"] is False
    assert live_result["cache_hit"] is False  # never the cached sample page
    assert [c["title"] for c in live_result["jobs"]] == ["Backend Engineer"]


def test_sample_fixture_uses_fictional_companies_and_no_links():
    rows = jobs_explorer.load_greenhouse_sample_jobs()
    assert len(rows) >= 8
    assert all(r["company"].startswith("Example ") for r in rows)
    assert all(r["redirect_url"] == "" for r in rows)
