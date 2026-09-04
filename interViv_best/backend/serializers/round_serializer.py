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


def sanitize_round_for_client(
    round_doc: dict[str, Any],
    *,
    is_session_completed: bool = False,
    review_policy: str = DEFAULT_REVIEW_POLICY,
) -> dict[str, Any]:
    """Return a strictly sanitized copy of a round document for candidate delivery."""
    cleaned = dict(round_doc)
    round_type = cleaned.get("round_type", "technical_short_answer")
    config = dict(cleaned.get("config_json") or {})

    # Ensure public config includes rules
    config.setdefault("attempt_policy", "single_submission_final")
    config.setdefault("review_policy", review_policy if review_policy in SUPPORTED_REVIEW_POLICIES else DEFAULT_REVIEW_POLICY)
    cleaned["config_json"] = config

    effective_policy = config.get("review_policy", DEFAULT_REVIEW_POLICY)
    allow_review = is_session_completed and (effective_policy == "after_session")

    q_ctx = dict(cleaned.get("question_context") or {})

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

    return cleaned
