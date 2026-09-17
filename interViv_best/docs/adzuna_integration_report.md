# Adzuna job discovery report

**Branch:** `jobs/adzuna-integration`  
**Worktree:** `.worktrees/cursor-adzuna-integration`  
**Base (Phase 3B tip):** `1ff018dee91d6ef1f2f6551d1f711613166030c3`  
**Date:** 2026-09-17

## Reused infrastructure

- `modules/jobs_explorer.py` — search cache, SQL `jobs_cache` / `jobs_search_cache` (migration `20260907_0003`), lexicon skills, rate limit
- `backend/routes/jobs.py` — authenticated `/jobs` API
- `frontend/src/pages/Jobs.jsx` + `jobsMapping.js`
- Config: `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JOBS_LIVE_FETCH`, `JOBS_CACHE_TTL_SECONDS`, `JOBS_RATE_LIMIT_PER_MINUTE`
- Fixtures: `data/jobs_fixture_adzuna.json` when live fetch is off

## What changed

- New `modules/adzuna_client.py`: validated countries, HTTPS search, timeouts/retries, auth/quota/timeout error kinds, safe redirect URL check; credentials never logged in URLs
- Live failures no longer silently fall back to fixtures (config/auth/rate/timeout/provider are distinct from empty live results)
- Per-listing “Jobs by Adzuna” attribution + View job
- Salary display with Jobsworth predicted label when `salary_is_predicted`
- Prepare → confirm practice handoff (optional full JD); does not auto-start; Practice remains available standalone
- Country query param; unsupported country → 422 (no silent substitute)

## Configuration

| Name | Role |
| --- | --- |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | Server-side only; placeholders in `.env.example` |
| `JOBS_LIVE_FETCH` | Default `0` — fixtures; set `1` for live |
| `JOBS_CACHE_TTL_SECONDS` | Cache TTL (default 21600) |
| `JOBS_RATE_LIMIT_PER_MINUTE` | Per-user search throttle |

## Verification

| Check | Result |
| --- | --- |
| `pytest tests/test_jobs_explorer.py tests/test_adzuna_integration.py` | 17 passed |
| `pytest tests/test_demo_path_contracts.py` | 1 passed |
| Frontend `npm test` | 106 passed |
| `tsc --noEmit` | exit 0 |
| `npm run build` | success |
| Live Adzuna smoke | **skipped** — no local `ADZUNA_*` credentials configured |
| Scoring / AI gates | unchanged (`LLM_LIVE_FETCH=0`, reviewed-only off) |

## Terms note

Publishing listings only (permissible use). Per-ad “Jobs by Adzuna” branding applied. No derived vacancy analytics / aggregation products introduced.

## Final SHA

`ffa003fae4049cb08faa12d08a7ca6fc60ffe270`

## Remaining limitations

- Live market data requires operator-set credentials + `JOBS_LIVE_FETCH=1`
- Logo image may 404 if Adzuna CDN path changes; text “Adzuna” link remains
- Practice handoff uses lexicon skills only — never invents company questions or promotes drafts
- No push / merge / deploy
