#!/bin/bash
# Phase 1 voice interview on 8001/5174. Does not touch a server already on 8000/5173.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIDDIR="${VOICE_PHASE1_PIDDIR:-${TMPDIR:-/tmp}/interviv-voice-phase1}"
mkdir -p "$PIDDIR"
MODE="${1:-start}"

if [[ "$MODE" == "stop" ]]; then
  if [[ -f "$PIDDIR/pids" ]]; then
    while read -r pid; do
      if [[ -n "${pid}" ]]; then kill "$pid" 2>/dev/null || true; fi
    done < "$PIDDIR/pids"
    rm -f "$PIDDIR/pids"
  fi
  exit 0
fi

if [[ -f "$PIDDIR/pids" ]]; then
  echo "Voice phase 1 already has pid file $PIDDIR/pids. Stop it first." >&2
  exit 1
fi

DEMO_DB="${DEMO_DB:-$HOME/interviv-demo/interviv-demo.sqlite3}"
ENV_FILE="${INTERVIV_ENV:-$(cd "$ROOT/../../.." && pwd)/interViv_best/.env}"
if [[ -n "${PYTHON:-}" && -x "$PYTHON" ]]; then
  :
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="python3"
fi
if [[ ! -f "$DEMO_DB" ]]; then
  echo "Demo database not found: $DEMO_DB" >&2
  exit 1
fi

cd "$ROOT"
nohup "$PYTHON" - "$ENV_FILE" "$DEMO_DB" "$ROOT" > "$PIDDIR/backend.log" 2>&1 <<'PY' &
import os, sys
from dotenv import dotenv_values
env_file, demo, root = sys.argv[1:]
vals = dotenv_values(env_file) if os.path.isfile(env_file) else {}
for key, value in (vals or {}).items():
    if key and value and key not in os.environ:
        os.environ[key] = value
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.abspath(demo)
os.environ["AI_INTERVIEW_ROUTING_ENABLED"] = "0"
os.environ["LLM_LIVE_FETCH"] = "0"
os.environ["REVIEWED_BUNDLES_ONLY"] = "false"
os.environ["STAGED_INLINE_FOLLOW_UPS"] = "1"
os.environ["SCORER_VERSION"] = "v3"
os.environ["JOBS_LIVE_FETCH"] = "0"
os.environ["QUESTION_GENERATION_MODE"] = "csv"
os.chdir(root)
sys.path.insert(0, root)
import uvicorn
uvicorn.run("backend.main:app", host="127.0.0.1", port=8001, log_level="info")
PY
BACK_PID=$!

cd "$ROOT/frontend"
nohup env VITE_DEV_API="http://127.0.0.1:8001" node "$ROOT/frontend/node_modules/vite/bin/vite.js" --host 127.0.0.1 --port 5174 --strictPort > "$PIDDIR/frontend.log" 2>&1 &
FRONT_PID=$!
printf '%s\n%s\n' "$BACK_PID" "$FRONT_PID" > "$PIDDIR/pids"
echo "Voice phase 1: backend $BACK_PID on 127.0.0.1:8001, frontend $FRONT_PID on 127.0.0.1:5174"
echo "Stop with: bash scripts/run_voice_phase1.sh stop"
