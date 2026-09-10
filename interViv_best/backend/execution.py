"""Local Piston client. Candidate code runs only in the external sandbox.

The server compares returned values with private expectations. Infrastructure
failure stays retryable and never becomes a candidate score. Disabled by
default; set ``CODING_EXECUTOR_URL=http://127.0.0.1:19000`` only after isolation
probes pass. Public executors (emkc.org and similar) are rejected.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
import time
from threading import BoundedSemaphore, Lock
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from backend.coding_languages import LANGUAGES, build_driver, normalize_language

# Only this loopback URL is accepted. Never emkc.org / public Piston.
ALLOWED_EXECUTOR_URL = "http://127.0.0.1:19000"


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

RATE_LIMIT_REASON = (
    "Too many coding execution requests. Wait a minute and retry; "
    "nothing was scored."
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


class CodingRateLimitedError(Exception):
    """Per-user or per-round app-boundary limit hit (HTTP 429)."""

    def __init__(self, reason: str = RATE_LIMIT_REASON) -> None:
        super().__init__(reason)
        self.reason = reason


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
_RATE_LOCK = Lock()
_USER_RATE: dict[str, list[float]] = {}


def executor_url_is_allowed(url: str | None) -> bool:
    """True only for the localhost-bound self-hosted executor."""
    raw = (url or "").strip().rstrip("/")
    if raw != ALLOWED_EXECUTOR_URL:
        return False
    parsed = urlsplit(raw)
    return (
        parsed.scheme == "http"
        and parsed.hostname == "127.0.0.1"
        and parsed.port == 19000
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
        and parsed.path in ("", "/")
    )


def _configured_executor_url() -> str:
    url = os.environ.get("CODING_EXECUTOR_URL", "").strip().rstrip("/")
    if not executor_url_is_allowed(url):
        raise ExecutionUnavailableError()
    return url


def coding_user_rate_ok(user_id: str, *, per_minute: int | None = None) -> bool:
    """In-process per-user sliding window for coding run/submit execute paths."""
    limit = per_minute
    if limit is None:
        try:
            limit = int(os.environ.get("CODING_RATE_LIMIT_PER_MINUTE") or "30")
        except ValueError:
            limit = 30
    limit = max(1, limit)
    key = str(user_id or "").strip() or "anonymous"
    now = time.time()
    with _RATE_LOCK:
        bucket = [t for t in _USER_RATE.get(key, []) if now - t < 60.0]
        if len(bucket) >= limit:
            _USER_RATE[key] = bucket
            return False
        bucket.append(now)
        _USER_RATE[key] = bucket
        return True


def consume_round_exec_slot(
    target_round: dict[str, Any],
    *,
    limits: CodingLimits | None = None,
) -> int:
    """Increment and enforce ``max_requests_per_round`` on the round dict.

    Returns the new count. Raises ``CodingRateLimitedError`` when exhausted.
    Caller must persist the updated round.
    """
    limits = limits or DEFAULT_LIMITS
    count = int(target_round.get("coding_exec_count") or 0)
    if count >= limits.max_requests_per_round:
        raise CodingRateLimitedError(
            f"This round reached the {limits.max_requests_per_round} execution "
            "request limit. Nothing further was run or scored."
        )
    count += 1
    target_round["coding_exec_count"] = count
    return count


def assert_coding_exec_allowed(user_id: str, target_round: dict[str, Any]) -> None:
    """App-boundary gates before any call into the executor."""
    if not coding_user_rate_ok(user_id):
        raise CodingRateLimitedError()
    consume_round_exec_slot(target_round)


def _service_request(path: str, payload: dict | None = None) -> Any:
    url = _configured_executor_url()
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
            "executor_url_policy": ALLOWED_EXECUTOR_URL,
            "scoring": "Deterministic visible and hidden test comparison; no AI judge."}
