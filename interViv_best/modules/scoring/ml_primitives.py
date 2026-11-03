"""Deterministic ML-primitives scoring (scorer ``v1-ml-primitives``).

Consumes the evaluation produced by backend/ml_primitives/evaluate.py:

    score = 100 x (cases passing every numerical check / cases)

A case passes when the submission ran, and its output matches the reference
in shape, dtype and value (within the pack tolerance) and satisfies every
pack property. Static/vectorization findings are reported separately and do
not change the score. Syntax errors and imports outside the pack allowlist
are candidate errors (score 0, nothing executed). Infrastructure failure
raises ExecutionUnavailableError upstream and never reaches this formula.
"""

from __future__ import annotations

from typing import Any, Callable

SCORING_SCHEMA_VERSION = "v1-ml-primitives"
EVALUATION_MODE = "ml_numeric_checks"

_ERROR_TEXT = {
    "syntax": "The submission has a syntax error, so it was not run.",
    "prohibited_import": "The submission imports a library outside the allowed list "
                         "(NumPy only), so it was not run.",
    "load": "The module failed to load (for example a top-level error or a missing function).",
    "timeout": "A case exceeded the time limit.",
    "memory": "A case exceeded the memory limit.",
    "output_limit": "The submission printed more output than allowed.",
    "runtime": "A case raised an exception.",
    "invalid_output": "A case returned a value that is not a NumPy array of a supported dtype.",
}


def score_ml_primitives_round(
    *,
    candidate_source: str,
    config: dict[str, Any] | None = None,
    executor: Callable[..., dict[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    cfg = dict(config or {})
    problem_id = str(cfg.get("problem_id") or "")
    if not problem_id:
        raise ValueError("ML primitives round has no problem_id.")
    if executor is None:
        from backend.ml_primitives.evaluate import evaluate_ml_submission as executor

    evaluation = executor(problem_id=problem_id, source=candidate_source or "")
    cases = list(evaluation.get("cases") or [])
    total = len(cases)
    passed = sum(1 for case in cases if case.get("passed") is True)
    final_score = round(100.0 * passed / total, 2) if total else 0.0
    properties = list(evaluation.get("properties") or [])
    static = evaluation.get("static") or {}
    findings = [f for f in static.get("findings") or [] if isinstance(f, dict)]
    error_kinds = sorted({c.get("error") for c in cases if c.get("error") not in (None, "mismatch")})

    content = [f"ML evaluation: {passed}/{total} cases passed every numerical check."]
    content += [_ERROR_TEXT[kind] for kind in error_kinds if kind in _ERROR_TEXT]
    style = sorted({f.get("name") for f in findings if f.get("name")})
    if style and evaluation.get("status") == "graded":
        content.append("Code signals (not scored): " + ", ".join(style) + ".")
    failed_props = [p["name"] for p in properties if not p.get("passed")]
    feedback = {
        "content": content,
        "strengths": [p["name"] for p in properties if p.get("passed")][:6],
        "weakness": failed_props[:6],
        "next_step": (
            "All cases passed. Check the code signals for vectorization."
            if passed == total and total
            else f"Fix the failing check first: {failed_props[0]}." if failed_props
            else "Make the function run on every case before tuning numerics."
        ),
    }
    artifact_json = {
        "evaluation": "ml_primitives",
        "problem_id": evaluation.get("problem_id") or problem_id,
        "grader_version": evaluation.get("grader_version"),
        "status": evaluation.get("status"),
        "cases": [{"case_id": c.get("case_id"), "passed": bool(c.get("passed")),
                   "error": c.get("error")} for c in cases],
        "cases_passed": passed,
        "cases_total": total,
        "properties": [{"name": p["name"], "passed": bool(p.get("passed"))} for p in properties],
        "static_findings": findings,
        "execution_status": (evaluation.get("execution") or {}).get("status"),
        "final_score": final_score,
    }
    return {
        "final_score": final_score,
        "nlp_score": None,
        "svm_label": None,
        "kg_score": None,
        "ner_entities": [],
        "feedback": feedback,
        "score_explanation": {
            "cases_passed": passed,
            "cases_total": total,
            "formula": "100 × cases passing every check ÷ cases",
        },
        "scoring_breakdown": {
            "final_score": final_score,
            "feedback": feedback,
            "ml_breakdown": artifact_json,
            "scoring_schema_version": SCORING_SCHEMA_VERSION,
        },
        "artifact_json": artifact_json,
        "scoring_schema_version": SCORING_SCHEMA_VERSION,
        "evaluation_mode": EVALUATION_MODE,
        "guard_applied": None,
    }
