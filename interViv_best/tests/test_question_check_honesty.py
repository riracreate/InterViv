"""Phase 0: the automated question check must be honest.

- Step E.2 blind check runs ``concept_evaluator_v3`` in strict mode (v3.1),
  so an alias mention never counts as concept support.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")
os.environ.setdefault("LLM_LIVE_FETCH", "0")

from backend import config as app_config
from backend.db.sqlalchemy_store import _sessionmaker, get_engine, get_sqlalchemy_database
from modules import (
    bundle_generator,
    bundle_jobs,
    bundle_store,
    concept_evaluator_v3,
    llm_usage,
    role_skills,
)

STRICT_VERSION = "concept_evaluator_v3.1"


def _clear_all_caches() -> None:
    app_config.get_settings.cache_clear()
    get_engine.cache_clear()
    _sessionmaker.cache_clear()
    get_sqlalchemy_database.cache_clear()


@pytest.fixture
def memory_store(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "true")
    monkeypatch.setenv("LLM_LIVE_FETCH", "0")
    # Deterministic offline: only the proposition and alias tiers run.
    monkeypatch.setenv("DISABLE_SEMANTIC_SCORING", "1")
    monkeypatch.delenv("REVIEWED_BUNDLES_ONLY", raising=False)
    _clear_all_caches()
    bundle_store.reset_memory_store()
    llm_usage.reset_memory_usage()
    bundle_jobs.reset_memory_bundle_jobs()
    role_skills.reset_role_skill_cache(reset_canonicals=True)
    bundle_generator.set_bundle_llm_override(None)
    yield tmp_path
    bundle_generator.set_bundle_llm_override(None)
    bundle_store.reset_memory_store()
    llm_usage.reset_memory_usage()
    bundle_jobs.reset_memory_bundle_jobs()
    role_skills.reset_role_skill_cache(reset_canonicals=True)
    _clear_all_caches()


def _payload() -> dict:
    """A generated bundle whose aliases and ids are not question words."""
    return {
        "question": (
            "A salary dataset has a few extreme high earners. Which summary statistic "
            "would you report for a typical employee, and why?"
        ),
        "reference_answer": (
            "Report the median. Salary data is usually right-skewed: a small number of very "
            "large salaries drag the arithmetic mean upward, so the average describes almost "
            "nobody. The median is the middle observation once salaries are sorted, so it only "
            "depends on rank order and stays close to what a typical worker earns even when the "
            "highest salaries grow. When the distribution is roughly symmetric the two measures "
            "agree, but for lopsided income data the median is the more representative figure. "
            "A trimmed mean is a reasonable alternative when an average is required."
        ),
        "acceptable_variants": ["Use the median, because outliers inflate the mean."],
        "keywords": ["median", "mean", "outliers", "skewness", "robust statistic"],
        "required_concepts": [
            {
                "id": "mean_pulled_by_outliers",
                "descriptor": "Extreme values pull the arithmetic mean toward them",
                "aliases": ["arithmetic average", "skewed mean"],
                "expected_propositions": [
                    "outliers pull the arithmetic mean upward",
                    "extreme earners inflate the average salary",
                ],
                "positive_examples": [
                    "A handful of very large salaries drags the average far above most pay.",
                    "The mean gets inflated because a few huge values pull it upward.",
                ],
            },
            {
                "id": "median_resists_outliers",
                "descriptor": "The median ignores how extreme the tail values are",
                "aliases": ["middle value", "50th percentile"],
                "expected_propositions": [
                    "the median resists extreme outliers",
                    "median salary stays near typical pay",
                ],
                "positive_examples": [
                    "The middle value barely moves even if the top earners double their pay.",
                    "Taking the midpoint of sorted salaries gives a figure the outliers cannot move.",
                ],
            },
            {
                "id": "report_median_for_skew",
                "descriptor": "Skewed distributions are better summarised by the median",
                "aliases": ["right skew", "skewed distribution"],
                "expected_propositions": [
                    "right skew makes median more representative",
                    "skewed salary distributions favour the median",
                ],
                "positive_examples": [
                    "Because pay is right-skewed, the median describes a normal worker better.",
                    "For lopsided income data I would quote the median rather than the mean.",
                ],
            },
        ],
        "optional_concepts": [
            {
                "id": "trimmed_mean_alternative",
                "descriptor": "A trimmed mean drops extreme values before averaging",
                "aliases": ["trimmed mean", "winsorizing"],
                "expected_propositions": ["trimmed mean drops extreme values"],
            }
        ],
        "misconceptions": [
            {
                "id": "mean_always_best",
                "description": "the mean is always the best summary of typical salary",
                "candidate_patterns": [
                    "mean is always the best summary",
                    "always report the average salary",
                ],
            }
        ],
        "depth_markers": ["rank-based statistic", "trimmed mean", "skewness coefficient"],
        "rubric_descriptors": {
            "coverage": "Explains outlier pull on the mean and median robustness.",
            "accuracy": "Does not claim the mean is always best.",
            "depth": "Mentions skew or a trimmed mean.",
            "clarity": "Gives a clear recommendation.",
        },
        "followups": [
            {
                "prompt": "Why does the median stay put when the top salaries grow?",
                "targets_concept": "median_resists_outliers",
            },
            {
                "prompt": "What happens to the average when one executive salary triples?",
                "targets_concept": "mean_pulled_by_outliers",
            },
        ],
        "calibration_examples": [
            {
                "answer": (
                    "Report the median: a few huge salaries pull the mean upward, while the "
                    "median stays near typical pay because the data are right-skewed."
                ),
                "author_level": 3,
                "expected_band": "Good",
            },
            {
                "answer": (
                    "You should always report the average salary because it uses every number "
                    "in the spreadsheet and statistics teachers say the average is the most "
                    "scientific measure there is. Outliers are not really a problem because "
                    "they cancel out over time when the company grows, and the median is only "
                    "used by people who cannot calculate averages properly. In my experience the "
                    "mean is always the best summary for any business decision, and managers "
                    "prefer it since it looks bigger and makes the company appear generous to "
                    "new hires and investors who read annual reports every quarter carefully."
                ),
                "author_level": 0,
                "expected_band": "Poor",
            },
        ],
    }


ALIAS_ONLY_ANSWER = (
    "I would talk about the arithmetic average, the middle value, and right skew. "
    "A skewed distribution and the 50th percentile both matter here."
)

PROPOSITION_ANSWER = (
    "Outliers pull the arithmetic mean upward, so the average overstates pay. "
    "The median resists extreme outliers, and right skew makes median more "
    "representative of a typical employee."
)


def _override(blind_answer: str, *, audit_issue: str = "propositions"):
    regen_count = {"n": 0}

    def _fake(purpose: str, model: str, messages: list[dict], **kwargs):
        if purpose == "bundle_generation":
            return {"content": json.dumps(_payload()), "usage": {"total_tokens": 100}}
        if purpose == "bundle_blind_answer":
            return {"content": blind_answer, "usage": {"total_tokens": 40}}
        if purpose == "bundle_check_audit":
            return {
                "content": json.dumps(
                    {"root_cause": "x", "issue_type": audit_issue, "missed_concepts": [], "fixes": []}
                ),
                "usage": {"total_tokens": 20},
            }
        if purpose == "bundle_regeneration":
            regen_count["n"] += 1
            payload = copy.deepcopy(_payload())
            payload["question"] = payload["question"].replace("A salary", "An HR salary")
            return {"content": json.dumps(payload), "usage": {"total_tokens": 100}}
        raise AssertionError(purpose)

    return _fake


def test_alias_only_blind_answer_no_longer_passes(memory_store) -> None:
    # Non-strict v3.0 would have counted every alias mention as support.
    lenient = concept_evaluator_v3.evaluate_answer(
        answer_text=ALIAS_ONLY_ANSWER, bundle_content=_payload()
    )
    assert lenient["coverage"]["k_supported"] == lenient["coverage"]["n_required"] == 3

    bundle_generator.set_bundle_llm_override(_override(ALIAS_ONLY_ANSWER))
    res = bundle_generator.generate_and_check_bundle(
        skill="Statistics", topic="mean vs median", difficulty="easy"
    )
    assert res["status"] == "rejected"
    assert res["blind_eval"]["evaluator_version"] == STRICT_VERSION
    states = {c["concept_id"]: (c["state"], c["match_type"]) for c in res["blind_eval"]["concepts"]}
    assert set(states.values()) == {("mentioned", "alias")}

    for version in bundle_store.list_versions(bundle_id=res["bundle_id"]):
        verdict = version["attribution_json"]["auto_check"]
        assert verdict["to_status"] == "rejected"
        assert verdict["evaluator_version"] == STRICT_VERSION


def test_proposition_backed_blind_answer_passes_and_records_strict_version(memory_store) -> None:
    bundle_generator.set_bundle_llm_override(_override(PROPOSITION_ANSWER))
    res = bundle_generator.generate_and_check_bundle(
        skill="Statistics", topic="mean vs median", difficulty="easy"
    )
    assert res["status"] == "auto_checked"
    assert res["retried"] is False
    match_types = {c["match_type"] for c in res["blind_eval"]["concepts"]}
    assert match_types == {"proposition"}
    verdict = res["bundle"]["attribution_json"]["auto_check"]
    assert verdict["evaluator_version"] == STRICT_VERSION
    assert res["blind_eval"]["evaluator_version"] == STRICT_VERSION

