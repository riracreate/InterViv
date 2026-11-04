"""Overhaul Phase 5: system-design written-content practice estimate.

Versioned separately (v1-system-design-content); the self-assessment scorer
is unchanged for rounds started under it. Results are practice_review
evidence and never move Elo, mastery or readiness (see
tests/test_phaseE_system_design.py).
"""

from __future__ import annotations

from modules.scoring import score_round
from modules.scoring.system_design import (
    CONTENT_EVALUATION_MODE,
    CONTENT_SCHEMA_VERSION,
    score_system_design_content_v1,
)

CTX = {"id": "sd_rate_limiter"}
STRONG = (
    "Requirements: allow 100 requests per minute per API key and return 429 Too Many Requests with a "
    "Retry-After header; the check must add little latency across multiple servers in a distributed setup. "
    "Algorithm: a token bucket stored in Redis, updated with an atomic Lua script, with a TTL on each key "
    "so idle clients expire. Scale: race conditions are avoided by the atomic update, keys are partitioned "
    "with consistent hashing, and a local in-memory counter absorbs bursts. If Redis is down we fail open "
    "because availability matters more than accuracy, which means some extra requests may pass. "
    "Trade-off: token bucket versus sliding window — the sliding window is more accurate but uses more memory."
)
WEAK = (
    "We will build a rate limiter service that checks every incoming request and blocks clients that "
    "send too many requests to the public API so the system stays healthy for all users."
)
RATINGS = {"requirements": 4, "api_data": 4, "scale": 4, "tradeoffs": 4}


def test_richer_notes_score_higher_with_per_criterion_evidence():
    strong = score_system_design_content_v1(answer=STRONG, question_context=CTX)
    weak = score_system_design_content_v1(answer=WEAK, question_context=CTX)
    assert strong["final_score"] > weak["final_score"]
    assert strong["evaluation_mode"] == CONTENT_EVALUATION_MODE
    assert strong["scoring_schema_version"] == CONTENT_SCHEMA_VERSION
    criteria = {c["id"]: c for c in strong["artifact_json"]["criteria"]}
    assert set(criteria) == {"requirements", "api_data", "scale", "tradeoffs"}
    assert "429 response" in criteria["requirements"]["mentioned"]
    assert any("token bucket" in e["excerpt"].lower() for e in criteria["api_data"]["excerpts"])
    assert criteria["tradeoffs"]["depth"] > 0  # "because" / "versus" explanations
    assert all(len(e["excerpt"]) <= 160 for c in criteria.values() for e in c["excerpts"])
    assert weak["feedback"]["missing_concepts"]


def test_blend_is_70_content_30_self_rating_only_with_all_four_ratings():
    content_only = score_system_design_content_v1(answer=STRONG, question_context=CTX)
    blended = score_system_design_content_v1(answer=STRONG, rubric_ratings=RATINGS, question_context=CTX)
    content = content_only["artifact_json"]["content_score"]
    assert content_only["final_score"] == content
    assert blended["final_score"] == round(0.7 * content + 0.3 * 75.0, 2)
    partial = score_system_design_content_v1(
        answer=STRONG, rubric_ratings={"requirements": 5, "scale": 5}, question_context=CTX)
    assert partial["final_score"] == content
    assert partial["artifact_json"]["self_rating_score"] is None


def test_written_content_is_required():
    short = score_system_design_content_v1(answer="Use Redis.", rubric_ratings=RATINGS, question_context=CTX)
    assert short["final_score"] is None and short["incomplete"] is True
    unknown_prompt = score_system_design_content_v1(answer=STRONG, question_context={"id": "nope"})
    assert unknown_prompt["final_score"] is None


def test_deterministic():
    first = score_system_design_content_v1(answer=STRONG, rubric_ratings=RATINGS, question_context=CTX)
    second = score_system_design_content_v1(answer=STRONG, rubric_ratings=RATINGS, question_context=CTX)
    assert first == second


def test_rounds_started_as_self_assessment_keep_the_original_scorer():
    legacy = score_round(round_type="system_design", answer_text="Short notes.",
                         rubric_ratings=RATINGS, question_context=CTX,
                         config={"evaluation_mode": "structured_self_assessment"})
    assert legacy["evaluation_mode"] == "structured_self_assessment"
    assert legacy["final_score"] == 75.0
    new = score_round(round_type="system_design", answer_text=STRONG, rubric_ratings=RATINGS,
                      question_context=CTX, config={"evaluation_mode": CONTENT_EVALUATION_MODE})
    assert new["evaluation_mode"] == CONTENT_EVALUATION_MODE
