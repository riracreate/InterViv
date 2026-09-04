"""Deterministic exact-match multi-question MCQ round scorer.

Implements item-level scoring and round-level aggregation:
- Exactly matches selected option IDs against trusted ground truth keys.
- Correct: +1.0 mark.
- Incorrect: -effective_penalty (from round config or question default).
- Unanswered: 0.0 marks.
- Clamped final score: max(0.0, min(100.0, (total_raw_marks / total_questions) * 100.0)).
- Zero LLM calls. Fully deterministic.
"""

from __future__ import annotations

from typing import Any


def score_mcq_round(
    *,
    answers: list[dict[str, Any]],
    assigned_questions: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score a multi-question MCQ round and return a standardized scoring payload."""
    config = config or {}
    round_penalty = config.get("negative_marking")

    assigned_map: dict[str, dict[str, Any]] = {
        str(q["id"]): q for q in assigned_questions
    }
    assigned_ids = list(assigned_map.keys())

    if not assigned_ids:
        raise ValueError("No questions assigned to this MCQ round.")

    # 1. Validation: check duplicate submitted question IDs
    seen_ids: set[str] = set()
    answers_map: dict[str, list[str]] = {}
    for ans in answers:
        if not isinstance(ans, dict) or "question_id" not in ans:
            raise ValueError("Each answer must be an object with 'question_id' and 'selected_option_ids'.")
        qid = str(ans.get("question_id", "")).strip()
        if not qid:
            raise ValueError("Empty question ID in submission.")
        if qid in seen_ids:
            raise ValueError(f"Duplicate question ID in submission: {qid!r}")
        seen_ids.add(qid)

        # 2. Validation: check unassigned question IDs
        if qid not in assigned_map:
            raise ValueError(f"Question ID not assigned to this round: {qid!r}")

        selected = ans.get("selected_option_ids")
        if selected is None:
            selected = []
        if not isinstance(selected, list):
            raise ValueError(f"selected_option_ids must be a list for question: {qid!r}")
        str_selected = [str(x) for x in selected]
        if len(str_selected) != len(set(str_selected)):
            raise ValueError(f"Duplicate options in selection for question: {qid!r}")
        answers_map[qid] = str_selected

    # 3. Score each assigned question
    scored_items: list[dict[str, Any]] = []
    covered_concepts: list[str] = []
    missing_concepts: list[str] = []

    for qid in assigned_ids:
        q_data = assigned_map[qid]
        valid_options = {
            str(opt["id"])
            for opt in q_data.get("options", q_data.get("options_json", []))
        }

        submitted_options = answers_map.get(qid, [])

        # 4. Validation: check forged/invalid option IDs
        for opt_id in submitted_options:
            if opt_id not in valid_options:
                raise ValueError(
                    f"Invalid option ID {opt_id!r} for question {qid!r}."
                )

        correct_ids = set(str(x) for x in q_data.get("correct_option_ids", []))
        selected_set = set(submitted_options)

        effective_penalty = (
            float(round_penalty)
            if round_penalty is not None
            else float(q_data.get("negative_marking", 0.0))
        )

        sub_domain = q_data.get("sub_domain") or q_data.get("skill") or "general"

        if len(submitted_options) == 0:
            is_correct = False
            raw_marks = 0.0
            unanswered = True
            missing_concepts.append(sub_domain)
        elif selected_set == correct_ids:
            is_correct = True
            raw_marks = 1.0
            unanswered = False
            covered_concepts.append(sub_domain)
        else:
            is_correct = False
            raw_marks = -effective_penalty
            unanswered = False
            missing_concepts.append(sub_domain)

        scored_items.append(
            {
                "question_id": qid,
                "selected_option_ids": submitted_options,
                "is_correct": is_correct,
                "raw_marks": round(raw_marks, 4),
                "unanswered": unanswered,
            }
        )

    total_questions = len(assigned_ids)
    correct_count = sum(1 for item in scored_items if item["is_correct"])
    incorrect_count = sum(
        1 for item in scored_items if not item["is_correct"] and not item["unanswered"]
    )
    unanswered_count = sum(1 for item in scored_items if item["unanswered"])
    total_raw_marks = round(sum(item["raw_marks"] for item in scored_items), 4)

    # Clamped final percentage score in [0.0, 100.0]
    final_score = max(
        0.0,
        min(100.0, round((total_raw_marks / total_questions) * 100.0, 2)),
    )

    artifact_json = {
        "questions": [
            {
                "question_id": item["question_id"],
                "selected_option_ids": item["selected_option_ids"],
                "is_correct": item["is_correct"],
                "raw_marks": item["raw_marks"],
            }
            for item in scored_items
        ],
        "total_questions": total_questions,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "unanswered_count": unanswered_count,
        "total_raw_marks": total_raw_marks,
        "final_score": final_score,
    }

    feedback = {
        "content": [
            f"Objective MCQ evaluation: {correct_count}/{total_questions} correct, "
            f"{incorrect_count} incorrect, {unanswered_count} unanswered. "
            f"Total raw marks: {total_raw_marks:.2f}."
        ],
        "strengths": [
            f"Demonstrated mastery in {c}" for c in sorted(set(covered_concepts))
        ],
        "next_step": (
            f"Review concepts: {', '.join(sorted(set(missing_concepts))[:4])}"
            if missing_concepts
            else "Full marks on all assigned questions."
        ),
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
        "mcq_breakdown": artifact_json,
    }

    return {
        "final_score": final_score,
        "nlp_score": None,
        "svm_label": None,
        "kg_score": None,
        "ner_entities": [],
        "feedback": feedback,
        "score_explanation": {
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "unanswered_count": unanswered_count,
            "total_raw_marks": total_raw_marks,
            "final_score": final_score,
        },
        "scoring_schema_version": "v11-mcq",
        "rubric": {
            "correctness": round(final_score / 10.0, 1),
            "coverage": round((correct_count / total_questions) * 10.0, 1),
            "depth": 0.0,
            "clarity": 0.0,
        },
        "concepts": {
            "covered": sorted(set(covered_concepts)),
            "missing": sorted(set(missing_concepts)),
        },
        "guard": {"fired": False, "reason": None},
        "guard_applied": None,
        "artifact_json": artifact_json,
        "scoring_breakdown": scoring_breakdown,
    }
