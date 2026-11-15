"""Scorer v4: flag, shared features, v4 guards, evaluator strict mode, version stamp."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("LLM_LIVE_FETCH", "0")

from modules import concept_evaluator_v3 as ev3
from modules.answer_guard_v4 import check_answer_quality_v4
from modules.scoring_features import FEATURE_NAMES, build_scoring_features
from modules.scoring_schema import current_scorer_version

OOP_IDEAL = (
    "The four pillars are encapsulation, inheritance, polymorphism, and abstraction. "
    "Encapsulation hides internal state behind methods; inheritance lets subclasses reuse "
    "behaviour; polymorphism allows subtypes to be used interchangeably via method overriding; "
    "abstraction exposes only essential operations and follows SOLID design principles."
)


def test_scorer_version_defaults_to_v3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCORER_VERSION", raising=False)
    assert current_scorer_version() == "v3"
    monkeypatch.setenv("SCORER_VERSION", "v4")
    assert current_scorer_version() == "v4"
    monkeypatch.setenv("SCORER_VERSION", "bogus")
    assert current_scorer_version() == "v3"


def test_features_have_no_word_count_or_pinned_keyword() -> None:
    feats = build_scoring_features(
        answer_text="Encapsulation hides internal state behind methods.",
        ideal_answer=OOP_IDEAL,
    )
    assert tuple(feats) == FEATURE_NAMES
    assert "word_count" not in feats and "length_ratio" not in feats
    # Empty reference must not pin any feature to 0.5.
    empty_ref = build_scoring_features(answer_text="Some answer text here.", ideal_answer="")
    assert empty_ref["ideal_content_recall"] == 0.0


def test_guard_v4_noun_phrase_not_truncated() -> None:
    out = check_answer_quality_v4(
        "Member functions and data members belonging to the class.",
        question_text="What are the elements typically included in a class definition?",
        ideal_answer="A class typically includes data members and member functions.",
    )
    assert out["cap_required"] is False


def test_guard_v4_two_word_repetition_not_flagged() -> None:
    out = check_answer_quality_v4("the data and methods", ideal_answer="Data and functions.")
    assert out.get("reason") != "repetition"


def test_guard_v4_code_answer_not_gibberish() -> None:
    out = check_answer_quality_v4(
        "Execution starts at int main() { return 0; } — the entry point.",
        question_text="Where does execution of a C program start?",
        ideal_answer="Execution starts at the main function.",
    )
    assert out.get("reason") != "gibberish"


def test_guard_v4_parroting_reference_overlap_exempt() -> None:
    out = check_answer_quality_v4(
        "What is a pointer variable that stores a memory address",
        question_text="What is a pointer?",
        ideal_answer="A pointer is a variable that stores a memory address.",
    )
    assert out.get("reason") != "question_parroting"


def test_guard_v4_short_full_marks_not_too_short() -> None:
    out = check_answer_quality_v4(
        "It follows the C3 linearization of the class hierarchy.",
        question_text="What is method resolution order (MRO) in Python?",
        ideal_answer=(
            "MRO determines the order Python searches for methods and attributes in class "
            "hierarchies with multiple inheritance. Python uses the C3 linearization algorithm."
        ),
    )
    assert out["cap_required"] is False


def test_guard_v4_still_catches_gibberish_and_repetition() -> None:
    assert check_answer_quality_v4("asdf qwer zxcv jkl;")["reason"] == "gibberish"
    repeated = check_answer_quality_v4(" ".join(["banana"] * 6))
    assert repeated["reason"] == "repetition"


def _bundle() -> dict:
    return {
        "required_concepts": [
            {
                "id": "token_bucket",
                "descriptor": "Token bucket controls burst and average rate",
                "aliases": ["token bucket"],
                "expected_propositions": ["steady refill rate replenishes the bucket"],
            }
        ]
    }


def test_evaluator_strict_alias_is_mentioned_never_supported() -> None:
    answer = "Token bucket."
    lenient = ev3.evaluate_answer(answer_text=answer, bundle_content=_bundle())
    strict = ev3.evaluate_answer(answer_text=answer, bundle_content=_bundle(), strict=True)
    assert lenient["concepts"][0]["state"] == "supported"
    assert lenient["concepts"][0]["match_type"] == "alias"
    assert strict["concepts"][0]["state"] == "mentioned"
    assert strict["coverage"]["k_supported"] == 0
    assert strict["evaluator_version"] == "concept_evaluator_v3.1"
    assert lenient["evaluator_version"] == ev3.EVALUATOR_VERSION


def test_pipeline_v4_dispatch_and_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCORER_VERSION", "v4")
    from backend.scoring import pipeline

    pipeline._load_v4_regression.cache_clear()
    pipeline._load_v4_calibration.cache_clear()
    out = pipeline.run_scoring_pipeline(
        answer_text="Encapsulation hides internal state behind public methods so callers depend only on the interface.",
        question_context={
            "question": "Explain the four pillars of OOP.",
            "ideal_answer": OOP_IDEAL,
            "ideal_keywords": "encapsulation, inheritance, polymorphism, abstraction",
        },
    )
    assert out["scorer_version"] == "v4"
    assert out["scoring_breakdown"]["scorer_version"] == "v4"
    assert "features_v4" in out["scoring_breakdown"]


def test_pipeline_default_remains_v3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SCORER_VERSION", raising=False)
    from backend.scoring import pipeline

    out = pipeline.run_scoring_pipeline(
        answer_text="Encapsulation hides internal state behind public methods.",
        question_context={
            "question": "Explain the four pillars of OOP.",
            "ideal_answer": OOP_IDEAL,
            "ideal_keywords": "encapsulation, inheritance, polymorphism, abstraction",
        },
    )
    assert out.get("scorer_version") is None
    assert out["scoring_breakdown"].get("scorer_version") is None


def test_round_persistence_stamps_scorer_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "rounds.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.delenv("SCORER_VERSION", raising=False)
    from backend import config as app_config
    from backend.db.sqlalchemy_models import Base, SessionRow, UserRow
    from backend.db.sqlalchemy_store import _SessionCollection, _sessionmaker, get_engine, session_scope

    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    Base.metadata.create_all(get_engine())
    try:
        with session_scope() as session:
            session.add(UserRow(id="u1", email="v4@example.test", password_hash="x"))
            session.flush()
            row = SessionRow(id="sess-v4-test", user_id="u1", status="active")
            session.add(row)
            session.flush()
            _SessionCollection._replace_rounds(
                session,
                row,
                [{"round": 1, "answer_text": "x", "scoring_breakdown": {"final_score": 42.0}}],
            )
            session.flush()
            stored = session.query(SessionRow).one().rounds[0].scoring_breakdown_json
        assert stored["scorer_version"] == "v3"
    finally:
        app_config.get_settings.cache_clear()
        get_engine.cache_clear()
        _sessionmaker.cache_clear()
