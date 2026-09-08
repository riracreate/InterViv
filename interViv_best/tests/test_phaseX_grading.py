"""Pure grader contract checks; trusted pack checks live alongside these."""

from dataclasses import replace

import numpy as np
import pytest

from backend.ml_primitives.grading import OracleCase, OracleSuite, Tolerance, grade, static_signals


def test_envelope_structure_dtype_and_tolerance_are_real_checks():
    suite = OracleSuite(
        "contract.v1", 1, 41, Tolerance(rtol=0, atol=0.01),
        (OracleCase("one", {}, np.array([1.0])),), {},
        {"imports": {"name": "allowed imports", "allow": ["numpy"]}},
    )
    def properties(output, oracle=suite):
        return {p["name"]: p["passed"] for p in grade("", {"one": output}, suite=oracle)["properties"]}

    assert properties(np.array([1.005])) == {"shape": True, "dtype": True, "reference agreement": True}
    strict = replace(suite, tolerance=Tolerance(rtol=0, atol=0.001))
    assert properties(np.array([1.005]), strict)["reference agreement"] is False
    assert properties(np.array([[1.0]]))["shape"] is False  # no broadcasting
    assert properties(np.array([1]))["dtype"] is False
    assert properties([1.0])["shape"] is False
    assert properties(np.array([np.nan]))["reference agreement"] is False
    assert properties(np.array([np.inf]))["reference agreement"] is False
    with pytest.raises(ValueError, match="envelope"):
        grade("", {}, suite=suite)
    with pytest.raises(ValueError, match="envelope"):
        grade("", {"one": np.array([1.0]), "extra": 1}, suite=suite)


def test_static_is_ast_only_and_reports_pack_names_and_lines(tmp_path):
    marker = tmp_path / "must-not-exist"
    source = f"import os\nopen({str(marker)!r}, 'w').write('executed')\n"
    config = {"imports": {"name": "approved dependencies", "allow": ["numpy"]}}
    assert static_signals(source, config) == {
        "syntax_error": None, "findings": [{"name": "approved dependencies", "line": 1}],
    }
    assert not marker.exists()
    assert static_signals("# import os\ntext = 'import sklearn'", config)["findings"] == []
    assert static_signals("from sklearn.metrics import roc_auc_score", config)["findings"][0]["line"] == 1
    assert static_signals("from .numpy import x", config)["findings"]
    assert static_signals("def f(:", config)["syntax_error"] == {"line": 1}


def test_static_vectorization_configuration_and_aliases():
    config = {
        "imports": {"name": "imports", "allow": ["numpy"]},
        "rules": [{"name": "batch axis loop", "kind": "for_over_axis", "arrays": ["batch"]}],
    }
    for source in (
        "def f(batch):\n    for row in batch:\n        pass",
        "def f(batch):\n    for i in range(batch.shape[0]):\n        pass",
        "def f(batch):\n    return [row for row in batch]",
    ):
        assert static_signals(source, config)["findings"] == [{"name": "batch axis loop", "line": 2}]
    assert static_signals("def f(batch):\n    return batch @ batch.T", config)["findings"] == []
    config["rules"] = []
    assert static_signals("def f(batch):\n    return [row for row in batch]", config)["findings"] == []


def test_static_shift_signal_tracks_numpy_and_assignment_aliases():
    config = {
        "imports": {"name": "imports", "allow": ["numpy"]},
        "rules": [{
            "name": "unshifted exponentiation", "kind": "call_on_unshifted_input",
            "calls": ["numpy.exp"], "inputs": ["values"],
            "reductions": ["numpy.max"], "reduction_methods": ["max"],
        }],
    }
    raw = "import numpy as n\ndef f(values):\n    alias = values\n    return n.exp(alias)"
    assert static_signals(raw, config)["findings"] == [{"name": "unshifted exponentiation", "line": 4}]
    shifted = "from numpy import exp as e, max as m\ndef f(values):\n    shifted = values - m(values)\n    return e(shifted)"
    assert static_signals(shifted, config)["findings"] == []
    method = "import numpy as np\ndef f(values):\n    return np.exp(values - values.max())"
    assert static_signals(method, config)["findings"] == []
