#!/usr/bin/env bash
# Start this checkout: backend, frontend, local Ollama, OpenRouter questions,
# live Adzuna jobs, and the local coding runner that executes and judges code.
#
# From the workspace root:
#   bash interViv_best/scripts/run_current.sh
#
# Scoring stays deterministic. The coding judge compares tests. It does not
# ask a model to grade code. Accounts stay in the local demo database when
# that file is present, so a restart still accepts the same login.

set -euo pipefail

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN="$APP/local-data/run"
PY="$APP/.venv/bin/python"
CACHE="$APP/local-data/piston-cache"
mkdir -p "$RUN"

if [[ ! -x "$PY" ]]; then
  echo "Missing $PY. From interViv_best: python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

cd "$APP"

presence() {
  "$PY" - <<'PY'
import os
from pathlib import Path

vals = {}
try:
    from dotenv import dotenv_values
except ImportError:
    dotenv_values = None
env_path = Path(".env")
if dotenv_values and env_path.is_file():
    vals = dotenv_values(env_path) or {}

def present(name: str) -> bool:
    return bool(str(os.environ.get(name) or vals.get(name) or "").strip())

print("openrouter", "set" if present("OPENROUTER_API_KEY") else "missing")
print("adzuna", "set" if present("ADZUNA_APP_ID") and present("ADZUNA_APP_KEY") else "missing")
PY
}

listening() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

stop_ours() {
  local port="$1"
  local pid cwd
  local pids
  pids="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  for pid in $pids; do
    cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1)"
    case "$cwd" in
      "$APP"|"$APP"/*)
        kill "$pid" 2>/dev/null || true
        ;;
      *)
        echo "Port $port is already used by pid $pid ($cwd)."
        echo "Stop that process, then run this script again."
        return 1
        ;;
    esac
  done
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    listening "$port" || return 0
    sleep 0.3
  done
  echo "Port $port is still busy."
  return 1
}

detach() {
  local pidfile="$1"
  shift
  "$PY" - "$pidfile" "$@" <<'PY'
import os, sys
pidfile, cmd = sys.argv[1], sys.argv[2:]
if os.fork():
    os._exit(0)
os.setsid()
if os.fork():
    os._exit(0)
devnull = os.open(os.devnull, os.O_RDONLY)
os.dup2(devnull, 0)
with open(pidfile, "w") as handle:
    handle.write(str(os.getpid()))
os.execvp(cmd[0], cmd)
PY
}

wait_http() {
  local url="$1"
  local i
  for i in $(seq 1 120); do
    if curl -sf -o /dev/null "$url"; then
      return 0
    fi
    sleep 0.5
  done
  echo "Timed out waiting for $url"
  return 1
}

stop_all() {
  local name pid
  for name in backend frontend ollama; do
    if [[ -f "$RUN/$name.pid" ]]; then
      pid="$(cat "$RUN/$name.pid")"
      kill "$pid" 2>/dev/null || true
      rm -f "$RUN/$name.pid"
    fi
  done
  stop_ours 8000 || true
  stop_ours 5173 || true
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker compose -f "$APP/compose.coding.yml" stop executor >/dev/null 2>&1 || true
  fi
  echo "Stopped backend, frontend, and the coding executor."
  echo "Ollama is left running if it was already a system service."
}

if [[ "${1:-}" == "stop" ]]; then
  stop_all
  exit 0
fi

HAS_OPENROUTER=missing
HAS_ADZUNA=missing
while read -r name state; do
  case "$name" in
    openrouter) HAS_OPENROUTER=$state ;;
    adzuna) HAS_ADZUNA=$state ;;
  esac
done <<< "$(presence)"

echo "1. Backend  http://127.0.0.1:8000"
stop_ours 8000
(
  cd "$APP"
  # An empty DATABASE_URL keeps accounts in process memory. They vanish on
  # restart, and the next login reports "Invalid email or password."
  accounts="${HOME}/interviv-demo/interviv-demo.sqlite3"
  if [[ -f "$accounts" ]]; then
    export DATABASE_URL="sqlite:///${accounts}"
  else
    export DATABASE_URL=
  fi
  export CODING_EXECUTOR_URL=http://127.0.0.1:19000
  if [[ "$HAS_OPENROUTER" == "set" ]]; then
    export LLM_LIVE_FETCH=1
    export QUESTION_LLM_PROVIDER=openrouter
    export QUESTION_GENERATION_MODE=llm
  else
    export LLM_LIVE_FETCH=0
  fi
  if [[ "$HAS_ADZUNA" == "set" ]]; then
    export JOBS_LIVE_FETCH=1
  else
    export JOBS_LIVE_FETCH=0
  fi
  export ROLE_PRACTICE_ENABLED=1
  # Role-only targets and role interviews; off in code.
  export ROLE_ONLY_TARGETS=1
  detach "$RUN/backend.pid" "$PY" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 \
    >>"$RUN/backend.log" 2>&1
)
wait_http "http://127.0.0.1:8000/docs"

echo "2. Frontend  http://127.0.0.1:5173"
stop_ours 5173
(
  cd "$APP/frontend"
  export VITE_ROLE_PRACTICE=1
  export VITE_ROLE_ONLY_TARGETS=1
  detach "$RUN/frontend.pid" npm run dev -- --host 127.0.0.1 --port 5173 \
    >>"$RUN/frontend.log" 2>&1
)
wait_http "http://127.0.0.1:5173"

echo "3. Local LLM  Ollama gemma2:2b on http://127.0.0.1:11434"
if ! command -v ollama >/dev/null 2>&1; then
  echo "   Ollama is not installed. Coding hints use the built-in text until it is."
else
  if ! curl -sf -o /dev/null "http://127.0.0.1:11434/api/tags"; then
    detach "$RUN/ollama.pid" ollama serve >>"$RUN/ollama.log" 2>&1
    wait_http "http://127.0.0.1:11434/api/tags" || echo "   Ollama did not answer. See $RUN/ollama.log"
  fi
  if ! curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null; then
    echo "   Ollama did not answer. Coding hints use the built-in text until it does."
  elif curl -sf "http://127.0.0.1:11434/api/tags" | grep -q "gemma2:2b"; then
    echo "   gemma2:2b is ready"
  else
    echo "   Pulling gemma2:2b"
    ollama pull gemma2:2b
  fi
fi

echo "4. OpenRouter LLM  interview questions"
if [[ "$HAS_OPENROUTER" == "set" ]]; then
  echo "   Enabled on the backend (LLM_LIVE_FETCH=1, provider openrouter)"
else
  echo "   OPENROUTER_API_KEY is missing. Questions stay on the CSV fallback."
fi

echo "5. Jobs  Adzuna live search and Greenhouse boards"
if [[ "$HAS_ADZUNA" == "set" ]]; then
  echo "   Live Adzuna search is on. Greenhouse boards need no key."
else
  echo "   Adzuna keys are missing. Adzuna stays on sample listings. Greenhouse still works."
fi

echo "6. Coding platform  run and judge on http://127.0.0.1:19000"
if ! command -v docker >/dev/null 2>&1; then
  echo "   Docker is not installed. Run and Submit stay unavailable until the local executor is up."
elif ! docker info >/dev/null 2>&1; then
  echo "   Docker is not running. Start Docker, then run this script again for Run and Submit."
else
  if [[ ! -f "$CACHE/index" ]]; then
    echo "   Downloading the approved language runtimes into local-data/piston-cache"
    "$PY" scripts/setup_coding_runtimes.py --download "$CACHE" || {
      echo "   Could not download the coding runtimes."
    }
  fi
  if [[ -f "$CACHE/index" ]] && CODING_RUNTIME_CACHE="$CACHE" docker compose -f "$APP/compose.coding.yml" up -d; then
    wait_http "http://127.0.0.1:19000/api/v2/runtimes" || echo "   Executor did not answer yet."
    if ! curl -sf "http://127.0.0.1:19000/api/v2/runtimes" | grep -q python; then
      echo "   Installing python, node, java, and gcc into the local executor"
      "$PY" scripts/setup_coding_runtimes.py --install
    fi
    docker compose -f "$APP/compose.coding.yml" stop runtime-cache >/dev/null 2>&1 || true
    echo "   Executor is on. The backend judges a submission by its visible and hidden tests."
  else
    echo "   Could not start the coding executor."
  fi
fi

echo
echo "App        http://127.0.0.1:5173"
echo "API        http://127.0.0.1:8000/docs"
echo "Logs       $RUN"
echo "Stop       bash \"$0\" stop"
