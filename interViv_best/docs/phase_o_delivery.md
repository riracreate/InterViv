# Phase O — Jobs honesty defects closed

**Branch tip:** see git log (commit message: Phase O). **Parent:** `0d5fd54` (Phase N). **Chain root:** `0442493` (A).  
**Scope:** two contained fixes only. No JobSourceClient, no real listings, fixture JSON unchanged, Step 4 sourcing decision remains owner-open. `match_pct` framing untouched / still open.

**Phase M ports:** `:18000` / `:5173` were **not** disturbed. Disposable verify used `127.0.0.1:18001` + `127.0.0.1:5174` and `/tmp/interviv_phaseo_disposable.db`.

---

## Defect 1 findings (before the fix)

### Call path

`GET /jobs` → `backend/routes/jobs.py` `list_jobs` → `modules.jobs_explorer.search_jobs` → (cache miss) → `fetch_adzuna` → **`httpx.Client.get`** to `https://api.adzuna.com/v1/api/jobs/in/search/{page}` (≈L176–177 prior to gate).

### Credentials

- Env: `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` via `backend/config.py` → `Settings.adzuna_app_id` / `adzuna_app_key`.
- Committed: empty placeholders in `.env.example` only.
- This environment at Phase O start: **no** `.env`, neither key set in process env.

### Could it fire under default config?

**Latent** under the credentials-missing default (fixture path, no HTTP). **Live constraint violation** if credentials were present: fetch ran with no offline gate (unlike Phase J Hub offline).

### Degrade pattern

On any exception after attempting live fetch: silent return of fixtures with `fixture_fallback` — **SemanticScorer-like silent degrade**, not transcription fail-loud (503).

### Other ungated outbound (scan)

| Module | Library | Gate today |
|--------|---------|------------|
| `modules/jobs_explorer.py` | `httpx` → Adzuna | **Fixed in O:** `JOBS_LIVE_FETCH` default 0 |
| `modules/question_runtime.py` | `urllib.request.urlopen` LLM | Credential / mode gated (not Hub-style offline default) |
| `modules/question_bank.py` | `urllib` LLM | Same |
| `modules/guidance_coach.py` | `urllib` LLM | Same |

No second Adzuna-style market fetch found. LLM paths were noted only; not changed in O.

### Fix

- `backend/runtime_env.py`: `setdefault("JOBS_LIVE_FETCH", "0")`.
- `Settings.jobs_live_fetch`; `fetch_adzuna` returns fixtures without entering `httpx` unless gate on.
- Documented in `.env.example`, `docker-compose.yml`, Phase J delivery cross-note.
- Test: `test_default_jobs_live_fetch_skips_httpx` (credentials set + BoomClient).
- Gate on + no credentials: `test_live_fetch_enabled_without_credentials_uses_fixtures`.

---

## Defect 2 fix

Cache hits no longer set `source: "cache"` or clear the sample banner.

- Cached records carry `provenance` (+ `fetched_at` / `fetched_at_iso`).
- Envelope: `source` ≡ `provenance`; `cache_hit` is a separate axis; `fetched_at` survives warm path.
- `empty_reason` keys off provenance ∈ `{fixture, fixture_fallback}`.
- FE: `data-testid="jobs-sample-banner"` + `jobs-fetched-at` freshness line (shows cache note when `cache_hit`).

Warm-path test: `test_cache_hit_preserves_fixture_provenance_and_label`.

SQL datetime compare: `_as_utc` so SQLite naive `fetched_at` does not break warm reads (latent naive/aware issue; surfaced by post-put re-read under disposable SQL).

---

## Browser verification (disposable)

Account: signup `phaseo.user1@example.local` on `:5174` against `:18001` / disposable SQLite. Method: Cursor browser automation + DOM reads (`data-testid`).

| Check | Result | Method |
|-------|--------|--------|
| Sample label on first Jobs load | **VERIFIED** | Banner text present (`jobs-sample-banner`); 3 cards |
| Label still present after re-search (warm) | **VERIFIED** | Search click; banner unchanged; freshness shows “served from cache; provenance unchanged · source: fixture” |
| Freshness visible / correct | **VERIFIED** | `jobs-fetched-at` ISO timestamp matches cold obtain time across warm reload |
| Target this job | **VERIFIED** | Click → `GET /target-context/me` shows `job_id=adzuna:fixture-adzuna-1`, `jd_source=job` |
| Practice from job (Phase D flow) | **VERIFIED** | Navigated to `/interview/54e2a79b-…` with DBMS question; media permission UI environmental (not Jobs honesty) |

---

## Still open

- **Sourcing decision** (Phase N Step 4): owner.
- **`match_pct` framing** beside real company names: noted; not redesigned in O.
- Live JobSourceClient / Adzuna enabled product path.

---

## Evidence / scoring boundary

Jobs remain context only. No scoring, readiness, guard, or bank path edits. Alembic head unchanged: `20260907_0008`.

---

## Test pins changed

| Pin | Why |
|-----|-----|
| `tests/test_jobs_explorer.py` — added three tests | Gate default; gate-on no creds; warm provenance |
| `JOBS_LIVE_FETCH=0` setdefault in that module | Match runtime default under TestClient |
| Sample `empty_reason` copy when gate off | Mentions `JOBS_LIVE_FETCH` (honest about why fixtures show) |

Existing fixture-pinned Jobs tests retained and still pass.
