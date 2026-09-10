"""Local Piston client. Candidate code runs only in the external sandbox.

The server compares returned values with private expectations. Infrastructure
failure stays retryable and never becomes a candidate score. Disabled by
default; configure CODING_EXECUTOR_URL after running the isolation probes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
from threading import BoundedSemaphore
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from backend.coding_languages import LANGUAGES, build_driver, normalize_language


@dataclass(frozen=True)
class CodingLimits:
    """Service limits applied at the execution boundary (C.2 backend)."""

    wall_seconds: float = 5.0
    memory_mb: int = 256
    output_bytes: int = 1_000_000
    max_requests_per_round: int = 50


DEFAULT_LIMITS = CodingLimits()

MISSING_INFRASTRUCTURE: tuple[str, ...] = (
    "configured local Piston service and installed language runtime",
)

UNAVAILABLE_REASON = (
    "Code execution is unavailable in this environment. "
    "Your code was not run and nothing was scored; retry later."
)


class ExecutionUnavailableError(Exception):
    """Infrastructure cannot run candidate code right now (retryable)."""

    def __init__(
        self,
        reason: str = UNAVAILABLE_REASON,
        *,
        missing: tuple[str, ...] = MISSING_INFRASTRUCTURE,
        retryable: bool = True,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.missing = missing
        self.retryable = retryable


def execute_python_tests(
    *,
    source: str,
    function: str,
    visible_tests: list[dict[str, Any]],
    hidden_tests: list[dict[str, Any]],
    limits: CodingLimits | None = None,
    language: str = "python",
    problem: dict | None = None,
) -> dict[str, Any]:
    """Run candidate source against tests via the execution service.

    Legacy Python entry point, also accepting an explicit supported language.
    A connected backend returns per-test outcomes shaped as
    {"visible": [...], "hidden": [...]}, each outcome carrying only
    {"passed": bool, "error": str | None, "stdout": str | None,
    "time_ms": float | None} with hidden stdout already stripped.
    Error vocabulary (scorer contract): None on pass; on failure one of
    "compile" | "runtime" | "timeout" | "mismatch". "compile"/"runtime"
    mark a candidate failure and cap the score at 25; "timeout" counts
    as an ordinary failed test.
    """
    return execute_tests(source=source, function=function, visible_tests=visible_tests,
                         hidden_tests=hidden_tests, limits=limits, language=language,
                         problem=problem)


_JOBS = BoundedSemaphore(2)


def _service_request(path: str, payload: dict | None = None) -> Any:
    url = os.environ.get("CODING_EXECUTOR_URL", "").strip().rstrip("/")
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")):
        raise ExecutionUnavailableError()
    data = json.dumps(payload, allow_nan=False).encode() if payload is not None else None
    request = Request(url + "/api/v2/" + path, data=data,
                      headers={"Content-Type": "application/json"})
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=25 if data else 3) as response:
            body = response.read(1_000_001)
        if len(body) > 1_000_000:
            raise ValueError("Oversized service response")
        return json.loads(body)
    except (OSError, HTTPError, URLError, ValueError) as exc:
        raise ExecutionUnavailableError() from exc


def _runtime(language: str) -> dict:
    spec = LANGUAGES[language]
    runtimes = _service_request("runtimes")
    if not isinstance(runtimes, list):
        raise ExecutionUnavailableError()
    for runtime in runtimes:
        if (isinstance(runtime, dict) and runtime.get("language") == spec["runtime"]
                and runtime.get("version") == spec["version"]):
            return runtime
    raise ExecutionUnavailableError(f"The {spec['label']} runtime is unavailable. Your code was not run; retry after it is installed.")


def _equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        return isinstance(actual, bool) and actual == expected
    if isinstance(expected, (float, int)):
        return (type(actual) in (float, int) and (not isinstance(actual, float) or math.isfinite(actual))
                and (math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)
                     if isinstance(expected, float) else actual == expected))
    if isinstance(expected, list):
        return (isinstance(actual, list) and len(actual) == len(expected)
                and all(_equal(a, e) for a, e in zip(actual, expected)))
    return type(actual) is type(expected) and actual == expected


def execute_tests(*, source: str, function: str, visible_tests: list[dict],
                  hidden_tests: list[dict], language: str = "python",
                  problem: dict | None = None, limits: CodingLimits | None = None) -> dict:
    language = normalize_language(language)
    if not source.strip() or len(source.encode()) > 20_000:
        raise ValueError("Solution must contain 1–20,000 UTF-8 bytes.")
    if not _JOBS.acquire(blocking=False):
        raise ExecutionUnavailableError("Both execution slots are busy. Nothing was scored; retry shortly.")
    try:
        runtime = _runtime(language)
        tests = visible_tests + hidden_tests
        limits = limits or DEFAULT_LIMITS
        marker = "INTERVIV_" + uuid4().hex + ":"
        try:
            files = build_driver(source=source, function=function, tests=tests,
                                 language=language, marker=marker, problem=problem)
        except SyntaxError as exc:
            outcomes = [{"passed": False, "error": "compile",
                         "message": f"Line {exc.lineno}: {exc.msg}"} for _ in tests]
            return _public_outcomes(outcomes, len(visible_tests))
        response = _service_request("execute", {
            "language": runtime["language"], "version": runtime["version"],
            "files": files, "stdin": "", "args": [],
            "compile_timeout": 15000, "run_timeout": int(limits.wall_seconds * 1000),
            "compile_cpu_time": 10000, "run_cpu_time": 3000,
            "compile_memory_limit": 768 * 1024 * 1024,
            "run_memory_limit": limits.memory_mb * 1024 * 1024,
        })
        if not isinstance(response, dict):
            raise ExecutionUnavailableError()
        compile_result = response.get("compile") or {}
        run = response.get("run") or {}
        if compile_result.get("status") == "XX" or run.get("status") == "XX":
            raise ExecutionUnavailableError()
        compile_failed = bool(compile_result and (compile_result.get("code") != 0 or compile_result.get("signal")))
        if not compile_failed and not run:
            raise ExecutionUnavailableError()
        failure = ("compile" if compile_failed else
                   "timeout" if run.get("status") == "TO" else "runtime")
        output = str(run.get("stdout") or "")
        records = {}
        for line in output.splitlines():
            if not line.startswith(marker):
                continue
            try:
                record = json.loads(line[len(marker):])
                index = record["i"]
                if type(index) is not int or index in records or not 0 <= index < len(tests):
                    raise ValueError("Invalid result index")
                records[index] = record
            except (ValueError, KeyError, TypeError):
                records = {}
                break
        diagnostics = str((compile_result if compile_failed else run).get("stderr") or "")[:4000]
        outcomes = []
        for i, case in enumerate(tests):
            record = records.get(i, {})
            has_value = "value" in record and not compile_failed
            passed = has_value and _equal(record["value"], case["expected"])
            outcome = {"passed": passed, "error": None if passed else ("mismatch" if has_value else failure)}
            if i < len(visible_tests):
                outcome.update({"actual": record.get("value"),
                                "message": str(record.get("message") or diagnostics)[:4000]})
            outcomes.append(outcome)
        return _public_outcomes(outcomes, len(visible_tests))
    finally:
        _JOBS.release()


def _public_outcomes(outcomes: list[dict], visible_count: int) -> dict:
    return {"visible": outcomes[:visible_count],
            "hidden": [{"passed": o["passed"], "error": o["error"]}
                       for o in outcomes[visible_count:]]}


def get_execution_status() -> dict[str, Any]:
    """Machine-readable execution availability for honest UI affordances."""
    try:
        runtimes = _service_request("runtimes")
    except ExecutionUnavailableError:
        runtimes = []
    if not isinstance(runtimes, list):
        runtimes = []
    languages = []
    for language, spec in LANGUAGES.items():
        available = any(isinstance(r, dict) and r.get("language") == spec["runtime"]
                        and r.get("version") == spec["version"] for r in runtimes)
        languages.append({"id": language, **spec, "available": available})
    available = any(item["available"] for item in languages)
    return {"available": available, "reason": None if available else UNAVAILABLE_REASON,
            "missing": [] if available else list(MISSING_INFRASTRUCTURE),
            "languages": languages, "limits": asdict(DEFAULT_LIMITS), "provider": "piston",
            "scoring": "Deterministic visible and hidden test comparison; no AI judge."}
