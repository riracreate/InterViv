#!/usr/bin/env python3
"""Run the local app with persistent SQLite and no automatic model downloads.

Usage:
  .venv/bin/python scripts/run_local.py                  # offline app (CSV question bank)
  .venv/bin/python scripts/run_local.py --live-questions # enable LLM questions with CSV fallback
  .venv/bin/python scripts/run_local.py --fetch-models   # one-time model download, then run
  .venv/bin/python scripts/run_local.py --trusted-local-execution  # Python coding + ML, no Docker
  .venv/bin/python scripts/run_local.py --with-executor  # also start the Docker coding executor
  .venv/bin/python scripts/run_local.py --with-executor --live-jobs  # live jobs and coding
  .venv/bin/python scripts/run_local.py --live-questions # generate interview questions with the .env provider

Ctrl+C stops only the processes started by this launcher. Interview questions
stay offline using the CSV question bank by default: a provider key in .env is
not enough, because this launcher pins the offline bank. --live-questions
enables LLM generation with CSV fallback and opens the LLM gate for question
generation only (LLM_LIVE_CONSUMERS=questions); the guidance coach and
narration stay offline. --live-jobs explicitly enables job provider requests.
Model downloads happen only with --fetch-models.

Coding and ML execution, in order of preference:
- --with-executor starts the isolated local Piston executor (Docker required)
  for Python, JavaScript, Java and C++; it keeps running after Ctrl+C.
- --trusted-local-execution runs Python coding and NumPy ML submissions in a
  fresh local worker process when Piston is not running. It is a trusted
  local demo mode for your own code, not a security sandbox; the backend
  honours it only in development on 127.0.0.1.
Without either flag, coding and ML submissions are stored but not run or scored.
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

from dotenv import load_dotenv

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
        print("Docker is not installed. The Docker executor stays off "
              "(--trusted-local-execution can still run Python).", flush=True)
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


def _runtime_environment(
    state: Path,
    *,
    executor_on: bool,
    live_jobs: bool,
    trusted_local: bool = False,
    live_questions: bool = False,
) -> dict[str, str]:
    """Build a local, persistent runtime with network access explicitly selected."""
    env = dict(os.environ)
    env.update({
        "DATABASE_URL": f"sqlite:///{state / 'interviv-local.sqlite3'}",
        "ENVIRONMENT": "development",
        "REDIS_URL": "",
        # The LLM provider is dialed only when asked, and then only to
        # generate interview questions: the gate is limited to that consumer,
        # so the guidance coach and narration do not start using it too.
        "LLM_LIVE_FETCH": "1" if live_questions else "0",
        "LLM_LIVE_CONSUMERS": "questions" if live_questions else "",
        "JOBS_LIVE_FETCH": "1" if live_jobs else "0",
        "QUESTION_GENERATION_MODE": "llm_csv_fallback" if live_questions else "csv",
        "QUESTION_REQUIRE_LLM": "false",
        "QUESTION_LLM_PROVIDER": "auto",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "VITE_API_BASE_URL": "/api",
    })
    if executor_on:
        env["CODING_EXECUTOR_URL"] = EXECUTOR_URL
    else:
        # Do not accidentally connect to a stale or externally supplied executor.
        env.pop("CODING_EXECUTOR_URL", None)
    # The backend honours the trusted local runner only in development on
    # loopback; the launcher binds 127.0.0.1 and says so explicitly.
    env["INTERVIV_BIND_HOST"] = "127.0.0.1"
    if trusted_local:
        env["INTERVIV_TRUSTED_LOCAL_EXECUTION"] = "1"
    else:
        env.pop("INTERVIV_TRUSTED_LOCAL_EXECUTION", None)
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description="Run interViv locally (offline by default, persistent SQLite).")
    parser.add_argument("--fetch-models", action="store_true",
                        help="download the MiniLM and faster-whisper models once before starting")
    parser.add_argument("--with-executor", action="store_true",
                        help="start the Docker coding executor so Run/Submit work")
    parser.add_argument("--live-jobs", action="store_true",
                        help="enable live Adzuna and Greenhouse searches (Adzuna needs credentials in .env)")
    parser.add_argument("--live-questions", action="store_true",
                        help="enable live LLM question generation with offline CSV fallback; "
                             "nothing else (coach, narration) uses the provider")
    parser.add_argument("--trusted-local-execution", action="store_true",
                        help="run Python coding and NumPy ML submissions in a local worker process "
                             "when no executor is running (trusted local demo only, not a sandbox)")
    args = parser.parse_args()

    if os.getenv("INTERVIV_DISABLE_DOTENV") != "1":
        load_dotenv(ROOT / ".env", override=False)

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
    env = _runtime_environment(
        state,
        executor_on=executor_on,
        live_jobs=args.live_jobs,
        trusted_local=args.trusted_local_execution,
        live_questions=args.live_questions,
    )
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
        if args.live_questions:
            print("Question generation uses LLM with offline CSV fallback (--live-questions). "
                  "The guidance coach and narration stay offline.", flush=True)
        else:
            print("Question generation uses the offline bank; pass --live-questions for LLM questions.", flush=True)
        print("Live job search is enabled." if args.live_jobs else "Jobs use sample listings; pass --live-jobs for live results.", flush=True)
        if executor_on:
            print("Coding Run/Submit use the local executor.", flush=True)
        if args.trusted_local_execution:
            print("Trusted local runner is on: Python coding and NumPy ML run in a local "
                  "worker process (not a security sandbox; use only with your own code).", flush=True)
        elif not executor_on:
            print("Coding and ML need an executor: rerun with --with-executor or "
                  "--trusted-local-execution.", flush=True)
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
