"""Full-bank SQL execution: all 30 reference queries across all 90 datasets.

Uses the production SQL runner (``score_sql_round`` + sandbox validator):

- 30/30 reference queries score 100.0 with zero errors, zero timeouts, and
  zero row-limit overflows.
- 90/90 case executions succeed (result + row-count match on every case).
- Every reference query passes the same read-only sandbox gate candidates face
  (no prohibited function requirement hidden in the bank).
- Every defined mutant (an always-empty wrapper per problem) scores below 100
  and fails at least one hidden case, proving hidden cases discriminate.
"""

from __future__ import annotations

import pytest

from backend.db.phase2_content_bank import PHASE2_SQL_BANK
from modules.scoring.sql_round import score_sql_round
from modules.scoring.sql_security import validate_single_read_only_statement

PROBLEM_IDS = [p["id"] for p in PHASE2_SQL_BANK]


def _empty_mutant(reference_query: str) -> str:
    inner = reference_query.strip().rstrip(";")
    return f"SELECT * FROM ({inner}) AS mutant_empty WHERE 1 = 0;"


@pytest.mark.parametrize("problem_id", PROBLEM_IDS)
def test_bank_reference_query_passes_sandbox_gate(problem_id: str) -> None:
    """Each bank reference query must satisfy the candidate sandbox validator."""
    problem = next(p for p in PHASE2_SQL_BANK if p["id"] == problem_id)
    # Raises on write/DDL/multi-statement/prohibited constructs.
    validate_single_read_only_statement(problem["reference_query"])


@pytest.mark.parametrize("problem_id", PROBLEM_IDS)
def test_bank_reference_query_executes_all_cases_cleanly(problem_id: str) -> None:
    """Reference query: 100.0, no error/timeout/truncation on any of 3 cases."""
    problem = next(p for p in PHASE2_SQL_BANK if p["id"] == problem_id)
    res = score_sql_round(candidate_query=problem["reference_query"], question_context=problem)

    assert res["final_score"] == 100.0, f"{problem_id}: {res['score_explanation']}"
    cases = res["artifact_json"]["cases"]
    assert len(cases) == 3, f"{problem_id}: expected 3 case executions"
    for case in cases:
        assert case["error"] is None, f"{problem_id}: {case['error']}"
        assert case["passed"] is True
        assert case["result_match"] is True
        assert case["row_count_match"] is True
        # No timeout and no row-limit overflow on reference-scale data.
        assert float(case["execution_time_ms"]) < 2000.0, f"{problem_id} too slow"
        assert case["candidate_row_count"] == case["expected_row_count"] <= 1000


@pytest.mark.parametrize("problem_id", PROBLEM_IDS)
def test_bank_empty_mutant_fails_at_least_one_hidden_case(problem_id: str) -> None:
    """An always-empty mutant must score below 100 and fail a hidden case."""
    problem = next(p for p in PHASE2_SQL_BANK if p["id"] == problem_id)
    res = score_sql_round(
        candidate_query=_empty_mutant(problem["reference_query"]),
        question_context=problem,
    )
    assert res["final_score"] < 100.0, f"{problem_id}: empty mutant scored 100"
    hidden = [c for c in res["artifact_json"]["cases"] if c["case_type"] == "hidden"]
    assert len(hidden) == 2
    assert any(c["passed"] is False for c in hidden), f"{problem_id}: no hidden failure"
