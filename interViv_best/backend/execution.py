"""Code-execution client boundary (separate from scoring).

This module owns everything about *running* untrusted candidate Python:
service limits, availability, and the unavailable/retry outcome. Scoring
lives in modules/scoring/coding.py and only ever sees per-test outcomes.

Phase C.1: no execution service is reachable offline (no running
container daemon, no Judge0-compatible API, no sandbox runtime), so every
call raises ExecutionUnavailableError. Candidate code is never executed
in the application process and no homemade sandbox is built here. The
unavailable outcome must surface as retryable, never as a candidate zero.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CodingLimits:
    """Service limits applied at the execution boundary (C.2 backend)."""

    wall_seconds: float = 5.0
    memory_mb: int = 256
    output_bytes: int = 1_000_000
    max_requests_per_round: int = 50


DEFAULT_LIMITS = CodingLimits()

MISSING_INFRASTRUCTURE: tuple[str, ...] = (
    "running container daemon (docker CLI present, daemon socket unreachable)",
    "Judge0-compatible code-execution API on localhost",
    "sandbox runtime for untrusted Python (nsjail/firejail/gVisor-class)",
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
) -> dict[str, Any]:
    """Run candidate source against tests via the execution service.

    Phase C.1 has no service, so this always raises. The signature is the
    C.2 seam: a connected backend returns per-test outcomes shaped as
    {"visible": [...], "hidden": [...]}, each outcome carrying only
    {"passed": bool, "error": str | None, "stdout": str | None,
    "time_ms": float | None} with hidden stdout already stripped.
    Error vocabulary (scorer contract): None on pass; on failure one of
    "compile" | "runtime" | "timeout" | "mismatch". "compile"/"runtime"
    mark a candidate failure and cap the score at 25; "timeout" counts
    as an ordinary failed test.
    """
    raise ExecutionUnavailableError()


def get_execution_status() -> dict[str, Any]:
    """Machine-readable execution availability for honest UI affordances."""
    return {
        "available": False,
        "reason": UNAVAILABLE_REASON,
        "missing": list(MISSING_INFRASTRUCTURE),
        "limits": asdict(DEFAULT_LIMITS),
    }
