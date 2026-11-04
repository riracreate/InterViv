"""Worker process for the trusted local runner (see backend/local_runner.py).

Copied into a fresh temporary directory and started as
``python -I _interviv_worker.py``. It reads one JSON job from stdin,
preloads the allowed modules, narrows imports and a few builtins for the
candidate module, applies OS limits where the platform enforces them,
prints the READY marker, then runs the driver file.

This is a convenience boundary for a trusted local demo, NOT a security
sandbox: restricted builtins and import hooks can be bypassed by
determined code. Untrusted deployments must use the isolated executor.
"""

import builtins
import importlib
import json
import runpy
import sys

READY = "__INTERVIV_WORKER_READY__"
CANDIDATE_MODULES = frozenset({"solution", "candidate"})


def _apply_limits(job):
    try:
        import resource
    except ImportError:  # pragma: no cover - non-POSIX
        return
    used = resource.getrusage(resource.RUSAGE_SELF)
    cpu_used = int(used.ru_utime + used.ru_stime)
    cpu_limit = cpu_used + int(job.get("cpu_seconds", 3)) + 1
    for name, value in (
        ("RLIMIT_CPU", (cpu_limit, cpu_limit + 1)),
        ("RLIMIT_FSIZE", (1_000_000, 1_000_000)),
        ("RLIMIT_CORE", (0, 0)),
    ):
        limit = getattr(resource, name, None)
        if limit is None:
            continue
        try:
            resource.setrlimit(limit, value)
        except (ValueError, OSError):
            pass
    # Address-space limits are enforced on Linux only (macOS ignores
    # RLIMIT_AS); the parent's RSS watchdog is the limit on every platform.
    if sys.platform.startswith("linux") and job.get("address_space_bytes"):
        try:
            cap = int(job["address_space_bytes"])
            resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
        except (ValueError, OSError):
            pass


def _guard_imports(allowed):
    original = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        importer = (globals or {}).get("__name__", "")
        if importer in CANDIDATE_MODULES:
            top = name.split(".")[0]
            if level or top not in allowed:
                raise ImportError(f"Import of '{name}' is not allowed in this exercise.")
        return original(name, globals, locals, fromlist, level)

    builtins.__import__ = guarded


def _blocked(name):
    def refuse(*args, **kwargs):
        raise PermissionError(f"{name}() is not available in this exercise.")
    return refuse


def main():
    job = json.loads(sys.stdin.read() or "{}")
    allowed = frozenset(job.get("allowed_modules") or ())
    for module in job.get("preload") or ():
        importlib.import_module(module)
    for module in sorted(allowed):
        try:
            importlib.import_module(module)
        except ImportError:
            pass
    _guard_imports(allowed)
    for name in ("open", "input", "breakpoint", "help", "exit", "quit"):
        setattr(builtins, name, _blocked(name))
    _apply_limits(job)
    sys.setrecursionlimit(max(200, int(job.get("recursion_limit", 3000))))
    sys.stdout.write(READY + "\n")
    sys.stdout.flush()
    runpy.run_path(job.get("driver", "main.py"), run_name="__main__")


if __name__ == "__main__":
    main()
