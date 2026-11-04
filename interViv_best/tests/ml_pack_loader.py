"""Test helpers over the production pack loader (backend/ml_primitives/packs.py)."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from backend.ml_primitives.catalog import PACK_ROOT
from backend.ml_primitives.grading import OracleSuite
from backend.ml_primitives.packs import as_output, build_suite


def pack_roots() -> list[Path]:
    return sorted(path.parent for path in PACK_ROOT.glob("*/v*/manifest.json"))


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    """Suite comes from the production loader; tests add the buggy variants."""
    token = f"mlpack_{root.parent.name}_{root.name}"
    manifest, function, suite = build_suite(root)
    return Pack(
        root=root,
        problem_id=manifest["id"],
        source=(root / "reference.py").read_text(encoding="utf-8"),
        function=function,
        suite=suite,
        outputs={case.id: case.reference_output for case in suite.cases},
        bugs=_bugs(root, manifest["function"], token),
    )


def load_all_packs() -> list[Pack]:
    packs = [load_pack(root) for root in pack_roots()]
    if len(packs) != 6:
        raise AssertionError(f"Expected 6 ML primitive packs, found {len(packs)}")
    return packs
