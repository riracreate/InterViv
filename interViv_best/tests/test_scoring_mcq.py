"""Unit tests for deterministic exact-match multi-question MCQ round scoring."""

from __future__ import annotations

import pytest

from backend.db.phase2a_fixtures import PHASE2A_MCQ_FIXTURES
from modules.scoring.mcq import score_mcq_round
from modules.scoring import score_round


def test_mcq_scoring_15_question_worked_example():
    """Worked example: 15 questions.
    - 10 correct (+1.0 each = +10.0)
    - 2 incorrect (-0.25 each = -0.50)
    - 3 unanswered (0.0 each = 0.0)
    Expected raw marks = 10.0 - 0.50 = 9.50
    Expected percentage = (9.50 / 15) * 100 = 63.33%
    """
    assigned = PHASE2A_MCQ_FIXTURES[:15]
    assert len(assigned) == 15

    answers = []
    # 10 correct
    for i in range(10):
        answers.append({
            "question_id": assigned[i]["id"],
            "selected_option_ids": assigned[i]["correct_option_ids"],
        })
    # 2 incorrect (pick wrong option)
    for i in range(10, 12):
        correct = assigned[i]["correct_option_ids"][0]
        wrong = [opt["id"] for opt in assigned[i]["options_json"] if opt["id"] != correct][0]
        answers.append({
            "question_id": assigned[i]["id"],
            "selected_option_ids": [wrong],
        })
    # 3 unanswered: omit from answers list or pass empty list
    answers.append({
        "question_id": assigned[12]["id"],
        "selected_option_ids": [],
    })
    # questions 13 and 14 are completely omitted from answers

    result = score_mcq_round(
        answers=answers,
        assigned_questions=assigned,
        config={"negative_marking": 0.25},
    )

    assert result["final_score"] == 63.33
    expl = result["score_explanation"]
    assert expl["correct_count"] == 10
    assert expl["incorrect_count"] == 2
    assert expl["unanswered_count"] == 3
    assert expl["total_raw_marks"] == 9.50
    assert expl["final_score"] == 63.33

    artifact = result["artifact_json"]
    assert artifact["total_questions"] == 15
    assert artifact["correct_count"] == 10
    assert artifact["incorrect_count"] == 2
    assert artifact["unanswered_count"] == 3
    assert artifact["total_raw_marks"] == 9.50
    assert artifact["final_score"] == 63.33

    # Verify that artifact_json contains no question text, no correct option IDs, and no explanations
    for item in artifact["questions"]:
        assert "stem" not in item
        assert "question" not in item
        assert "correct_option_ids" not in item
        assert "explanation" not in item


def test_mcq_scoring_all_correct():
    """All assigned questions answered correctly -> 100%."""
    assigned = PHASE2A_MCQ_FIXTURES[:15]
    answers = [
        {"question_id": q["id"], "selected_option_ids": q["correct_option_ids"]}
        for q in assigned
    ]
    result = score_mcq_round(answers=answers, assigned_questions=assigned)
    assert result["final_score"] == 100.0
    assert result["score_explanation"]["correct_count"] == 15
    assert result["score_explanation"]["incorrect_count"] == 0
    assert result["score_explanation"]["unanswered_count"] == 0


def test_mcq_scoring_all_unanswered():
    """All questions unanswered -> 0%."""
    assigned = PHASE2A_MCQ_FIXTURES[:15]
    result = score_mcq_round(answers=[], assigned_questions=assigned)
    assert result["final_score"] == 0.0
    assert result["score_explanation"]["unanswered_count"] == 15
    assert result["score_explanation"]["total_raw_marks"] == 0.0


def test_mcq_scoring_negative_marks_clamped_to_zero():
    """All questions wrong with negative marking clamps final score at 0.0."""
    assigned = PHASE2A_MCQ_FIXTURES[:15]
    answers = []
    for q in assigned:
        wrong = [opt["id"] for opt in q["options_json"] if opt["id"] not in q["correct_option_ids"]][0]
        answers.append({"question_id": q["id"], "selected_option_ids": [wrong]})

    result = score_mcq_round(
        answers=answers,
        assigned_questions=assigned,
        config={"negative_marking": 0.25},
    )
    # Raw marks: 15 * -0.25 = -3.75 -> clamps to 0.0
    assert result["final_score"] == 0.0
    assert result["score_explanation"]["total_raw_marks"] == -3.75


def test_mcq_negative_marking_config_precedence():
    """Round config overrides question-level negative marking."""
    assigned = [dict(PHASE2A_MCQ_FIXTURES[0], negative_marking=0.10)]
    correct = assigned[0]["correct_option_ids"][0]
    wrong = [opt["id"] for opt in assigned[0]["options_json"] if opt["id"] != correct][0]

    # Without config override: uses question default 0.10
    res_default = score_mcq_round(
        answers=[{"question_id": assigned[0]["id"], "selected_option_ids": [wrong]}],
        assigned_questions=assigned,
        config={},
    )
    assert res_default["artifact_json"]["questions"][0]["raw_marks"] == -0.10

    # With config override: uses round config 0.50
    res_override = score_mcq_round(
        answers=[{"question_id": assigned[0]["id"], "selected_option_ids": [wrong]}],
        assigned_questions=assigned,
        config={"negative_marking": 0.50},
    )
    assert res_override["artifact_json"]["questions"][0]["raw_marks"] == -0.50


def test_mcq_rejects_duplicate_question_id():
    assigned = PHASE2A_MCQ_FIXTURES[:5]
    answers = [
        {"question_id": assigned[0]["id"], "selected_option_ids": ["a"]},
        {"question_id": assigned[0]["id"], "selected_option_ids": ["b"]},
    ]
    with pytest.raises(ValueError, match="Duplicate question ID in submission"):
        score_mcq_round(answers=answers, assigned_questions=assigned)


def test_mcq_rejects_unassigned_question_id():
    assigned = PHASE2A_MCQ_FIXTURES[:2]
    answers = [
        {"question_id": "unassigned_id_999", "selected_option_ids": ["a"]},
    ]
    with pytest.raises(ValueError, match="Question ID not assigned to this round"):
        score_mcq_round(answers=answers, assigned_questions=assigned)


def test_mcq_rejects_invalid_option_id():
    assigned = PHASE2A_MCQ_FIXTURES[:2]
    answers = [
        {"question_id": assigned[0]["id"], "selected_option_ids": ["forged_opt_z"]},
    ]
    with pytest.raises(ValueError, match="Invalid option ID 'forged_opt_z'"):
        score_mcq_round(answers=answers, assigned_questions=assigned)


def test_mcq_scoring_dispatcher_contract():
    """Verify score_round(round_type='mcq', ...) returns standard breakdown keys."""
    assigned = PHASE2A_MCQ_FIXTURES[:3]
    answers = [
        {"question_id": assigned[0]["id"], "selected_option_ids": assigned[0]["correct_option_ids"]},
    ]
    result = score_round(
        round_type="mcq",
        answers=answers,
        question_context={"questions": assigned},
        config={"negative_marking": 0.25},
    )

    required_keys = {
        "layer1_score",
        "layer2_score",
        "layer3_score",
        "semantic_score",
        "tfidf_score",
        "keyword_coverage",
        "kg_score",
        "ner_score",
        "guard_applied",
        "final_score",
        "nlp_score",
        "svm_label",
        "feedback",
    }
    assert required_keys.issubset(set(result["scoring_breakdown"].keys()))
    assert result["nlp_score"] is None
    assert result["svm_label"] is None
    assert result["kg_score"] is None
    assert result["ner_entities"] == []
    assert result["final_score"] == 33.33  # 1/3 * 100
