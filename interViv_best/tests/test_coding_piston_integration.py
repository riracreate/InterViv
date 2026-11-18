"""Opt-in checks against the actual loopback Piston service and runtimes."""

import os

import pytest

from backend.execution import execute_tests


pytestmark = pytest.mark.skipif(
    os.getenv("INTERVIV_REAL_EXECUTOR") != "1",
    reason="requires the local Piston executor and installed runtimes",
)

CASE = {"input": {"args": [2, 3]}, "expected": 5}
HIDDEN = {"input": {"args": [-2, 7]}, "expected": 5}
PROBLEM = {"starter_code": "def sum_two(a, b):\n    pass\n", "visible_tests": [CASE]}


@pytest.mark.parametrize(("language", "source"), [
    ("python", "def sum_two(a, b):\n    return a + b\n"),
    ("javascript", "function sum_two(a, b) { return a + b; }"),
    ("java", "import java.util.*;\nclass Solution { public int sum_two(int a, int b) { return a + b; } }"),
    ("java", "/* comment before imports */\nimport java.util.*;\npublic class Solution { public int sum_two(int a, int b) { return a + b; } }"),
    ("cpp", "class Solution { public: int sum_two(int a, int b) { return a + b; } };"),
])
def test_installed_languages_execute_visible_and_hidden_cases(language, source):
    result = execute_tests(
        source=source, function="sum_two", visible_tests=[CASE],
        hidden_tests=[HIDDEN], language=language, problem=PROBLEM,
    )

    assert result["visible"][0]["passed"] is True, result["visible"]
    assert result["hidden"] == [{"passed": True, "error": None}]
