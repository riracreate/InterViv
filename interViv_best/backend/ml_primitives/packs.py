"""Production loader for the ML primitive packs (trusted server-side code).

Imports each pack's own ``reference.py`` and ``properties.py`` — repository
code, never candidate code — to rebuild the deterministic oracle suite from
the pack seed. Candidate code is executed only in the local runner worker
(backend/ml_primitives/evaluate.py).

Arrays cross the worker boundary as JSON envelopes with an explicit dtype and
shape (``encode_value`` / ``decode_value``); pickle is never used.
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from functools import lru_cache
from math import prod
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from backend.ml_primitives.catalog import PACK_ROOT
from backend.ml_primitives.grading import OracleCase, OracleSuite, Tolerance

ALLOWED_DTYPES = frozenset({
    "float64", "float32", "int64", "int32", "int16", "int8", "uint8", "bool",
})
MAX_ELEMENTS = 1_000_000
MAX_DEPTH = 4


@dataclass(frozen=True)
class LoadedPack:
    problem_id: str
    version: int
    function: str
    suite: OracleSuite
    import_rule_name: str


def pack_roots() -> list[Path]:
    return sorted(path.parent for path in PACK_ROOT.glob("*/v*/manifest.json"))


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def as_output(value: Any) -> Any:
    """Normalize a reference output: nested dicts of NumPy arrays."""
    if isinstance(value, dict):
        return {key: as_output(item) for key, item in value.items()}
    return np.asarray(value)


def _root_for(problem_id: str) -> Path:
    name, _, version = str(problem_id).partition(".")
    root = PACK_ROOT / name / version
    if not name or not version or not (root / "manifest.json").is_file():
        raise ValueError(f"Unknown ML primitive problem: {problem_id!r}.")
    return root


def build_suite(root: Path) -> tuple[dict, Any, OracleSuite]:
    """Manifest, reference function and oracle suite for one pack root."""
    token = f"mlpack_{root.parent.name}_{root.name}"
    properties = _load_module(root / "properties.py", f"{token}_properties")
    reference = _load_module(root / "reference.py", f"{token}_reference")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    function = getattr(reference, manifest["function"])
    rng = np.random.default_rng(properties.SEED)
    cases = []
    for raw in properties.generate_cases(rng):
        cases.append(OracleCase(raw["id"], raw["inputs"], as_output(function(**raw["inputs"]))))
    suite = OracleSuite(
        problem_id=manifest["id"],
        version=int(manifest["version"]),
        seed=int(properties.SEED),
        tolerance=Tolerance(**properties.TOLERANCE),
        cases=tuple(cases),
        properties=dict(properties.PROPERTIES),
        static_rules=yaml.safe_load((root / "static_rules.yaml").read_text(encoding="utf-8")),
    )
    return manifest, function, suite


@lru_cache(maxsize=None)
def load_pack(problem_id: str) -> LoadedPack:
    manifest, _, suite = build_suite(_root_for(problem_id))
    if manifest["id"] != problem_id:
        raise ValueError(f"Pack identity mismatch for {problem_id!r}.")
    return LoadedPack(
        problem_id=manifest["id"],
        version=int(manifest["version"]),
        function=str(manifest["function"]),
        suite=suite,
        import_rule_name=str(suite.static_rules["imports"]["name"]),
    )


def encode_value(value: Any, depth: int = 0) -> dict[str, Any]:
    if depth > MAX_DEPTH:
        raise ValueError("Output nesting is too deep.")
    if isinstance(value, dict):
        return {"kind": "dict",
                "items": {str(k): encode_value(v, depth + 1) for k, v in value.items()}}
    array = np.asarray(value)
    if array.dtype.name not in ALLOWED_DTYPES:
        raise ValueError(f"Unsupported dtype {array.dtype.name}.")
    return {"kind": "ndarray", "dtype": array.dtype.name,
            "shape": list(array.shape), "data": array.ravel().tolist()}


def decode_value(obj: Any, depth: int = 0) -> Any:
    """Validate and rebuild an envelope produced by the worker."""
    if depth > MAX_DEPTH or not isinstance(obj, dict):
        raise ValueError("Malformed output envelope.")
    kind = obj.get("kind")
    if kind == "dict":
        items = obj.get("items")
        if not isinstance(items, dict):
            raise ValueError("Malformed output envelope.")
        return {str(k): decode_value(v, depth + 1) for k, v in items.items()}
    if kind != "ndarray":
        raise ValueError("Malformed output envelope.")
    dtype, shape, data = obj.get("dtype"), obj.get("shape"), obj.get("data")
    if dtype not in ALLOWED_DTYPES:
        raise ValueError("Unsupported dtype.")
    if (not isinstance(shape, list) or len(shape) > 8
            or not all(type(n) is int and n >= 0 for n in shape)):
        raise ValueError("Malformed shape.")
    size = prod(shape) if shape else 1
    if size > MAX_ELEMENTS or not isinstance(data, list) or len(data) != size:
        raise ValueError("Output size does not match its shape.")
    if not all(type(x) in (int, float, bool) for x in data):
        raise ValueError("Output data must be numeric.")
    return np.array(data, dtype=dtype).reshape(shape)
