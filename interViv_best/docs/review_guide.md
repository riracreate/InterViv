# Review guide — chain A through Q

**Audience:** reviewers of `codex/phase-b-block-practice`  
**Base (chain root):** Phase A tip `0442493`  
**Tip at this guide refresh (Phase R):** `c58e106` (Phase Q)  
**This file:** introduced in Phase H.1 (`9e91e08`); **refreshed in Phase R** (docs only). No history rewrite; describe only.

**First paragraph (read this before the tables):** Coding “execution” is a **503 seam with nothing behind it**. `POST /session/coding/run` and scored coding submits return infrastructure-unavailable; the editor stays open; Progress treats coding as unscored coverage, not a zero. C.2 (Docker/live runner) was never started. Do not review this branch as if candidates can receive coding scores today.

---

## (a) Commit inventory

### B → G.1 (`0442493..65a456e`) — 13 commits

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

### H → Q (`65a456e..c58e106`) — 10 commits

| SHA | Role | What / why | Independently reviewable? |
|-----|------|------------|---------------------------|
| `594f3d9` | **H.0** docs | Rescue record for at-risk phase21 dangling objects | **Skim** |
| `9e91e08` | **H.1** docs | This review guide (initial); correct overstated verification | **Skim** (superseded in part by Phase R refresh) |
| `e8addaf` | **I** feat | Spaced-review schedule over notebook misses; migration `20260907_0008` | After G; practice-only, no mastery move |
| `dac9c3c` | **J** ops | `HF_HUB_OFFLINE` (etc.) via `runtime_env`; Hub TCP gated on warm MiniLM | Mechanical; pair with §e / §e2 |
| `29a8998` | **K** docs | Rescued phase21 Verbal UI vs chain — assessment only | **Skim** |
| `8466c48` | **L** fix | Gate Interview media by `block_category` (Verbal/OA skip) | After K; SSR pin `interviewMediaGate.test.js` |
| `0d5fd54` | **N** docs | Real job-data engineering assessment (no integration) | **Skim** |
| `43ac864` | **O** fix | `JOBS_LIVE_FETCH=0`; fixture provenance survives cache | Mechanical Jobs honesty |
| `bb5702a` | **P** docs+fix | Outbound/LLM audit; Google Fonts CDN removed from default CSS | Audit + narrow CSS gate |
| `c58e106` | **Q** fix | `LLM_LIVE_FETCH=0`; mode enforced at shared LLM client; adaptive cannot bypass | Mechanical gating |

**No Phase M commit** is on this chain. Phase M work was attempted in session (whisper Step 0 offline; disposable servers on `:18000`/`:5173`) and left **incomplete** awaiting owner browser permission — see §f and §i. There is no `phase_m_delivery.md` in-tree.

Pure documentation / skim-first among H–Q: `594f3d9`, `9e91e08`, `29a8998`, `0d5fd54`, and the audit half of `bb5702a`.

### LLM question generation — ADJACENT (owner judgment)

Phase P classified the interview question path as **ADJACENT**, not CLEAR and not a VIOLATION: an LLM may generate the question text and the `ideal_answer` / `ideal_keywords` references; the deterministic scorer (and guard) then grades the candidate against those references. The LLM does not return a score, band, readiness number, or guard verdict.

That sits inside the **letter** of the contract (no LLM judge in scoring, readiness, guard decisions, or gap analysis). Whether shaping the answer key this way sits inside the contract’s **intent** is an **owner judgment**, not an established fact on this chain. Reviewers who encounter LLM-authored `ideal_*` fields should treat the classification as ADJACENT and escalate intent to the owner rather than assuming CLEAR. Default configuration keeps LLM dials off (`LLM_LIVE_FETCH=0`, Phase Q).

---

## (b) Risk order (highest first)

Spend the **first hour** here:

1. **`39a7579` (B.1)** — SQLAlchemy persistence + answer submit/finalizing lock. Wrong here corrupts sessions or double-scores.
2. **`736b36f` + `dd13aab` (G.0/G.0b)** — scoring-mode plumbing on every scored attempt; evidence honesty for degraded SemanticScorer.
3. **`7002fa2` (F.0)** — self-assessment segregation from mastery/readiness/notebook; touches learning aggregates.
4. **`8466c48` (L)** — Interview media gate by block category; wrong here reintroduces camera/mic on Verbal/OA.
5. **`98d3813` (C.1)** — coding bank + 503 boundary + formula; confirm no fake scores on infra failure.
6. **`daa18b4` (D)** — target context + assistance events; ownership boundaries.
7. **`a47944a` (E.1)** — system-design self-report path; AV “unavailable” honesty (no speech scores).
8. **`1601e91` (B)** — large UI/contract surface; review after B.1 semantics are clear.

**Lower risk / mechanical (skim after the above):** Phase J Hub-offline defaults; Phase O Jobs live-fetch gate + provenance; Phase P outbound audit + fonts CDN removal; Phase Q `LLM_LIVE_FETCH` + client-boundary mode gate. These close honesty/outbound holes; they are not persistence or scoring-formula changes.

Named scorer/guard modules (aside from the Phase Q `question_bank.py` gate exception in §c) were **not** formula-edited on this chain. Persistence and submit-lock outrank chrome.

---

## (c) Protected-file attestation

Re-run against tip `c58e106` (Phase R):

```text
$ git diff --stat 0442493..HEAD -- \
  interViv_best/backend/scoring/pipeline.py \
  interViv_best/modules/nlp_scorer.py \
  interViv_best/modules/nlp_scorer_patch.py \
  interViv_best/modules/answer_guard.py \
  interViv_best/modules/semantic_scorer.py \
  interViv_best/modules/knowledge_graph.py \
  interViv_best/modules/ner_scorer.py \
  interViv_best/modules/c4_feedback.py \
  interViv_best/modules/question_bank.py \
  interViv_best/modules/model_metadata.json \
  'interViv_best/modules/*.joblib'

 interViv_best/modules/question_bank.py | 7 +++++++
 1 file changed, 7 insertions(+)
```

```text
$ git diff --name-status 0442493..HEAD -- <same paths>
M	interViv_best/modules/question_bank.py
```

**Conclusion:** among the named protected scorer/guard/bank-module set above, **`question_bank.py` is the only file that differs from Phase A**. Pipeline, nlp/semantic/ner scorers, answer_guard, knowledge_graph, c4_feedback, `model_metadata.json`, and `*.joblib` are unchanged vs `0442493`.

### Authorized exception — Phase Q gate in `question_bank.py`

| Field | Value |
|-------|--------|
| Phase | **Q** (`c58e106`) |
| Reason | Close latent OpenAI/OpenRouter outbound from `_generate_via_llm` under the shared `LLM_LIVE_FETCH` / generation-mode gate (same boundary as `call_llm_with_cache_retry`) |
| Scope | Gate wiring only |

Full diff vs Phase A (complete; nothing omitted):

```diff
diff --git a/interViv_best/modules/question_bank.py b/interViv_best/modules/question_bank.py
index 1c3f41b..edcaa69 100644
--- a/interViv_best/modules/question_bank.py
+++ b/interViv_best/modules/question_bank.py
@@ -325,6 +325,13 @@ def _generate_via_llm(skill: str, sub_domain: Optional[str], difficulty: str, as
     global _LAST_LLM_ERROR
     _LAST_LLM_ERROR = None
 
+    # Phase Q: shared outbound gate (minimal touch on this protected module).
+    from modules.llm_outbound_gate import question_llm_outbound_allowed
+
+    if not question_llm_outbound_allowed():
+        _LAST_LLM_ERROR = "LLM outbound gated off (LLM_LIVE_FETCH / QUESTION_GENERATION_MODE)."
+        return None
+
     provider, api_key, model = _llm_provider()
     if not provider or not api_key or not model:
         _LAST_LLM_ERROR = "No supported LLM provider/key/model was configured."
```

**Gate-only verdict:** no question content added, removed, or altered; no bank CSV/data touched by this diff; when the gate permits a call, generation behavior after the early return is unchanged from Phase A.

### Bank data (separate from the module file)

| Artifact | vs Phase A `0442493` |
|----------|----------------------|
| `data/fallback_question_bank.csv` | **Byte-identical** (MD5 `e60b1e32bec52064d2c951a7d3766634`) |
| `data/interview_dataset_v6.csv` | **Byte-identical** (MD5 `a4d176433776dbb04e9ce56632eeab67`) |
| `backend/db/phase2_content_bank.py` (MCQ/SQL) | **Byte-identical** (MD5 `e9ecf82e2e61f50df596cd41eceb8cd7`) |
| `backend/db/phase21_verbal_bank.py` | **Not in A** — added B (`1601e91`); MD5 `05e73d867b75648291d538c476c6dca0` matches phase21 `fe75a32` |
| `backend/db/phase_c_coding_bank.py` | **Not in A** — added C (`98d3813`); MD5 `3eb5bd436179045c509e520220e9d337` |

**Authorized new scoring modules (not in the frozen “existing modules” list):** `modules/scoring/coding.py` (C), `modules/scoring/system_design.py` (E.1) — deterministic only; no LLM judge.

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

**`parent_revision()` (G.0):** persistence tests previously pinned absolute parents because Alembic relative `-1` breaks when HEAD advances. `tests/alembic_helpers.py` resolves the current head’s parent dynamically.

---

## (e) Environment-dependent scoring (fresh reader)

SemanticScorer loads **`all-MiniLM-L6-v2` in-process** from the Hugging Face Hub
cache under `~/.cache/huggingface/hub/…`.

**Phase J finding (see `docs/phase_j_delivery.md`):** on this machine the
checkpoint is already cached (~87M `model.safetensors`). Without offline env,
`SentenceTransformer(...)` still opens **TCP to `huggingface.co:443`** for
Hub **HEAD** / resolve checks. A **403** on that path flips the process into
sticky lexical fallback and changes **both guard labels and numeric scores**.

With **`HF_HUB_OFFLINE=1`** (and typically `TRANSFORMERS_OFFLINE=1`),
`huggingface_hub` raises `OfflineModeIsEnabled` **before** socket connect.
Warm cache → full scorer; **no Hub TCP**. Cold / empty `HF_HOME` → library
`OSError`, then the app’s existing sticky degrade (fail-fast still not built).

| Mode | How | `scoring_regression` |
|------|-----|----------------------|
| full | cached MiniLM + Hub offline env (`backend.runtime_env` / `.env.example`) | **2/8** — always-present: gibberish→repetition (6.06); keyword_stuffing→gibberish (10.00) |
| degraded | `DISABLE_SEMANTIC_SCORING=1` (same sticky pattern as Hub-403 / cold-cache miss) | **4/8** — above + paraphrase out of band + off_topic guard None |

F.0 exposed mode on `/health`. G.0/G.0b **record `scoring_mode` on each scored attempt** (inside `scoring_breakdown` JSON) and surface it; rows without a stored mode read as **`unknown`** (never guessed).

**Phase J** makes Hub-offline the **recommended local operating configuration**
so warm machines stay in full mode without an outbound Hub request. That does
**not** retire fail-fast. Mode-on-attempt remains the durable record if a worker
runs degraded anyway.

Outbound inventory and LLM/Jobs gates: `docs/phase_p_outbound_audit.md` (updated through Phase Q). Defaults: `HF_HUB_OFFLINE=1`, `JOBS_LIVE_FETCH=0`, `LLM_LIVE_FETCH=0` via `backend/runtime_env.py`. Google Fonts CDN removed from default CSS in Phase P.

---

## (e2) Degrade patterns (four paths, one decision frame)

The codebase documents four failure paths that do **not** agree. Stated once:

| Path | On failure | Pattern |
|------|------------|---------|
| **SemanticScorer** (MiniLM / Hub) | Sticky lexical fallback for the process; changes labels and scores | **Silent degrade**. Mode recorded on scored attempts (G.0/G.0b) |
| **Jobs** live Adzuna fetch | Returns fixture listings as `fixture_fallback` (when live fetch is enabled and fails) | **Silent degrade**. Default: live fetch **off** (`JOBS_LIVE_FETCH=0`, Phase O) |
| **LLM question / coach** chat completions | Soft `None` → CSV / lexicon / plan fallback | **Silent degrade**. Default: dials **off** (`LLM_LIVE_FETCH=0`, Phase Q); generation also needs mode ∈ `{llm, llm_csv_fallback}` at the client boundary |
| **Transcription** (Whisper / Hub cold under offline) | `LocalEntryNotFoundError` → HTTP **503** `transcription_unavailable` | **Fail loud** (Phase M Step 0 observation; no Phase M commit) |

Three paths degrade silently; **transcription is the outlier** and is the behavior the project’s own honesty rules would favor (unavailable labeled, not a quiet substitute presented as success).

The still-open **fail-fast versus labeled-degrade** product decision (framed since Phase F primarily around SemanticScorer) **applies to all three silent paths**, not only to the scorer. Owner decides once whether missing dependency / failed fetch should abort, surface a durable unavailable label, or continue with a substitute.

**Mode-on-attempt** is the durable safeguard for **scoring** specifically (evidence rows carry `scoring_mode`). Jobs and LLM silent paths have **no equivalent** on evidence rows because their output is context / generation / coaching — not scored attempts.

Do not treat this section as a resolution. It is the decision surface.

---

## (f) Honest capability inventory

**Works today (with disposable DB + local servers):** auth/home/progress; block practice (Verbal/OA/SQL/Interview) with Phase L media gate (Verbal/OA skip camera/mic); builder presets/drafts; Problems browse + start; learning notebook/retry/assistance labeling; **spaced-review due list + review sessions (practice only)**; target context prefill on Practice/Learn; system-design **self-assessment** (explicitly not measured mastery); scoring-mode disclosure on new attempts; AV capability **reporting** and unavailable-state wiring; Jobs explorer with **fixture provenance / sample banner** (including warm cache, Phase O); offline Google Fonts default (Phase P).

**Shipped but unavailable:** **coding execution and coding scores** (503 / unscored). Video recording / durable AV blobs / speech scoring (E.2 not started).

**Phase M (incomplete — no commit):** Step 0 observed that `faster_whisper` `"tiny.en"` loads from the local Hub cache under `HF_HUB_OFFLINE=1`, and that a cold disposable `HF_HOME` fails **loudly** (503). Owner-present browser AV verification (Allow camera/mic through calibration) was **not finished** — session left waiting on a permission prompt; ports `:18000`/`:5173` may still hold that stack. Do not treat Phase M as closing live mic/camera or the seven AV UI states.

**Never built on this chain:** C.2 live runner; E.2 ffmpeg/blob retention; phase21 **Upload Verbal Ability entry** (rescued blobs only — see `docs/phase_h0_rescue.md`); LLM judge in scoring/readiness/guard/gaps (forbidden).

---

## (g) Outstanding decisions (owner)

| Item | Status | Notes |
|------|--------|-------|
| Fail-fast vs labeled-degrade | **Open** | Applies to SemanticScorer, Jobs live-fail, and LLM soft-fallback (§e2) |
| C.2 Docker / live coding runner | **Not started** | Keep 503 seam or authorize Docker |
| phase21 Verbal Upload entry snapshot | **Not integrated** | Media gate done in L; Upload entry still skipped |
| Job data sourcing | **Open** | Engineering: `phase_n_jobs_data_assessment.md`; recommend labeled sample / offline import; live adapter later |
| ADJACENT question-generation intent | **Open** | Letter vs intent (§a); default dials off in Q |
| Home target picker vs `/target-context/me` | Known gap | Prefill inconsistency |

---

## (h) Reproduction instructions

### Disposable environment

Use ports that do **not** collide with a possible Phase M stack on `:18000`/`:5173` (e.g. `18001` / `5174`).

```bash
cd "/Users/praneetsharma/Downloads/mega 2 copy/.worktrees/phase-b-block-practice/interViv_best"
rm -f /tmp/interviv_review_disposable.db
DATABASE_URL='sqlite:////tmp/interviv_review_disposable.db' .venv/bin/alembic upgrade head

DATABASE_URL='sqlite:////tmp/interviv_review_disposable.db' \
INTERVIV_USE_MEMORY_DB=false \
JWT_SECRET_KEY='review-disposable-secret-key-32bytes!!' \
OPENAI_API_KEY= OPENROUTER_API_KEY= \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
JOBS_LIVE_FETCH=0 LLM_LIVE_FETCH=0 \
QUESTION_GENERATION_MODE=csv QUESTION_REQUIRE_LLM=false \
ADZUNA_APP_ID= ADZUNA_APP_KEY= \
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 18001

# other terminal
cd frontend && VITE_API_BASE_URL=http://127.0.0.1:18001 npm run dev -- --host 127.0.0.1 --port 5174
```

`runtime_env.py` already setdefaults Hub / Jobs / LLM offline flags; the explicit env above documents the contract. Default CSS does **not** load Google Fonts (Phase P).

Signup via the real UI. **Never** point at the developer’s personal database.

Confirm mode: `curl -s http://127.0.0.1:18001/health` → `scoring.mode` `full` | `lexical_fallback_degraded`.

### Suites (mode recorded)

```bash
.venv/bin/python -m pytest tests/ -q
cd frontend && npm test && npm run build

HF_HUB_OFFLINE=1 .venv/bin/python scripts/scoring_regression.py          # expect 2/8 fail full (6/8 pass)
DISABLE_SEMANTIC_SCORING=1 HF_HUB_OFFLINE=1 .venv/bin/python scripts/scoring_regression.py  # expect 4/8 fail

.venv/bin/alembic heads   # 20260907_0008
# After pytest: restore docs/human_baseline_report.md
# MD5 5421f9f0fd6efad395666c545e5cf76a, 230 lines
git checkout -- docs/human_baseline_report.md
```

### Rescue refs (do not merge)

```bash
git show-ref | grep refs/rescue/
# docs: interViv_best/docs/phase_h0_rescue.md
```

---

## (i) Findings list (known, unfixed)

| Finding | Status |
|---------|--------|
| Jobs: if `JOBS_LIVE_FETCH=1` and live fetch fails → silent fixture fallback | Deferred with sourcing decision (O/P/Q) |
| Jobs: sample `empty_reason` copy names `JOBS_LIVE_FETCH` (raw config label in UI) | Deferred with sourcing / copy ownership |
| Three silent-degrade paths (SemanticScorer, Jobs live-fail, LLM soft fallback) vs transcription fail-loud | Decision open — see §e2 |
| Phase M incomplete: no commit; no `phase_m_delivery.md`; live mic/camera / seven AV UI states not closed | STILL OPEN / session may still hold `:18000`/`:5173` |
| 409 message visible in UI | PARTIAL (G/H) — client gate; race or post-submit retry UX not proven |
| Target does not override explicit topic | PARTIAL — override scenario not walked |
| Builder coding start in browser | PARTIAL — API/test covered; builder UI start not filmed |
| AV seven states in live UI | PARTIAL / BLOCKED — permission overrides / hardware |
| Real mic/camera | STILL BLOCKED — hardware; Phase M did not finish |
| C.2 Docker execution | Not started |
| E.2 AV artifacts | Not started |
| phase21 Verbal Upload entry | Not integrated (L gated media only) |
| ADJACENT LLM question generation vs contract intent | Owner judgment (§a) |
| Home target picker vs `/target-context/me` | Known gap |
| No Phase M delivery doc despite session work | Docs gap noticed in Phase R — record only |

---

## Related delivery docs

`phase_a_delivery.md` … `phase_g_delivery.md`, `phase_h0_rescue.md`, `phase_i_delivery.md`, `phase_j_delivery.md`, `phase_k_verbal_assessment.md`, `phase_n_jobs_data_assessment.md`, `phase_o_delivery.md`, `phase_p_outbound_audit.md` (includes Phase Q closure notes). Prefer this guide for onboarding; use per-phase docs for detailed evidence tables (note Phase H downgrades in F/G where VERIFIED had been overstated).
