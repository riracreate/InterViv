"""Tests for the Phase 2.1 Verbal Ability bank (original content, separate list)."""

from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.db.sqlalchemy_models import Base, MCQQuestionRow, SkillRow
from backend.db.phase2_content_bank import PHASE2_MCQ_BANK, PHASE2_SQL_BANK
from backend.db.phase21_verbal_bank import (
    PHASE21_VERBAL_BANK,
    VERBAL_SKILL,
    seed_verbal_bank,
)

NEGATIVE_STEM_PATTERN = re.compile(
    r"\b(not|except|neither|nor|incorrect|untrue|least|never)\b",
    re.IGNORECASE,
)

GROUPS = ("vocabulary", "grammar", "completion", "comprehension", "ordering", "idioms")


def test_verbal_bank_size_and_distribution() -> None:
    """30 questions: 6 groups x 5, each 2 easy / 2 medium / 1 hard."""
    assert len(PHASE21_VERBAL_BANK) == 30
    assert VERBAL_SKILL == "Verbal Ability"

    subs = Counter(q["sub_domain"] for q in PHASE21_VERBAL_BANK)
    assert dict(subs) == {g: 5 for g in GROUPS}

    diffs = Counter(q["difficulty"] for q in PHASE21_VERBAL_BANK)
    assert dict(diffs) == {"easy": 12, "medium": 12, "hard": 6}

    for group in GROUPS:
        actual = Counter(
            q["difficulty"] for q in PHASE21_VERBAL_BANK if q["sub_domain"] == group
        )
        assert dict(actual) == {"easy": 2, "medium": 2, "hard": 1}, group

    assert {q["skill"] for q in PHASE21_VERBAL_BANK} == {VERBAL_SKILL}


def test_verbal_bank_schema_invariants() -> None:
    """Unique ids/stems, 4 options a-d, one valid key, explained distractors."""
    ids = [q["id"] for q in PHASE21_VERBAL_BANK]
    assert len(ids) == len(set(ids)) == 30
    assert all(i.startswith("mcq_verbal_") for i in ids)

    stems = [q["stem"] for q in PHASE21_VERBAL_BANK]
    assert len(stems) == len(set(stems)), "stems must be unique (DB constraint)"

    for q in PHASE21_VERBAL_BANK:
        qid = q["id"]
        match = NEGATIVE_STEM_PATTERN.search(q["stem"])
        assert match is None, f"{qid} negative phrasing {match.group(0)!r}"

        options = q["options_json"]
        assert [o["id"] for o in options] == ["a", "b", "c", "d"], qid
        texts = [o["text"].strip() for o in options]
        assert all(texts), f"{qid} has an empty option"
        assert len({t.lower() for t in texts}) == 4, f"{qid} has duplicate options"

        correct = q["correct_option_ids"]
        assert len(correct) == 1 and correct[0] in "abcd", qid

        explanation = q.get("explanation") or ""
        assert len(explanation) >= 80, f"{qid} explanation too short"
        for letter in "abcd":
            if letter != correct[0]:
                assert f"({letter})" in explanation, f"{qid} never rules out ({letter})"

        assert q["negative_marking"] == 0.25, qid


def test_verbal_key_positions_balanced() -> None:
    """Each of a-d is the key 7 or 8 times across the 30 questions."""
    keys = Counter(q["correct_option_ids"][0] for q in PHASE21_VERBAL_BANK)
    assert set(keys) == set("abcd")
    for letter, count in sorted(keys.items()):
        assert 7 <= count <= 8, f"key {letter} used {count} times"


def test_verbal_passages_self_contained() -> None:
    """Comprehension stems embed the full passage; exactly 2 original passages."""
    stems = [q["stem"] for q in PHASE21_VERBAL_BANK if q["sub_domain"] == "comprehension"]
    assert len(stems) == 5
    passages = set()
    for stem in stems:
        assert "Passage:" in stem and "Question:" in stem
        assert len(stem) > 300, "comprehension stem looks truncated"
        passages.add(stem.split("Passage:", 1)[1].split("Question:", 1)[0].strip())
    assert len(passages) == 2, "expected exactly 2 distinct passages"


def test_verbal_bank_disjoint_from_technical() -> None:
    """No shared ids or stems with the approved Phase 2 bank."""
    tech_ids = {q["id"] for q in PHASE2_MCQ_BANK}
    tech_stems = {q["stem"] for q in PHASE2_MCQ_BANK}
    for q in PHASE21_VERBAL_BANK:
        assert q["id"] not in tech_ids, q["id"]
        assert q["stem"] not in tech_stems, q["id"]


def _fresh_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return Session(bind=engine)


def test_seed_verbal_bank_idempotent() -> None:
    """First seed inserts 30; second seed inserts nothing and duplicates nothing."""
    session = _fresh_session()
    try:
        assert seed_verbal_bank(session) == 30
        assert seed_verbal_bank(session) == 0
        rows = session.scalars(select(MCQQuestionRow)).all()
        assert len(rows) == 30
        assert len({r.id for r in rows}) == 30
        skills = session.scalars(
            select(SkillRow).where(SkillRow.canonical_name == VERBAL_SKILL)
        ).all()
        assert len(skills) == 1
        assert {r.skill_id for r in rows} == {skills[0].id}
    finally:
        session.close()


def test_existing_banks_unchanged() -> None:
    """The approved Phase 2 banks keep their exact size."""
    assert len(PHASE2_MCQ_BANK) == 150
    assert len(PHASE2_SQL_BANK) == 30
