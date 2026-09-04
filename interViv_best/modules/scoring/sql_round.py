"""Multi-case sandboxed SQL round evaluation and deterministic scoring.

Evaluates candidate SQL against 1 visible sample case + hidden evaluation cases.
Rubric per case:
- Result equality: 60% (order-insensitive multiset equality by default; ordered if order_matters=True)
- Row count match: 20%
- No forbidden constructs: 20%
Total: 100% per case, aggregated across all cases.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from typing import Any

from modules.scoring.sql_security import (
    SQLSecurityError,
    SQLSingleStatementError,
    SQLTimeoutError,
    check_forbidden_constructs,
    execute_sandboxed_sql,
)


def _normalize_cell(val: Any) -> Any:
    """Normalize cell values for clean numeric and type comparisons."""
    if val is None:
        return None
    if isinstance(val, float):
        return round(val, 4)
    return val


def normalize_row(row: tuple[Any, ...]) -> tuple[Any, ...]:
    """Return a tuple with normalized cell values."""
    return tuple(_normalize_cell(c) for c in row)


def score_sql_round(
    *,
    candidate_query: str,
    question_context: dict[str, Any],
    config: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Score a candidate SQL query across all test cases for the problem."""
    config = config or {}
    schema_ddl = question_context.get("schema_ddl") or ""
    reference_query = question_context.get("reference_query") or ""
    cases = question_context.get("cases") or []
    checks_json = question_context.get("checks_json") or {}

    order_matters = bool(checks_json.get("order_matters", False))
    forbidden_list = checks_json.get("forbidden_constructs") or checks_json.get("forbidden") or []

    # 1. Check forbidden constructs across the candidate query
    forbidden_found = check_forbidden_constructs(candidate_query, forbidden_list)
    has_forbidden = len(forbidden_found) > 0
    construct_points = 0.0 if has_forbidden else 20.0

    case_results = []
    case_scores = []

    # If no cases provided, we cannot evaluate
    if not cases:
        return {
            "final_score": 0.0,
            "score_explanation": {"error": "No test cases configured for SQL problem."},
            "artifact_json": {"total_cases": 0, "passed_cases": 0, "cases": []},
            "scoring_breakdown": {
                "layer1_score": 0.0,
                "layer2_score": 0.0,
                "layer3_score": 0.0,
                "semantic_score": None,
                "tfidf_score": 0.0,
                "keyword_coverage": 0.0,
                "kg_score": None,
                "ner_score": 0.0,
                "guard_applied": None,
                "final_score": 0.0,
                "nlp_score": None,
                "svm_label": None,
                "feedback": {"summary": "No test cases configured.", "strengths": [], "weaknesses": []},
            },
            "nlp_score": None,
            "svm_label": None,
            "kg_score": None,
            "ner_entities": [],
            "feedback": {"content": ["No test cases configured."], "strengths": [], "next_step": ""},
        }

    # 2. Evaluate against each test case in a clean in-memory database
    for idx, case in enumerate(cases):
        raw_c_type = case.get("case_type", "sample" if idx == 0 else "hidden")
        case_type = "sample" if raw_c_type in ("sample", "visible_sample", "visible") else "hidden"
        description = case.get("description", f"Case {idx + 1}")
        seed_data = case.get("seed_data") or ""

        conn = sqlite3.connect(":memory:")
        ref_rows: list[tuple[Any, ...]] = []
        cand_rows: list[tuple[Any, ...]] = []
        cand_cols: list[str] = []
        truncated = False
        elapsed_ms = 0.0
        error_msg: str | None = None

        try:
            # Trusted setup: run DDL and seed data before candidate restrictions
            conn.executescript(schema_ddl)
            if seed_data.strip():
                conn.executescript(seed_data)

            # Establish ground truth using trusted reference query
            ref_cur = conn.cursor()
            ref_cur.execute(reference_query)
            ref_rows = ref_cur.fetchall()
            ref_cur.close()

            # Execute candidate query under security sandbox
            cand_cols, cand_rows, truncated, elapsed_ms = execute_sandboxed_sql(
                conn=conn,
                query=candidate_query,
                timeout_seconds=float(config.get("timeout_seconds", 2.0)),
                max_rows=int(config.get("max_rows", 1000)),
            )
        except (SQLSecurityError, SQLTimeoutError, SQLSingleStatementError, sqlite3.DatabaseError) as exc:
            error_msg = str(exc)
        except Exception as exc:
            error_msg = f"Execution error: {exc}"
        finally:
            conn.close()

        # Score this case
        if error_msg:
            result_match = False
            row_count_match = False
            result_points = 0.0
            row_count_points = 0.0
        else:
            row_count_match = (not truncated) and (len(cand_rows) == len(ref_rows))
            row_count_points = 20.0 if row_count_match else 0.0

            if truncated:
                result_match = False
                result_points = 0.0
            elif order_matters:
                norm_cand = [normalize_row(r) for r in cand_rows]
                norm_ref = [normalize_row(r) for r in ref_rows]
                result_match = (norm_cand == norm_ref)
                result_points = 60.0 if result_match else 0.0
            else:
                # Order-insensitive multiset comparison
                counter_cand = Counter(normalize_row(r) for r in cand_rows)
                counter_ref = Counter(normalize_row(r) for r in ref_rows)
                result_match = (counter_cand == counter_ref)
                result_points = 60.0 if result_match else 0.0

        total_case_score = result_points + row_count_points + construct_points
        case_passed = result_match and row_count_match and (not has_forbidden)

        case_scores.append(total_case_score)
        case_results.append({
            "case_type": case_type,
            "description": description,
            "passed": case_passed,
            "result_match": result_match,
            "row_count_match": row_count_match,
            "candidate_row_count": len(cand_rows),
            "expected_row_count": len(ref_rows),
            "execution_time_ms": elapsed_ms,
            "error": error_msg,
        })

    # 3. Aggregate final score across cases
    final_score = round(sum(case_scores) / len(case_scores), 2)
    final_score = max(0.0, min(100.0, final_score))

    passed_count = sum(1 for c in case_results if c["passed"])
    total_count = len(case_results)

    avg_result_score = round(
        sum(60.0 if c["result_match"] else 0.0 for c in case_results) / total_count, 2
    )
    avg_row_score = round(
        sum(20.0 if c["row_count_match"] else 0.0 for c in case_results) / total_count, 2
    )

    # 4. Objective feedback generation
    feedback_items = [
        f"Passed {passed_count} of {total_count} test cases.",
    ]
    if has_forbidden:
        feedback_items.append(
            f"Forbidden SQL constructs detected: {', '.join(forbidden_found)} (-20% penalty applied)."
        )
    for c in case_results:
        if c["error"]:
            feedback_items.append(f"{c['case_type'].capitalize()} case error: {c['error']}")
        elif not c["passed"]:
            if not c["row_count_match"]:
                feedback_items.append(
                    f"{c['case_type'].capitalize()} case: expected {c['expected_row_count']} rows, got {c['candidate_row_count']} rows."
                )
            elif not c["result_match"]:
                feedback_items.append(f"{c['case_type'].capitalize()} case: query output values did not match expected results.")

    artifact_json = {
        "total_cases": total_count,
        "passed_cases": passed_count,
        "cases": case_results,
        "has_forbidden_constructs": has_forbidden,
        "forbidden_constructs_found": forbidden_found,
        "final_score": final_score,
    }

    score_explanation = {
        "total_cases": total_count,
        "passed_cases": passed_count,
        "has_forbidden_constructs": has_forbidden,
        "forbidden_constructs_found": forbidden_found,
        "result_score": avg_result_score,
        "row_count_score": avg_row_score,
        "construct_score": construct_points,
        "final_score": final_score,
    }

    scoring_breakdown = {
        "layer1_score": avg_result_score,
        "layer2_score": avg_row_score,
        "layer3_score": construct_points,
        "semantic_score": None,
        "tfidf_score": 0.0,
        "keyword_coverage": 0.0 if has_forbidden else 1.0,
        "kg_score": None,
        "ner_score": 0.0,
        "guard_applied": None,
        "final_score": final_score,
        "nlp_score": None,
        "svm_label": None,
        "feedback": {
            "summary": f"SQL Evaluation: {passed_count}/{total_count} cases passed. Score: {final_score}%.",
            "strengths": [f"Passed {passed_count} test cases"] if passed_count > 0 else [],
            "weaknesses": [f"Failed {total_count - passed_count} test cases"] if passed_count < total_count else [],
        },
    }

    return {
        "final_score": final_score,
        "score_explanation": score_explanation,
        "scoring_breakdown": scoring_breakdown,
        "artifact_json": artifact_json,
        "feedback": {
            "content": feedback_items,
            "strengths": [f"Passed {passed_count} test cases"] if passed_count > 0 else [],
            "next_step": "Review failing test case discrepancies" if passed_count < total_count else "All test cases passed cleanly",
        },
        "nlp_score": None,
        "svm_label": None,
        "kg_score": None,
        "ner_entities": [],
    }
