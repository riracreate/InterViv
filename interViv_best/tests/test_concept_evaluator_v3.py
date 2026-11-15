"""Tests for concept_evaluator_v3 (3-tier proposition, alias, MiniLM semantic)."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path

import pytest

from modules import concept_evaluator_v2 as v2
from modules import concept_evaluator_v3 as v3

ROOT = Path(__file__).resolve().parent.parent


def _sample_bundle(*, with_optional: bool = True) -> dict:
    bundle = {
        "bundle_id": "test.generators",
        "version": 2,
        "required_concepts": [
            {
                "id": "yield",
                "descriptor": "The yield keyword pauses function execution and emits a value lazily.",
                "aliases": ["yield statement", "yield keyword"],
                "expected_propositions": [
                    "generator function uses yield to pause and resume execution"
                ],
                "positive_examples": [
                    "Calling next resumes from the last yield point until the next yield.",
                    "Streaming chunks on demand prevents holding the whole sequence in RAM.",
                ],
                "negative_cases": [
                    "yield immediately terminates the function like return."
                ],
            },
            {
                "id": "lazy_evaluation",
                "descriptor": "Values are computed on demand one at a time rather than materialized upfront.",
                "aliases": ["lazy evaluation", "on-demand generation"],
                "expected_propositions": [],
                "positive_examples": [
                    "Items are generated one by one as requested instead of building a full list."
                ],
                "negative_cases": [],
            },
        ],
        "optional_concepts": (
            [
                {
                    "id": "state_preservation",
                    "descriptor": "Local variables and instruction pointer stay intact between yields.",
                    "aliases": ["frame state"],
                    "expected_propositions": [],
                    "positive_examples": [],
                    "negative_cases": [],
                }
            ]
            if with_optional
            else []
        ),
        "misconceptions": [
            {
                "id": "yield_same_as_return",
                "candidate_patterns": ["yield is the same as return", "yield terminates permanently"],
            }
        ],
    }
    return bundle


def _concept_by_id(result: dict, cid: str, *, optional: bool = False) -> dict:
    bucket = result["optional_concepts"] if optional else result["concepts"]
    return next(c for c in bucket if c["concept_id"] == cid)


def test_match_type_proposition_takes_priority() -> None:
    bundle = _sample_bundle()
    answer = (
        "A generator function uses yield to pause and resume execution across iterations."
    )
    res = v3.evaluate_answer(
        answer_text=answer,
        bundle_content=bundle,
        bundle_content_hash="abc123",
    )
    assert res["assessable"] is True
    assert res["bundle_content_hash"] == "abc123"
    c = _concept_by_id(res, "yield")
    assert c["state"] == "supported"
    assert c["match_type"] == "proposition"
    assert c["matched_text"] is None
    assert c["semantic_score"] is None
    assert any(ev.get("type") == "proposition" for ev in c["evidence"])


def test_match_type_alias_whole_term_and_precedence() -> None:
    bundle = _sample_bundle()
    answer = "Python avoids eager memory use through lazy evaluation across items."
    res = v3.evaluate_answer(answer_text=answer, bundle_content=bundle)
    c = _concept_by_id(res, "lazy_evaluation")
    assert c["state"] == "supported"
    assert c["match_type"] == "alias"
    assert c["matched_text"] is None
    assert c["semantic_score"] is None
    assert any(ev.get("type") == "alias" for ev in c["evidence"])

    # Whole-term boundary: "gil" must not match inside "agile" or "gilded".
    gil_bundle = {
        "required_concepts": [
            {
                "id": "GIL",
                "descriptor": "Unrelated mathematical theorem about prime gaps.",
                "aliases": ["gil"],
                "expected_propositions": [],
                "positive_examples": [],
            }
        ]
    }
    non_match = v3.evaluate_answer(
        answer_text="An agile gilded workflow ships code faster.",
        bundle_content=gil_bundle,
    )
    assert _concept_by_id(non_match, "GIL")["state"] == "not_demonstrated"
    assert _concept_by_id(non_match, "GIL")["match_type"] is None


def test_match_type_semantic_with_sentence_and_score() -> None:
    bundle = _sample_bundle()
    answer = (
        "First, remember to name functions clearly. "
        "Each value is computed on demand one at a time instead of materializing everything upfront."
    )
    res = v3.evaluate_answer(answer_text=answer, bundle_content=bundle)
    c = _concept_by_id(res, "lazy_evaluation")
    assert c["state"] == "supported"
    assert c["match_type"] == "semantic"
    assert c["matched_text"] == (
        "Each value is computed on demand one at a time instead of materializing everything upfront."
    )
    assert c["semantic_score"] is not None
    assert v3.DEFAULT_SEMANTIC_THRESHOLD <= c["semantic_score"] <= 1.0
    assert c["matched_reference"] is not None
    assert any(ev.get("type") == "semantic" for ev in c["evidence"])

    unrelated = v3.evaluate_answer(
        answer_text="Sourdough bread rises slowly when fermented overnight in a cool room.",
        bundle_content=bundle,
    )
    for item in unrelated["concepts"]:
        assert item["state"] == "not_demonstrated"
        assert item["match_type"] is None


def test_negation_on_alias_blocks_tier2_and_tier3_on_negated_sentence() -> None:
    bundle = _sample_bundle()

    # Single negated sentence must not be rescued by Tier 2 or Tier 3.
    neg_res = v3.evaluate_answer(
        answer_text="A generator does not use yield and avoids pausing.",
        bundle_content=bundle,
    )
    c_yield = _concept_by_id(neg_res, "yield")
    assert c_yield["state"] != "supported"
    assert c_yield["state"] == "uncertain"
    assert c_yield["match_type"] is None

    # Cross-clause boundary: negation in clause 1 must not clobber unnegated alias in clause 2.
    cross_bundle = {
        "required_concepts": [
            {
                "id": "consistency",
                "descriptor": "Transactions preserve database invariants.",
                "aliases": ["consistency"],
                "expected_propositions": [],
                "positive_examples": [],
            }
        ]
    }
    cross_res = v3.evaluate_answer(
        answer_text="Atomicity leaves no partial state), Consistency preserves invariants.",
        bundle_content=cross_bundle,
    )
    assert _concept_by_id(cross_res, "consistency")["state"] == "supported"
    assert _concept_by_id(cross_res, "consistency")["match_type"] == "alias"


def test_leave_one_out_exclude_examples() -> None:
    isolated_bundle = {
        "required_concepts": [
            {
                "id": "custom_streaming",
                "descriptor": "Completely unrelated geometric optics refraction formula.",
                "aliases": [],
                "expected_propositions": [],
                "positive_examples": [
                    "Streaming large files lazily avoids loading everything into RAM."
                ],
            }
        ]
    }
    target_example = "Streaming large files lazily avoids loading everything into RAM."

    # Without exclusion, positive example self-matches at ~1.0.
    with_self = v3.evaluate_answer(
        answer_text=target_example,
        bundle_content=isolated_bundle,
    )
    c_self = _concept_by_id(with_self, "custom_streaming")
    assert c_self["state"] == "supported"
    assert c_self["match_type"] == "semantic"
    assert c_self["semantic_score"] >= 0.99

    # With flat iterable exclude_examples, the self-match is removed (no circularity).
    loo_flat = v3.evaluate_answer(
        answer_text=target_example,
        bundle_content=isolated_bundle,
        exclude_examples=[target_example],
    )
    c_loo_flat = _concept_by_id(loo_flat, "custom_streaming")
    assert c_loo_flat["state"] == "not_demonstrated"
    assert c_loo_flat["match_type"] is None

    # With per-concept mapping and extra whitespace, exclusion also removes the self-match.
    loo_map = v3.evaluate_answer(
        answer_text=target_example,
        bundle_content=isolated_bundle,
        exclude_examples={
            "custom_streaming": [
                "  Streaming   large files lazily avoids loading everything into RAM. "
            ]
        },
    )
    assert _concept_by_id(loo_map, "custom_streaming")["match_type"] is None


def test_output_shape_parity_with_v2_misconceptions_and_optional() -> None:
    bundle = _sample_bundle(with_optional=True)
    answer = (
        "Each item is generated only when requested via next(). "
        "It retains local variables and the instruction pointer across pauses. "
        "Actually yield is the same as return."
    )
    res_v2 = v2.evaluate_answer(answer_text=answer, bundle_content=bundle, bundle_content_hash="h1")
    res_v3 = v3.evaluate_answer(answer_text=answer, bundle_content=bundle, bundle_content_hash="h1")

    assert set(res_v2.keys()) == set(res_v3.keys())
    assert res_v3["evaluator_version"] == v3.EVALUATOR_VERSION
    assert res_v3["assessable"] is True
    assert res_v3["headline_total"] is None
    assert set(res_v3["coverage"].keys()) == {"n_required", "k_supported", "level"}
    assert set(res_v3["criteria"].keys()) == {"coverage", "accuracy", "depth", "clarity"}
    assert res_v3["misconceptions"] and res_v3["misconceptions"][0]["matched"] is True

    # Optional concept can match semantically too.
    opt = _concept_by_id(res_v3, "state_preservation", optional=True)
    assert opt["state"] == "supported"
    assert opt["match_type"] == "semantic"

    # Unassessable output shape matches v2.
    un_v2 = v2.evaluate_answer(answer_text="hello", bundle_content={"required_concepts": []})
    un_v3 = v3.evaluate_answer(answer_text="hello", bundle_content={"required_concepts": []})
    assert set(un_v2.keys()) == set(un_v3.keys())
    assert un_v3["assessable"] is False
    assert un_v3["reason"] == "missing_required_concepts"


def test_disable_semantic_scoring_falls_back_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISABLE_SEMANTIC_SCORING", "1")
    bundle = _sample_bundle()
    answer = (
        "Python uses lazy evaluation here, and items are emitted on demand without full materialization."
    )
    res = v3.evaluate_answer(answer_text=answer, bundle_content=bundle)
    # Tier 2 alias still succeeds when semantic scoring is disabled.
    assert _concept_by_id(res, "lazy_evaluation")["state"] == "supported"
    assert _concept_by_id(res, "lazy_evaluation")["match_type"] == "alias"
    # Tier 3 does not fire when semantic scoring is disabled.
    assert _concept_by_id(res, "yield")["match_type"] is None


def test_v2_module_unchanged() -> None:
    assert v2.EVALUATOR_VERSION == "concept_evaluator_v2.0"
    v2_path = ROOT / "modules" / "concept_evaluator_v2.py"
    actual_sha = hashlib.sha256(v2_path.read_bytes()).hexdigest()
    golden_path = ROOT / "tests" / "fixtures" / "step1_golden_prechange.json"
    if golden_path.exists():
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        file_hashes = golden.get("file_sha256") or golden.get("files") or golden
        # Support exact fixture structure dynamically while checking known key.
        if "modules/concept_evaluator_v2.py" in file_hashes:
            assert actual_sha == file_hashes["modules/concept_evaluator_v2.py"]
    assert actual_sha == "b55a03b4a96d17383fd838a925351b787b881c60fec96014fef0356ab8cc818c"


def test_concept_evaluator_v3_never_imported_in_candidate_scoring() -> None:
    """Step 2 confirmation: candidate scoring modules/routes must never import or reference v3."""
    scoring_dir = ROOT / "backend" / "scoring"
    scoring_files = sorted(scoring_dir.rglob("*.py"))
    assert scoring_files, f"Expected Python files under {scoring_dir}"

    targets = [
        *scoring_files,
        ROOT / "backend" / "routes" / "answer.py",
        ROOT / "modules" / "nlp_scorer.py",
        ROOT / "modules" / "semantic_scorer.py",
        ROOT / "modules" / "question_concepts.py",
    ]
    ref_pattern = re.compile(r"concept_evaluator_v3")

    for path in targets:
        assert path.is_file(), f"Expected candidate scoring path to exist: {path}"
        source = path.read_text(encoding="utf-8")
        assert ref_pattern.search(source) is None, (
            f"{path.relative_to(ROOT)} unexpectedly references concept_evaluator_v3"
        )

        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "concept_evaluator_v3" not in alias.name, (
                        f"{path.relative_to(ROOT)} imports {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                assert "concept_evaluator_v3" not in module_name, (
                    f"{path.relative_to(ROOT)} imports from {module_name}"
                )
                for alias in node.names:
                    assert "concept_evaluator_v3" not in alias.name, (
                        f"{path.relative_to(ROOT)} imports symbol {alias.name}"
                    )
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "concept_evaluator_v3" not in node.value, (
                    f"{path.relative_to(ROOT)} references string {node.value!r}"
                )
