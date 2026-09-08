"""Trusted-pack proofs for Layers A and B. Candidate code is never executed."""

from __future__ import annotations

import json

import numpy as np
import pytest

from backend.ml_primitives.catalog import list_problems, public_problem, select_problems
from backend.ml_primitives.grading import grade, static_signals
from tests.ml_pack_loader import as_output, call_function, load_all_packs, load_pack

PACKS = load_all_packs()
PACK_IDS = [pack.problem_id for pack in PACKS]
SENTINELS = (
    "PHASEX_REF_SENTINEL",
    "PHASEX_PROP_SENTINEL",
    "PHASEX_BUG_SENTINEL",
    "PHASEX_RULE_INTERNAL",
)


def _perturb_float(value, amount):
    if isinstance(value, dict):
        for key in sorted(value):
            try:
                cloned = dict(value)
                cloned[key] = _perturb_float(value[key], amount)
                return cloned
            except ValueError:
                continue
        raise ValueError("no floating leaf")
    array = np.array(value, copy=True)
    if not np.issubdtype(array.dtype, np.floating):
        raise ValueError("not floating")
    if array.shape == ():
        return np.asarray(array + amount, dtype=array.dtype)
    flat = array.reshape(-1)
    flat[0] = flat[0] + amount
    return array


@pytest.mark.parametrize("pack", PACKS, ids=PACK_IDS)
def test_reference_passes_every_named_property_and_static_rule(pack):
    assert len(pack.suite.properties) >= 4
    result = grade(pack.source, pack.outputs, suite=pack.suite)
    failed = [item["name"] for item in result["properties"] if not item["passed"]]
    assert failed == [], failed
    assert result["static"]["syntax_error"] is None
    assert result["static"]["findings"] == []
    assert result["seed"] == pack.suite.seed
    assert result["tolerance"] == {
        "rtol": pack.suite.tolerance.rtol,
        "atol": pack.suite.tolerance.atol,
    }
    assert "score" not in result
    assert "final_score" not in result


@pytest.mark.parametrize("pack", PACKS, ids=PACK_IDS)
def test_known_bad_solutions_miss_their_named_target(pack):
    assert len(pack.bugs) >= 2
    for bug in pack.bugs:
        assert bug.violates_property or bug.violates_static, bug.name
        if bug.violates_static:
            findings = static_signals(bug.source, pack.suite.static_rules)["findings"]
            names = {item["name"] for item in findings}
            assert bug.violates_static in names, (bug.name, names)
            assert all(item["line"] >= 1 for item in findings)
        if bug.violates_property:
            assert bug.execute and bug.function is not None, bug.name
            with np.errstate(all="ignore"):
                outputs = {
                    case.id: call_function(bug.function, case.inputs)
                    for case in pack.suite.cases
                }
            result = grade(bug.source, outputs, suite=pack.suite)
            by_name = {item["name"]: item["passed"] for item in result["properties"]}
            assert by_name[bug.violates_property] is False, (bug.name, by_name)


@pytest.mark.parametrize("pack", PACKS, ids=PACK_IDS)
def test_layer_a_is_deterministic_for_pack_seed(pack):
    first = grade(pack.source, pack.outputs, suite=pack.suite)
    second = grade(pack.source, pack.outputs, suite=pack.suite)
    assert first == second
    reloaded = load_pack(pack.root)
    assert reloaded.suite.seed == pack.suite.seed
    assert [case.id for case in reloaded.suite.cases] == [case.id for case in pack.suite.cases]
    for left, right in zip(pack.suite.cases, reloaded.suite.cases):
        for key in left.inputs:
            assert np.array_equal(left.inputs[key], right.inputs[key])
        assert grade(pack.source, reloaded.outputs, suite=reloaded.suite) == first


@pytest.mark.parametrize("pack", PACKS, ids=PACK_IDS)
def test_pack_tolerance_is_applied_to_reference_agreement(pack):
    case = pack.suite.cases[0]
    broken = dict(pack.outputs)
    broken[case.id] = as_output(_perturb_float(pack.outputs[case.id], 1.0))
    result = grade(pack.source, broken, suite=pack.suite)
    by_name = {item["name"]: item["passed"] for item in result["properties"]}
    assert by_name["reference agreement"] is False
    if pack.suite.tolerance.atol > 0:
        tiny = dict(pack.outputs)
        tiny[case.id] = as_output(_perturb_float(
            pack.outputs[case.id], pack.suite.tolerance.atol * 0.25,
        ))
        close = grade(pack.source, tiny, suite=pack.suite)
        close_by_name = {item["name"]: item["passed"] for item in close["properties"]}
        assert close_by_name["reference agreement"] is True


def test_tolerances_are_recorded_per_problem_not_globally():
    recorded = {(pack.suite.tolerance.rtol, pack.suite.tolerance.atol) for pack in PACKS}
    assert len(recorded) > 1


def test_catalog_exposes_six_public_problems_without_hidden_material():
    public = list_problems()
    assert [item["id"] for item in public] == PACK_IDS
    blob = json.dumps(public)
    for sentinel in SENTINELS:
        assert sentinel not in blob
    for item in public:
        assert item["scoring_available"] is False
        assert item["category"] == "ml_primitives"
        assert set(item) >= {
            "id", "version", "title", "difficulty", "topics", "constraints",
            "function", "starter_code", "statement", "scoring_available",
        }
        assert "properties" not in item
        assert "reference" not in item
        assert public_problem(item["id"])["statement"] == item["statement"]
    softmax = select_problems(topics=["softmax"], count=1)
    assert softmax[0]["id"] == "softmax_stable.v1"
    pinned = select_problems(problem_ids=["layer_norm.v1", "binary_auc.v1"])
    assert [item["id"] for item in pinned] == ["layer_norm.v1", "binary_auc.v1"]
