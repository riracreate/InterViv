"""Full-bank SQL execution: all 30 reference queries across all 90 datasets.

Uses the production SQL runner (``score_sql_round`` + sandbox validator):

- 30/30 reference queries score 100.0 with zero errors, zero timeouts, and
  zero row-limit overflows.
- 90/90 case executions succeed (result + row-count match on every case).
- Every reference query passes the same read-only sandbox gate candidates face
  (no prohibited function requirement hidden in the bank).
- Every problem has a realistic misconception mutant that scores below 100
  and fails at least one hidden case, proving hidden cases discriminate.
- Mutants prefer visible-sample survival: 25 of 30 pass the visible case before
  failing hidden data. The remaining five encode realistic mistakes that the
  visible samples already catch.
"""

from __future__ import annotations

import pytest

from backend.db.phase2_content_bank import PHASE2_SQL_BANK
from modules.scoring.sql_round import score_sql_round
from modules.scoring.sql_security import validate_single_read_only_statement

PROBLEM_IDS = [p["id"] for p in PHASE2_SQL_BANK]


_REPLACEMENT_MUTANTS: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {
    "sql_prob_001": (
        "inclusive HAVING boundary",
        (("HAVING SUM(o.amount) > 100", "HAVING SUM(o.amount) >= 100"),),
    ),
    "sql_prob_002": (
        "missing tie-break order",
        ((", employee_name ASC;", ";"),),
    ),
    "sql_prob_003": (
        "inclusive aggregate threshold",
        (("HAVING SUM(stock_quantity) > 10", "HAVING SUM(stock_quantity) >= 10"),),
    ),
    "sql_prob_004": (
        "missing required rounding",
        (("ROUND(AVG(price), 2)", "AVG(price)"),),
    ),
    "sql_prob_006": (
        "wrong LIMIT",
        (("LIMIT 3;", "LIMIT 2;"),),
    ),
    "sql_prob_007": (
        "NULL equality instead of IS NULL",
        (("agent_id IS NULL", "agent_id = NULL"),),
    ),
    "sql_prob_008": (
        "missing tie-break order",
        ((", s.name ASC;", ";"),),
    ),
    "sql_prob_009": (
        "path-prefix boundary",
        (("LIKE '/checkout%'", "LIKE '/checkout/%'"),),
    ),
    "sql_prob_010": (
        "missing tie-break order",
        ((", w.city ASC;", ";"),),
    ),
    "sql_prob_011": (
        "exclusive aggregate boundary",
        (("HAVING SUM(amount) >= 1000", "HAVING SUM(amount) > 1000"),),
    ),
    "sql_prob_012": (
        "missing DISTINCT",
        (("SELECT DISTINCT salary", "SELECT salary"),),
    ),
    "sql_prob_013": (
        "exactly one order per year",
        (("THEN 1 ELSE 0 END) > 0", "THEN 1 ELSE 0 END) = 1"),),
    ),
    "sql_prob_015": (
        "missing window tie-break",
        ((
            "PARTITION BY account_id\n                    ORDER BY tx_date ASC, id ASC",
            "PARTITION BY account_id\n                    ORDER BY tx_date ASC",
        ),),
    ),
    "sql_prob_017": (
        "inclusive comparison to average",
        (("WHERE p.price > c.avg_cat_price", "WHERE p.price >= c.avg_cat_price"),),
    ),
    "sql_prob_018": (
        "inclusive activity boundary",
        ((
            "WHERE activity_date > '2025-06-01'",
            "WHERE activity_date >= '2025-06-01'",
        ),),
    ),
    "sql_prob_019": (
        "inclusive salary comparison",
        (("WHERE m.salary < e.salary", "WHERE m.salary <= e.salary"),),
    ),
    "sql_prob_020": (
        "missing cumulative tie-break",
        ((
            "ORDER BY units_sold DESC, product_name ASC\n                    ) /",
            "ORDER BY units_sold DESC\n                    ) /",
        ),),
    ),
    "sql_prob_021": (
        "duplicate activity days counted",
        (
            ("SELECT DISTINCT user_id, activity_date", "SELECT user_id, activity_date"),
            ("ROW_NUMBER() OVER (", "DENSE_RANK() OVER ("),
        ),
    ),
    "sql_prob_022": (
        "fixed hierarchy depth cap",
        ((
            "JOIN org_tree ot ON e.manager_id = ot.id",
            "JOIN org_tree ot ON e.manager_id = ot.id\n                WHERE ot.level < 3",
        ),),
    ),
    "sql_prob_023": (
        "lower median only for even groups",
        ((
            "WHERE ABS(CAST(rnk_asc AS INTEGER) - CAST(rnk_desc AS INTEGER)) <= 1",
            "WHERE rnk_asc = rnk_desc OR rnk_asc + 1 = rnk_desc",
        ),),
    ),
    "sql_prob_024": (
        "INNER JOIN drops inactive users",
        (("LEFT JOIN user_events e", "JOIN user_events e"),),
    ),
    "sql_prob_025": (
        "inclusive overlap boundary",
        ((
            "WHERE r1.start_time < r2.end_time\n              AND r2.start_time < r1.end_time",
            "WHERE r1.start_time <= r2.end_time\n              AND r2.start_time <= r1.end_time",
        ),),
    ),
    "sql_prob_026": (
        "ROW_NUMBER instead of DENSE_RANK",
        (("DENSE_RANK() OVER", "ROW_NUMBER() OVER"),),
    ),
    "sql_prob_027": (
        "missing user partition in LAG",
        ((
            "LAG(click_time) OVER (PARTITION BY user_id ORDER BY click_time ASC, id ASC)",
            "LAG(click_time) OVER (ORDER BY click_time ASC, id ASC)",
        ),),
    ),
    "sql_prob_028": (
        "exact instead of minimum co-purchase count",
        (("HAVING COUNT(*) >= 2", "HAVING COUNT(*) = 2"),),
    ),
    "sql_prob_029": (
        "zero treated as stockout",
        (("WHERE current_stock < 0", "WHERE current_stock <= 0"),),
    ),
    "sql_prob_030": (
        "missing tie-break order",
        ((", category ASC;", ";"),),
    ),
}


_CUSTOM_MUTANTS: dict[str, tuple[str, str]] = {
    "sql_prob_005": (
        "highest login ID assumed to be latest",
        """
            SELECT u.username, l.login_timestamp AS last_login
            FROM users u
            JOIN logins l ON u.id = l.user_id
            WHERE l.id = (
                SELECT MAX(l2.id)
                FROM logins l2
                WHERE l2.user_id = u.id
            )
            ORDER BY u.username ASC;
        """,
    ),
    "sql_prob_014": (
        "ROW_NUMBER drops tied maximum earners",
        """
            WITH ranked AS (
                SELECT
                    d.name AS department_name,
                    e.name AS employee_name,
                    e.salary,
                    ROW_NUMBER() OVER (
                        PARTITION BY e.department_id
                        ORDER BY e.salary DESC, e.id ASC
                    ) AS salary_row
                FROM employees e
                JOIN departments d ON e.department_id = d.id
            )
            SELECT department_name, employee_name, salary
            FROM ranked
            WHERE salary_row = 1
            ORDER BY department_name ASC, employee_name ASC;
        """,
    ),
    "sql_prob_016": (
        "NULL first interval coerced to zero",
        """
            SELECT
                customer_id,
                id,
                order_date,
                COALESCE(
                    CAST(
                        ROUND(
                            julianday(order_date) - julianday(
                                LAG(order_date) OVER (
                                    PARTITION BY customer_id
                                    ORDER BY order_date ASC, id ASC
                                )
                            )
                        ) AS INTEGER
                    ),
                    0
                ) AS days_since_prev
            FROM customer_orders
            ORDER BY customer_id ASC, order_date ASC, id ASC;
        """,
    ),
}


# These mutants deliberately survive the public sample before hidden data
# exposes the misconception. The five omitted problems still use realistic
# mistakes, but their visible samples are already strong enough to reject them.
VISIBLE_SAMPLE_SURVIVORS = set(PROBLEM_IDS) - {
    "sql_prob_006",
    "sql_prob_007",
    "sql_prob_016",
    "sql_prob_023",
    "sql_prob_026",
}


def _realistic_mutant(problem: dict) -> tuple[str, str]:
    problem_id = problem["id"]
    if problem_id in _CUSTOM_MUTANTS:
        return _CUSTOM_MUTANTS[problem_id]

    kind, replacements = _REPLACEMENT_MUTANTS[problem_id]
    mutant = problem["reference_query"]
    for original, replacement in replacements:
        assert original in mutant, f"{problem_id}: mutation target no longer exists"
        mutant = mutant.replace(original, replacement)
    return kind, mutant


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
def test_bank_realistic_mutant_fails_at_least_one_hidden_case(problem_id: str) -> None:
    """A likely SQL misconception must execute and be caught by hidden data."""
    problem = next(p for p in PHASE2_SQL_BANK if p["id"] == problem_id)
    mutant_kind, mutant_query = _realistic_mutant(problem)

    assert mutant_kind
    assert "where 1 = 0" not in mutant_query.lower()
    validate_single_read_only_statement(mutant_query)

    res = score_sql_round(candidate_query=mutant_query, question_context=problem)
    cases = res["artifact_json"]["cases"]
    assert all(c["error"] is None for c in cases), (
        f"{problem_id} ({mutant_kind}): {[c['error'] for c in cases]}"
    )
    assert res["final_score"] < 100.0, (
        f"{problem_id} ({mutant_kind}): realistic mutant scored 100"
    )

    visible = [c for c in cases if c["case_type"] == "sample"]
    assert len(visible) == 1
    if problem_id in VISIBLE_SAMPLE_SURVIVORS:
        assert visible[0]["passed"] is True, (
            f"{problem_id} ({mutant_kind}): should survive visible sample"
        )

    hidden = [c for c in cases if c["case_type"] == "hidden"]
    assert len(hidden) == 2
    assert any(c["passed"] is False for c in hidden), (
        f"{problem_id} ({mutant_kind}): no hidden failure"
    )
