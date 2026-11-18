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


# ─── 0.A.2: aliases must not be question words ───────────────────────────────


def _assemble(payload: dict) -> dict:
    doc, _ = bundle_generator._assemble_and_validate_doc(
        raw_payload=payload,
        bundle_id="statistics.mean-vs-median-easy",
        version=1,
        canonical_skill="Statistics",
        canonical_topic="mean vs median",
        difficulty="easy",
        model="test-model",
        provider="test",
        role=None,
    )
    return doc


def test_validator_accepts_aliases_that_are_not_question_words(memory_store) -> None:
    from modules.question_bundles import alias_question_overlap

    assert alias_question_overlap(_payload()) == []
    assert _assemble(_payload())["question"]


@pytest.mark.parametrize(
    "concept_index, alias",
    [
        (0, "salary"),            # single question word
        (0, "salaries"),          # plural of a question word
        (1, "summary statistic"),  # multi-word phrase from the question
        (2, "typical-employee"),   # hyphen splits like the evaluator does
    ],
)
def test_validator_rejects_alias_found_in_question(memory_store, concept_index, alias) -> None:
    from modules.question_bundles import BundleContentError

    payload = _payload()
    payload["required_concepts"][concept_index]["aliases"].append(alias)
    with pytest.raises(BundleContentError, match="aliases must not be words from the question"):
        _assemble(payload)


def test_validator_rejects_concept_id_found_in_question(memory_store) -> None:
    from modules.question_bundles import BundleContentError

    payload = _payload()
    payload["optional_concepts"][0]["id"] = "extreme_high_earners"
    for followup in payload["followups"]:
        assert followup["targets_concept"] != "extreme_high_earners"
    with pytest.raises(BundleContentError, match="extreme_high_earners"):
        _assemble(payload)


def test_alias_in_question_triggers_one_writer_retry_with_feedback(memory_store) -> None:
    sent: list[str] = []

    def _fake(purpose: str, model: str, messages: list[dict], **kwargs):
        if purpose == "bundle_generation":
            sent.append(messages[1]["content"])
            payload = _payload()
            if len(sent) == 1:
                payload["required_concepts"][1]["aliases"] = ["typical employee"]
            return {"content": json.dumps(payload), "usage": {"total_tokens": 100}}
        if purpose == "bundle_blind_answer":
            return {"content": PROPOSITION_ANSWER, "usage": {"total_tokens": 40}}
        raise AssertionError(purpose)

    bundle_generator.set_bundle_llm_override(_fake)
    res = bundle_generator.generate_and_check_bundle(
        skill="Statistics", topic="mean vs median", difficulty="easy"
    )
    assert res["status"] == "auto_checked"
    assert len(sent) == 2
    assert "aliases must not be words from the question" in sent[1]
    assert "'typical employee'" in sent[1]


def test_prompts_state_the_alias_rule() -> None:
    prompt_b = "\n".join(
        m["content"]
        for m in bundle_generator._build_prompt_b_messages(
            skill="Statistics", topic="mean vs median", difficulty="easy"
        )
    )
    assert "Aliases must not be words from the question" in prompt_b
    assert "never count as evidence" in prompt_b
    regen = "\n".join(
        m["content"]
        for m in bundle_generator._build_regeneration_messages(
            skill="Statistics",
            topic="mean vs median",
            difficulty="easy",
            previous_content=_payload(),
            blind_answer=ALIAS_ONLY_ANSWER,
            eval_res={"concepts": [], "misconceptions": []},
            audit_diagnosis={},
        )
    )
    assert "into aliases so the automated matcher" not in regen
    assert "Aliases never count as support" in regen


# ─── 0.A.3: positive_examples on every required concept ──────────────────────


def test_positive_examples_are_kept_in_stored_content(memory_store) -> None:
    doc = _assemble(_payload())
    for concept in doc["required_concepts"]:
        assert 2 <= len(concept["positive_examples"]) <= 3
    assert "positive_examples" not in doc["optional_concepts"][0]


def _with_examples(index: int, examples) -> dict:
    payload = _payload()
    payload["required_concepts"][index]["positive_examples"] = examples
    return payload


@pytest.mark.parametrize(
    "examples, message",
    [
        (None, "positive_examples must be a list"),
        (["The mean gets inflated because a few huge values pull it upward."], "at least 2"),
        (
            [
                "The mean gets inflated because a few huge values pull it upward.",
                "A handful of very large salaries drags the average far above most pay.",
                "Big outliers make the arithmetic average overstate what people earn.",
                "One enormous salary is enough to move the average a lot.",
            ],
            "at most 3",
        ),
        (
            ["Outliers inflate the average.", "A few huge salaries drag the average far upward."],
            "6-25 words",
        ),
        (
            [
                "The mean gets inflated because a few huge values pull it upward, and this "
                "happens every single time a company reports its pay data to anyone at all.",
                "A handful of very large salaries drags the average far above most pay.",
            ],
            "6-25 words",
        ),
        (
            [
                "The mean is inflated. A few huge values pull it upward every time.",
                "A handful of very large salaries drags the average far above most pay.",
            ],
            "one sentence",
        ),
        (
            [
                "A small number of very large salaries drag the arithmetic mean upward.",
                "A handful of very large salaries drags the average far above most pay.",
            ],
            "copied from the reference answer",
        ),
        (
            [
                "A handful of very large salaries drags the average far above most pay.",
                "A handful of very large salaries drags the average far above typical pay.",
            ],
            "different wording",
        ),
    ],
)
def test_validator_rejects_bad_positive_examples(memory_store, examples, message) -> None:
    from modules.question_bundles import BundleContentError

    with pytest.raises(BundleContentError, match=message):
        _assemble(_with_examples(0, examples))


def test_strict_schema_requires_two_to_three_examples_on_required_concepts_only() -> None:
    from modules import interview_llm

    schema = interview_llm.generated_bundle_schema()
    required_item = schema["properties"]["required_concepts"]["items"]
    optional_item = schema["properties"]["optional_concepts"]["items"]
    assert "positive_examples" in required_item["required"]
    examples = required_item["properties"]["positive_examples"]
    assert (examples["minItems"], examples["maxItems"]) == (2, 3)
    assert "positive_examples" not in optional_item["properties"]


def test_prompts_ask_for_fresh_positive_examples() -> None:
    prompt_b = "\n".join(
        m["content"]
        for m in bundle_generator._build_prompt_b_messages(
            skill="Statistics", topic="mean vs median", difficulty="easy"
        )
    )
    assert "positive_examples (required_concepts only): 2-3 natural one-sentence answers" in prompt_b
    assert "never copied or lightly edited from reference_answer" in prompt_b
    regen = "\n".join(
        m["content"]
        for m in bundle_generator._build_regeneration_messages(
            skill="Statistics",
            topic="mean vs median",
            difficulty="easy",
            previous_content=_payload(),
            blind_answer=ALIAS_ONLY_ANSWER,
            eval_res={"concepts": [], "misconceptions": []},
            audit_diagnosis={},
        )
    )
    assert "never copy or lightly edit sentences from blind_answer_excerpt" in regen


def test_regeneration_examples_copied_from_blind_answer_are_rejected(memory_store) -> None:
    blind = {"n": 0}
    regen_prompts: list[str] = []

    def _fake(purpose: str, model: str, messages: list[dict], **kwargs):
        if purpose == "bundle_generation":
            return {"content": json.dumps(_payload()), "usage": {"total_tokens": 100}}
        if purpose == "bundle_blind_answer":
            blind["n"] += 1
            text = ALIAS_ONLY_ANSWER if blind["n"] == 1 else PROPOSITION_ANSWER
            return {"content": text, "usage": {"total_tokens": 40}}
        if purpose == "bundle_check_audit":
            return {
                "content": json.dumps(
                    {"root_cause": "x", "issue_type": "propositions", "missed_concepts": [], "fixes": []}
                ),
                "usage": {"total_tokens": 20},
            }
        if purpose == "bundle_regeneration":
            regen_prompts.append(messages[1]["content"])
            payload = _payload()
            payload["question"] = payload["question"].replace("A salary", "An HR salary")
            if len(regen_prompts) == 1:
                payload["required_concepts"][0]["positive_examples"][0] = (
                    "I would talk about the arithmetic average, the middle value, and right skew."
                )
            return {"content": json.dumps(payload), "usage": {"total_tokens": 100}}
        raise AssertionError(purpose)

    bundle_generator.set_bundle_llm_override(_fake)
    res = bundle_generator.generate_and_check_bundle(
        skill="Statistics", topic="mean vs median", difficulty="easy"
    )
    assert res["status"] == "auto_checked"
    assert res["retried"] is True
    assert len(regen_prompts) == 2
    assert "copied from the blind answer" in regen_prompts[1]
    stored = res["bundle"]["content_json"]["required_concepts"][0]["positive_examples"]
    assert all("I would talk about" not in ex for ex in stored)


# ─── 0.B: python.lists-vs-tuples v3 ──────────────────────────────────────────


def _lists_vs_tuples(version: int) -> dict:
    from modules.question_bundles import default_bundle_root, iter_bundle_files, validate_bundle_doc

    path = default_bundle_root() / "python" / "python.lists-vs-tuples.yaml"
    for _, doc in iter_bundle_files(path.parent):
        if doc["bundle_id"] == "python.lists-vs-tuples" and doc["version"] == version:
            return validate_bundle_doc(doc)["content"]
    raise AssertionError(f"v{version} missing")


def test_lists_vs_tuples_v3_has_no_question_word_terms_and_valid_examples() -> None:
    from modules.question_bundles import (
        _validate_positive_examples,
        alias_question_overlap,
        validate_generated_bundle_text_quality,
    )

    v2 = _lists_vs_tuples(2)
    assert ("tuple", "tuple") in alias_question_overlap(v2)
    v3 = _lists_vs_tuples(3)
    assert alias_question_overlap(v3) == []
    terms = {
        t.lower()
        for c in v3["required_concepts"] + v3["optional_concepts"]
        for t in [c["id"], *c["aliases"]]
    }
    assert not terms & {"tuple", "tuples", "list", "lists"}
    validate_generated_bundle_text_quality(v3)
    _validate_positive_examples(v3)
    for concept in v3["required_concepts"]:
        assert len(concept["positive_examples"]) == 2
        for prop in concept["expected_propositions"]:
            assert len(prop.split()) >= 4


def test_lists_vs_tuples_v3_under_strict_mode(monkeypatch) -> None:
    monkeypatch.setenv("DISABLE_SEMANTIC_SCORING", "1")
    v3 = _lists_vs_tuples(3)
    strong = (
        "Lists are mutable sequences, so you can append items to a list or change elements "
        "in place. Tuples are immutable sequences: tuple contents stay fixed after creation."
    )
    echo = "Lists and tuples are different in Python. Lists are lists and tuples are tuples."
    res = concept_evaluator_v3.evaluate_answer(answer_text=strong, bundle_content=v3, strict=True)
    assert res["evaluator_version"] == STRICT_VERSION
    assert res["coverage"]["k_supported"] == res["coverage"]["n_required"] == 2
    assert {c["match_type"] for c in res["concepts"]} == {"proposition"}
    res = concept_evaluator_v3.evaluate_answer(answer_text=echo, bundle_content=v3, strict=True)
    assert res["coverage"]["k_supported"] == 0


# ─── 0.A.4: strict live re-run helpers (offline) ─────────────────────────────


def test_live_check_strict_reports_match_type_per_concept_and_shadows_existing() -> None:
    from scripts.live_check_strict import SHADOW_SUFFIX, concept_rows, shadow_doc
    from scripts.live_check_direct_providers import assert_safe_tmp_db_path

    rows = concept_rows({"concepts": [
        {"concept_id": "a", "state": "supported", "match_type": "proposition"},
        {"concept_id": "b", "state": "supported", "match_type": "semantic", "semantic_score": 0.7},
        {"concept_id": "c", "state": "mentioned", "match_type": "alias"},
        {"concept_id": "d", "state": "not_demonstrated", "match_type": None},
    ]})
    assert [r["match"] for r in rows] == [
        "proposition", "semantic", "alias-mentioned", "none (not_demonstrated)",
    ]
    doc = shadow_doc({
        "bundle_id": "python.gil", "version": 2, "source": "human_authored",
        "author_id": "phase1b-dev", "attribution_json": {"note": "x", "auto_check": {"to_status": "auto_checked"}},
        "content_json": {"bundle_id": "python.gil", "question": "Q?"},
    })
    assert doc["bundle_id"] == "python.gil" + SHADOW_SUFFIX and doc["version"] == 1
    assert doc["attribution"] == {"note": "x", "strict_recheck_of": "python.gil@2"}
    with pytest.raises(RuntimeError):
        assert_safe_tmp_db_path(Path.home() / "interviv-demo" / "interviv-demo.sqlite3")
