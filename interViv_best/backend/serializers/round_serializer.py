"""Canonical round serializer and review policy enforcement.

Enforces:
- Public disclosure of question count, duration, negative marking, attempt policy, and review policy.
- Zero leakage of correct option IDs, explanations, reference queries, or hidden cases during active rounds.
- Review policy gating: correct option IDs and explanations are revealed only when review_policy == 'after_session'
  AND the session is completed.
- SQL reference queries and hidden evaluation cases are authoring/grading artifacts and NEVER exposed.
"""

from __future__ import annotations

from typing import Any


DEFAULT_REVIEW_POLICY = "none"
SUPPORTED_REVIEW_POLICIES = {"none", "after_session"}


def sanitize_sql_artifact_for_client(artifact: dict[str, Any] | None) -> dict[str, Any]:
    """Reduce SQL evaluation artifact to safe aggregate evidence with zero hidden case leakage."""
    if not artifact or not isinstance(artifact, dict):
        return {
            "evaluation_cases": 0,
            "cases_passed": 0,
            "row_count_cases_passed": 0,
            "result_equality_points": 0.0,
            "row_count_points": 0.0,
            "constraint_points": 0.0,
            "final_score": 0.0,
        }

    cases = artifact.get("cases") or []
    evaluation_cases = int(artifact.get("evaluation_cases") or artifact.get("total_cases") or len(cases))
    cases_passed = int(artifact.get("cases_passed") or artifact.get("passed_cases") or sum(1 for c in cases if c.get("passed")))
    row_count_cases_passed = int(
        artifact.get("row_count_cases_passed")
        if artifact.get("row_count_cases_passed") is not None
        else sum(1 for c in cases if c.get("row_count_match"))
    )

    if evaluation_cases > 0 and "result_equality_points" not in artifact:
        result_equality_points = round(sum(60.0 if c.get("result_match") else 0.0 for c in cases) / evaluation_cases, 2)
    else:
        result_equality_points = float(artifact.get("result_equality_points", 0.0))

    if evaluation_cases > 0 and "row_count_points" not in artifact:
        row_count_points = round(sum(20.0 if c.get("row_count_match") else 0.0 for c in cases) / evaluation_cases, 2)
    else:
        row_count_points = float(artifact.get("row_count_points", 0.0))

    if "constraint_points" not in artifact:
        has_forbidden = bool(artifact.get("has_forbidden_constructs", False))
        constraint_points = 0.0 if has_forbidden else 20.0
    else:
        constraint_points = float(artifact.get("constraint_points", 0.0))

    final_score = float(artifact.get("final_score", 0.0))

    return {
        "evaluation_cases": evaluation_cases,
        "cases_passed": cases_passed,
        "row_count_cases_passed": row_count_cases_passed,
        "result_equality_points": result_equality_points,
        "row_count_points": row_count_points,
        "constraint_points": constraint_points,
        "final_score": final_score,
    }


def sanitize_round_for_client(
    round_doc: dict[str, Any],
    *,
    is_session_completed: bool = False,
    review_policy: str = DEFAULT_REVIEW_POLICY,
) -> dict[str, Any]:
    """Return a strictly sanitized copy of a round document for candidate delivery."""
    cleaned = dict(round_doc)
    # Attempt snapshots are server-side only (frozen answers and grading
    # inputs); they never travel to clients on any round type or policy.
    cleaned.pop("attempt_snapshot", None)
    round_type = cleaned.get("round_type", "technical_short_answer")
    config = dict(cleaned.get("config_json") or {})

    # Ensure timestamps are ISO strings for consistent frontend parsing
    for ts_key in ("started_at", "expires_at", "submitted_at"):
        if ts_key in cleaned and hasattr(cleaned[ts_key], "isoformat"):
            cleaned[ts_key] = cleaned[ts_key].isoformat()

    # Ensure public config includes rules
    config.setdefault("attempt_policy", "single_submission_final")
    config.setdefault("review_policy", review_policy if review_policy in SUPPORTED_REVIEW_POLICIES else DEFAULT_REVIEW_POLICY)
    cleaned["config_json"] = config

    effective_policy = config.get("review_policy", DEFAULT_REVIEW_POLICY)
    allow_review = is_session_completed and (effective_policy == "after_session")

    q_ctx = dict(cleaned.get("question_context") or {})

    if round_type == "ml_primitives":
        from backend.ml_primitives.catalog import public_problem

        # Rebuild content from the public-only reader, then allowlist round
        # fields. Stored private oracle material cannot escape on any policy.
        public = public_problem(config["problem_id"])
        safe_keys = (
            "round", "round_type", "status", "difficulty", "skill",
            "block_id", "block_position", "block_category", "block_index", "block_total",
            "started_at", "expires_at", "submitted_at",
        )
        result = {key: cleaned[key] for key in safe_keys if key in cleaned}
        result.update(question=public["title"], question_context=public, final_score=None)
        result["config_json"] = {
            key: config[key] for key in (
                "duration_minutes", "attempt_policy", "review_policy",
                "problem_id", "problem_version", "language", "scoring_available",
            ) if key in config
        }
        return result

    if round_type == "mcq":
        # Sanitize assigned questions in question_context
        sanitized_questions = []
        raw_questions = q_ctx.get("questions") or []
        for q in raw_questions:
            item = {
                "id": q.get("id"),
                "stem": q.get("stem"),
                "options": [
                    {"id": opt["id"], "text": opt["text"]}
                    for opt in q.get("options", q.get("options_json", []))
                ],
                "selection_mode": q.get("selection_mode", "single"),
                "negative_marking": float(q.get("negative_marking", 0.0)),
                "difficulty": q.get("difficulty"),
                "skill": q.get("skill"),
                "sub_domain": q.get("sub_domain"),
            }
            if allow_review:
                item["correct_option_ids"] = list(q.get("correct_option_ids", []))
                item["explanation"] = q.get("explanation")
            sanitized_questions.append(item)

        q_ctx["questions"] = sanitized_questions
        # Do not expose raw answer keys in top-level context
        q_ctx.pop("correct_option_ids", None)
        q_ctx.pop("explanation", None)
        cleaned["question_context"] = q_ctx

        # Sanitize artifact_json if present
        artifact = dict(cleaned.get("artifact_json") or {})
        if artifact and "questions" in artifact:
            cleaned_artifact_questions = []
            for aq in artifact["questions"]:
                aq_copy = {
                    "question_id": aq.get("question_id"),
                    "selected_option_ids": aq.get("selected_option_ids", []),
                    "is_correct": aq.get("is_correct"),
                    "raw_marks": aq.get("raw_marks"),
                }
                # Never include correct_option_ids or explanation in artifact_json
                cleaned_artifact_questions.append(aq_copy)
            artifact["questions"] = cleaned_artifact_questions
            cleaned["artifact_json"] = artifact

    elif round_type == "sql":
        # SQL never exposes reference_query or hidden test cases under any policy
        q_ctx.pop("reference_query", None)
        raw_cases = q_ctx.get("cases") or []
        sample_cases = [
            {
                "case_type": "sample",
                "description": c.get("description", ""),
                "seed_data": c.get("seed_data", ""),
            }
            for c in raw_cases
            if c.get("case_type") in ("sample", "visible_sample", "visible")
        ]
        q_ctx["sample_cases"] = sample_cases
        q_ctx.pop("cases", None)
        q_ctx.pop("hidden_cases", None)
        cleaned["question_context"] = q_ctx

        # Sanitize SQL artifact_json to safe aggregate evidence
        if "artifact_json" in cleaned and cleaned["artifact_json"]:
            cleaned["artifact_json"] = sanitize_sql_artifact_for_client(cleaned["artifact_json"])

    elif round_type == "coding":
        # Coding never exposes hidden tests, reference solutions, or
        # hidden execution detail under any review policy.
        for forbidden in ("hidden_tests", "reference_solution",
                          "mutant_solution", "hidden_stdout",
                          "hidden_stderr"):
            q_ctx.pop(forbidden, None)
        visible = []
        for case in (q_ctx.get("visible_tests") or []):
            visible.append({
                "input": dict(case.get("input") or {}),
                "expected": case.get("expected"),
            })
        q_ctx["visible_tests"] = visible
        cleaned["question_context"] = q_ctx

        artifact = dict(cleaned.get("artifact_json") or {})
        if artifact:
            cleaned["artifact_json"] = {
                "evaluation": artifact.get("evaluation", "coding"),
                "problem_id": artifact.get("problem_id"),
                "visible": {
                    "passed": (artifact.get("visible") or {}).get("passed"),
                    "total": (artifact.get("visible") or {}).get("total"),
                    "cases": [
                        {"passed": bool(c.get("passed")),
                         "error": c.get("error")}
                        for c in ((artifact.get("visible") or {}).get("cases") or [])
                    ],
                },
                "hidden": {
                    "passed": (artifact.get("hidden") or {}).get("passed"),
                    "total": (artifact.get("hidden") or {}).get("total"),
                },
                "capped": artifact.get("capped"),
                "final_score": artifact.get("final_score"),
            }

    elif round_type == "technical_short_answer":
        # Pre-answer / active-round: rebuild from an explicit allowlist.
        # Reference answers, keywords, concepts, and rubrics stay server-side.
        from modules.bundle_scoring import candidate_technical_context

        cleaned["question_context"] = candidate_technical_context(q_ctx)

    # Top-level reference material never rides on candidate round payloads.
    # Dashboard may attach ideals only after a completed assessment.
    for forbidden in (
        "ideal_answer", "ideal_keywords", "ideal_keywords_list",
        "reference_answer", "keywords",
    ):
        cleaned.pop(forbidden, None)

    return cleaned
