"""Tests for Phase 2 verified MCQ and SQL content banks."""

from __future__ import annotations

import re
from collections import Counter
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.db.sqlalchemy_models import Base, MCQQuestionRow, SQLProblemRow, SQLProblemCaseRow, SkillRow
from backend.db.phase2_content_bank import PHASE2_MCQ_BANK, PHASE2_SQL_BANK, seed_phase2_content_bank
from modules.scoring.sql_round import score_sql_round


NEGATIVE_STEM_PATTERN = re.compile(
    r"\b(not|except|neither|nor|incorrect|untrue|least|never)\b",
    re.IGNORECASE,
)


def test_mcq_bank_size_and_skill_distribution() -> None:
    """Verify bank contains 150 MCQs, 30 per core skill, 10 easy/medium/hard each."""
    assert len(PHASE2_MCQ_BANK) == 150

    skills = Counter(q["skill"] for q in PHASE2_MCQ_BANK)
    expected_skills = {"DBMS", "Python", "OS", "Computer Networks", "DSA"}
    assert set(skills.keys()) == expected_skills

    for skill_name in expected_skills:
        assert skills[skill_name] == 30
        diffs = Counter(q["difficulty"] for q in PHASE2_MCQ_BANK if q["skill"] == skill_name)
        assert diffs == {"easy": 10, "medium": 10, "hard": 10}


def test_mcq_bank_quality_and_schema_invariants() -> None:
    """Verify uniqueness, zero negative phrasing, 4 options, and valid single keys."""
    ids = [q["id"] for q in PHASE2_MCQ_BANK]
    assert len(ids) == len(set(ids)), "MCQ IDs must be unique"

    stems = [q["stem"] for q in PHASE2_MCQ_BANK]
    assert len(stems) == len(set(stems)), "MCQ stems must be unique"

    for q in PHASE2_MCQ_BANK:
        qid = q["id"]
        stem = q["stem"]
        match = NEGATIVE_STEM_PATTERN.search(stem)
        assert match is None, f"Question {qid} has negative phrasing '{match.group(0)}': {stem}"

        options = q["options_json"]
        assert len(options) == 4, f"Question {qid} must have exactly 4 options"
        opt_ids = [opt["id"] for opt in options]
        assert opt_ids == ["a", "b", "c", "d"], f"Question {qid} must have options a, b, c, d"

        for opt in options:
            assert opt["text"].strip(), f"Question {qid} option {opt['id']} text is empty"

        correct = q["correct_option_ids"]
        assert len(correct) == 1, f"Question {qid} must have exactly 1 correct option"
        assert correct[0] in opt_ids, f"Question {qid} correct option {correct[0]} not in options"

        explanation = q.get("explanation") or ""
        assert explanation.strip(), f"Question {qid} must have non-empty explanation"
        assert q["negative_marking"] == 0.25, f"Question {qid} negative_marking must be 0.25"


def test_sql_bank_size_and_case_distribution() -> None:
    """Verify 30 SQL problems (10 easy, 10 medium, 10 hard), each with 3 cases."""
    assert len(PHASE2_SQL_BANK) == 30

    diffs = Counter(p["difficulty"] for p in PHASE2_SQL_BANK)
    assert diffs == {"easy": 10, "medium": 10, "hard": 10}

    prob_ids = [p["id"] for p in PHASE2_SQL_BANK]
    assert len(prob_ids) == len(set(prob_ids)), "Problem IDs must be unique"

    for p in PHASE2_SQL_BANK:
        pid = p["id"]
        assert p["prompt"].strip(), f"Problem {pid} prompt is empty"
        assert p["schema_ddl"].strip(), f"Problem {pid} schema_ddl is empty"
        assert p["reference_query"].strip(), f"Problem {pid} reference_query is empty"

        cases = p.get("cases") or []
        assert len(cases) == 3, f"Problem {pid} must have exactly 3 cases"
        case_types = [c["case_type"] for c in cases]
        assert case_types == ["visible_sample", "hidden_case", "hidden_case"]
        sort_orders = [c["sort_order"] for c in cases]
        assert sort_orders == [0, 1, 2]
        for c in cases:
            assert c["seed_data"].strip(), f"Problem {pid} case {c['sort_order']} seed_data is empty"


@pytest.mark.parametrize("prob_idx", list(range(30)))
def test_sql_bank_reference_queries_solve_all_cases(prob_idx: int) -> None:
    """Verify that every reference query scores 100% across all 3 test cases."""
    problem = PHASE2_SQL_BANK[prob_idx]
    res = score_sql_round(candidate_query=problem["reference_query"], question_context=problem)

    assert res["final_score"] == 100.0, f"Problem {problem['id']} failed scoring: {res['score_explanation']}"
    artifact = res["artifact_json"]
    assert artifact["total_cases"] == 3
    assert artifact["passed_cases"] == 3
    for case in artifact["cases"]:
        assert case["passed"] is True
        assert case["result_match"] is True
        assert case["row_count_match"] is True
        assert case["error"] is None


def test_seed_phase2_content_bank_idempotent() -> None:
    """Verify that seeding into a fresh SQLite database succeeds and is idempotent."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_phase2_content_bank(session)

    with Session(engine) as session:
        mcq_count = len(session.scalars(select(MCQQuestionRow)).all())
        sql_count = len(session.scalars(select(SQLProblemRow)).all())
        case_count = len(session.scalars(select(SQLProblemCaseRow)).all())
        skill_count = len(session.scalars(select(SkillRow)).all())

        assert mcq_count == 150
        assert sql_count == 30
        assert case_count == 90
        assert skill_count == 5

        # Re-seed to verify idempotency
        seed_phase2_content_bank(session)

        # Assert counts remain identical
        assert len(session.scalars(select(MCQQuestionRow)).all()) == 150
        assert len(session.scalars(select(SQLProblemRow)).all()) == 30
        assert len(session.scalars(select(SQLProblemCaseRow)).all()) == 90
        assert len(session.scalars(select(SkillRow)).all()) == 5
