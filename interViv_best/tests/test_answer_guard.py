from __future__ import annotations

from backend.scoring.pipeline import run_scoring_pipeline
from modules.answer_guard import check_answer_quality_v2


QUESTION_CONTEXT = {
    "question": "Explain binary search and when it is useful.",
    "ideal_answer": (
        "Binary search works on sorted data by repeatedly halving the search "
        "range and comparing the middle element with the target. It runs in "
        "O(log n) time and is useful when random access is available."
    ),
    "ideal_keywords": "binary search, sorted array, middle element, target, O(log n)",
    "skill": "DSA",
    "sub_domain": "dsa_core",
}


def _score(answer: str) -> dict:
    return run_scoring_pipeline(
        answer_text=answer,
        word_count=999,
        question_context=QUESTION_CONTEXT,
        difficulty="medium",
    )


def test_random_single_token_gibberish_is_capped_to_10() -> None:
    result = _score("gctcititxi")

    assert result["guard_applied"] == "gibberish"
    assert result["final_score"] <= 10
    assert result["scoring_breakdown"]["guard_caps"] == [10]


def test_random_two_token_gibberish_is_capped_to_10() -> None:
    result = _score("fvitugceigc vgcyutrxrtxtci")

    assert result["guard_applied"] == "gibberish"
    assert result["final_score"] <= 10


def test_empty_and_whitespace_answers_are_capped_to_5() -> None:
    for answer in ("", "     \n\t  "):
        result = _score(answer)

        assert result["guard_applied"] == "empty"
        assert result["final_score"] <= 5


def test_keyboard_spam_examples_are_capped_to_10() -> None:
    for answer in ("asdfasdfasdf", "qwerty qwerty qwerty"):
        result = _score(answer)

        assert result["guard_applied"] == "gibberish"
        assert result["final_score"] <= 10


def test_repeated_meaningless_tokens_are_capped() -> None:
    result = check_answer_quality_v2("aaaaaa bbbbbb cccccc")

    assert result["cap_required"] is True
    assert result["score_cap"] <= 15


def test_repeated_keyword_without_explanation_is_capped() -> None:
    result = check_answer_quality_v2("python python python python python")

    assert result["cap_required"] is True
    assert result["score_cap"] <= 15


def test_keyword_stuffing_cap_remains_35() -> None:
    result = _score("binary search sorted array middle target log time")

    assert result["guard_applied"] == "keyword_stuffing"
    assert result["final_score"] <= 35


def test_meaningful_short_technical_answers_are_not_flagged() -> None:
    good_answers = [
        "binary search divides a sorted array into halves until the target is found",
        "database indexing improves query performance by reducing full table scans",
        "process scheduling decides which process gets CPU time next",
    ]

    for answer in good_answers:
        result = check_answer_quality_v2(answer)
        assert result["cap_required"] is False, f"false positive for: {answer!r} -> {result}"


def test_guard_feedback_message_is_user_facing() -> None:
    result = _score("gctcititxi")

    assert (
        "Your answer looks incomplete or gibberish. Please write a meaningful explanation."
        in result["feedback"]["content"]
    )
