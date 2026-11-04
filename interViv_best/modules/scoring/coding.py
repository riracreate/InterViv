"""Deterministic coding-round scoring (no execution, no LLM judge).

Scoring consumes per-test outcomes produced by the execution client
(backend/execution.py) and applies exactly:

    score = 100 x (0.6 x visible_pass_rate + 0.4 x hidden_pass_rate)

Candidate compile or runtime failures cap the score at 25. Timeouts count
as ordinary failed tests. Infrastructure failure never reaches the
formula: the executor raises ExecutionUnavailableError, which callers
must surface as an unavailable/retry outcome rather than a zero.

Hidden outcomes reaching this module must already be stripped of stdout
and metadata; the scorer strips them again defensively so hidden detail
can never flow into artifacts, feedback, or explanations.
"""

from __future__ import annotations

from typing import Any, Callable

VISIBLE_WEIGHT = 0.6
HIDDEN_WEIGHT = 0.4
CANDIDATE_FAILURE_CAP = 25.0
CANDIDATE_ERRORS = frozenset({"compile", "runtime"})

Executor = Callable[..., dict[str, Any]]


def _pass_rate(outcomes: list[dict[str, Any]]) -> float:
    if not outcomes:
        return 0.0
    passed = sum(1 for outcome in outcomes if outcome.get("passed") is True)
    return passed / len(outcomes)


def compute_coding_score(
    *,
    visible_outcomes: list[dict[str, Any]],
    hidden_outcomes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply the coding formula over already-executed test outcomes."""
    visible = list(visible_outcomes or [])
    hidden = list(hidden_outcomes or [])
    visible_rate = _pass_rate(visible)
    hidden_rate = _pass_rate(hidden)
    raw = 100.0 * (VISIBLE_WEIGHT * visible_rate + HIDDEN_WEIGHT * hidden_rate)
    capped = any(
        str(outcome.get("error") or "").lower() in CANDIDATE_ERRORS
        for outcome in visible + hidden
    )
    final = min(raw, CANDIDATE_FAILURE_CAP) if capped else raw
    return {
        "final_score": round(final, 2),
        "visible_pass_rate": round(visible_rate, 4),
        "hidden_pass_rate": round(hidden_rate, 4),
        "visible_passed": sum(1 for o in visible if o.get("passed") is True),
        "visible_total": len(visible),
        "hidden_passed": sum(1 for o in hidden if o.get("passed") is True),
        "hidden_total": len(hidden),
        "capped": capped,
    }


def _safe_visible_case(outcome: dict[str, Any]) -> dict[str, Any]:
    return {
        "passed": bool(outcome.get("passed")),
        "error": outcome.get("error"),
    }


def score_coding_round(
    *,
    candidate_source: str,
    question_context: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    executor: Executor | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Evaluate candidate source against the bank problem's tests.

    Hidden tests are loaded server-side from the bank; they are never
    accepted from the client. Raises ExecutionUnavailableError when the
    execution service cannot run (callers roll back and answer 503).
    """
    from backend.db.phase_c_coding_bank import get_coding_problem
    from backend.execution import execute_python_tests

    context = dict(question_context or {})
    cfg = dict(config or {})
    problem_id = str(cfg.get("problem_id") or context.get("problem_id") or "")
    problem = get_coding_problem(problem_id) if problem_id else None
    if problem is None:
        raise ValueError(f"Unknown coding problem: {problem_id!r}.")

    run = executor or execute_python_tests
    result = run(
        source=candidate_source or "",
        function=str(problem.get("function") or ""),
        visible_tests=list(problem.get("visible_tests") or []),
        hidden_tests=list(problem.get("hidden_tests") or []),
    )
    visible = list((result or {}).get("visible") or [])
    # Hidden detail is counts-only by contract; strip defensively anyway.
    hidden = [
        {"passed": bool(o.get("passed")), "error": o.get("error")}
        for o in ((result or {}).get("hidden") or [])
    ]
    totals = compute_coding_score(visible_outcomes=visible,
                                  hidden_outcomes=hidden)
    final_score = totals["final_score"]
    topics = [str(t) for t in (problem.get("topics") or [])]
    solved = final_score >= 100.0
    capped_note = (
        " A compile or runtime failure capped the score at 25."
        if totals["capped"] else ""
    )
    feedback = {
        "content": [
            f"Coding evaluation: {totals['visible_passed']}/"
            f"{totals['visible_total']} visible passed, "
            f"{totals['hidden_passed']}/{totals['hidden_total']} hidden "
            f"passed.{capped_note}"
        ],
        "strengths": [f"Solved {problem.get('title')}"] if solved else [],
        "next_step": (
            "Solved all visible and hidden tests."
            if solved
            else "Fix the failing visible examples first; hidden details "
                 "are withheld."
        ),
    }
    artifact_json = {
        "evaluation": "coding",
        "problem_id": problem_id,
        "visible": {
            "passed": totals["visible_passed"],
            "total": totals["visible_total"],
            "cases": [_safe_visible_case(o) for o in visible],
        },
        "hidden": {
            "passed": totals["hidden_passed"],
            "total": totals["hidden_total"],
        },
        "capped": totals["capped"],
        "final_score": final_score,
    }
    scoring_breakdown = {
        "layer1_score": None,
        "layer2_score": None,
        "layer3_score": None,
        "semantic_score": None,
        "tfidf_score": None,
        "keyword_coverage": None,
        "kg_score": None,
        "ner_score": None,
        "guard_applied": None,
        "final_score": final_score,
        "nlp_score": None,
        "svm_label": None,
        "feedback": feedback,
        "coding_breakdown": artifact_json,
    }
    return {
        "final_score": final_score,
        "nlp_score": None,
        "svm_label": None,
        "kg_score": None,
        "ner_entities": [],
        "feedback": feedback,
        "score_explanation": {
            "visible_passed": totals["visible_passed"],
            "visible_total": totals["visible_total"],
            "hidden_passed": totals["hidden_passed"],
            "hidden_total": totals["hidden_total"],
            "visible_pass_rate": totals["visible_pass_rate"],
            "hidden_pass_rate": totals["hidden_pass_rate"],
            "capped": totals["capped"],
            "final_score": final_score,
        },
        "scoring_schema_version": "v1-coding",
        "rubric": {
            "correctness": round(final_score / 10.0, 1),
            "coverage": round(totals["hidden_pass_rate"] * 10.0, 1),
            "depth": 0.0,
            "clarity": 0.0,
        },
        "concepts": {
            "covered": topics if solved else [],
            "missing": [] if solved else topics,
        },
        "guard": {"fired": False, "reason": None},
        "guard_applied": None,
        "artifact_json": artifact_json,
        "scoring_breakdown": scoring_breakdown,
    }
