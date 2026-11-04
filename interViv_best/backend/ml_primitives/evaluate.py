"""Execute an ML primitive submission and grade it against its pack.

Pipeline (candidate code runs only inside the local runner worker):

1. Static AST signals (grading.static_signals). A syntax error or an import
   outside the pack's allowlist is a candidate error: nothing is executed.
2. The worker imports the submission as module ``candidate`` and calls the
   pack function on each deterministic case; outputs return as JSON
   envelopes with explicit dtype/shape (no pickle).
3. grading.grade() checks shape, dtype, reference agreement within the pack
   tolerance, and every pack property per case.

Per-case errors expose only an error kind and exception type, never messages
that could echo hidden inputs. Infrastructure failures raise
ExecutionUnavailableError and never become a score.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

import numpy as np

from backend.ml_primitives.grading import grade, static_signals
from backend.ml_primitives.packs import decode_value, encode_value, load_pack
from backend.local_runner import (
    LocalRunnerUnavailable,
    run_python_job,
    trusted_local_execution_enabled,
)

GRADER_VERSION = "v1-ml-primitives"
MAX_SOURCE_CHARS = 100_000

_DRIVER = r'''
import json, importlib.util
import numpy as np

MARKER = __MARKER__
FUNCTION = __FUNCTION__
CASES = json.loads(__CASES__)
ALLOWED = {"float64", "float32", "int64", "int32", "int16", "int8", "uint8", "bool"}


def decode(obj):
    if obj["kind"] == "dict":
        return {k: decode(v) for k, v in obj["items"].items()}
    return np.array(obj["data"], dtype=obj["dtype"]).reshape(obj["shape"])


def encode(value, depth=0):
    if depth > 4:
        raise ValueError("nesting")
    if isinstance(value, dict):
        return {"kind": "dict", "items": {str(k): encode(v, depth + 1) for k, v in value.items()}}
    array = np.asarray(value)
    if array.dtype.name not in ALLOWED:
        raise TypeError("unsupported dtype " + array.dtype.name)
    return {"kind": "ndarray", "dtype": array.dtype.name,
            "shape": list(array.shape), "data": array.ravel().tolist()}


def emit(record):
    print(MARKER + json.dumps(record, allow_nan=True), flush=True)


try:
    spec = importlib.util.spec_from_file_location("candidate", "solution.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, FUNCTION)
except BaseException as exc:
    emit({"load_error": type(exc).__name__})
    raise SystemExit(0)

for case in CASES:
    try:
        inputs = {name: decode(value) for name, value in case["inputs"].items()}
        value = function(**inputs)
    except Exception as exc:
        emit({"id": case["id"], "error": type(exc).__name__})
        continue
    try:
        emit({"id": case["id"], "output": encode(value)})
    except Exception:
        emit({"id": case["id"], "invalid_output": True})
'''


def ml_scoring_available() -> bool:
    """ML submissions can be executed only by the trusted local runner."""
    return trusted_local_execution_enabled()


def _driver_source(marker: str, function: str, cases: list[dict]) -> str:
    return (_DRIVER
            .replace("__MARKER__", repr(marker))
            .replace("__FUNCTION__", repr(function))
            .replace("__CASES__", repr(json.dumps(cases, allow_nan=True))))


def _candidate_error(pack, static, error: str) -> dict[str, Any]:
    return {
        "status": "candidate_error",
        "error": error,
        "grader_version": GRADER_VERSION,
        "problem_id": pack.problem_id,
        "version": pack.version,
        "cases": [{"case_id": c.id, "passed": False, "error": error} for c in pack.suite.cases],
        "properties": [],
        "static": static,
        "execution": {"status": "not_run"},
    }


def evaluate_ml_submission(*, problem_id: str, source: str) -> dict[str, Any]:
    """Run and grade one submission. Raises ExecutionUnavailableError when
    the runner is disabled or cannot start (retryable; nothing scored)."""
    from backend.execution import _JOBS, ExecutionUnavailableError

    if not source or not source.strip() or len(source) > MAX_SOURCE_CHARS:
        raise ValueError("Python source must contain 1–100,000 characters.")
    pack = load_pack(problem_id)
    # Unavailable means unavailable: nothing is scored, not even static errors.
    if not ml_scoring_available():
        raise ExecutionUnavailableError(
            "ML execution is unavailable in this environment. "
            "Your code was not run and nothing was scored; retry later."
        )
    static = static_signals(source, pack.suite.static_rules)
    if static.get("syntax_error"):
        return _candidate_error(pack, static, "syntax")
    if any(f["name"] == pack.import_rule_name for f in static.get("findings", [])):
        return _candidate_error(pack, static, "prohibited_import")

    marker = "INTERVIV_ML_" + uuid4().hex + ":"
    cases = [{"id": c.id, "inputs": {k: encode_value(v) for k, v in c.inputs.items()}}
             for c in pack.suite.cases]
    if not _JOBS.acquire(blocking=False):
        raise ExecutionUnavailableError("Both execution slots are busy. Nothing was scored; retry shortly.")
    try:
        result = run_python_job(
            {"main.py": _driver_source(marker, pack.function, cases), "solution.py": source},
            numpy=True,
        )
    except LocalRunnerUnavailable as exc:
        raise ExecutionUnavailableError() from exc
    finally:
        _JOBS.release()

    records: dict[str, dict] = {}
    load_error = None
    for line in result.stdout.splitlines():
        if not line.startswith(marker):
            continue
        try:
            record = json.loads(line[len(marker):])
        except ValueError:
            continue
        if "load_error" in record:
            load_error = str(record["load_error"])[:80]
        elif isinstance(record.get("id"), str) and record["id"] not in records:
            records[record["id"]] = record

    run_failure = {"timeout": "timeout", "memory": "memory",
                   "output_limit": "output_limit", "runtime": "runtime"}.get(result.status)
    outputs: dict[str, Any] = {}
    errors: dict[str, str | None] = {}
    for case in pack.suite.cases:
        record = records.get(case.id)
        if load_error:
            errors[case.id] = "load"
        elif record is None:
            errors[case.id] = run_failure or "runtime"
        elif "error" in record:
            errors[case.id] = "runtime"
        elif record.get("invalid_output"):
            errors[case.id] = "invalid_output"
        else:
            try:
                outputs[case.id] = decode_value(record.get("output"))
                errors[case.id] = None
            except (ValueError, TypeError):
                errors[case.id] = "invalid_output"
        # Failed cases still need an envelope entry; it fails every check.
        outputs.setdefault(case.id, np.full((), np.nan))

    try:
        graded = grade(source, outputs, suite=pack.suite)
    except Exception:  # pragma: no cover - grading bug must not crash submit
        graded = {"properties": [], "static": static}
        errors = {cid: err or "grading" for cid, err in errors.items()}

    by_case: dict[str, bool] = {c.id: errors[c.id] is None for c in pack.suite.cases}
    for prop in graded.get("properties", []):
        for entry in prop.get("cases", []):
            if not entry.get("passed"):
                by_case[entry["case_id"]] = False
    return {
        "status": "graded",
        "error": "load" if load_error else None,
        "grader_version": GRADER_VERSION,
        "problem_id": pack.problem_id,
        "version": pack.version,
        "cases": [
            {"case_id": c.id, "passed": by_case[c.id],
             "error": errors[c.id] or (None if by_case[c.id] else "mismatch")}
            for c in pack.suite.cases
        ],
        "properties": [{"name": p["name"], "passed": bool(p["passed"])}
                       for p in graded.get("properties", [])],
        "static": static,
        "execution": {"status": result.status, "elapsed_ms": result.elapsed_ms},
    }
