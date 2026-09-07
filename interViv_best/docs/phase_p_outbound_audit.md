# Phase P — LLM path audit and outbound sweep

**Read-mostly investigation.** Branch tip before this commit: `43ac864` (Phase O).  
**Chain root:** `0442493` (A). **Alembic head:** `20260907_0008` (unchanged).  
**Phase M ports:** not started / not disturbed (no servers required).

No LLM judge was found in scoring, readiness, guard, gap analysis, or mastery.  
One **live** default outbound (Google Fonts CDN) was gated off in this phase.  
LLM chat paths remain **latent** (credential-gated); recommendations below, not redesigned here.

---

## Step 0 — each LLM call path

Shared URL helper: `modules/question_bank._chat_completion_url` →  
`https://openrouter.ai/api/v1/chat/completions` or `https://api.openai.com/v1/chat/completions`.

Credentials (all paths): `QUESTION_LLM_PROVIDER` (`auto`/`openai`/`openrouter`),  
`OPENAI_API_KEY` / `OPENROUTER_API_KEY`, optional model overrides.  
**This environment:** no `.env`; keys **unset**. `.env.example` has empty placeholders.  
Code default when `QUESTION_GENERATION_MODE` unset: **`llm`** (disposable recipe usually forces `csv`).

### Path A — `modules/question_runtime.call_llm_with_cache_retry`

| Item | Detail |
|------|--------|
| Call site | `question_runtime.py` ≈L353–426; `urllib.request.urlopen` ≈L398 |
| Entry | `generate_question` when mode ∈ `{llm, llm_csv_fallback}`; also adaptive `_call_llm` |
| Sent | Chat JSON: `model`, `messages[{role,content}]`, `max_tokens`, `temperature`. Prompt may include company/role, **resume skill list**, weak/target concepts, difficulty, last ≤8 **question stems**. **No** candidate answer, transcript, or full JD |
| Response | Parsed to `question` / `ideal_answer` / `ideal_keywords` → session `question_context` → deterministic `pipeline` / guard as **references** → scores → mastery/readiness |
| Failure | Soft `None` + CSV/template fallback (SemanticScorer-like). `QUESTION_REQUIRE_LLM` **not** enforced on this path |
| Product | **Reachable** for Interview short-answer when mode is llm* and keys present |
| Default config | **LATENT** — empty keys abort before `urlopen`; with `csv` mode, `generate_question` never enters LLM branch |

### Path A′ — adaptive targeting (`adaptive_question_selector`)

| Item | Detail |
|------|--------|
| Call site | `_call_llm` → same `call_llm_with_cache_retry` (not a fourth HTTP client) |
| Gate hole | Attempts targeted LLM when `target_concepts` non-empty **without checking** `QUESTION_GENERATION_MODE` |
| Default config | Still **LATENT** without keys (returns `None` before dial). With keys + csv mode, would be **LIVE** — deferred finding |
| Failure | Silent → falls through to `generate_question` |

### Path B — `modules/question_bank._generate_via_llm`

| Item | Detail |
|------|--------|
| Call site | `question_bank.py` ≈L324–390; `urlopen` ≈L355 |
| Caller | Only `get_next_question` ≈L898 |
| Product | **Dead for today’s session product** — `session._get_next_question` uses adaptive / `generate_question`, not `get_next_question` |
| Sent | skill / sub_domain / difficulty / asked stems — no answer/resume/JD |
| Failure | Soft `None`; if `QUESTION_REQUIRE_LLM` and mode llm → `RuntimeError` (only fail-loud LLM path) |
| Default config | **LATENT** / unused |

### Path C — `modules/guidance_coach._llm_extract_phrases`

| Item | Detail |
|------|--------|
| Call site | `guidance_coach.py` ≈L87–136; `urlopen` ≈L126 |
| Entry | `build_coach_plan` → `POST /coach/plan` |
| Sent | Up to 4000 chars of sanitized **jd_text / goal_text** inside `USER_TEXT`; asks for `{"skills":[...]}` only. **No** interview answer / transcript / score request |
| Response | Phrases → lexicon map → plan links / practice preview. Unmapped phrases never enter practice |
| Failure | Bare `except` → `None` → lexicon-only (`mode=fallback`). Silent |
| Product | **Reachable** (`/coach`) |
| Default config | **LATENT** — empty keys |

---

## Step 1 — contract classification

**No VIOLATION found.** Audit continues.

| Path | Class | Trace |
|------|-------|-------|
| A / A′ question + `ideal_*` | **ADJACENT** | LLM authors question text and scoring *references*. Guard / pipeline / readiness / mastery / gap algorithms remain deterministic. LLM does not return a score, band, or pass/fail |
| B legacy bank LLM | **ADJACENT** if revived; **CLEAR of product** while dead | Same shape as A |
| C coach phrases | **CLEAR** for scoring boundary | Output is UI plan / skill chips only; does not write scores, readiness, guard, gap, or mastery |

Gap / readiness / mastery code paths consume **deterministic scores** that may have used LLM-authored references when questions were LLM-sourced — that is the ADJACENT boundary the contract allows for generation, not judging.

### Protected banks — LLM persistence?

**Runtime banks are read-only.** No `save_question` / write-back from LLM modules into CSV or bank modules.

| Artifact | vs Phase A `0442493` |
|----------|----------------------|
| `data/fallback_question_bank.csv` | **Identical** MD5 |
| `data/interview_dataset_v6.csv` | **Identical** MD5 |
| `backend/db/phase2_content_bank.py` (MCQ/SQL) | **Identical** MD5 |
| `modules/question_bank.py` | **Identical** MD5 |
| `backend/db/phase21_verbal_bank.py` | Added Phase B (`1601e91`) — in-module constants, not LLM-written |
| `backend/db/phase_c_coding_bank.py` | Added Phase C (`98d3813`) — same |

**Conclusion:** no evidence that LLM-generated content has been persisted into the protected technical / SQL / Verbal / coding banks.

---

## Step 2 — complete outbound table

**Default = disposable offline (post–Phase Q):** no API keys/DSNs, `HF_HUB_OFFLINE=1`, `JOBS_LIVE_FETCH=0`, `LLM_LIVE_FETCH=0` (via `runtime_env`).

| # | Site | Contacts | Gate | Default | Verdict |
|---|------|----------|------|---------|---------|
| 1 | `jobs_explorer.fetch_adzuna` `httpx` | `api.adzuna.com` | `JOBS_LIVE_FETCH` + Adzuna keys | No | **Latent** (Phase O) |
| 2 | `question_runtime.call_llm_with_cache_retry` | OpenAI / OpenRouter chat | **`LLM_LIVE_FETCH` + mode ∈ {llm, llm_csv_fallback}** + keys | No | **Latent** (Phase Q gate) |
| 3 | `adaptive_question_selector._call_llm` | Same as #2 (shared client) | Same boundary as #2 | No | **Latent**; mode hole **closed** in Q |
| 4 | `question_bank._generate_via_llm` | Same | Same generation outbound gate + keys | No | **Latent / dead** |
| 5 | `guidance_coach._llm_extract_phrases` | Same | **`LLM_LIVE_FETCH`** + keys (mode N/A) | No | **Latent** (Phase Q) |
| 6 | `backend/observability` Sentry | DSN host | `SENTRY_DSN` | No | **Latent** |
| 7 | `frontend/src/lib/sentry.js` | DSN envelope | `VITE_SENTRY_DSN` | No | **Latent** |
| 8 | `frontend/src/index.css` Google Fonts | — | Removed from default CSS | No | **Gated in P** |
| 9 | `semantic_scorer` / warmup MiniLM | HF Hub on cache miss | `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE` | No successful outbound | **Latent** (Phase J) |
| 10 | `transcribe` Whisper `tiny.en` | HF Hub on cache miss | Same offline env; cold → **503** | No successful outbound | **Latent**; fail-loud if cold |
| 11 | `frontend` `api.js` `fetch` | `VITE_API_BASE_URL` / `/api` | Always | Loopback only | **Live local** |
| 12 | Vite proxy / Redis / Postgres | Local compose hosts | URLs set | Local if used | **Live/latent local** |
| 13 | `face-api` `/models` | Same-origin static | Interview path | Local assets | **Live local** |
| 14 | Jobs Apply / Learn resource `<a href>` | External URLs in data | User click | Only if clicked | **User-initiated** |
| 15 | `aiohttp` / `requests` / curl subprocess | — | — | — | **Absent** |
| 16 | Normal `pytest` / `npm test` | External hosts | Mocks / offline env | No intentional | **Suite-safe** |

---

## Step 3 — fixes and deferrals

### Gated in Phase P (live + contained)

| Item | Action |
|------|--------|
| Google Fonts CDN | Removed active `@import` from `index.css`. Opt-in URL retained as comment in `fonts.css`. Theme stacks keep branded names with system fallbacks. Test: `frontend/tests/offlineFonts.test.js`. Documented in `.env.example` |

### Closed in Phase Q (gating gaps)

| Item | How closed |
|------|------------|
| Adaptive path ignored `QUESTION_GENERATION_MODE` | Mode + `LLM_LIVE_FETCH` enforced in `call_llm_with_cache_retry` (shared client). Adaptive `_call_llm` cannot route around it. Same generation gate on `_generate_via_llm`. |
| No `runtime_env` LLM default | `LLM_LIVE_FETCH=0` via `backend/runtime_env.py` (Phase J/O pattern). Holds even when API keys are set. Coach uses `LLM_LIVE_FETCH` only. Tests: `tests/test_phaseQ_llm_gate.py`. |

**Failure mode (observed, not changed):** when the gate is off, behavior matches today’s no-credentials path — soft `None` / CSV–lexicon fallback (SemanticScorer-like silent degrade). When the gate is on and the provider call fails, the same soft-fallback pattern remains; fail-loud vs labeled-unavailable for LLM is a separate decision.

### Still deferred (owner / sourcing)

| Finding | Recommendation |
|---------|----------------|
| Phase O: if `JOBS_LIVE_FETCH=1` and fetch fails → silent fixture fallback | Wrong vs fail-loud / labeled-unavailable; fix with sourcing decision |
| Phase O: sample `empty_reason` names `JOBS_LIVE_FETCH` | Violates no-raw-API-labels spirit; reword when Jobs copy is owned |
| Path B dead `get_next_question` LLM | Leave or delete later |
| Fail-fast vs sticky SemanticScorer | Still open (Phase J/F) |

### Not fixed (by instruction)

- No VIOLATION existed to escalate.
- No JobSourceClient / scoring formula changes. Phase Q inserted a minimal outbound gate into protected `question_bank._generate_via_llm` only.

---

## Test pins

| Pin | Why |
|-----|-----|
| `frontend/tests/offlineFonts.test.js` (Phase P) | Assert default CSS does not load Google Fonts |
| `tests/test_phaseQ_llm_gate.py` (Phase Q, new) | Default / keys+csv / adaptive / coach / bank: no urlopen; gate-on without keys unchanged |
| `tests/test_task8_hardening.py` / `test_adaptive_selector.py` | Set `LLM_LIVE_FETCH=1` so stubbed live-client tests still reach the boundary |

No scoring / Jobs labeling / fonts / AV pins otherwise changed.

---

## Process attestation

| Check | Result |
|-------|--------|
| Real LLM / Adzuna / Hub call made | **No** |
| Phase M ports disturbed | **No** |
| Protected banks / scoring pipeline edited | **No** |
| Migration | Not required |
| `refs/rescue/*` | Untouched; still reachable |
