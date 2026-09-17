# Adzuna job discovery report

**Branch:** `jobs/adzuna-integration`  
**Worktree:** `.worktrees/cursor-adzuna-integration`  
**Base (Phase 3B tip):** `37900731439a272879309466e171c341b829790a`  
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
- Merged final Phase 3B tip `3790073` onto this branch (ort merge; Adzuna commits preserved)
- Test hardening: `test_live_fetch_enabled_without_credentials_is_config_failure` sets empty `ADZUNA_*` (not `delenv`) so local `.env` cannot refill credentials mid-test

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
| `pytest tests/test_jobs_explorer.py tests/test_adzuna_integration.py tests/test_demo_path_contracts.py` | **17 passed** |
| Frontend `npm test` | **113 passed** |
| `tsc --noEmit` | exit 0 |
| `npm run build` | success |
| Live Adzuna smoke | **connected** — country=`in`, query=`software engineer`, outcome=success, result_count=5 (bounded page); credentials only from gitignored `.env` |
| Scoring / AI gates | unchanged (`LLM_LIVE_FETCH=0`, reviewed-only off) |

## Terms note

Publishing listings only (permissible use). Per-ad “Jobs by Adzuna” branding applied. No derived vacancy analytics / aggregation products introduced.

## Final SHA

Recorded in follow-up docs pin after verification commit.

## Remaining limitations

- Live market data requires operator-set credentials + `JOBS_LIVE_FETCH=1`
- Logo image may 404 if Adzuna CDN path changes; text “Adzuna” link remains
- Practice handoff uses lexicon skills only — never invents company questions or promotes drafts
- No push / merge / deploy
