"""Trusted pack loader for tests. Production routes never import this."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from backend.ml_primitives.catalog import PACK_ROOT
from backend.ml_primitives.grading import OracleCase, OracleSuite, Tolerance


def pack_roots() -> list[Path]:
    return sorted(path.parent for path in PACK_ROOT.glob("*/v*/manifest.json"))


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def as_output(value):
    if isinstance(value, dict):
        return {key: as_output(item) for key, item in value.items()}
    return np.asarray(value)


def call_function(function, inputs: dict):
    return as_output(function(**inputs))


@dataclass(frozen=True)
class Bug:
    name: str
    source: str
    violates_property: str | None
    violates_static: str | None
    execute: bool
    function: object | None


@dataclass(frozen=True)
class Pack:
    root: Path
    problem_id: str
    source: str
    function: object
    suite: OracleSuite
    outputs: dict
    bugs: tuple[Bug, ...]


def _bugs(root: Path, function_name: str, token: str) -> tuple[Bug, ...]:
    found = []
    for source_path in sorted((root / "bugs").glob("*.py")):
        meta = yaml.safe_load((source_path.with_suffix(".meta.yaml")).read_text(encoding="utf-8"))
        execute = bool(meta.get("execute", True))
        function = None
        if execute:
            module = _load_module(source_path, f"{token}_bug_{source_path.stem}")
            function = getattr(module, function_name)
        found.append(Bug(
            name=source_path.stem,
            source=source_path.read_text(encoding="utf-8"),
            violates_property=meta.get("violates_property"),
            violates_static=meta.get("violates_static"),
            execute=execute,
            function=function,
        ))
    return tuple(found)


def load_pack(root: Path) -> Pack:
    token = f"mlpack_{root.parent.name}_{root.name}"
    properties = _load_module(root / "properties.py", f"{token}_properties")
    reference = _load_module(root / "reference.py", f"{token}_reference")
    manifest = yaml.safe_load((root / "manifest.json").read_text(encoding="utf-8"))
    function = getattr(reference, manifest["function"])
    cases = []
    outputs = {}
    rng = np.random.default_rng(properties.SEED)
    for raw in properties.generate_cases(rng):
        output = call_function(function, raw["inputs"])
        cases.append(OracleCase(raw["id"], raw["inputs"], output))
        outputs[raw["id"]] = output
    suite = OracleSuite(
        problem_id=manifest["id"],
        version=int(manifest["version"]),
        seed=int(properties.SEED),
        tolerance=Tolerance(**properties.TOLERANCE),
        cases=tuple(cases),
        properties=dict(properties.PROPERTIES),
        static_rules=yaml.safe_load((root / "static_rules.yaml").read_text(encoding="utf-8")),
    )
    return Pack(
        root=root,
        problem_id=manifest["id"],
        source=(root / "reference.py").read_text(encoding="utf-8"),
        function=function,
        suite=suite,
        outputs=outputs,
        bugs=_bugs(root, manifest["function"], token),
    )


def load_all_packs() -> list[Pack]:
    packs = [load_pack(root) for root in pack_roots()]
    if len(packs) != 6:
        raise AssertionError(f"Expected 6 ML primitive packs, found {len(packs)}")
    return packs
