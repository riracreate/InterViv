"""
Tests for modules/answer_guard.check_answer_quality_v2 — extended guard.

Covers all 8 attack vectors:
  1 empty            → cap 5
  2 gibberish        → cap 10
  3 repetition       → cap 15
  4 too_short        → cap 20
  5 keyword_stuffing → cap 35
  6 question_parroting → cap 25
  7 low_density (fluff)→ cap 30
  8 off_topic        → cap 30 (skipped if SemanticScorer unavailable)

Run with:  python -m pytest tests/test_guard_v2.py -v
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.answer_guard import check_answer_quality_v2
from modules import semantic_scorer as _semantic_scorer


def test_empty_answer():
    r = check_answer_quality_v2("")
    assert r["cap_required"] is True
    assert r["score_cap"] == 5
    assert r["reason"] == "empty"


def test_gibberish_answer():
    r = check_answer_quality_v2("asdfasdf qwer hjkl")
    assert r["cap_required"] is True
    assert r["score_cap"] == 10
    assert r["reason"] == "gibberish"


def test_repetition_answer():
    r = check_answer_quality_v2("docker docker docker docker docker docker")
    assert r["cap_required"] is True
    assert r["score_cap"] == 15
    assert r["reason"] == "repetition"


def test_too_short_answer():
    r = check_answer_quality_v2("containers are good")
    assert r["cap_required"] is True
    assert r["score_cap"] == 20
    assert r["reason"] == "too_short"


def test_keyword_stuffing_answer():
    # Six keywords, no real explanation → stuffing rule fires before too_short.
    # Vowel ratio kept above 0.30 to avoid the gibberish rule.
    r = check_answer_quality_v2(
        "REST stateless caching cache uri endpoint",
        ideal_keywords="rest, stateless, caching, cache, uri, endpoint",
    )
    assert r["cap_required"] is True
    assert r["score_cap"] == 35
    assert r["reason"] == "keyword_stuffing"


def test_question_parroting():
    # Long enough to clear too_short, but answer's content tokens almost
    # exactly mirror the question's. Jaccard of {hash, table, works,
    # internally} ∩ {hash, table, works} over union = 3/4 = 0.75.
    answer = (
        "A hash table works. The hash table works. "
        "A hash table works internally and works."
    )
    r = check_answer_quality_v2(
        answer,
        question_text="Explain how a hash table works.",
    )
    assert r["cap_required"] is True
    assert r["score_cap"] == 25
    assert r["reason"] == "question_parroting"


def test_low_density_fluff():
    # 12+ words, mostly fluff vocabulary, almost no technical content.
    fluff = "This is a very important topic in computer science and very interesting."
    r = check_answer_quality_v2(
        fluff,
        question_text="What is Docker?",
        ideal_keywords="container, isolation, dependencies",
    )
    assert r["cap_required"] is True
    assert r["score_cap"] == 30
    assert r["reason"] == "low_density"


def test_off_topic_answer():
    # Skip if semantic model isn't loadable (no internet, etc).
    probe = _semantic_scorer.SemanticScorer().score(
        "the cat sat on the mat", "machine learning is about training models"
    )
    if probe is None:
        pytest.skip("SemanticScorer unavailable in this environment")

    # Talking about cooking when asked about Docker; no keyword overlap.
    # Padded past 12 words so too_short doesn't fire first.
    r = check_answer_quality_v2(
        "Cooking risotto requires constant stirring and patience over a low flame for thirty minutes today.",
        question_text="What is Docker?",
        ideal_keywords="container, isolation, kernel",
        ideal_answer=(
            "Docker is a container runtime that packages applications with their "
            "dependencies into isolated environments sharing the host OS kernel."
        ),
    )
    assert r["cap_required"] is True
    assert r["score_cap"] == 30
    assert r["reason"] == "off_topic"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
