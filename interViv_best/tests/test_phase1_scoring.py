from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.scoring import pipeline
from modules.scoring_schema import SCORING_SCHEMA_VERSION


FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "scoring_calibration.json"


@pytest.fixture(autouse=True)
def _disable_semantic_for_calibration(monkeypatch):
    monkeypatch.setenv("DISABLE_SEMANTIC_SCORING", "true")


def _items() -> list[dict]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _context(item: dict) -> dict:
    return {
        "question": item["question"],
        "ideal_answer": item["ideal_answer"],
        "ideal_keywords": item["ideal_keywords"],
        "skill": item["skill"],
        "sub_domain": item["sub_domain"],
    }


def _score(item: dict, answer: str | None = None) -> dict:
    return pipeline.run_scoring_pipeline(
        answer_text=item["answer"] if answer is None else answer,
        word_count=999,
        question_context=_context(item),
        difficulty=item.get("difficulty", "medium"),
    )


def _rank(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda pair: pair[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[index][1]:
            end += 1
        avg_rank = (index + end + 2) / 2.0
        for pos in range(index, end + 1):
            ranks[ordered[pos][0]] = avg_rank
        index = end + 1
    return ranks


def _pearson(a: list[float], b: list[float]) -> float:
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    numerator = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    den_a = sum((x - mean_a) ** 2 for x in a) ** 0.5
    den_b = sum((y - mean_b) ** 2 for y in b) ** 0.5
    return numerator / (den_a * den_b)


def _spearman(a: list[float], b: list[float]) -> float:
    return _pearson(_rank(a), _rank(b))


def _by_id(item_id: str) -> dict:
    return next(item for item in _items() if item["id"] == item_id)


def test_excellent_paraphrased_answer_scores_at_least_7():
    result = _score(_by_id("rest_correct_2"))
    assert result["final_score"] / 10 >= 7.0
    assert result["score_explanation"]["semantic_available"] is False
    assert result["scoring_breakdown"]["semantic_component_source"] == "lexical_fallback"


def test_keyword_stuffed_answer_is_capped():
    item = _by_id("rest_correct_1")
    result = _score(
        item,
        "resources URI HTTP methods stateless JSON cacheability uniform interface",
    )
    assert result["guard_applied"] == "keyword_stuffing"
    assert result["final_score"] <= 35


def test_gibberish_answer_is_capped_low():
    item = _by_id("python_correct_1")
    result = _score(item, "asdfasdf qwer hjkl zxcv bnm")
    assert result["guard_applied"] == "gibberish"
    assert result["final_score"] <= 10


def test_empty_answer_scores_within_guard_cap():
    result = _score(_by_id("db_correct_1"), "")
    assert result["guard_applied"] == "empty"
    assert result["final_score"] <= 5


def test_short_answer_keeps_hard_guard_cap_even_with_high_semantic(monkeypatch):
    item = _by_id("rest_correct_1")

    def fake_nlp_score(*args, **kwargs):
        return 82.0, {
            "overall_score": 82.0,
            "layer1_score": 82.0,
            "layer2_score": 55.0,
            "layer3_score": 50.0,
            "cosine_similarity": 0.72,
            "tfidf_score": 0.50,
            "semantic_score": 0.82,
            "semantic_scoring_available": True,
            "semantic_fallback_reason": None,
            "keyword_coverage": 0.70,
            "keyword_coverage_details": {
                "score": 0.70,
                "matches": [{"keyword": "stateless", "covered": True}],
                "semantic_threshold": 0.72,
            },
            "concept_coverage": 0.40,
            "clarity_score": 0.25,
            "depth_score": 0.25,
            "structure_score": 0.1,
            "accuracy_score": 0.5,
            "advanced_bonus": 0.0,
            "difficulty_bonus": 0.0,
        }

    monkeypatch.setattr(pipeline, "_run_nlp_score", fake_nlp_score)
    result = _score(item, "It is stateless.")

    assert result["guard_applied"] == "too_short"
    assert result["final_score"] <= 20
    assert result["scoring_breakdown"]["guard_softened"] is False


def test_semantic_unavailable_falls_back_cleanly():
    result = _score(_by_id("docker_correct_2"))
    breakdown = result["scoring_breakdown"]

    assert breakdown["semantic_scoring_available"] is False
    assert breakdown["semantic_fallback_reason"]
    assert breakdown["semantic_component_source"] == "lexical_fallback"
    assert isinstance(result["final_score"], float)


def test_backend_ignores_client_word_count():
    item = _by_id("python_correct_2")
    result = _score(item)
    actual = len(pipeline._WORD_RE.findall(item["answer"]))

    assert result["scoring_breakdown"]["server_word_count"] == actual
    assert result["scoring_breakdown"]["client_word_count_ignored"] == 999


def test_score_explanation_shape_is_additive():
    result = _score(_by_id("ml_correct_1"))
    explanation = result["score_explanation"]

    assert {"summary", "strengths", "weaknesses", "guard_reason", "semantic_available"} <= set(explanation)
    assert "score_explanation" in result["scoring_breakdown"]


def test_rubric_structured_output_shape_is_additive():
    result = _score(_by_id("ml_correct_1"))
    breakdown = result["scoring_breakdown"]
    rubric = result["rubric"]

    assert result["scoring_schema_version"] == SCORING_SCHEMA_VERSION
    assert breakdown["scoring_schema_version"] == SCORING_SCHEMA_VERSION
    assert breakdown["rubric"] == rubric
    assert result["concepts"] == breakdown["concepts"]
    assert result["guard"] == breakdown["guard"]
    assert rubric["version"] == SCORING_SCHEMA_VERSION
    assert rubric["scale"] == "0-10"
    assert {"correctness", "coverage", "depth", "clarity", "weighted_score"} <= set(rubric)
    assert abs(sum(rubric["weights"].values()) - 1.0) < 0.0001
    for key in ("correctness", "coverage", "depth", "clarity", "weighted_score"):
        assert 0.0 <= float(rubric[key]) <= 10.0
    assert result["guard"]["applied"] is False
    assert isinstance(result["concepts"]["covered"], list)
    assert isinstance(result["concepts"]["missing"], list)


def test_guard_cap_also_caps_rubric_dimensions():
    result = _score(_by_id("python_correct_1"), "gctcititxi")
    rubric = result["rubric"]

    assert result["guard_applied"] == "gibberish"
    assert result["guard"]["applied"] is True
    assert result["guard"]["score_cap"] <= 10
    assert result["final_score"] <= 10
    assert rubric["guard_capped"] is True
    for key in ("correctness", "coverage", "depth", "clarity", "weighted_score"):
        assert float(rubric[key]) <= 1.0


def test_debug_scoring_logs_only_when_enabled(monkeypatch, caplog):
    item = _by_id("db_partial_1")
    monkeypatch.setenv("DEBUG_SCORING", "true")

    with caplog.at_level(logging.INFO, logger="backend.scoring.pipeline"):
        _score(item)

    assert "DEBUG_SCORING" in caplog.text
    assert "candidate_answer" in caplog.text
    monkeypatch.delenv("DEBUG_SCORING", raising=False)


def test_calibration_spearman_correlation_at_least_0_7():
    predicted = []
    human = []
    for item in _items():
        predicted.append(_score(item)["final_score"] / 10.0)
        human.append(float(item["human_score"]))

    correlation = _spearman(predicted, human)
    assert correlation >= 0.70, f"Spearman correlation too low: {correlation:.4f}"
