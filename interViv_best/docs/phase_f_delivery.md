# Phase F delivery — verification, consolidation, honesty audit

No new features. No C.2. No E.2. No push. No merge.

## Branch and chain

| Item | Value |
|------|--------|
| Worktree | `/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/phase-b-block-practice` |
| Application | `.../interViv_best` |
| Branch | `codex/phase-b-block-practice` (name mismatch retained; carries B→F) |
| Base before F | `a47944a` (E.1) |
| F.0 | `7002fa2` — segregate self-assessment; disclose scorer degradation; real-route leakage fixtures |
| F.1 | this commit — browser verification report + honesty UI/start fixes |

Linear chain rooted on Phase A `0442493`:

```
0442493 (A) → 1601e91 (B) → 39a7579 (B.1) → 98d3813 (C.1)
→ 670f5ea (D Step 0) → daa18b4 (D) → 4303577 (E.0) → a47944a (E.1)
→ 7002fa2 (F.0) → <F.1>
```

`codex/phase-a-home-progress` tip = `0442493` = `merge-base(codex/phase-a-home-progress, HEAD)`.

**Branch naming recommendation (no rename performed):** review as stacked PRs or one “phases B–F” review with the delivery docs as the map; do not rename `codex/phase-b-block-practice` mid-chain.

### Protected paths vs Phase A (`git diff 0442493..HEAD`)

Empty for: `backend/scoring/pipeline.py`, `modules/nlp_scorer.py`, `modules/nlp_scorer_patch.py`, `modules/answer_guard.py`, `modules/semantic_scorer.py`, `modules/knowledge_graph.py`, `modules/ner_scorer.py`, `modules/c4_feedback.py`, `modules/question_bank.py`, `modules/model_metadata.json`.

Banks: verbal (`phase21_verbal_bank.py`) and coding (`phase_c_coding_bank.py`) **added** after A; `question_bank.py` unchanged. Verbal bank MD5 matches `fe75a32` (`05e73d867b75648291d538c476c6dca0`).

Migrations: no historical edits to 0001–0007; single head `20260907_0007`. Untracked Ticket B/C/D revision files remain on disk (preserved; not touched).

### Alembic pin convention

E.1 pinned Phase D downgrade to absolute `20260907_0005` because relative `-1` breaks when the head advances. **Convention going forward:** always pin absolute revision ids in persistence tests; never use relative `-1`/`+1` against a moving head.

---

## Disposable environment (reproducible)

Created for browser verification only. **Never** pointed at the user’s existing database.

```bash
cd "/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/phase-b-block-practice/interViv_best"
rm -f /tmp/interviv_phasef_disposable.db
DATABASE_URL='sqlite:////tmp/interviv_phasef_disposable.db' .venv/bin/alembic upgrade head

INTERVIV_USE_MEMORY_DB=false \
DATABASE_URL='sqlite:////tmp/interviv_phasef_disposable.db' \
JWT_SECRET_KEY='phase-f-disposable-secret-key-32b!!' \
OPENAI_API_KEY= OPENROUTER_API_KEY= HF_HUB_OFFLINE=1 \
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

Accounts created through the real signup UI / `/auth/signup`:

- `contributors@example.invalid` / `PhaseF123`
- `contributors@example.invalid` / `PhaseF123`

---

## Step 0 — four audits

Findings first (recorded before F.0); F.0 fixes second.

### (a) SemanticScorer reachability and guard degradation

**What it calls:** in-process `sentence-transformers/all-MiniLM-L6-v2`. First load may `HEAD`/`GET` Hugging Face Hub (`https://huggingface.co/...`) unless weights are already cached. That outbound attempt is a **pre–Phase A constraint violation** when network is reachable.

Observed 403 path: Hub/proxy returns 403 → sticky lexical fallback (`SemanticScorer unavailable; falling back to lexical scoring`).

| State | How produced here | Failures |
|-------|-------------------|----------|
| Full (`semantic_scoring_available: true`, `mode: full`) | Local cache + `HF_HUB_OFFLINE=1` | **2/8** always-present: `gibberish`→`repetition` (6.06), `keyword_stuffing`→`gibberish` (10.00) |
| Degraded | `DISABLE_SEMANTIC_SCORING=1` (same 4/8 pattern as Hub-403 fallback) | **4/8**: above pair + `paraphrase` score 39.75 outside [45,100] + `off_topic` guard `None` vs `off_topic` |

Fallback changes **both** guard labels **and** numeric scores (e.g. excellent 91.39→86.50). Offline deploy without a local model cache runs degraded permanently.

**F.0 disclosure (no scorer outcome change):** `/health` → `scoring.mode` `full` | `lexical_fallback_degraded`, `semantic_fallback_reason`, operator note. Answer responses can carry semantic disclosure fields. Protected scorer/guard files were not modified to change outcomes.

### (b) Self-assessment score

**Pre-F.0:** `structured_self_assessment` score (e.g. 100) flowed into Elo/mastery/session averages/readiness/notebook like measured evidence.

**F.0:** `backend/evidence_kind.py`; self-reported rounds excluded from measured mastery/readiness/Elo updates; Progress exposes `self_reported_average` separately; notebook excludes system-design misses. Incomplete rubric still yields **no score** (422 / client gate), not a zero.

**Browser (F.1):** Progress after a completed self-assessment showed System Design skill **Not measured** and session score **Not measured**, while Verbal Ability remained measured at 40%. Result UI: “Self-assessment score” / “Self-assessment recorded… diagrams were not auto-scored.”

### (c) Verbal provenance (read-only)

- Bank/attribution **byte-identical** to `fe75a32` on phase21-verbal-ability.
- Routes/UI rebuilt under Phase B blocks (not a merge of that branch).
- phase21 worktree was **clean** — no uncommitted interview/UI fixes to inspect.
- Gap: dedicated phase21 verbal suites / Upload Verbal entry vs Practice Hub only.
- **Integration not performed** in Phase F.

### (d) Leakage fixtures

Hand-built sanitizer dicts converted in F.0 to assert against real route responses where possible (`test_sanitizer_strips_injected_coding_secrets_under_any_policy`, MCQ review leakage). SQL/system_design already real-route. Any remaining offline-impossible fixture is marked explicitly in-test (none left unmarked as silent coverage).

---

## F.1 honesty fixes (found during browser verification)

1. **Builder label:** `system_design` add-button rendered as “Interview”. Fixed label + empty-state copy in `Practice.jsx`.
2. **Standalone System design:** mode was listed in `STANDALONE_MODES` but had **no setup form** (`mode=system_design` showed only “← All modes”). Added standalone form (prompts 1–5, time, start).
3. **Coding start with skill `DSA`:** block `skills: ['DSA']` was passed as bank **topics**, yielding `found 0, need 1` for every Standalone Coding start. Shared-path fix in `session.py`: treat `DSA`/`coding` as skill-category labels, not topic filters. Real topics (e.g. `arrays`) still filter.

---

## Commands and evidence

### Suites

```
pytest tests/ -q
→ 455 passed, 1 skipped
(human_baseline_report.md regenerated to 68 lines; restored to MD5 5421f9f0fd6efad395666c545e5cf76a, 230 lines)

npm test → 48 passed
npm run build → clean
alembic heads → 20260907_0007 (single)
git diff --check → clean
```

### scoring_regression.py (state recorded)

Full SemanticScorer (`HF_HUB_OFFLINE=1`, model loaded):

```
2/8 case(s) failed.   # gibberish, keyword_stuffing
```

Degraded (`DISABLE_SEMANTIC_SCORING=1`):

```
4/8 case(s) failed.   # paraphrase, gibberish, keyword_stuffing, off_topic
```

`/health` during disposable run: `scoring.mode == full`.

---

## Verification backlog (browser)

Status legend: **VERIFIED** (browser observation) · **STILL BLOCKED** · **NOT APPLICABLE**

### Auth / Home / Progress (Phase A)

| Item | Status | Evidence |
|------|--------|----------|
| Signup via real UI | VERIFIED | Created `phasef.user1` → `/home` “Hello, Phase…” |
| Login / logout | VERIFIED | Logout → `/login`; login works |
| Safe `next=/practice?mode=custom` | VERIFIED | Landed on custom builder |
| Unsafe `next=https://example.test` | VERIFIED | Landed on `/home` |
| Other unsafe next variants (`//…`, `/login`, encoded) | STILL BLOCKED | Z #26: not individually exercised before AV/scoring stop; sanitizer tests do not close browser behavior |
| Home empty starter actions | VERIFIED | New account: Start practicing / Help me choose; target Not set |
| Progress absence (not zeros) for new account | VERIFIED | “Readiness Not measured”, “No scored sessions yet.” |
| Progress with measured data | VERIFIED | User1 Verbal Ability 40%, Elo changes; System Design **Not measured** |
| Continue practice / deep-link restore | STILL BLOCKED | Z #27: full interrupted-plan resume not closed before stop |
| Target alone does not invent readiness | VERIFIED | Readiness stayed Not measured without target practice |
| Responsive 375 / no page-wide overflow | VERIFIED | `innerWidth=375`, `scrollWidth=375` on Progress |
| Keyboard-only full Home/Progress pass | STILL BLOCKED | Z #28: full keyboard tour not completed |
| `/dashboard/:sessionId` report loads dark premium UI | VERIFIED | Verbal report with C4 panels at `/dashboard/ba80ea9e-…` |
| Pixel compare vs pre-A screenshot | STILL BLOCKED | Z #29: frozen pre-A screenshot still unavailable |

### Practice blocks (Phase B / B.1)

| Item | Status | Evidence |
|------|--------|----------|
| Verbal standalone (5 Q, English MCQ) | VERIFIED | Session `ba80ea9e-…`; synonym MCQs |
| OA topic filter + content limit | VERIFIED | OOP need 15 / found 10 message; stayed on setup (422) |
| SQL / Interview standalone entry | VERIFIED | Present on hub; Interview used in mixed builder |
| Mixed Verbal→Interview→SQL start | VERIFIED | Session `2d47ad75-…`; order Verbal first |
| Mid-session refresh identity/options | VERIFIED | Same concise/expand stems and option order after reload |
| Repeated block type | PARTIAL | Z #30: two OA blocks completed at 50%; wrong question/result association and stale answered count (Z-F04/05) |
| Builder add/remove/reorder/repeat UI | VERIFIED | Blocks, Up/Down, Repeat, Remove, per-block settings, total-time summary “45 timed minutes…” |
| Presets save/load/delete | PARTIAL | Z #31: real save and keyboard load verified; delete not exercised before stop |
| Autosaved drafts | VERIFIED | “Draft saved” / “Saving…” status |
| Draft recovery after refresh | VERIFIED | Returning to `mode=custom` restored Verbal/Interview/SQL draft |
| Draft reject submitted/expired | PARTIAL | Z #32: stale submitted draft reached server 409 without visible error; expired-draft UI not separately closed |
| Duplicate submit rejection | PARTIAL | Z #33: real stale tab reached 409; no visible rejection message (Z-F06), no additional scored round shown |
| Keyboard-only builder (no drag) | PARTIAL | Z #34: keyboard remove/load/reorder worked; complete add/repeat tour remains open |
| Second-account isolation (sessions/presets/drafts) | PARTIAL | Z #35: browser session denial and preset isolation observed; builder draft leaked between accounts (Z-F03) |

### Coding (Phase C)

| Item | Status | Evidence |
|------|--------|----------|
| Problems list | VERIFIED | 15 problems (Two Sum, …) |
| Standalone coding start | VERIFIED | After F.1 DSA-topic fix; session `c5dca423-…` Two Sum |
| Run → unavailable panel | VERIFIED | “Code execution is currently unavailable… submitting now will not score” |
| Submit → 503, round open | VERIFIED | `POST /session/coding/run` 503; `POST /session/answer` 503; UI remained on editor |
| Retry submit 503 (not 409) | PARTIAL | Z #37: only natural-expiry 409 was exercised; unexpired 503 retry remains open |
| Progress shows unscored / coding unavailable (not 0%) | VERIFIED | “0/1 rounds scored · … coding unavailable · Not measured” |

### Learning / target (Phase D)

| Item | Status | Evidence |
|------|--------|----------|
| Target prefill ATS/coach/practice | PARTIAL | Z #38/39: Practice explicit Python retained after saving TCS target; ATS/Coach not exercised |
| Resume upload → ATS selection | STILL BLOCKED | Z #40: not exercised before AV/scoring stop |
| Jobs sample-data labeling | STILL BLOCKED | Z #41: not freshly exercised; Phase O historical browser evidence remains separately attributed |
| Mistakes notebook / retry set | VERIFIED | Z #42: actual Python miss appeared in Learn; UI-created five-question retry completed; no inserted attempts |
| Hint-assisted vs unassisted miss | PARTIAL | Z #43: actual unassisted misses observed; fresh assisted pair not exercised; G historical evidence retained |
| Ownership of notebook/bookmarks/target | PARTIAL | Z #44: second-account notebook/retry/schedule empty; meaningful bookmark and target comparison incomplete |

### System design + AV (Phase E)

| Item | Status | Evidence |
|------|--------|----------|
| Rubric named criteria visible | VERIFIED | Requirements clarity, API and data model, Scale and reliability, Trade-offs |
| Incomplete rubric → no score | VERIFIED | Alert: “Rate every rubric criterion (1–5) before submitting.” |
| Complete → labeled self-reported | VERIFIED | “Self-assessment score 68.8” / “Self-assessment recorded…” |
| `/av/capabilities` distinct unavailable_states list | PARTIAL | Z #16: two permission banners rendered; API list is not proof of all seven states |
| Each AV unavailable state distinct in UI | PARTIAL | Z #7–13: not-requested and denied rendered; five states remain unverified |
| Device capture with real mic/camera | VERIFIED | Z #14: owner manual screenshot and confirmation; agent browser remained denied |
| No AV score fabricated | PARTIAL | Z #17/Z-F00: source-confirmed label enters scoring metadata; no live numeric influence demonstrated; verification stopped |

---

## Still missing / blocked (summary)

- C.2 live coding execution (out of scope).
- E.2 durable AV blobs / ffmpeg / speech scores (out of scope).
- Real microphone/camera capture: closed by owner manual evidence in Z; server transcription and full calibration remain open.
- Exhaustive AV permission-state UI tour.
- Full duplicate-submit and draft-vs-expired UI proofs.
- Full Phase D learning/ATS/jobs browser checklist.
- Historical pixel-diff of session report.
- Branch rename (not done; review strategy recommended above).

---

## Exact commits

| Commit | Role |
|--------|------|
| `7002fa2` | F.0 honesty (self-reported segregation, scorer disclosure, leakage fixtures) |
| F.1 | This delivery doc + Practice.jsx system-design/label fixes + session.py DSA topic filter honesty |

Working tree after F.1: clean of F-scoped changes. Unrelated untracked Ticket/Track files preserved and unstaged.

## Phase Z status update

The updated rows above refer to [Phase Z](phase_z_browser_verification.md), the current itemized evidence record. Z stopped at a source-confirmed AV-label-to-scoring interface path; numeric influence was not established. No product fixes were made. Older VERIFIED rows otherwise retain their original phase attribution.
