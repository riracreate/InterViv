# Local demo guide

Updated 2026-11-04 for the `overhaul/reliable-journey` branch. The earlier
version described the removed `.worktrees/cursor-ai-design-acceptance`
checkout; that checkout no longer exists. Run everything from
`interViv_best/` in this repository.

## 1. Prerequisites (macOS)

- Python 3.12 environment at `interViv_best/.venv` (already present; if
  missing: `python3.12 -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt`)
- Node.js with `frontend/node_modules` installed (already present; if
  missing: `cd frontend && npm ci`)
- Optional: Docker Desktop, only for the Piston executor (JavaScript, Java,
  C++, or isolated Python execution)
- Optional: system Ollama with `gemma2:2b`, only for LLM coding hints

No `.env` is required for the offline demo. Keep any secrets (Adzuna keys) in
the local, git-ignored `.env`, never in committed files.

## 2. Start

One command starts the backend (port 8000) and frontend (port 5173), applies
migrations, and keeps accounts and progress in
`local-data/interviv-local.sqlite3`:

```bash
cd interViv_best
.venv/bin/python scripts/run_local.py --trusted-local-execution
```

Open <http://127.0.0.1:5173>. Ctrl+C stops both services.

| Option | Effect |
|---|---|
| (none) | Offline: no coding execution, fixture jobs, no live LLM |
| `--trusted-local-execution` | Python coding and NumPy ML Primitives run in local worker processes. Not a security sandbox; see `coding_execution_security.md` |
| `--with-executor` | Starts the Docker Piston executor on 127.0.0.1:19000 for all four coding languages |
| `--live-jobs` | Live Adzuna (needs credentials in `.env`) and Greenhouse searches |
| `--fetch-models` | Downloads the MiniLM and faster-whisper models once before starting |

Options can be combined. For coding, Piston takes priority when it is
running; ML Primitives always use the trusted local runner.

Checks once it is up:

```bash
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8000/problems/execution/status   # python mode: trusted_local
.venv/bin/python scripts/smoke_local.py --state-file local-data/demo-smoke.json
```

## 3. First run

- Sign up at `/signup`; there is no built-in demo account.
- Accounts, sessions and plans persist across launcher restarts.
- Starting uvicorn directly without `DATABASE_URL` uses disposable in-memory
  storage instead; the launcher always selects its SQLite file.

## 4. Runtime modes

| Capability | Default | With options |
|---|---|---|
| Database | Local SQLite (launcher) | `DATABASE_URL` for PostgreSQL; run `alembic upgrade head` |
| Coding execution | Unavailable; nothing is scored | `--trusted-local-execution` (Python) or `--with-executor` (all languages) |
| ML Primitives | Stored ungraded; round stays open | `--trusted-local-execution`, scorer `v1-ml-primitives` |
| System design | Self-ratings plus a content practice estimate (`v1-system-design-content`), excluded from Elo and mastery | — |
| Jobs | Labeled offline samples (Adzuna and Greenhouse fixtures) | `--live-jobs` |
| Coding hints | Curated templates | Ollama with `gemma2:2b` on 11434 |
| Interview, roadmap, coach text | Deterministic rules and templates | Live LLM stays off |
| Voice | Browser speech recognition and read-aloud when supported; typing always works | — |

## 5. Manual browser checklist

Use the checklist in [`overhaul_acceptance.md`](overhaul_acceptance.md#manual-checklist-run-in-your-own-browser):
upload and Back, interview review and Next, coding and ML without Docker,
voice, navigation and sign out, and report tabs. The automated journey test
(`tests/test_full_journey.py`) covers the same path through the API.

## 6. Troubleshooting

- The launcher reports a port in use: another server is already running on
  8000 or 5173. Stop it, or use the app it is already serving.
- Blank page on 5173: check `curl http://127.0.0.1:8000/ready`, then restart
  the launcher.
- Coding or ML shows "execution is unavailable": start with
  `--trusted-local-execution` (Python and ML) or `--with-executor`.
- Stale UI after changes: hard-refresh; `cd frontend && npm run build` should
  pass cleanly.
