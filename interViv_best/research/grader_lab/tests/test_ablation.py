from __future__ import annotations

from research.grader_lab.ablation import _score_without_term, _uncapped_score


def _payload(*, cap_required: bool = True) -> dict:
    return {
        "scoring_breakdown": {
            "formula_breakdown": {
                "base_score": 70.0,
                "semantic_term": 31.5,
                "classifier_term": 12.5,
                "keyword_term": 14.0,
                "tfidf_term": 12.0,
                "kg_bonus": 2.0,
                "ner_bonus": 1.0,
                "brevity_penalty": 0.0,
            },
            "guard": {"applied": cap_required, "score_cap": 40.0},
        }
    }


def test_uncapped_score_uses_pre_guard_formula():
    assert _uncapped_score(_payload()) == 73.0


def test_term_ablation_renormalizes_and_retains_guard_cap():
    # (70 - 12.5) / .75 + 3 bonuses = 79.667, then guard cap = 40.
    assert _score_without_term(
        _payload(), term="classifier_term", weight=0.25
    ) == 40.0


def test_term_ablation_without_cap_is_not_artificially_truncated():
    value = _score_without_term(
        _payload(cap_required=False), term="keyword_term", weight=0.20
    )
    assert value == 73.0
