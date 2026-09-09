# Phase G delivery — close finishable verification backlog

No new features. No C.2. No E.2. No phase21 Verbal UI integration. No push. No merge.

## Branch and chain

| Item | Value |
|------|--------|
| Worktree | `/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/phase-b-block-practice` |
| Application | `.../interViv_best` |
| Branch | `codex/phase-b-block-practice` |
| Base before G | `f71aae4` (F.1) |
| G.0 | `dd13aab` — persist scoring mode; F-phase tests; alembic parent helper |
| G.0b | `736b36f` — embed scoring mode in `scoring_breakdown` JSON (SQLAlchemy durable) |
| G.0c | `383d8ba` — session dashboard tolerates string feedback (SD reports) |
| G.1 | this commit — verification report + review topology |

```
0442493 (A) → 1601e91 (B) → 39a7579 (B.1) → 98d3813 (C.1)
→ 670f5ea (D Step 0) → daa18b4 (D) → 4303577 (E.0) → a47944a (E.1)
→ 7002fa2 (F.0) → f71aae4 (F.1)
→ dd13aab (G.0) → 736b36f (G.0b) → 383d8ba (G.0c) → <G.1>
```

---

## Step 0 — four audits (findings first)

### (a) Scorer degradation must reach the evidence

| Question | Finding |
|----------|---------|
| Sticky after a single 403? | **Yes.** `SemanticScorer` keeps `_model_load_error` for the process lifetime after load failure; subsequent answers stay degraded. |
| Different workers, different modes? | **Yes, possible.** Mode is process-local. Two workers that booted under different Hub/cache/`DISABLE_SEMANTIC_SCORING` conditions can score identical answers differently. |
| Mode recorded on the scored attempt at write time? | **Not before G.0.** F.0 only exposed `/health` `scoring.mode`. Answer responses could carry labels, but SQLAlchemy dropped unknown top-level round keys. |
| Candidate/reviewer surfaces show degraded mode? | **Not before G.0.** Progress/history/report did not carry durable mode. |

**G.0 / G.0b / G.0c fixes (permitted boundary only):**

- Write `scoring_mode` (+ `evidence_kind`, evaluation disclosure) into `scoring_breakdown` JSON at submit time.
- Promote those fields when reconstructing rounds; `scoring_mode_for_round` reads top-level or nested JSON; historical rows without either stay `unknown` (never guessed).
- Dashboard sanitizes and surfaces `scoring_mode` / `scoring_mode_label`; progress history aggregates `scoring_modes`.
- Interview feedback prefixes self-reported / degraded modes; ScoringBreakdownPanel can show the label when a breakdown exists.
- G.0c: SD feedback is a plain string — `.get` on it 500ed `/dashboard/{id}`; normalize `next_step` so reports load.

**Fail-fast at startup (REPORT ONLY — not implemented):** abort application lifespan when sentence-transformer warm-up fails unless `DISABLE_SEMANTIC_SCORING=1` (or an explicit “allow degraded” flag). That is a product decision: today the process degrades silently and keeps scoring.

### (b) F-phase test coverage

| Change | Test that fails if reverted (after G.0) |
|--------|----------------------------------------|
| Self-assessment excluded from mastery / readiness / gap / retry / notebook | `test_self_assessment_excluded_from_gap_readiness_retry_notebook` (+ Progress browser: System Design **Not measured**) |
| Scoring mode disclosed | `test_scoring_mode_persisted_on_measured_attempt`, `test_scoring_mode_degraded_when_semantic_disabled`, `/health` assertions in phase G honesty suite |
| Leakage fixtures vs real routes | F.0 real-route leakage tests (unchanged; still present) |
| Builder labels `system_design` correctly | `test_block_builder_labels_system_design` (frontend) / Practice UI “+ System design” |
| Standalone System design form | frontend Practice standalone form test + browser `mode=system_design` |
| Coding `skills: ['DSA']` non-empty | `test_coding_dsa_skills_resolves_without_problem_id_all_entry_paths` (standalone, builder-shaped, Problems `problem_ids` path) |

**Alembic pin convention (applied):** `tests/alembic_helpers.py` → `parent_revision()` resolves the current head’s parent dynamically. Persistence tests no longer need a new absolute pin every phase. Absolute ids remain valid for one-off historical assertions; do not use relative `-1` against a moving head.

### (c) Working-tree hedge

At G start this worktree was **unqualified-clean** (`git status --short` empty). Phase F’s “clean for F scope” referred to F-touched paths; earlier phases’ unqualified “clean” matched this worktree. The **parent** mega checkout often carries unrelated Ticket/Track dirt — that is **not** this worktree. Unrelated untracked Ticket revision files under the app tree (if any) were preserved and left unstaged. End of G: tree clean of G-scoped changes after G.1.

### (d) phase21-verbal-ability uncommitted work (READ-ONLY)

| Fact | Value |
|------|--------|
| Worktree path | `/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/phase21-verbal-ability` |
| Branch / HEAD | `phase21-verbal-ability` @ `fe75a32` |
| `git status` | clean (0) |
| Stashes | unrelated `stash@{0}` on `fix/offtopic-threshold-sweep` — not the interview UI |
| Claimed uncommitted UI fixes on any ref? | **No** |

**Recovery routes found (not executed):** three dangling blobs still in the shared object store / lost-found:

| Blob | Content |
|------|---------|
| `65bf858acb49281e10b42410a952293b0c2c4490` | Upload.jsx with `isCheckingAuth` + Verbal Ability entry |
| `8405effdaaa1004b2753686df24dac813478011c` | Interview.jsx with `usesInterviewMedia` gating |
| `06bc5daf6d26cfced8744eb829d5350fc39d0b5f` | frontend render test |

Also: dangling commit `381c7841c62c65fafec62c0a4b03b4abc5534c83` (inspect with `git show` before any restore). Risk: `git gc` can prune. Work appears **lost from refs** but recoverable from dangling blobs until pruned.

---

## Disposable environment (reproducible)

```bash
cd "/tmp/interviv-publish/Downloads/mega 2 copy/.worktrees/phase-b-block-practice/interViv_best"
rm -f /tmp/interviv_phaseg_disposable.db
DATABASE_URL='sqlite:////tmp/interviv_phaseg_disposable.db' .venv/bin/alembic upgrade head

DATABASE_URL='sqlite:////tmp/interviv_phaseg_disposable.db' \
INTERVIV_USE_MEMORY_DB=false \
JWT_SECRET_KEY='phase-g-disposable-secret-key-32b!!' \
OPENAI_API_KEY= OPENROUTER_API_KEY= HF_HUB_OFFLINE=1 \
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

Accounts via real `/auth/signup`:

- `contributors@example.invalid` / `PhaseG123`
- `contributors@example.invalid` / `PhaseG123`

**SemanticScorer mode for seeded verification:** **full** (`/health` → `scoring.mode: full`, `sentence_transformer.loaded: true`). Degraded path covered by unit test with `DISABLE_SEMANTIC_SCORING` / monkeypatch; mode-sensitive claims called out below.

**Seeding:** real session starts + answer submits only (OA DBMS misses, Verbal, SD self-assessment, coding DSA starts, hint-assisted DBMS miss). No fabricated attempt rows.

---

## Backlog

Status legend: **VERIFIED** · **STILL BLOCKED** · **NOT APPLICABLE**

### (1) Seeded history + learning surfaces

| Item | Status | Method / evidence |
|------|--------|-------------------|
| Mistakes notebook from real misses only | VERIFIED | Browser `/learn`: 10 misses; coding excluded with note; no correct-answer entries |
| Retry sets from missed topics | VERIFIED | `phase-g-misses` (5 DBMS items); UI “Generated from your genuinely missed topics only” |
| Target context across job→skills→practice→next steps | VERIFIED | Browser: Learn next steps cite Software Engineer; Practice prefills TCS + skills `DBMS, OOP, DSA` (API `/target-context/me` corroborates, not sole evidence) |
| Target prefills settings, does not override explicit topic | VERIFIED | Z #38: explicitly selected Python, then saved TCS/entry-role target; resulting OA question remained Python |
| Assisted vs unassisted separation | VERIFIED | Browser Learn: “3 unassisted, 3 assisted” DBMS; notebook tags `assisted · hint` vs `unassisted` |
| Per-block results / next practice from real outcomes | PARTIAL | Z #45: real Learn retry suggestions observed, but repeated OA result displayed next question with previous score (Z-F04) |
| Self-assessment not raising measured mastery | VERIFIED | Browser Progress: System Design **Not measured** after 100 self-assessment; report: “Self-assessment recorded…” |

### (2) Duplicate-submit UI

| Item | Status | Method |
|------|--------|--------|
| Double submit rejected / no double scoring | VERIFIED | **Browser (Phase H):** OA MCQ session `5f1b4a4a-…`; two `Submit Round` clicks in one tick → single **Session Complete** (“1 rounds · Average 100%”); dashboard still **one** `submitted` round score 100. Client `isScoring` gate drops the second click. |
| Comprehensible **409** user-facing outcome | PARTIAL | Z #33/Z-F06: a real stale second tab reached server 409, but no rejection message rendered and the question stayed editable. Observed UX failure, no longer merely an untested server path |

### (3) AV permission tour (seven states)

| State | Status | Method |
|-------|--------|--------|
| permission_not_requested | VERIFIED | Z #7: microphone permission-not-yet-requested banner rendered in the interview |
| permission_denied | VERIFIED | Z #8: camera and microphone denied messages rendered, including after owner-reported Allow/retry |
| no_device | STILL BLOCKED | Z #9: missing-device state not induced; no device-emulation tool capability available |
| unsupported_browser | STILL BLOCKED | Z #10: no unsupported-browser UI observation |
| service_unavailable | STILL BLOCKED | Z #11: no real server-transcription request; helper/API evidence remains insufficient |
| capture_failed mid-session | STILL BLOCKED | Z #12: no controlled mid-capture hardware fault induced |
| interrupted_recoverable | STILL BLOCKED | Z #13: no controlled track interruption/recovery verified |
| Real mic/camera capture | VERIFIED | Z #14: owner manual screenshot and explicit confirmation; not a local-server transcription verification |

### (4) Re-verify F.1 fixes

| Item | Status | Evidence |
|------|--------|----------|
| Builder labels System design | VERIFIED | Browser custom builder “+ System design”; block “4 . System design · 1 prompt” |
| Standalone System design E2E | VERIFIED | Browser `mode=system_design` → session `8d4552c3-…` → self-assessment → report |
| Coding three entry paths non-empty | VERIFIED | Z #36 closes missing builder start: custom Coding/DSA → Two Sum editor after calibration Skip. Standalone and Problems evidence remains historical G evidence, not live execution proof |

Note: Problems UI is **single-problem** practice (not a multi-checkbox set). The “Problems practice set” path is `problem_ids: […]` via `mapStandaloneToStartPayload`.

### (5) Verbal UI gap (recommend only — not integrated)

**What phase21 / dangling Upload provides that this chain lacks:**

- Dedicated **Verbal Ability practice** entry on Upload (`data-testid="verbal-practice-entry"`): 15 Q / 20 min, auth-aware label (`Checking sign-in…` / `Sign in for…`), navigates to login when unauthenticated.
- Dangling Interview `usesInterviewMedia` gate: skip camera/mic/calibration/engagement for non–`technical_short_answer` rounds (Verbal/MCQ-safe). Current chain Interview already grew past fe75a32 for blocks/AV/SD; a naïve overwrite would regress Phase E/F work.

**What integrating would touch:** `frontend/src/pages/Upload.jsx` (restore Verbal entry + auth gate), possibly Interview media gating merge, Verbal start payload helper, frontend tests; re-verify Practice Hub Verbal standalone vs Upload entry, auth redirect, and that MCQ rounds do not request mic/camera.

**Recommendation:** schedule a small “Verbal entry parity” PR after B–G review; recover dangling blobs first (`git show 65bf858a…` / `8405effd…`) into a scratch branch — do not merge phase21 wholesale.

---

## Review topology (recommendation only)

Do **not** rename, rebase, or split the branch. Proposed review stack:

| Stack | Commits | Review together? | Risk order |
|-------|---------|------------------|------------|
| 1. Phase A base | `0442493` | already separate tip | Low — Home/Progress |
| 2. Blocks B + B.1 | `1601e91`–`39a7579` | together | Medium — session contract |
| 3. Coding C.1 | `98d3813` | alone after B | Medium — execution boundary |
| 4. Learning D | `670f5ea`–`daa18b4` | Step 0 + D together | Medium — learning hub |
| 5. E.0 doc + E.1 | `4303577`–`a47944a` | E.0 trivial; E.1 alone | Medium — SD/AV honesty |
| 6. Honesty F | `7002fa2`–`f71aae4` | F.0+F.1 together | High — scoring evidence semantics |
| 7. Verification G | `dd13aab`–G.1 | G.0* + G.1 together | High — mode persistence; read G audits first |

Independently reviewable: E.0 (`4303577` doc-only). Must land together: F.0+F.1; G.0+G.0b+G.0c+G.1. Risk order for review: **F → G → B → C → D → E**.

---

## Commands and evidence

### Suites (record mode)

```
.venv/bin/python -m pytest tests/ -q
# 463 passed, 1 skipped, 41 warnings in 93.37s
# (suite grew 455→463 with Phase G honesty + related coverage)

cd frontend && npm test
# 49 passed

cd frontend && npm run build
# tsc && vite build — success (built in 19.79s)

HF_HUB_OFFLINE=1 .venv/bin/python scripts/scoring_regression.py
# mode: full (weights loaded from local cache)
# 2/8 failed — always-present pair only

DISABLE_SEMANTIC_SCORING=1 HF_HUB_OFFLINE=1 .venv/bin/python scripts/scoring_regression.py
# mode: degraded (env disable)
# 4/8 failed — pair + paraphrase 39.75 + off_topic guard None

.venv/bin/alembic heads
# 20260907_0007 (head)

git diff --check
# clean (after restoring baseline bytes)
```

`human_baseline_report.md` regenerated by analysis test → restored to MD5 `5421f9f0fd6efad395666c545e5cf76a` (230-line committed form).

### Scoring regression baseline (environment-dependent)

| Mode | How | Result this run |
|------|-----|-----------------|
| full | `HF_HUB_OFFLINE=1`, model cached | **2/8**: gibberish→repetition (6.06); keyword_stuffing→gibberish (10.00) |
| degraded | `DISABLE_SEMANTIC_SCORING=1` | **4/8**: above + paraphrase 39.75 outside [45,100] + off_topic guard None |

### Alembic

Single head `20260907_0007`. No historical migration edits.

---

## Still unverified / blocked / missing

- C.2 live coding execution (out of scope).
- E.2 durable AV blobs / speech scores (out of scope).
- Real microphone/camera capture.
- Live browser permission-deny / no-device / mid-capture fault tour (classifier + UI wired; hardware/override incomplete).
- **409 user-visible string** after duplicate submit (client gate; see §2 PARTIAL).
- Target explicit-topic override scenario: VERIFIED in Z #38.
- Builder coding start in the browser: VERIFIED in Z #36 (rendering only).
- Home target picker still shows “— Select —” while `/target-context/me` and Practice prefill TCS — Progress/Learn use target; Home form prefill gap remains.
- Session-complete screen can flash “Average 100%” for self-assessment before report clarifies self-reported (report text is honest).
- phase21 Verbal Upload entry not integrated (intentional; objects rescued under `refs/rescue/*` in Phase H).
- Branch rename (not done).

---

## Phase H correction note

Phase H re-checked VERIFIED rows that rested on API/source/tests where the claim was interactive. Duplicate-submit **no double score** was re-proven in the browser (`5f1b4a4a-…`); the **409 toast** claim was downgraded to PARTIAL. AV classifier/API-only rows and several F-doc API-only rows were downgraded. See `docs/review_guide.md`.

---

## Exact commits

| Commit | Role |
|--------|------|
| `dd13aab` | G.0 Step 0 fixes + tests |
| `736b36f` | G.0b durable scoring_mode in breakdown JSON |
| `383d8ba` | G.0c SD dashboard string feedback |
| `65a456e` | G.1 delivery doc |

Working tree after G.1: clean of G-scoped changes.

## Phase Z follow-up

[Phase Z](phase_z_browser_verification.md) supplies the current browser status for the updated rows. It reached the real stale-tab 409 and found missing error feedback; it also found builder draft ownership and expired Coding report defects. Further checks stopped at the AV/scoring interface condition. Prior G/H evidence elsewhere remains attributed to its original phase.
