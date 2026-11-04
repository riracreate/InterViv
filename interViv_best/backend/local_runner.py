"""Trusted local runner: Docker-free Python/NumPy execution for local demos.

Enabled only by ``scripts/run_local.py --trusted-local-execution``, which
sets ``INTERVIV_TRUSTED_LOCAL_EXECUTION=1`` and ``INTERVIV_BIND_HOST=127.0.0.1``
for a development backend bound to loopback. Every other deployment keeps
the isolated-executor requirement (backend/execution.py).

Each job runs in a fresh ``sys.executable -I`` process inside a temporary
directory with a minimal environment, an import allowlist for the candidate
module, bounded output, a separate startup timeout, a wall-clock budget for
candidate code, and process-group cleanup. Memory is enforced by an RSS
watchdog (macOS ignores RLIMIT_AS); Linux additionally gets an address-space
cap. This is a trusted local runner, not a security sandbox: restricted
builtins and import hooks are not isolation.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TRUSTED_LOCAL_FLAG = "INTERVIV_TRUSTED_LOCAL_EXECUTION"
BIND_HOST_VAR = "INTERVIV_BIND_HOST"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
WORKER_SOURCE = Path(__file__).with_name("local_runner_worker.py")
READY_MARKER = "__INTERVIV_WORKER_READY__"

CANDIDATE_BUDGET_SECONDS = 2.5
STARTUP_TIMEOUT_SECONDS = 8.0
PYTHON_MEMORY_MB = 256
NUMPY_MEMORY_MB = 512
OUTPUT_LIMIT_BYTES = 256_000
POLL_SECONDS = 0.02

# Stdlib modules a coding solution may import. Everything else (os, sys,
# subprocess, socket, importlib, ctypes, …) is refused for candidate code.
PYTHON_ALLOWED_MODULES = (
    "array", "bisect", "collections", "copy", "dataclasses", "decimal", "enum",
    "fractions", "functools", "heapq", "itertools", "json", "math", "numbers",
    "operator", "random", "re", "statistics", "string", "typing",
)
NUMPY_ALLOWED_MODULES = PYTHON_ALLOWED_MODULES + ("numpy",)


@dataclass(frozen=True)
class LocalRunResult:
    """Outcome of one worker run. ``status`` is candidate-facing:

    ``ok`` (driver finished), ``runtime`` (non-zero exit), ``timeout``,
    ``memory`` or ``output_limit``. Infrastructure failures raise instead.
    """

    status: str
    stdout: str
    stderr: str
    returncode: int | None
    elapsed_ms: float


class LocalRunnerUnavailable(RuntimeError):
    """The worker could not be started or never became ready (retryable)."""


def trusted_local_execution_enabled() -> bool:
    """True only for an explicitly enabled development backend on loopback."""
    flag = os.environ.get(TRUSTED_LOCAL_FLAG, "").strip().lower()
    if flag not in {"1", "true", "yes", "on"}:
        return False
    from backend.config import get_settings

    if get_settings().environment != "development":
        logger.warning("Trusted local execution ignored outside development.")
        return False
    host = os.environ.get(BIND_HOST_VAR, "").strip().lower()
    if host not in LOOPBACK_HOSTS:
        logger.warning("Trusted local execution ignored: backend is not bound to loopback.")
        return False
    return True


def _minimal_env(workdir: str) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": workdir,
        "TMPDIR": workdir,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        # One BLAS thread keeps NumPy's footprint and timing predictable.
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
    }


def _kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.kill()
    except OSError:
        pass


class _Reader(threading.Thread):
    """Drain a pipe into a bounded buffer; note overflow and the READY line."""

    def __init__(self, stream, limit: int, watch_ready: bool = False) -> None:
        super().__init__(daemon=True)
        self.stream = stream
        self.limit = limit
        self.chunks: list[bytes] = []
        self.size = 0
        self.overflow = False
        self.ready = threading.Event()
        self.ready_at: float | None = None
        self.watch_ready = watch_ready
        self._pending = b""

    def run(self) -> None:
        marker = READY_MARKER.encode() + b"\n"
        while True:
            chunk = self.stream.read1(65536) if hasattr(self.stream, "read1") else self.stream.read(65536)
            if not chunk:
                break
            if self.watch_ready and not self.ready.is_set():
                self._pending += chunk
                if marker in self._pending:
                    _, _, rest = self._pending.partition(marker)
                    self.ready_at = time.monotonic()
                    self.ready.set()
                    self._pending = b""
                    chunk = rest
                elif len(self._pending) > 65536:
                    self._pending = self._pending[-len(marker):]
                    continue
                else:
                    continue
            if self.size + len(chunk) > self.limit:
                self.chunks.append(chunk[: max(0, self.limit - self.size)])
                self.size = self.limit
                self.overflow = True
                break
            self.chunks.append(chunk)
            self.size += len(chunk)

    def text(self) -> str:
        return b"".join(self.chunks).decode("utf-8", errors="replace")


def _rss_bytes(pid: int) -> int:
    import psutil

    try:
        parent = psutil.Process(pid)
        total = parent.memory_info().rss
        for child in parent.children(recursive=True):
            try:
                total += child.memory_info().rss
            except psutil.Error:
                pass
        return total
    except psutil.Error:
        return 0


def run_python_job(
    files: dict[str, str],
    *,
    driver: str = "main.py",
    numpy: bool = False,
    budget_seconds: float = CANDIDATE_BUDGET_SECONDS,
    startup_seconds: float = STARTUP_TIMEOUT_SECONDS,
    memory_mb: int | None = None,
    output_bytes: int = OUTPUT_LIMIT_BYTES,
) -> LocalRunResult:
    """Run ``driver`` from ``files`` in a fresh isolated-mode Python process.

    Raises LocalRunnerUnavailable when the worker cannot start or never
    reports ready (an infrastructure problem, never a candidate score).
    """
    try:
        import psutil  # noqa: F401  (required for the memory watchdog)
    except ImportError as exc:  # pragma: no cover - psutil is a pinned dependency
        raise LocalRunnerUnavailable("psutil is required for the local runner.") from exc

    memory_limit = int((memory_mb or (NUMPY_MEMORY_MB if numpy else PYTHON_MEMORY_MB)) * 1024 * 1024)
    allowed = NUMPY_ALLOWED_MODULES if numpy else PYTHON_ALLOWED_MODULES
    job = {
        "driver": driver,
        "allowed_modules": list(allowed),
        "preload": ["json", "importlib.util"] + (["numpy"] if numpy else []),
        "cpu_seconds": int(budget_seconds) + 1,
        "address_space_bytes": memory_limit + 1024 * 1024 * 1024,
    }
    workdir = tempfile.mkdtemp(prefix="interviv-run-")
    started = time.monotonic()
    proc: subprocess.Popen | None = None
    try:
        for name, content in files.items():
            if "/" in name or "\\" in name or name.startswith("."):
                raise ValueError(f"Invalid job file name: {name!r}")
            Path(workdir, name).write_text(content, encoding="utf-8")
        worker = Path(workdir, "_interviv_worker.py")
        shutil.copyfile(WORKER_SOURCE, worker)
        try:
            proc = subprocess.Popen(
                [sys.executable, "-I", str(worker)],
                cwd=workdir,
                env=_minimal_env(workdir),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                close_fds=True,
            )
        except OSError as exc:
            raise LocalRunnerUnavailable(f"Could not start the local runner: {exc}") from exc
        out = _Reader(proc.stdout, output_bytes, watch_ready=True)
        err = _Reader(proc.stderr, 16_000)
        out.start()
        err.start()
        try:
            proc.stdin.write(json.dumps(job).encode())
            proc.stdin.close()
        except OSError:
            pass

        status = None
        while True:
            now = time.monotonic()
            code = proc.poll()
            if not out.ready.is_set():
                if code is not None or now - started > startup_seconds:
                    _kill_group(proc)
                    proc.wait()
                    err.join(timeout=1)
                    raise LocalRunnerUnavailable(
                        "The local runner did not start. "
                        + (err.text().strip().splitlines() or [""])[-1][:300]
                    )
            else:
                if code is not None:
                    status = "ok" if code == 0 else "runtime"
                    break
                if out.overflow:
                    status = "output_limit"
                    break
                if now - (out.ready_at or now) > budget_seconds:
                    status = "timeout"
                    break
                if _rss_bytes(proc.pid) > memory_limit:
                    status = "memory"
                    break
            time.sleep(POLL_SECONDS)
        if proc.poll() is None:
            _kill_group(proc)
        proc.wait()
        out.join(timeout=1)
        err.join(timeout=1)
        if status in ("ok", "runtime") and out.overflow:
            status = "output_limit"
        # RLIMIT_CPU delivers SIGXCPU; report it as the timeout it is.
        if status == "runtime" and proc.returncode in (-signal.SIGXCPU, -signal.SIGKILL):
            status = "timeout"
        return LocalRunResult(
            status=status,
            stdout=out.text(),
            stderr=err.text()[-4000:],
            returncode=proc.returncode,
            elapsed_ms=round((time.monotonic() - (out.ready_at or started)) * 1000, 1),
        )
    finally:
        if proc is not None and proc.poll() is None:
            _kill_group(proc)
            proc.wait()
        shutil.rmtree(workdir, ignore_errors=True)


def describe_mode() -> dict[str, Any]:
    """Public description for status endpoints and docs."""
    return {
        "mode": "trusted_local",
        "label": "Trusted local runner (not a security sandbox)",
        "languages": ["python"],
        "budget_seconds": CANDIDATE_BUDGET_SECONDS,
        "memory_mb": {"python": PYTHON_MEMORY_MB, "numpy": NUMPY_MEMORY_MB},
        "output_bytes": OUTPUT_LIMIT_BYTES,
    }
