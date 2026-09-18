# Local demo guide (acceptance checkout)

- Checkout: `.worktrees/cursor-ai-design-acceptance`
- Open in Muse Code:
  `/Users/praneetsharma/Downloads/mega 2 copy/.worktrees/cursor-ai-design-acceptance`
- App directory: `interViv_best/` inside that checkout
- Branch: `qa/demo-acceptance`
- Frontend and backend must both run from this checkout (the Vite dev
  server proxies API calls to the local backend on port 8000).

## 1. Prerequisites (macOS)

- Python 3.12 with the checkout's venv: `interViv_best/.venv`
  (already present; if missing: `python3.12 -m venv .venv &&
  .venv/bin/pip install -r requirements.txt` from `interViv_best/`)
- Node.js with `frontend/node_modules` installed (already present; if
  missing: `cd frontend && npm install`)
- Optional, only for live coding execution: Docker Desktop
- Optional, only for LLM coding hints: system Ollama with `gemma2:2b`

No `.env` file ships with the checkout and none is required: with no
`DATABASE_URL` the backend uses the in-memory store. Keep any secrets
(API keys) in a local ignored `.env`, never in committed files.

## 2. Startup (three terminals, exact commands)

Terminal 1 — backend (from the app directory):

```bash
cd "/Users/praneetsharma/Downloads/mega 2 copy/.worktrees/cursor-ai-design-acceptance/interViv_best"
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Terminal 2 — frontend:

```bash
cd "/Users/praneetsharma/Downloads/mega 2 copy/.worktrees/cursor-ai-design-acceptance/interViv_best/frontend"
npm run dev -- --host 127.0.0.1 --port 5175
```

Terminal 3 — optional coding executor (only for Run/Submit on
`/problems`):

```bash
cd "/Users/praneetsharma/Downloads/mega 2 copy/.worktrees/cursor-ai-design-acceptance/interViv_best"
docker compose -f compose.coding.yml up executor
```

Reachable URLs once both servers are up:

- App: <http://127.0.0.1:5175>
- API + interactive docs: <http://127.0.0.1:8000> and
  <http://127.0.0.1:8000/docs>

Stop everything: Ctrl+C the uvicorn and vite terminals, then

```bash
docker stop interviv-coding-executor-1 interviv-coding-runtime-cache-1
lsof -nP -iTCP:8000,5175,19000 -sTCP:LISTEN   # should print nothing
```

## 3. First run

- Sign up in the app (`/signup`) — there is no built-in demo account.
- With the default in-memory DB, accounts, sessions, and plans disappear
  when the backend restarts. For a persistent demo, set `DATABASE_URL` to
  a Postgres (or file SQLite) URL and run `alembic upgrade head` first;
  downgrade target for the newest revision is its parent
  (`alembic downgrade 20260918_0015` removes only `sessions.revision`).

## 4. Effective runtime modes (as shipped)

| Capability | Mode without extra setup | How to enable live mode |
|---|---|---|
| Database | In-memory | Set `DATABASE_URL`, run migrations |
| Jobs (`/jobs`) | Local fixtures, labeled `fixture` | Set `ADZUNA_APP_ID` + `ADZUNA_APP_KEY` |
| Coding execution | Unavailable; API says so and scores nothing | Start the Piston container above |
| Coding hints | Curated fallback | Run Ollama with `gemma2:2b` on 11434 |
| Interview/roadmap/coach text | Deterministic rules + templates | No live path in this build (LLM stays off) |

Settings stay OFF: reviewed-only selection, experimental concept
evaluator, live generation/narration.

## 5. Manual browser checklist

API-verified flows are marked (API); the rest needs eyes on the UI.

Practice journeys (API):

- [ ] Standalone Verbal, OA, SQL, Interview: start, answer, feedback
      renders, no answer leakage before disclosure
- [ ] Mixed + repeated blocks: start interview+OA+interview, answer
      through, dashboard shows 3 separate block metric groups
- [ ] Refresh mid-session, then resume from progress (same questions,
      no rescore)
- [ ] Blocked continuation: force an empty-inventory block, confirm the
      blocked message names the block and offers a way out
- [ ] Timed MCQ/SQL: confirm countdown, expiry marks the round expired,
      late submit returns 400
- [ ] Assessment vs coached practice labels; follow-up schedules on a
      coached parent, second attempt on the same parent is refused with
      an explanatory reason
- [ ] Completed report: averages use assessment-eligible rounds only;
      answers disclose per policy after completion

Roadmap / coach / study (API):

- [ ] Roadmap with no history: starter plan, no readiness percentage,
      explicit "no eligible history" note
- [ ] Roadmap with assistance-only history: labeled practice, not mastery
- [ ] Coach: multi-turn conversation persists across reopen; goal and
      hours-per-week updates stick
- [ ] Study-task completion advances the plan without changing measured
      mastery, Elo, or readiness

Jobs:

- [ ] `/jobs` lists fixture results labeled as fixtures (API)
- [ ] Job detail → confirmed Practice handoff starts a session (API);
      confirm the Coach handoff path from a job detail page

Browser-only (not verifiable headless):

- [ ] Mobile (390px) and desktop layouts for Practice, Dashboard,
      Roadmap, Coach, Jobs
- [ ] Keyboard focus order and visible focus on all primary actions
- [ ] Sign-out returns to a signed-out landing state; protected routes
      redirect to login

## 6. Troubleshooting

- `EADDRINUSE` on 8000/5175: another process holds the port — find it
  with the `lsof` line in §2 and stop it; never run two checkouts'
  servers on the same ports.
- Blank page on 5175: confirm the backend answers
  `curl http://127.0.0.1:8000/docs` and restart vite.
- Stale UI after backend changes: hard-refresh; for API-shape changes
  rebuild (`npm run build` passes clean).
- Coding Run/Submit errors: expected without the Piston container; the
  message must say execution is unavailable (it does — verified).
