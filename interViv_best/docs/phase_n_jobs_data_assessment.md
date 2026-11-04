# Phase N — what real job data would require

**Read-only engineering assessment. No integration. No external contact.**
**Branch tip assessed:** `8466c48` (Phase L). **Chain root:** `0442493` (A).
**Phase M** may still hold `:18000` / `:5173`; this phase started no servers and did not disturb that stack.

Owner decision territory (terms of service, data protection, whether to lift offline rules) is **stated, not decided**. This document covers only what interViv would have to change to accept listings from *any* external source.

---

## Step 0 — inventory of the current Jobs implementation

### Where sample data lives

| Item | Detail |
|------|--------|
| Path | `interViv_best/data/jobs_fixture_adzuna.json` |
| Format | JSON array of flat Adzuna-like objects |
| Count | **3** records (`fixture-adzuna-1` … `-3`) |
| Production | Hand-authored, checked in. No generator script. |
| Loader | `modules/jobs_explorer.py` → `load_fixture_jobs()` (≈L89–91) reads the file and normalizes with `from_fixture=True` |

Used when Adzuna credentials are missing (`source: "fixture"`, ≈L160–162) or when a live fetch fails (`source: "fixture_fallback"`, ≈L180–181).

### Schema as the application consumes it

**Fixture / provider input (pre-normalize)** — fields on each fixture object:

| Field | Type | Required? | Role |
|-------|------|-----------|------|
| `id` | string | effectively yes | becomes `external_id` |
| `title` | string | optional → `""` | display |
| `company` | string (fixture) or `{display_name}` (live) | optional → `""` | display; shape selects normalize branch |
| `location` | string or `{display_name}` | optional → `""` | display |
| `description` | string | optional → `""` | truncated to snippet (2000 chars) |
| `redirect_url` | string | optional → `""` | Apply outbound link |
| `created` | string / any | optional | listing age (API only today) |
| `salary_min` / `salary_max` | number \| null | optional | mapped in FE helper; not shown on Jobs cards |

**Normalized card** (`_normalize_adzuna_item`, ≈L119–143):

| Field | Type | Notes |
|-------|------|--------|
| `id` | `adzuna:{external_id}` | Stable composite; `get_job` requires `:` |
| `provider` | `"adzuna"` | Cache / identity key |
| `external_id` | string | Provider-side id |
| `title`, `company`, `location` | string | Always present (may be empty) |
| `created` | any \| null | Optional |
| `salary_min` / `salary_max` | number \| null | Optional |
| `snippet` | string | From description |
| `redirect_url` | string | Apply only if truthy |
| `skills` | `list[str]` | **Derived** via `extract_skills_from_text(title + snippet)` — lexicon, no LLM |
| `payload` | dict | Persisted in `jobs_cache.payload` |

**Search API envelope** (`search_jobs`, ≈L305–340): `jobs`, `count`, `page`, `q`, `where`, `source`, `cache_hit`, `empty_reason`, `disclaimer`. Each card adds `match_pct` (null if either skill side empty).

**SQL** (migration `20260907_0003`): `jobs_cache` `(provider, external_id)` unique; `jobs_search_cache` keyed by `query_hash`. `target_contexts.job_id` / `jd_source` / `jd_text` (Phase D).

### Sample labels and “preserving” them

There is **no** per-card `source_label` field. Honesty is envelope-level:

| Signal | Values | Rendered? |
|--------|--------|-----------|
| `source` | `live` \| `fixture` \| `fixture_fallback` \| `cache` \| `override` | Stored in FE `meta`; **not** shown as a badge on cards |
| `empty_reason` | free-text warning when credentials missing **and** `source ∈ {fixture, fixture_fallback}` | Jobs header warn (`Jobs.jsx` ≈L118–120) |
| `disclaimer` | always (Adzuna India / not LinkedIn–Naukri) | Always (`data-testid="jobs-disclaimer"`) |
| `created` | per listing | **API only — not rendered** |
| `fetched_at` | cache metadata | DB/memory only |

**What “preserve sample-job labels and source/freshness” means in code today:** keep returning `source`, `empty_reason` (when fixture/fallback), and `disclaimer`, and keep Home’s promise that Jobs identifies sample listings (`Home.jsx`). It does **not** currently mean a durable per-card “Sample” chip or a visible age.

**Known honesty gap (already in tree):** after a search is cached, `source` becomes `"cache"` and `empty_reason` is cleared even when credentials were never set — so the sample banner can **disappear** on TTL cache hits. Phase D asked reviewers to “confirm the listing is labelled as sample data”; Phase F marked Jobs sample-data labeling **STILL BLOCKED**.

### Consumers

| Consumer | Reads | Assumes |
|----------|-------|---------|
| **Jobs UI** (`frontend/src/pages/Jobs.jsx`, `jobsMapping.js`) | `GET /jobs` cards + disclaimer / empty_reason | Auth; `job.id` for target/practice; Apply iff `redirect_url` |
| **Target context** (`backend/routes/target_context.py`) | `get_job(job_id)` to validate; stores `job_id`, title/company | Id `provider:external_id` must resolve (memory → SQL → fixture fallback) |
| **Jobs → target from UI** | `{ job_id, jd_source: 'job' }` | **Does not** copy snippet into `jd_text` |
| **JD / skills** | Lexicon on `title+snippet` at normalize time | No LLM JD parse (`jobs_explorer` module header) |
| **`match_pct`** | Job skills ∩ user resume/graph skills | Null if either empty — not a hiring probability |
| **Practice from job** (`POST /jobs/{id}/practice`) | `missing_skills_for_job` → session start | Caps skills; falls back toward `["DSA"]` |
| **Gap / roadmap / Learn** | **Company-role skills**, not job listings | Job data is not measurement input |
| **ATS / Coach** | Prefill **pasted** `jd_text` / role from target | Targeting a job without pasting JD does **not** feed ATS the job snippet |
| **Coach plan links** | `/jobs?q=…` hrefs | Does not load records by id |

**Evidence / scoring:** job listings are **context**, not attempts. They do not write scores, readiness, mastery, or notebook rows. Confirmed by consumer map: gap/readiness paths ignore `job_id` listings.

### Static / cache assumptions

| Store | TTL | Cross-session |
|-------|-----|---------------|
| Search memory / SQL search cache | yes (~6h default) | SQL durable |
| `_JOB_MEMORY` / SQL `jobs_cache` | **no TTL on `get_job`** | Durable until overwrite |
| Fixture file | forever | Always fallback for `get_job` |
| Rate limit | process-local | — |

So some consumers **do** assume listings remain fetchable by stable `adzuna:{id}` across sessions (target validation, practice-by-job-id). Fixture ids are immortal; live/cache ids can go stale without UI aging.

---

## Step 1 — interface a real source would need

Source-agnostic. Pattern: Phase C execution client — separate client, unavailable ≠ zero, no coupling into scoring or evidence.

### Adapter shape

```
JobSourceClient
  search(q, where, page) -> SearchPage | Unavailable
  get(external_id) -> Listing | NotFound | Unavailable
```

- **Seam:** new module (e.g. `modules/job_source_client.py`) behind `jobs_explorer.search_jobs` / `get_job`. Today’s Adzuna `httpx` path and fixture path become two implementations of the same client.
- **Ask:** query string, location, page size, optional cursor.
- **Receive:** normalized cards matching the internal schema above, plus provenance (`source`, optional `fetched_at`, optional `expires_at`).
- **Must not:** call scorer, write attempts, invent listings when unavailable, or present an empty list as “no jobs match your profile” when the source failed.

### Field mapping (generic external → current schema)

| Current field | Likely from any source? | If missing |
|---------------|-------------------------|------------|
| `external_id` | Yes (required for identity) | Reject listing |
| `title` | Yes | Default `""` (weak UX) |
| `company` | Usually | Default `""` |
| `location` | Often | Default `""` |
| `description` / snippet | Usually | Default `""`; skills may be `[]` |
| `redirect_url` | Often (apply URL) | Optional — hide Apply |
| `created` | Often | Optional — mark freshness unknown |
| `salary_*` | Sometimes | Optional null |
| `skills` | Rarely authoritative | **Keep deriving** via lexicon (or leave empty) |
| `provider` | Adapter-supplied constant | Required |
| `match_pct` | Never from source | Always computed locally |

**Would become explicitly optional in product terms:** `salary_*`, `created`, `redirect_url`, rich description. **Must stay required for cache/target:** `provider`, `external_id`, composite `id`.

### Freshness

- Represent `created` (listing age) and `fetched_at` / `expires_at` (cache age) separately; render at least one honestly.
- Stale: search TTL already refreshes pages; **job detail cache has no TTL** — needs expiry or revalidate-on-get.
- Disappeared: `get_job` → not found; target that holds that `job_id` must show “listing no longer available” without deleting the user’s company/role target unless they choose.

### Persistence

- Live-only: weak offline demos; every target/`get_job` needs network.
- Store normalized cards (extend `jobs_cache`): fits B.1 lesson — every field round-trips, `__getitem__` registered, migration if new columns (e.g. `expires_at`, `source_label`).
- Search cache can remain TTL’d; detail rows need explicit retention.

### Unavailability

Phase C/D pattern:

| Condition | Show | Must not show |
|-----------|------|----------------|
| Credentials / network / quota fail | Labeled unavailable + retry | Empty list as “no matches” |
| Source empty for a real query | Empty result, labeled as empty query | Fixture silently substituted without label |
| Offline product mode | Fixture **or** last-good cache, **labeled** | Live-looking unlabeled cards |

Today’s fixture-on-missing-keys is a demo path; a live product must not confuse it with “the market has three internships.”

### Identity and deduplication

- Stable id: `{provider}:{external_id}` (already).
- Same listing twice: unique `(provider, external_id)` on `jobs_cache` (already).
- Cross-provider duplicates: out of scope unless a later content-hash policy is owned; do not invent one here.

---

## Step 2 — what would break

### Phase D connections that assume sample / static resolution

| Connection | Risk |
|------------|------|
| Target a job by id | Live ids vanish; `get_job` fixture fallback only helps fixture ids |
| Jobs → practice | Missing listing → practice start fails |
| ATS/Coach | Mostly pasted JD — **less** coupled to live listings; still inherit target title/company |
| Gap/roadmap | Role-based — **not** listing-coupled |
| Sample labeling | Cache/`source: cache` already weakens labels; live data makes unlabeled “real” claims worse if honesty regresses |

### Re-verification blast radius (from existing records)

From `phase_d_delivery.md` / `phase_f_delivery.md` / `review_guide.md`:

- Jobs list loads; disclaimer visible; Apply opens `redirect_url`
- Target a listing; target context stores `job_id`
- Practice from a job
- Sample-data labeling (F: STILL BLOCKED — must be closed or redesigned before claiming live honesty)
- Second-account isolation (targets/jobs practice ownership)
- Home “identifies sample listings” copy vs actual banner behavior

### Product claims / framing

Contract: fit is **not** an employer ATS score or hiring probability. Today `match_pct` is a lexicon overlap. Real listings with richer descriptions could inflate perceived authority of the same number. Harder to hold if UI grows “fit score” chrome next to live employer brands — keep naming as skill-overlap / practice hint, never hiring odds.

### Saved target when listing vanishes

`target_contexts.job_id` becomes dangling. Need: soft failure on `get_job`, preserve `role_id` / company target, clear or flag `job_id`, no fabricated replacement listing.

### Evidence / measurement

**Unaffected** if the boundary holds: listings must not write attempts, readiness, mastery, or notebook rows. Confirm in any future PR by grepping scoring/learning paths for `job_id` / `jobs_cache`.

### Test surface

| Existing pin | Breakage |
|--------------|----------|
| `tests/test_jobs_explorer.py` fixture load / cache / practice | Must keep fixture path for offline CI |
| `test_phaseD_learning.py` targets `load_fixture_jobs()[0]["id"]` | Breaks if fixture removed |
| `jobsMapping.test.js` Apply href | Still valid |
| New needed | Unavailable labeled (not empty-as-match); stale/missing listing on target; optional live client mocked; cache no longer clears `empty_reason` incorrectly |

---

## Step 3 — data and obligations (stated, not decided)

Based on current schema and what external sources typically return:

**May appear in a listing:** job title, company name, location, salary range, description text (may include recruiter emails/phones), apply URL, timestamps, provider id.

**Storage today / proposed:** process memory + SQL `jobs_cache` / `jobs_search_cache`; target holds `job_id` and optional `jd_text` (user-pasted). Ownership: search is user-authenticated but cache is **global** per process/DB today — a live design must decide whether cached listings are shared catalog vs per-user (shared catalog is normal; must not leak other users’ searches into personal evidence).

**Retention / deletion needed for live:** TTL on detail cache; purge stale search pages; user delete of target must not require deleting global cache; document that Apply leaves the product via `redirect_url`.

**Leave the machine:** live search already would (HTTP to provider). Stored copies need a policy: stay local vs re-fetch only. Playback of listings is display only.

**Narrowest offline-constraint amendment (engineering wording, not a recommendation to adopt):**

> Allow outbound HTTPS solely from the Jobs source client to a single configured job-search host, only when explicitly enabled by environment flag, with credentials present; default remains offline fixture/cache with labeled sample or unavailable states. No other features gain network.

**Terms of service and data-protection / DPDP / employment-data questions are the owner’s to resolve and are outside this assessment.**

---

## Step 4 — options and recommendation

| Option | Engineering cost | Honesty posture | Demands from owner |
|--------|------------------|-----------------|-------------------|
| **A. Keep sample fixture, labeled** | None (fix cache/`empty_reason` bug optional) | Matches offline contract; labels already intended | Accept 3 demo listings; no ToS/network change |
| **B. One-time authorized import → static local dataset** | Low–medium: replace/extend JSON; keep explorer offline | Remains offline; must label “imported snapshot as of DATE”, not live market | Owner obtains data under their rights; import **outside** the app; no runtime vendor client |
| **C. Live adapter behind feature flag, unavailable by default** | Medium–high: client seam, TTL on detail, unavailable UI, migration fields, re-verify D journeys | Strong if unavailable≠empty and live vs sample never confused; weak if cache clears labels | Amend offline rule; ToS; credentials; retention decision |
| **D. Remove Jobs market UI; keep target company/role only** | Medium (product cut) | Avoids market-data honesty entirely | Accept Jobs as non-goal |

### Recommendation

**Recommend A in the near term, with B as the only expansion that stays offline.**
Reasoning: the chain’s Jobs path already treats Adzuna as optional and fixture as the offline truth; Phase F never closed sample labeling; gap/roadmap do not need live listings; C pulls ToS, network, retention, and re-verification into a product that still has C.2/E.2 blocked. Fixing the `source: cache` / `empty_reason` wipe is a small honesty repair under A, not a live integration.

**Strongest argument against A:** if the owner’s real goal is market-facing practice (“jobs like the ones I’m applying to”), three fixtures will never satisfy; delaying C only accumulates product debt. In that case B (dated static import) is the next step that does not yet open a live socket.

---

## Process attestation

| Check | Result |
|-------|--------|
| External job service contacted | **No** |
| Dependency / client / Jobs source edit | **No** |
| Phase M ports disturbed | **No** (no server start) |
| phase21 worktree / `refs/rescue/*` | Untouched / still reachable |
| Product source changed | **Docs only** |
| Migration | Not required |

Notable contrast for the open fail-fast debate: Phase M Step 0 found transcription **fails loudly** (503) when the whisper cache is cold under `HF_HUB_OFFLINE=1`, whereas SemanticScorer **sticky-degrades**. Jobs’ fixture-on-missing-credentials is a third pattern (demo substitute). A live Jobs client should follow transcription/coding — **unavailable labeled** — not silent fixture substitution presented as market truth.

---

## Phase O — honesty defects closed (2026-09-07)

Assessment-only Phase N; fixes landed in Phase O (`docs/phase_o_delivery.md`). Sourcing decision (Step 4) remains **owner-open**; no JobSourceClient, no real listings, fixture bytes unchanged.

| Defect | How closed |
|--------|------------|
| **1. Ungated Adzuna outbound** when credentials present | `JOBS_LIVE_FETCH` defaults to `0` via `backend/runtime_env.py` (Phase J pattern). `fetch_adzuna` retains the `httpx` path but does not enter it unless the gate is on. Test: `test_default_jobs_live_fetch_skips_httpx`. Documented in `.env.example` / `docker-compose.yml` / Phase J delivery cross-note. |
| **2. Cache hit clears sample banner** (`source: cache` wiped `empty_reason`) | Provenance stamped onto cached records; `source` / `provenance` stay `fixture` (etc.) on warm path; `cache_hit` is a separate axis; `fetched_at` survives round-trip; sample banner keys off provenance. Test: `test_cache_hit_preserves_fixture_provenance_and_label`. |

**Still open (not Phase O):** `match_pct` framing beside real company names; live JobSourceClient / Step 4 sourcing choice.

## Phase Z attribution update

Jobs sample labeling was not freshly exercised before the Z-F00 stop (Z #41). The Phase O provenance fix and historical verification remain separately attributed; this assessment is not evidence of a current cache-label failure. See [Phase Z](phase_z_browser_verification.md).
