"""Scorer v4 baseline fixture: v3 cases extended with five v4 cases."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("LLM_LIVE_FETCH", "0")

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "scorer_v4_baseline.json"


@pytest.fixture(scope="module")
def fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _run(item: dict) -> dict:
    os.environ["SCORER_VERSION"] = "v4"
    try:
        from backend.scoring.pipeline import run_scoring_pipeline

        ctx = {
            "question": item.get("question") or "",
            "ideal_answer": item.get("ideal_answer") or "",
            "ideal_keywords": item.get("ideal_keywords") or "",
            "skill": "OOP",
            "difficulty": "medium",
        }
        if item.get("required_concepts"):
            ctx["required_concepts"] = item["required_concepts"]
        return run_scoring_pipeline(answer_text=item["answer"], question_context=ctx)
    finally:
        os.environ.pop("SCORER_VERSION", None)


def test_v4_fixture_extends_v3_cases(fixture: dict) -> None:
    assert fixture["scorer_version"] == "v4"
    ids = {item["id"] for item in fixture["items"]}
    assert {
        "short_full_marks", "noun_phrase_answer", "code_syntax_answer",
        "paraphrase_exceeds_90", "alias_only_mention",
    } <= ids
    assert len(fixture["items"]) == 16


@pytest.mark.requires_semantic_model
def test_v4_new_cases_behave(fixture: dict) -> None:
    by_id = {item["id"]: item for item in fixture["items"]}

    short = _run(by_id["short_full_marks"])
    assert short["guard_applied"] is None
    assert short["final_score"] >= 70.0

    noun = _run(by_id["noun_phrase_answer"])
    assert noun["guard_applied"] is None

    code = _run(by_id["code_syntax_answer"])
    assert code["guard_applied"] != "gibberish"

    para = _run(by_id["paraphrase_exceeds_90"])
    assert para["final_score"] > 90.0

    alias = _run(by_id["alias_only_mention"])
    assert alias["scoring_breakdown"]["concept_coverage"] == 0.0
