"""
Smoke test for modules/answer_guard.py — Change 1.

Run with:  python -m pytest tests/test_guard.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.answer_guard import check_answer_quality


def test_empty_answer():
    """Empty string → cap 5, reason 'empty'."""
    result = check_answer_quality("")
    assert result["cap_required"] is True, f"Expected cap, got {result}"
    assert result["score_cap"] == 5, f"Expected cap=5, got {result['score_cap']}"
    assert result["reason"] == "empty", f"Expected reason='empty', got {result['reason']}"


def test_gibberish_answer():
    """'asdfasdf' → cap 10, reason 'gibberish'."""
    result = check_answer_quality("asdfasdf qwer hjkl")
    assert result["cap_required"] is True, f"Expected cap, got {result}"
    assert result["score_cap"] == 10, f"Expected cap=10, got {result['score_cap']}"
    assert result["reason"] == "gibberish", f"Expected reason='gibberish', got {result['reason']}"


def test_repetition_answer():
    """'docker docker docker docker' → cap 15, reason 'repetition'."""
    result = check_answer_quality("docker docker docker docker docker docker")
    assert result["cap_required"] is True, f"Expected cap, got {result}"
    assert result["score_cap"] == 15, f"Expected cap=15, got {result['score_cap']}"
    assert result["reason"] == "repetition", f"Expected reason='repetition', got {result['reason']}"


def test_too_short_answer():
    """'containers are good' (3 words) → cap 20, reason 'too_short'."""
    result = check_answer_quality("containers are good")
    assert result["cap_required"] is True, f"Expected cap, got {result}"
    assert result["score_cap"] == 20, f"Expected cap=20, got {result['score_cap']}"
    assert result["reason"] == "too_short", f"Expected reason='too_short', got {result['reason']}"


def test_good_answer_no_cap():
    """A real, substantive answer → no cap applied."""
    answer = (
        "Docker is a containerization platform that packages applications and their dependencies "
        "into isolated containers. Unlike virtual machines, containers share the host OS kernel, "
        "making them lightweight and fast to start. This allows developers to ensure consistency "
        "across development, testing, and production environments, solving the 'works on my machine' "
        "problem. Docker uses a layered filesystem, so image layers are cached and reused efficiently."
    )
    result = check_answer_quality(answer)
    assert result["cap_required"] is False, f"Expected no cap for good answer, got {result}"


if __name__ == "__main__":
    tests = [
        test_empty_answer,
        test_gibberish_answer,
        test_repetition_answer,
        test_too_short_answer,
        test_good_answer_no_cap,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed+failed} passed")
