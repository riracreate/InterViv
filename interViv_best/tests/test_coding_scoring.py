"""Phase C scoring: exact formula, 25-cap rule, and round-result shape.

The formula is pinned exactly::

    score = 100 x (0.6 x visible_pass_rate + 0.4 x hidden_pass_rate)

A candidate compile or runtime failure caps the score at 25. Timeouts
count as ordinary failed tests (no cap). Infrastructure failure never
reaches the formula: with no execution service the default executor
raises ExecutionUnavailableError.

Stub executors below return fixed outcomes (no code is run); they only
feed the scorer through its ``executor`` seam.
"""

from __future__ import annotations

import json

import pytest

from backend.db.phase_c_coding_bank import get_coding_problem
from backend.execution import ExecutionUnavailableError
from modules.scoring.coding import (
    CANDIDATE_FAILURE_CAP,
    HIDDEN_WEIGHT,
    VISIBLE_WEIGHT,
    compute_coding_score,
    score_coding_round,
)


def _outcome(passed: bool, error: str | None = None) -> dict:
    return {"passed": passed, "error": error}


def _all_pass(n: int) -> list[dict]:
    return [_outcome(True) for _ in range(n)]


def _all_fail(n: int, error: str | None = "mismatch") -> list[dict]:
    return [_outcome(False, error) for _ in range(n)]


def test_formula_weights_and_cap_constants() -> None:
    assert VISIBLE_WEIGHT == 0.6
    assert HIDDEN_WEIGHT == 0.4
    assert CANDIDATE_FAILURE_CAP == 25.0


def test_all_pass_scores_100() -> None:
    totals = compute_coding_score(
        visible_outcomes=_all_pass(3), hidden_outcomes=_all_pass(5)
    )
    assert totals["final_score"] == 100.0
    assert totals["capped"] is False
    assert (totals["visible_passed"], totals["visible_total"]) == (3, 3)
    assert (totals["hidden_passed"], totals["hidden_total"]) == (5, 5)


def test_exact_weighted_value() -> None:
    totals = compute_coding_score(
        visible_outcomes=_all_pass(2) + _all_fail(1),
        hidden_outcomes=_all_pass(4) + _all_fail(1),
    )
    # 100 x (0.6 x 2/3 + 0.4 x 4/5) = 72.0
    assert totals["final_score"] == pytest.approx(72.0)
    assert totals["visible_pass_rate"] == round(2 / 3, 4)
    assert totals["hidden_pass_rate"] == round(4 / 5, 4)


def test_visible_only_scores_60() -> None:
    totals = compute_coding_score(
        visible_outcomes=_all_pass(3), hidden_outcomes=_all_fail(5)
    )
    assert totals["final_score"] == 60.0
    assert totals["capped"] is False


def test_hidden_only_scores_40() -> None:
    totals = compute_coding_score(
        visible_outcomes=_all_fail(3), hidden_outcomes=_all_pass(5)
    )
    assert totals["final_score"] == 40.0
    assert totals["capped"] is False


def test_total_failure_scores_zero_without_cap() -> None:
    totals = compute_coding_score(
        visible_outcomes=_all_fail(3), hidden_outcomes=_all_fail(5)
    )
    assert totals["final_score"] == 0.0
    assert totals["capped"] is False


def test_empty_outcomes_score_zero() -> None:
    totals = compute_coding_score(visible_outcomes=[], hidden_outcomes=[])
    assert totals["final_score"] == 0.0
    assert totals["visible_pass_rate"] == 0.0
    assert totals["hidden_pass_rate"] == 0.0


def test_compile_failure_caps_at_25() -> None:
    totals = compute_coding_score(
        visible_outcomes=_all_pass(2) + [_outcome(False, "compile")],
        hidden_outcomes=_all_pass(5),
    )
    assert totals["final_score"] == 25.0
    assert totals["capped"] is True


def test_runtime_failure_caps_even_when_everything_passes() -> None:
    # A runtime error marker anywhere caps, regardless of pass counts.
    totals = compute_coding_score(
        visible_outcomes=[_outcome(True, "Runtime")] + _all_pass(2),
        hidden_outcomes=_all_pass(5),
    )
    assert totals["final_score"] == 25.0
    assert totals["capped"] is True


def test_timeout_is_an_ordinary_failure_without_cap() -> None:
    totals = compute_coding_score(
        visible_outcomes=_all_pass(2) + [_outcome(False, "timeout")],
        hidden_outcomes=_all_pass(5),
    )
    # 100 x (0.6 x 2/3 + 0.4 x 1) = 80.0, uncapped.
    assert totals["final_score"] == pytest.approx(80.0)
    assert totals["capped"] is False


def test_passed_requires_strict_true() -> None:
    totals = compute_coding_score(
        visible_outcomes=[{"passed": 1, "error": None}],
        hidden_outcomes=[],
    )
    assert totals["visible_passed"] == 0
    assert totals["final_score"] == 0.0


def _stub_executor(visible: list[dict], hidden: list[dict]):
    def run(**kwargs):
        assert kwargs["hidden_tests"], "scorer must load hidden tests itself"
        return {"visible": visible, "hidden": hidden}

    return run


def test_round_all_pass_shape() -> None:
    result = score_coding_round(
        candidate_source="def two_sum(nums, target): ...",
        question_context={"problem_id": "coding_two_sum"},
        config={"problem_id": "coding_two_sum"},
        executor=_stub_executor(_all_pass(3), _all_pass(5)),
    )
    assert result["final_score"] == 100.0
    assert result["scoring_schema_version"] == "v1-coding"
    assert result["guard"] == {"fired": False, "reason": None}
    artifact = result["artifact_json"]
    assert artifact["evaluation"] == "coding"
    assert artifact["problem_id"] == "coding_two_sum"
    assert (artifact["visible"]["passed"], artifact["visible"]["total"]) == (3, 3)
    assert len(artifact["visible"]["cases"]) == 3
    assert (artifact["hidden"]["passed"], artifact["hidden"]["total"]) == (5, 5)
    # Hidden evidence is counts-only: no per-case detail, no stdout.
    assert set(artifact["hidden"]) == {"passed", "total"}
    assert artifact["capped"] is False
    assert artifact["final_score"] == 100.0
    explanation = result["score_explanation"]
    assert (explanation["visible_passed"], explanation["hidden_passed"]) == (3, 5)
    assert "3/3 visible" in result["feedback"]["content"][0]
    assert "5/5 hidden" in result["feedback"]["content"][0]
    assert result["concepts"]["covered"], "a solve covers the topics"


def test_round_mutant_like_scores_92() -> None:
    result = score_coding_round(
        candidate_source="...",
        question_context={"problem_id": "coding_two_sum"},
        config={},
        executor=_stub_executor(_all_pass(3), _all_pass(4) + _all_fail(1)),
    )
    assert result["final_score"] == pytest.approx(92.0)
    assert result["artifact_json"]["capped"] is False
    assert "hidden details are withheld" in result["feedback"]["next_step"]


def test_round_strips_hidden_stdout_defensively() -> None:
    hidden = [
        {"passed": True, "error": None, "stdout": "LEAKED-HIDDEN-STDOUT",
         "input_echo": "LEAKED-HIDDEN-INPUT"}
        for _ in range(5)
    ]
    result = score_coding_round(
        candidate_source="...",
        question_context={"problem_id": "coding_two_sum"},
        config={},
        executor=_stub_executor(_all_pass(3), hidden),
    )
    blob = json.dumps(result)
    assert "LEAKED-HIDDEN-STDOUT" not in blob
    assert "LEAKED-HIDDEN-INPUT" not in blob
    assert result["artifact_json"]["hidden"] == {"passed": 5, "total": 5}


def test_round_loads_hidden_tests_from_bank_not_client() -> None:
    seen: dict = {}

    def run(**kwargs):
        seen.update(kwargs)
        return {"visible": _all_pass(3), "hidden": _all_pass(5)}

    problem = get_coding_problem("coding_two_sum")
    assert problem is not None
    score_coding_round(
        candidate_source="...",
        # A hostile client cannot smuggle easier hidden tests in.
        question_context={"problem_id": "coding_two_sum",
                          "hidden_tests": [{"input": {}, "expected": 0}]},
        config={},
        executor=run,
    )
    assert seen["hidden_tests"] == problem["hidden_tests"]
    assert seen["function"] == problem["function"]


def test_round_unknown_problem_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown coding problem"):
        score_coding_round(
            candidate_source="...",
            question_context={"problem_id": "coding_nope"},
            config={},
            executor=_stub_executor([], []),
        )


def test_round_without_executor_raises_unavailable() -> None:
    """C.1 has no execution service: the default path raises, never zero."""
    with pytest.raises(ExecutionUnavailableError):
        score_coding_round(
            candidate_source="...",
            question_context={"problem_id": "coding_two_sum"},
            config={},
        )


def test_round_is_deterministic() -> None:
    kwargs = dict(
        candidate_source="...",
        question_context={"problem_id": "coding_two_sum"},
        config={},
    )
    first = score_coding_round(
        executor=_stub_executor(_all_pass(2) + _all_fail(1),
                                _all_pass(3) + _all_fail(2)),
        **kwargs,
    )
    second = score_coding_round(
        executor=_stub_executor(_all_pass(2) + _all_fail(1),
                                _all_pass(3) + _all_fail(2)),
        **kwargs,
    )
    assert first == second
