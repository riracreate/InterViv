"""Adaptive question selector tests (Phase 2 Task 7).

Spec scenario:
    Run a 6-round session for a user weak in Trees and Dynamic
    Programming. Rounds 3-6 must increasingly target those concepts.

We don't call the real OpenRouter API here — instead we monkey-patch
``modules.adaptive_question_selector._call_llm`` with a stub that
echoes the targeted concepts back into the question text so the
assertion can verify what was prompted.
"""
from __future__ import annotations

import json
import os
import re

import pytest

# Loosen the LLM-strict guard the project .env sets for production —
# tests use the CSV/template fallback when the targeted LLM is mocked off.
os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ["QUESTION_GENERATION_MODE"] = "llm_csv_fallback"
os.environ["QUESTION_REQUIRE_LLM"] = "false"
# Adaptive tests stub _call_llm; keep generation mode llm* for stubs that
# exercise the targeted path. Force live-fetch on so an unstubbed call would
# still reach the client (tests that assert no dial use monkeypatch).
os.environ["LLM_LIVE_FETCH"] = "1"

from modules import adaptive_question_selector as aqs  # noqa: E402
from modules.concept_mastery import ConceptMastery  # noqa: E402
from modules.skill_graph import StudentSkillGraph  # noqa: E402


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_pick_target_concepts_empty_for_unknown_user() -> None:
    assert aqs.pick_target_concepts("nobody", "DSA") == []


def test_pick_target_concepts_prefers_weak_over_untested() -> None:
    cm = ConceptMastery()
    cm.update_from_round(
        user_id="u-priority",
        skill="DSA",
        covered_concepts=["array", "pointer"],
        missing_concepts=["tree", "dynamic_programming"],
    )
    # tree + dynamic_programming attempted but not demonstrated → Weak.
    # Other DSA KG concepts are still Untested (no row).
    targets = aqs.pick_target_concepts("u-priority", "DSA", limit=4)
    # Weak entries come first
    weak_position = [i for i, t in enumerate(targets) if t in {"tree", "dynamic programming"}]
    assert weak_position == sorted(weak_position)
    assert "tree" in targets or "dynamic programming" in targets


def test_build_targeted_prompt_appends_spec_extension() -> None:
    prompt = aqs.build_targeted_prompt(
        "DSA", "general", "medium", [], ["tree", "dynamic programming"]
    )
    expected = (
        "ADDITIONAL TARGETING: Generate a question that primarily tests "
        "the following concepts: tree, dynamic programming. The question "
        "should naturally require the candidate to demonstrate "
        "understanding of these concepts."
    )
    assert expected in prompt


def test_build_targeted_prompt_no_targets_returns_base_prompt() -> None:
    base = aqs.build_targeted_prompt("DSA", "general", "medium", [], [])
    assert "ADDITIONAL TARGETING" not in base


def test_choose_adaptive_target_uses_skill_graph_when_no_role() -> None:
    graph = StudentSkillGraph("u-skill-target")
    graph.initialize_from_resume(["Python", "DSA"])
    graph.update_after_round("Python", 82, "medium")
    graph.update_after_round("DSA", 35, "medium")

    target = aqs.choose_adaptive_target(
        user_id="u-skill-target",
        fallback_skill="Python",
        fallback_difficulty="medium",
        session_skills=["Python", "DSA"],
    )

    assert target.skill == "DSA"
    assert target.source == "skill_graph"


def test_choose_adaptive_target_prefers_gap_analysis_role() -> None:
    graph = StudentSkillGraph("u-gap-target")
    graph.initialize_from_resume(["Python", "DSA", "DBMS", "OOP", "HR", "System Design"])
    graph.update_after_round("Python", 90, "medium")
    graph.update_after_round("DSA", 20, "medium")

    target = aqs.choose_adaptive_target(
        user_id="u-gap-target",
        fallback_skill="Python",
        fallback_difficulty="medium",
        session_skills=["Python", "DSA", "DBMS", "OOP", "HR", "System Design"],
        target_role_id="amazon_sde_intern",
    )

    assert target.skill == "DSA"
    assert target.source == "gap_analysis"


# ---------------------------------------------------------------------------
# select_next_question — adaptive vs fallback paths
# ---------------------------------------------------------------------------

def _fake_targeted_llm(captured: list[str]):
    """Return a stub _call_llm that records prompts and echoes the
    concept list back inside the question text."""
    def call(prompt: str) -> str:
        captured.append(prompt)
        # Extract the targeted concepts from the prompt for echo
        m = re.search(r"following concepts: ([^.]+)\.", prompt)
        concept_phrase = m.group(1).strip() if m else "the topic"
        return json.dumps({
            "question": f"Discuss {concept_phrase} in depth and explain trade-offs.",
            "ideal_answer": "A sample reference answer covering the targeted concepts.",
            "ideal_keywords": "tree, dynamic programming, recursion, memoization, complexity",
        })
    return call


def test_anonymous_session_skips_targeting(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(aqs, "_call_llm", _fake_targeted_llm(captured))
    q = aqs.select_next_question(
        user_id=None, skill="DSA", sub_domain="general",
        difficulty="medium", asked=[],
    )
    assert q.get("adaptive_selected") is False
    assert q.get("target_concepts") == []
    assert captured == [], "anonymous selection must not call the targeted LLM"


def test_user_without_mastery_skips_targeting(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(aqs, "_call_llm", _fake_targeted_llm(captured))
    q = aqs.select_next_question(
        user_id="u-fresh", skill="DSA", sub_domain="general",
        difficulty="medium", asked=[],
    )
    assert q.get("adaptive_selected") is False
    assert q.get("target_concepts") == []
    assert captured == []


def test_user_with_mastery_routes_through_targeted_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    cm = ConceptMastery()
    cm.update_from_round(
        user_id="u-targeted",
        skill="DSA",
        covered_concepts=["array"],
        missing_concepts=["tree", "dynamic_programming"],
    )
    captured: list[str] = []
    monkeypatch.setattr(aqs, "_call_llm", _fake_targeted_llm(captured))

    q = aqs.select_next_question(
        user_id="u-targeted", skill="DSA", sub_domain="general",
        difficulty="medium", asked=[],
    )
    assert q["adaptive_selected"] is True
    assert q["target_concepts"], "should be non-empty"
    assert len(captured) == 1
    assert "ADDITIONAL TARGETING" in captured[0]
    # The echoed question should reference the targeted concepts
    lowered = q["question"].lower()
    assert any(c in lowered for c in ("tree", "dynamic programming"))


def test_llm_failure_falls_back_to_question_bank(monkeypatch: pytest.MonkeyPatch) -> None:
    cm = ConceptMastery()
    cm.update_from_round(
        user_id="u-llm-down",
        skill="DSA",
        covered_concepts=["array"],
        missing_concepts=["tree"],
    )
    # _call_llm returns None → adaptive path bails out → fallback to
    # question_bank, which in llm_csv_fallback mode uses CSV/template.
    monkeypatch.setattr(aqs, "_call_llm", lambda prompt: None)
    q = aqs.select_next_question(
        user_id="u-llm-down", skill="DSA", sub_domain="general",
        difficulty="medium", asked=[],
    )
    assert q.get("adaptive_selected") is False
    assert q.get("question"), "fallback must still produce a question"


# ---------------------------------------------------------------------------
# Spec evidence — 6-round Trees + DP scenario
# ---------------------------------------------------------------------------

@pytest.fixture()
def trees_dp_user() -> str:
    """Seed concept mastery for a fresh user weak in Trees + DP."""
    user_id = "u-trees-dp-spec"
    cm = ConceptMastery()
    # Pretend round 1 covered easy DSA but missed Trees + DP.
    cm.update_from_round(
        user_id=user_id,
        skill="DSA",
        covered_concepts=["array", "pointer", "stack"],
        missing_concepts=["tree", "dynamic_programming"],
    )
    return user_id


def test_six_round_session_increasingly_targets_trees_and_dp(
    trees_dp_user: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_prompts: list[str] = []
    monkeypatch.setattr(aqs, "_call_llm", _fake_targeted_llm(captured_prompts))

    questions = []
    asked: list[str] = []
    for round_num in range(1, 7):
        q = aqs.select_next_question(
            user_id=trees_dp_user, skill="DSA", sub_domain="general",
            difficulty="medium", asked=asked,
        )
        questions.append(q)
        asked.append(q["question"])

        # Simulate the user continuing to struggle with Trees + DP each round.
        if round_num <= 3:
            ConceptMastery().update_from_round(
                user_id=trees_dp_user,
                skill="DSA",
                covered_concepts=["array"],
                missing_concepts=["tree", "dynamic_programming", "memoization"],
            )

    # Every round was adaptive (the user has mastery data from round 1).
    for i, q in enumerate(questions, start=1):
        assert q["adaptive_selected"] is True, f"round {i} not adaptive"

    # Rounds 3-6 must mention "tree" OR "dynamic programming" in the
    # generated question text — that's the spec's emphasis check.
    target_phrases = ("tree", "dynamic programming")
    for i in range(2, 6):  # zero-indexed: rounds 3-6
        text = questions[i]["question"].lower()
        assert any(p in text for p in target_phrases), (
            f"round {i + 1} question doesn't reference targets: {questions[i]['question']!r}"
        )

    # Every captured prompt carries the spec extension verbatim.
    for prompt in captured_prompts:
        assert "ADDITIONAL TARGETING" in prompt
        assert "primarily tests the following concepts" in prompt
