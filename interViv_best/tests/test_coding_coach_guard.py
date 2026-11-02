"""Coding-coach output guard: model hints that contain solution code are withheld."""
from __future__ import annotations

import pytest

from backend import coding_coach
from backend.coding_coach import build_hint, leaks_solution

PROBLEM = {"title": "Two Sum", "function": "two_sum", "topics": ["hash map"]}


@pytest.mark.parametrize(
    "text",
    [
        "Try this:\n```python\ndef two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        pass\n```",
        "```\nseen = {}\nfor i, n in enumerate(nums):\n    if target - n in seen:\n        return [seen[target - n], i]\n```",
        "def two_sum(nums, target):\n    return []",
        "class Solution:\n    pass",
        "public static int[] twoSum(int[] nums, int target) { return null; }",
        "function twoSum(nums, target) { }",
        "const twoSum = (nums, target) => { }",
        "#include <vector>\nint main() {}",
    ],
)
def test_solution_shaped_output_is_flagged(text: str) -> None:
    assert leaks_solution(text)


@pytest.mark.parametrize(
    "text",
    [
        "Think about what you need to remember after each element. A hash map from value to index fits.",
        "Keep a set of seen values: `seen = set()` and check membership before inserting.",
        "```python\nseen = {}\n```\nThen ask: what is the complement of the current number?",
        "Define the invariant first: before index i, the map holds every earlier value.",
    ],
)
def test_conceptual_hints_pass(text: str) -> None:
    assert not leaks_solution(text)


def test_leaking_ai_hint_falls_back_to_curated(monkeypatch) -> None:
    monkeypatch.setattr(coding_coach, "_ollama_hint", lambda **_: "def two_sum(nums, target):\n    return []")
    payload = build_hint(problem=PROBLEM, level=2)
    assert payload["kind"] == "curated"
    assert payload["ai_withheld"] == "solution_code"
    assert "def " not in payload["hint"]


def test_clean_ai_hint_is_returned_and_trimmed(monkeypatch) -> None:
    long_hint = "Track what you have seen. " * 100
    monkeypatch.setattr(coding_coach, "_ollama_hint", lambda **_: long_hint)
    payload = build_hint(problem=PROBLEM, level=1)
    assert payload["kind"] == "ai"
    assert len(payload["hint"]) <= coding_coach.MAX_HINT_CHARS
    assert "ai_withheld" not in payload


def test_unreachable_model_is_plain_curated(monkeypatch) -> None:
    monkeypatch.setattr(coding_coach, "_ollama_hint", lambda **_: None)
    payload = build_hint(problem=PROBLEM, level=3)
    assert payload["kind"] == "curated"
    assert "ai_withheld" not in payload
