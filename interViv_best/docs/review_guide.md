# Review guide — phases B through G

**Audience:** reviewers of `codex/phase-b-block-practice`  
**Base:** Phase A tip `0442493`  
**Tip at G.1:** `65a456e` (before Phase H docs)  
**This file ships in Phase H.1.** No history rewrite; describe only.

**First paragraph (read this before the tables):** Coding “execution” is a **503 seam with nothing behind it**. `POST /session/coding/run` and scored coding submits return infrastructure-unavailable; the editor stays open; Progress treats coding as unscored coverage, not a zero. C.2 (Docker/live runner) was never started. Do not review this branch as if candidates can receive coding scores today.

---

## (a) Commit inventory

There are **13** commits on `0442493..65a456e` (B→G.1). The brief said fourteen; the linear log has thirteen.

| SHA | Role | What / why | Scale | Independently reviewable? |
|-----|------|------------|-------|---------------------------|
| `1601e91` | **B** feat | Block contract; Verbal/OA/SQL/Interview practice; presets/drafts; Verbal bank file | ~17 files, +4.2k | Needs B.1 for SQLAlchemy truth |
| `39a7579` | **B.1** fix | Persist block plans, presets, drafts, answer drafts on SQLAlchemy; rewrite answer route for submit lock | ~6 files, +1.7k | **Land with B** |
| `98d3813` | **C.1** feat | Coding bank, Problems UI, execution boundary (503), scoring formula, migration 0005 | ~33 files, +3.9k | After B.1 |
| `670f5ea` | **D Step 0** docs | Adds/corrects Phase C delivery evidence notes | 1 file docs | **Skim** (docs) |
| `daa18b4` | **D** feat | Target context, learning hub (notebook, retry, assistance), migration 0006 | ~33 files, +4.2k | After C |
| `4303577` | **E.0** docs | Correct scoring_regression claim to **2/8** full | 1 file docs | **Skim** (docs) |
| `a47944a` | **E.1** feat | System-design self-assessment; AV capability honesty; migration 0007; `modules/scoring/system_design.py` (new) | ~23 files, +2.0k | After D |
| `7002fa2` | **F.0** fix | Self-assessment ≠ measured mastery; `/health` scoring.mode; real-route leakage fixtures | ~8 files | **Land with F.1** |
| `f71aae4` | **F.1** docs+fix | Browser verification doc; DSA-as-topic coding start; System design builder label + standalone form | 3 files | **Land with F.0** |
| `dd13aab` | **G.0** fix | Persist/disclose scoring mode; F-phase tests; `parent_revision()` alembic helper | ~15 files | **Land with G.0b/G.0c/G.1** |
| `736b36f` | **G.0b** fix | Embed `scoring_mode` in `scoring_breakdown` JSON (SQLAlchemy drops unknown columns) | 4 files | With G.0 |
| `383d8ba` | **G.0c** fix | Dashboard tolerates string feedback (SD reports 500ed) | 2 files | With G.0 |
| `65a456e` | **G.1** docs | Phase G verification / backlog / review topology notes | 1 file docs | **Skim** after reading F/G.0 |

Pure documentation / skim-first: `670f5ea`, `4303577`, `65a456e` (and F.1/G.1 delivery prose after reading the fix commits).

Phase H adds `594f3d9` (H.0 rescue doc) and this guide (H.1) — documentation only; not part of the B–G product chain above.

**Phase I** (`feat` after H.1): spaced-review scheduling over notebook misses — ladder `(1,3,7,16,35)`, due surface on Learn, reviews reuse the block engine and **do not** move measured mastery. Delivery: `docs/phase_i_delivery.md`. Migration head becomes `20260907_0008`.

**Phase J** (`ops/docs` after I): Hub-offline runtime defaults so a warm MiniLM cache loads full SemanticScorer without Hub TCP. Delivery: `docs/phase_j_delivery.md`. No migration.

**Phase K** (docs only): read-only assessment of rescued phase21 Verbal UI blobs vs the chain at `dac9c3c`. No integration. See `docs/phase_k_verbal_assessment.md`.

---

## (b) Risk order (highest first)

Spend the **first hour** here:

1. **`39a7579` (B.1)** — SQLAlchemy persistence + answer submit/finalizing lock. Wrong here corrupts sessions or double-scores.
2. **`736b36f` + `dd13aab` (G.0/G.0b)** — scoring-mode plumbing on every scored attempt; evidence honesty for degraded SemanticScorer.
3. **`7002fa2` (F.0)** — self-assessment segregation from mastery/readiness/notebook; touches learning aggregates.
4. **`98d3813` (C.1)** — coding bank + 503 boundary + formula; confirm no fake scores on infra failure.
5. **`daa18b4` (D)** — target context + assistance events; ownership boundaries.
6. **`a47944a` (E.1)** — system-design self-report path; AV “unavailable” honesty (no speech scores).
7. **`1601e91` (B)** — large UI/contract surface; review after B.1 semantics are clear.
8. **`f71aae4` / `383d8ba` / docs** — honesty fixes and verification records.

Protected scorer/guard modules were **not** edited on this chain (see §c). Persistence and submit-lock outrank chrome.

---

## (c) Protected-file attestation

Command (empty means unchanged):

```text
$ git diff --stat 0442493..65a456e -- \
  interViv_best/backend/scoring/pipeline.py \
  interViv_best/modules/nlp_scorer.py \
  interViv_best/modules/nlp_scorer_patch.py \
  interViv_best/modules/answer_guard.py \
  interViv_best/modules/semantic_scorer.py \
  interViv_best/modules/knowledge_graph.py \
  interViv_best/modules/ner_scorer.py \
  interViv_best/modules/c4_feedback.py \
  interViv_best/modules/question_bank.py \
  interViv_best/modules/model_metadata.json

(no output)
```

**Banks:**

- `modules/question_bank.py` — unchanged vs A (technical/SQL interview bank).
- `backend/db/phase21_verbal_bank.py` — **added** in B (`1601e91`); MD5 `05e73d867b75648291d538c476c6dca0` matches phase21 `fe75a32`.
- `backend/db/phase_c_coding_bank.py` — **added** in C (`98d3813`).

**Authorized new module (not in the frozen “existing modules” list):** `modules/scoring/system_design.py` in E.1 — deterministic self-assessment mapping only; no LLM judge.

---

## (d) Migration story

| Revision | Adds |
|----------|------|
| `20260907_0004` | Session block/round plan JSON columns; `practice_presets`, `builder_drafts`, `answer_drafts`; round block metadata |
| `20260907_0005` | `coding_submissions` table |
| `20260907_0006` | Round `assisted` / `assistance_kinds`; `target_contexts`, `retry_sets`, `bookmarks`, `assistance_events` |
| `20260907_0007` | `system_design_attempts` table |
| `20260907_0008` | `review_schedules` (Phase I spaced review) |

Chain: `0003 → 0004 → 0005 → 0006 → 0007 → 0008`.
`alembic heads` → **single head** `20260907_0008`.
No historical migration files were edited after introduction; only new revisions appended.

**`parent_revision()` (G.0):** persistence tests previously pinned absolute parents (e.g. E.1 pinned D downgrade to `0005`) because Alembic relative `-1` breaks when HEAD advances. `tests/alembic_helpers.py` resolves the current head’s parent dynamically so each phase does not need a pin update.

---

## (e) Environment-dependent scoring (fresh reader)

SemanticScorer loads **`all-MiniLM-L6-v2` in-process** from the Hugging Face Hub
cache under `~/.cache/huggingface/hub/…`.

**Phase J finding (see `docs/phase_j_delivery.md`):** on this machine the
checkpoint is already cached (~87M `model.safetensors`). Without offline env,
`SentenceTransformer(...)` still opens **TCP to `huggingface.co:443`** for
Hub **HEAD** / resolve checks (metadata, not necessarily a weight re-download).
A **403** on that path flips the process into sticky lexical fallback and
changes **both guard labels and numeric scores**.

With **`HF_HUB_OFFLINE=1`** (and typically `TRANSFORMERS_OFFLINE=1`),
`huggingface_hub` raises `OfflineModeIsEnabled` **before** socket connect.
Warm cache → full scorer; **no Hub TCP**. Cold / empty `HF_HOME` → library
`OSError`, then the app’s existing sticky degrade (fail-fast still not built).

| Mode | How | `scoring_regression` |
|------|-----|----------------------|
| full | cached MiniLM + Hub offline env (`backend.runtime_env` / `.env.example`) | **2/8** — always-present: gibberish→repetition (6.06); keyword_stuffing→gibberish (10.00) |
| degraded | `DISABLE_SEMANTIC_SCORING=1` (same sticky pattern as Hub-403 / cold-cache miss) | **4/8** — above + paraphrase out of band + off_topic guard None |

F.0 exposed mode on `/health`. G.0/G.0b **record `scoring_mode` on each scored attempt** (inside `scoring_breakdown` JSON) and surface it; rows without a stored mode read as **`unknown`** (never guessed). **Fail-fast at startup was deliberately not built** — product decision (abort vs labeled degrade) **remains open**.

**Phase J** makes Hub-offline the **recommended local operating configuration**
so warm machines stay in full mode without an outbound Hub request. That does
**not** retire fail-fast, and a fresh install without the cached model still
labeled-degrades. Mode-on-attempt remains the durable record if a worker runs
degraded anyway.

Other optional outbound (LLM keys, Adzuna, Sentry) is unchanged and unrelated
to MiniLM.
---

## (f) Honest capability inventory

**Works today (with disposable DB + local servers):** auth/home/progress; block practice (Verbal/OA/SQL/Interview); builder presets/drafts; Problems browse + start; learning notebook/retry/assistance labeling; **spaced-review due list + review sessions (practice only)**; target context prefill on Practice/Learn; system-design **self-assessment** (explicitly not measured mastery); scoring-mode disclosure on new attempts; AV capability **reporting** and unavailable-state wiring.

**Shipped but unavailable:** **coding execution and coding scores** (503 / unscored). Video recording / durable AV blobs / speech scoring (E.2 not started). Whisper transcription may be importable while device capture stays client-only.

**Never built on this chain:** C.2 live runner; E.2 ffmpeg/blob retention; phase21 **Upload Verbal Ability entry** (rescued blobs only — see `docs/phase_h0_rescue.md`); LLM judge in scoring/readiness/guard/gaps (forbidden).

---

## (g) Outstanding items

| Item | Status | Blocker / owner decision |
|------|--------|--------------------------|
| 409 message visible in UI | PARTIAL | Client gate hides second submit; need race or post-submit retry UX proof |
| Target does not override explicit topic | PARTIAL | Prefill+copy seen; override scenario not walked |
| Builder coding start in browser | PARTIAL | API/test covered; builder UI start not filmed in G |
| AV seven states in live UI | PARTIAL / BLOCKED | Permission overrides / hardware |
| Real mic/camera | STILL BLOCKED | Hardware |
| C.2 Docker execution | Not started | **Owner:** pursue Docker or keep 503 seam? |
| E.2 AV artifacts | Not started | Out of scope until authorized |
| phase21 Verbal Upload entry | Not integrated | **Owner:** see `docs/phase_k_verbal_assessment.md` (selective gate recommended; no drop-in) |
| Fail-fast vs labeled-degraded | Product | **Still open.** Phase J: Hub-offline env fixes warm-cache outbound; cold cache still sticky-degrades. Owner: abort on missing model vs continue with mode label? |
| Home target picker vs `/target-context/me` | Known gap | Prefill inconsistency |

---

## (h) Reproduction instructions

### Disposable environment

```bash
cd "/Users/praneetsharma/Downloads/mega 2 copy/.worktrees/phase-b-block-practice/interViv_best"
rm -f /tmp/interviv_phaseg_disposable.db
DATABASE_URL='sqlite:////tmp/interviv_phaseg_disposable.db' .venv/bin/alembic upgrade head

DATABASE_URL='sqlite:////tmp/interviv_phaseg_disposable.db' \
INTERVIV_USE_MEMORY_DB=false \
JWT_SECRET_KEY='phase-g-disposable-secret-key-32b!!' \
OPENAI_API_KEY= OPENROUTER_API_KEY= HF_HUB_OFFLINE=1 \
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# other terminal
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

Signup: `phaseg.user1@example.local` / `PhaseG123` (or fresh accounts via UI). **Never** point at the developer’s personal database.

Confirm mode: `curl -s http://127.0.0.1:8000/health` → `scoring.mode` `full` | `lexical_fallback_degraded`.

### Seed (real sessions only)

Drive OA (intentional misses), Verbal, system-design self-assessment, coding starts, and at least one `/learning/hint` before a miss through UI or authenticated API. Do not INSERT attempt rows.

### Suites (mode recorded)

```bash
# Backend / frontend / build
.venv/bin/python -m pytest tests/ -q
cd frontend && npm test && npm run build

# Scoring — always record which mode
HF_HUB_OFFLINE=1 .venv/bin/python scripts/scoring_regression.py          # expect 2/8 full
DISABLE_SEMANTIC_SCORING=1 HF_HUB_OFFLINE=1 .venv/bin/python scripts/scoring_regression.py  # expect 4/8

.venv/bin/alembic heads   # 20260907_0007
# After pytest: restore docs/human_baseline_report.md
# MD5 5421f9f0fd6efad395666c545e5cf76a, 230 lines
git checkout -- docs/human_baseline_report.md
```

### Browser checks worth redoing

Learn notebook + assisted labels; Progress System Design **Not measured** after SD self-assessment; Practice builder “System design”; standalone SD E2E; coding standalone + Problems Practice; **double-click Submit Round** on OA (expect one completion, not necessarily a 409 toast).

### Rescue refs (do not merge)

```bash
git show-ref | grep refs/rescue/
# docs: interViv_best/docs/phase_h0_rescue.md
```

---

## Related delivery docs

`phase_a_delivery.md` … `phase_g_delivery.md`, `phase_h0_rescue.md`, `phase_i_delivery.md`, `phase_j_delivery.md`, `phase_k_verbal_assessment.md`. Prefer this guide for onboarding; use per-phase docs for detailed evidence tables (note Phase H downgrades in F/G where VERIFIED had been overstated).
