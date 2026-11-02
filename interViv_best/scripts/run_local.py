#!/usr/bin/env python3
"""Run the local app with persistent SQLite and no automatic downloads.

Usage:
  .venv/bin/python scripts/run_local.py                  # offline app
  .venv/bin/python scripts/run_local.py --fetch-models   # one-time model download, then run
  .venv/bin/python scripts/run_local.py --with-executor  # also start the Docker coding executor

Ctrl+C stops only the processes started by this launcher. The app itself always
runs offline; downloads happen only with --fetch-models. Coding Run/Submit needs
the local Piston executor (--with-executor, Docker required); the executor keeps
running after Ctrl+C (stop it with `docker compose -f compose.coding.yml down`).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
EXECUTOR_URL = "http://127.0.0.1:19000"

# Local models the app loads offline, and what degrades without them.
MODELS = {
    "sentence-transformers/all-MiniLM-L6-v2": "semantic scoring falls back to lexical matching (results say 'lexical fallback')",
    "Systran/faster-whisper-tiny.en": "voice transcription is unavailable (POST /transcribe returns 503)",
}
# Revision the frozen scorer baselines were captured with (docs/scorer_versions.md).
BASELINE_MINILM_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


def _hf_hub_dir() -> Path:
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"]).expanduser()
    home = os.environ.get("HF_HOME") or str(Path.home() / ".cache" / "huggingface")
    return Path(home).expanduser() / "hub"


def _cached_revision(repo_id: str) -> str | None:
    """Commit that refs/main points at, if that snapshot exists locally."""
    repo = _hf_hub_dir() / ("models--" + repo_id.replace("/", "--"))
    ref = repo / "refs" / "main"
    if not ref.is_file():
        return None
    commit = ref.read_text().strip()
    snapshot = repo / "snapshots" / commit
    return commit if snapshot.is_dir() and any(snapshot.iterdir()) else None


def _fetch_models() -> bool:
    """Download the local models once. Runs in a child so offline flags don't apply."""
    env = {k: v for k, v in os.environ.items() if k not in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")}
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    for repo_id in MODELS:
        print(f"Downloading {repo_id} ...", flush=True)
        code = "import sys; from huggingface_hub import snapshot_download; snapshot_download(sys.argv[1])"
        if subprocess.run([sys.executable, "-c", code, repo_id], env=env).returncode != 0:
            print(f"Could not download {repo_id}.", file=sys.stderr)
            return False
    revision = _cached_revision("sentence-transformers/all-MiniLM-L6-v2")
    if revision and revision != BASELINE_MINILM_REVISION:
        print(
            f"Note: MiniLM main is now {revision[:12]}; scorer baselines were captured with "
            f"{BASELINE_MINILM_REVISION[:12]}. Check with scripts/replay_scorer_v1_baseline.py --version v2.",
            flush=True,
        )
    return True


def _model_preflight() -> None:
    for repo_id, degraded in MODELS.items():
        if _cached_revision(repo_id) is None:
            print(f"Model {repo_id} is not in the local cache: {degraded}.", flush=True)
            print("  Download it once with: .venv/bin/python scripts/run_local.py --fetch-models", flush=True)


def _http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def _start_executor() -> bool:
    """Start the local Piston executor with Docker (port of run_current.sh step 6)."""
    runtimes = f"{EXECUTOR_URL}/api/v2/runtimes"
    if _http_ok(runtimes):
        print("Coding executor already running on 127.0.0.1:19000.", flush=True)
        return True
    docker = shutil.which("docker")
    if not docker:
        print("Docker is not installed. Coding Run/Submit stays unavailable.", flush=True)
        return False
    if subprocess.run([docker, "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        print("Docker is not running. Start Docker Desktop, then run this again.", flush=True)
        return False
    cache = ROOT / "local-data" / "piston-cache"
    setup = [sys.executable, str(ROOT / "scripts" / "setup_coding_runtimes.py")]
    if not (cache / "index").is_file():
        print("Downloading the approved language runtimes into local-data/piston-cache ...", flush=True)
        if subprocess.run(setup + ["--download", str(cache)], cwd=ROOT).returncode != 0:
            print("Could not download the coding runtimes.", flush=True)
            return False
    compose = [docker, "compose", "-f", str(ROOT / "compose.coding.yml")]
    env = {**os.environ, "CODING_RUNTIME_CACHE": str(cache)}
    if subprocess.run(compose + ["up", "-d"], cwd=ROOT, env=env).returncode != 0:
        print("Could not start the coding executor.", flush=True)
        return False
    deadline = time.monotonic() + 30
    while not _http_ok(runtimes) and time.monotonic() < deadline:
        time.sleep(0.5)
    try:
        with urllib.request.urlopen(runtimes, timeout=5) as response:
            installed = b"python" in response.read()
    except (OSError, urllib.error.URLError):
        print("Executor did not answer on 127.0.0.1:19000.", flush=True)
        return False
    if not installed:
        print("Installing python, node, java, and gcc into the local executor ...", flush=True)
        if subprocess.run(setup + ["--install"], cwd=ROOT).returncode != 0:
            print("Could not install the coding runtimes.", flush=True)
            return False
    subprocess.run(compose + ["stop", "runtime-cache"], cwd=ROOT, env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Coding executor is on (Python, JavaScript, Java, C++).", flush=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Run interViv locally (offline, persistent SQLite).")
    parser.add_argument("--fetch-models", action="store_true",
                        help="download the MiniLM and faster-whisper models once before starting")
    parser.add_argument("--with-executor", action="store_true",
                        help="start the Docker coding executor so Run/Submit work")
    args = parser.parse_args()

    npm = shutil.which("npm")
    if not npm or not (ROOT / "frontend/node_modules/vite/bin/vite.js").is_file():
        print("Install the frontend dependencies with npm ci in frontend/ first.", file=sys.stderr)
        return 1
    for port in (8000, 5173):
        try:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", port))
        except PermissionError:
            print("Permission to bind local application ports was denied.", file=sys.stderr)
            return 1
        except OSError:
            print(f"Port {port} is unavailable. Stop the app using it before starting this checkout.", file=sys.stderr)
            return 1

    if args.fetch_models and not _fetch_models():
        return 1
    _model_preflight()
    executor_on = _start_executor() if args.with_executor else False

    state = ROOT / "local-data"
    state.mkdir(exist_ok=True)
    run = state / "local-run"
    run.mkdir(exist_ok=True)
    env = dict(os.environ)
    # This launcher is deliberately local and offline. The existing custom
    # run_current.sh remains available for separately configured live services.
    env.update({
        "DATABASE_URL": f"sqlite:///{state / 'interviv-local.sqlite3'}",
        "ENVIRONMENT": "development",
        "REDIS_URL": "",
        "LLM_LIVE_FETCH": "0", "JOBS_LIVE_FETCH": "0",
        "QUESTION_GENERATION_MODE": "csv", "QUESTION_REQUIRE_LLM": "false",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "VITE_API_BASE_URL": "/api",
    })
    if executor_on:
        env["CODING_EXECUTOR_URL"] = EXECUTOR_URL
    children = []
    handles = []

    def stop(signum=None, frame=None):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True)
        commands = [
            ("backend", [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"], ROOT),
            ("frontend", [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"], ROOT / "frontend"),
        ]
        for name, command, cwd in commands:
            handle = (run / f"{name}.log").open("a")
            handles.append(handle)
            children.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True))
        deadline = time.monotonic() + 90
        pending = {"http://127.0.0.1:8000/ready", "http://127.0.0.1:5173"}
        while pending:
            if any(child.poll() is not None for child in children):
                raise RuntimeError(f"An app process stopped. See logs in {run}.")
            if time.monotonic() >= deadline:
                raise RuntimeError(f"The app did not become ready. See logs in {run}.")
            for url in list(pending):
                try:
                    with urllib.request.urlopen(url, timeout=2) as response:
                        if response.status == 200:
                            pending.remove(url)
                except (OSError, urllib.error.URLError):
                    pass
            time.sleep(0.3)
        print("App ready: http://127.0.0.1:5173", flush=True)
        print(f"Accounts and progress are saved in {state / 'interviv-local.sqlite3'}", flush=True)
        if executor_on:
            print("Offline practice is enabled. Coding Run/Submit use the local executor.", flush=True)
        else:
            print("Offline practice is enabled. Coding Run/Submit need the executor: rerun with --with-executor.", flush=True)
        print("Press Ctrl+C to stop.", flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.5)
        raise RuntimeError(f"An app process stopped. See logs in {run}.")
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        # Children have their own groups, including npm's Vite child. Never
        # kill a process merely because it happens to own a known port.
        for child in children:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        for handle in handles:
            handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
