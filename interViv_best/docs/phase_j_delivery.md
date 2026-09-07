# Phase J — SemanticScorer Hub-offline environment

**Base:** `e8addaf` (Phase I)  
**Scope:** investigation + local runtime configuration + docs/tests.  
**Not changed:** scorer, guard, formulas, sticky fallback logic, protected modules.

## Step 0 findings

### (a) Cache state

| Item | Value |
|------|--------|
| Path | `/Users/praneetsharma/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2` |
| Size | **87M** (`du -sh`) |
| `refs/main` | `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` |
| Weights blob | `blobs/53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db` (**87M** `model.safetensors`) |
| Incomplete files | **none** |
| How it got there | Hugging Face Hub cache layout (`CACHEDIR.TAG` by `huggingface_hub`); snapshots dated Mar–Jul 2026; two revisions present (`c9745ed1…`, `1110a243…`) sharing the same weights blob |

This is a complete cached checkpoint, not a partial download.

### (b) What triggers the fetch

Path: `modules.semantic_scorer._get_model()` → `SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")` → `huggingface_hub` file resolution (`hf_hub_download` / snapshot resolve).

Without offline mode, the library issues **HTTP HEAD** requests to Hub resolve URLs such as:

- `https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/./modules.json`
- `…/resolve/main/adapter_config.json`

That is a **metadata / file-presence check** (revision resolve), not a full weight re-download when blobs are already cached — but it still opens **TCP to `huggingface.co:443`**. A 403 on that path triggers the sticky lexical fallback.

### (c) What `HF_HUB_OFFLINE=1` does

`huggingface_hub.constants.HF_HUB_OFFLINE` is set from env at **import time**. `get_session` registers an httpx hook that raises `OfflineModeIsEnabled` **before** network I/O.

| Probe | Result |
|-------|--------|
| TCP wrap on `socket.create_connection`, offline + warm | **`tcp_count=0`**, model loads, encode works |
| Same wrap, online + warm | **`tcp_count=8`** to `huggingface.co:443` (blocked in probe) |
| HTTP session recording, offline + warm | Code still *intends* a Hub HEAD; offline hook blocks it pre-socket |

**Confidence: high** for “no outbound TCP.” The request is suppressed at the Hub HTTP layer, not merely failed after connect.

### (d) Cold cache (`HF_HOME` = empty temp dir)

With `HF_HUB_OFFLINE=1` and empty disposable `HF_HOME`:

- `SentenceTransformer(...)` raises **`OSError`** (cannot connect; files not in cache).
- **`tcp_count=0`** (still no outbound).
- Application `_get_model()` **catches** that and sticky-degrades to lexical fallback (pre-existing behaviour).

So: load fails loudly at the library; the **app** still labeled-degrades. The env fix is safe for **warm** installs; it does **not** make a fresh install full-scorer without weights.

### (e) Reproducibility

Three fresh processes, `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1`:

| Run | Result | Failures |
|-----|--------|----------|
| 1 | **2/8** | gibberish 6.06 / repetition; keyword_stuffing 10.00 / gibberish |
| 2 | **2/8** | identical |
| 3 | **2/8** | identical |

`identical_across_3 True`. Always-present pair confirmed.

### (f) Other outbound paths (normal local operation)

Hub MiniLM fetch is the scorer-specific violation this phase targets. Remaining optional outbound (only when configured):

| Path | When |
|------|------|
| OpenAI / OpenRouter (`question_bank`, `question_runtime`, `guidance_coach`) | API keys set + LLM question/coach modes |
| Adzuna (`jobs_explorer`) | `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` set |
| Sentry | `SENTRY_DSN` set |

With keys blank (Phase A–I disposable recipe), startup warm-up + scoring + a non-LLM session do not need those. They are **not** closed by `HF_HUB_OFFLINE`.

## Decision: apply the env fix

Evidence supports applying **`HF_HUB_OFFLINE=1`** (plus `TRANSFORMERS_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`) as the **recommended local operating configuration** when the MiniLM cache is present:

- Prevents Hub TCP during SemanticScorer load.
- Makes full-mode `scoring_regression` (2/8) reproducible across processes.
- Does not change scorer/guard code.

Applied via:

- `backend/runtime_env.py` — `setdefault` after loading `.env` (no shell profile required).
- Called first from `backend/main.py` and `scripts/scoring_regression.py`.
- Documented in `.env.example` and `docker-compose.yml` backend env.
- Test `tests/test_phaseJ_offline_scoring.py` (skips if cache absent).

Phase O extends the same `runtime_env` pattern for Jobs: `JOBS_LIVE_FETCH` defaults to `0` so Adzuna `httpx` cannot fire unless deliberately enabled (see `docs/phase_o_delivery.md`).

## What this closes / leaves open

| Topic | Status |
|-------|--------|
| Hub outbound during SemanticScorer warm-up on a **warm** machine | **Resolved** for the recommended config |
| Fail-fast vs labeled-degraded at startup | **Still open** (Phase F product decision) |
| Mode-on-attempt (G.0/G.0b) | **Still the durable safeguard** if a deploy runs degraded |
| Fresh install **without** cached MiniLM | Load fails → sticky lexical degrade; not full scorer; operator must cache weights or accept degraded / choose fail-fast later |

An environment default on this machine is **not** an architectural guarantee for every deploy. Reviewers should treat warm-cache + offline env as the local operating contract, not as “SemanticScorer can never degrade.”
