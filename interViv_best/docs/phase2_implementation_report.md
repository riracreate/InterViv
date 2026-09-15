# Phase 2 implementation report — modular practice experience

Branch `phase2/modular-practice`, worktree
`.worktrees/cursor-ai-design-phase2`, based on Phase 1B tip
`a5b7492f584215c2f6991c74addeaa0dc5ce2032` (verified: branch, worktree,
and reported tip all match; Tree 2 and all source/checkpoint worktrees
untouched).

Scope: complete the modular practice experience on top of the existing
block contract, Practice builder, session lifecycle, round components,
and reports. Missing behavior implemented, defects fixed; completed
features reused, not rebuilt.

**Stopped before** reviewed-only activation, experimental-evaluator use,
Phase 3, push, merge, or deploy.

## 1. Reused as-is (verified, not rebuilt)

- Block contract (`backend/models/blocks.py`): stable per-block identity,
  requested order, repeated categories with independent settings.
  `MAX_BLOCKS = 10`, `MAX_TOTAL_ROUNDS = 50` preserved.
- `POST /session/start` with blocks + legacy normalization, upfront
  content validation (no session on failure), server-owned activation
  (`started_at` at build; refresh never extends).
- `GET /session/{id}` resume, `POST /session/answer` (per-session lock,
  409 duplicates, deadline enforcement, idempotent block-ordered
  progression, completion), drafts/presets with ownership, per-account
  draft isolation with sign-in/sign-out cleanup.
- Practice standalone entries + custom builder, round components
  (MCQ/SQL/Coding/SystemDesign/ML), completion → report navigation.
- Anonymous legacy-technical start; auth required for MCQ/SQL/coding/
  system-design/ml rounds; signed-out `/home` → sign-in → Home.
- Coding/Piston availability behavior, stock Gemma coach, SQL execution
  security, Resources, sign-out on Account: untouched, suites green.

## 2. What changed

### A — Reviewed-inventory availability (gate stays OFF)

- `modules/bundle_selector.py`: new `reviewed_available_count()` —
  counts eligible latest-`reviewed` versions without selecting content.
- `backend/routes/session.py`:
  - `_validate_block_content()` now checks interview blocks when the
    gate is on (per skill; difficulty- and topic-aware when pinned).
    Gate off → legacy/adaptive path unchanged.
  - New `POST /session/availability`: same payload shape as start, same
    auth rule, **no writes**. Returns the effective policy
    (`reviewed_only`), overall `available`, and per-block
    available/reason entries. Invalid shapes are 422, as at start.
  - Reviewed-inventory exhaustion at start/progression maps to **422**
    with the selector's message (unsatisfiable content under the pinned
    policy), not 503, and never a silent switch. Fixed a real wiring
    wart found while testing: build-time selection pinned
    topic=`sub_domain`, whose `"general"` default matched no bundle, so
    gate-ON start could never select reviewed content. The legacy
    `"general"` default no longer pins selection; an explicit
    non-default sub-domain still pins strictly.
- `frontend/src/pages/Practice.jsx` + `lib/api.js` +
  `lib/practiceBuilder.js`: interview-containing payloads are probed
  pre-start; unavailable inventory shows a dedicated notice
  (`data-testid="availability-notice"`, `role="alert"`) naming the
  blocked block/skill with "No session was started and nothing was
  consumed." Start-time 422/503 content failures render in the same
  panel; other errors keep the existing box.
- No unscored-practice alternative is offered under reviewed-only
  unavailability: none is supported, so the outcome is the clear
  notice above. Null scores preserved (nothing scored).

### B — Per-block reports (no blended overall)

- `backend/routes/dashboard.py` `_block_results()` (additive fields
  only): `attempted_rounds` (answer persisted; expired-then-zeroed is
  scored but not attempted), `unscored_rounds`, `block_position`, and
  planned-skills fallback so unstarted blocks are not mislabeled
  "General".
- `frontend/src/lib/dashboardMapping.js`: maps `block_results` to
  per-block cards with each block's own metric (MCQ accuracy, SQL
  correctness, Interview score, Coding score, Self-reported score,
  Ungraded practice) plus attempted/scored/unscored counts. Mixed
  sessions (block plan > 1 with > 1 measured block) show **no single
  overall percentage**: hero becomes "Mixed session / See per-block
  results below", average-derived layers/radar are suppressed, and the
  C1 card explains. Single-block and legacy sessions render exactly as
  before (`isMultiBlockSession` keys off `block_plan`, so historical
  rows are untouched).
- New `BlockResults.tsx` section in the session report (multi-block
  only); `ReviewSummary` accepts the blended variant text.
- Zero stays a real score; no measurement stays null throughout.

### C — Usability (required flows only)

- Practice builder/standalone/report flows use native, keyboard-
  operable controls with responsive layouts; verified by inspection.
- Added missing accessible names: Repeat/Remove per block position,
  Load/Delete per preset name. No drag-only or hover-only paths.
- Broader design-system overhaul left for Phase 3 (no theme changes).

## 3. Tests

New backend suites (33 tests, all passing):

| File | Covers |
| --- | --- |
| `tests/test_phase2_availability.py` (11) | probe/start parity; gate OFF + zero reviewed → legacy works; gate ON isolated → pre-commit unavailable, no session/candidate writes, no switch to drafts/another topic/difficulty; explicit topic pin strict; mid-run exhaustion 422 keeps scored round |
| `tests/test_phase2_reports.py` (5) | composed V→SQL→Interview per-block metrics/counts; repeated OA identities; expired → unscored+unattempted (not zero); scored zero stays 0.0; legacy-shaped report preserved |
| `tests/test_phase2_standalone.py` (7) | 4 standalone completions + reports from single-block payloads (no resume/JD/company/role); 10-block / 50-round caps + 50-round boundary accepted |
| `tests/test_phase2_resume.py` (4) | refresh preserves config/round/timing/question ref/results; duplicate 409 without double-count; expired/foreign sessions not resumable |
| `tests/test_phase2_access.py` (6) | anonymous legacy start + guest read/report; block start 401 without auth; cross-user candidate 403; draft/preset/bank/preview 401s; preset 404 + draft isolation cross-user |

New frontend tests (9): availability helpers + notice summary
(`practiceBuilder.test.js`), block labels/metrics, blended vs single
rendering, zero-vs-null (`dashboardMapping.test.js`).

## 4. Phase-boundary verification (this run)

```
.venv/bin/python -m pytest tests/ -q
→ 626 passed, 1 skipped, 81 warnings in 105.98s
  (593 baseline + 33 new; the skip is the inherited semantic-model path)

docs/human_baseline_report.md sha256 unchanged across the suite:
eb69fdb59cbf35250bdfe96492ba6b37fe8ac4bce9994fd71f25d57c65d3d2ea

.venv/bin/python scripts/scoring_regression.py
→ 6 PASS, 2 FAIL (known, unchanged: gibberish→repetition,
   keyword_stuffing→gibberish)

.venv/bin/python scripts/replay_scorer_v1_baseline.py
→ Replay matched 8 frozen items and asset hashes.

cd frontend && npm test -- --run
→ # tests 94 / # pass 94 / # fail 0 (85 baseline + 9 new)

frontend tsc --noEmit → exit 0
frontend production build → ✓ built (inherited chunk-size warning only)
```

End-to-end: the four standalone journeys, Verbal → SQL → Interview,
and repeated OA with different topics are exercised start → answer →
submit → completion → report through the API (TestClient), plus
refresh/resume, duplicate-submission, caps, unavailable-inventory,
null-score, and ownership-failure paths. A live-server browser pass
was attempted and blocked by the sandbox (`bind ... operation not
permitted`, same boundary as Phase B/Z); no browser rendering is
claimed.

## 5. Flags (production activation still blocked)

| Flag | Default | Wired? | Active? |
| --- | --- | --- | --- |
| `REVIEWED_BUNDLES_ONLY` | false | yes (selection + availability) | **no** |
| `EXPERIMENTAL_CONCEPT_EVALUATOR` | false | unchanged | no |
| `LENGTH_RATIO_MULTIPLIER_ENABLED` | false | unchanged | no |
| `LLM_LIVE_FETCH` | unchanged | unchanged | not enabled here |

## 6. Remaining blockers before activation / Phase 3

- Real human reviews (0 reviewed bundles); synthetic reviewed records
  exist in isolated tests only.
- Browser-rendered verification of the new availability notice and
  per-block cards (unit + API evidence only this run).
- Interview topic selection UX: explicit sub-domain pins are strict,
  but Practice offers no topic picker (standalone interview selects
  skills only). Product follow-up, not a Phase 2 defect.
- Held-out n=50 assets / form workbook still absent from this tree.
- Hint-coach comparison study not run; stock coding coach unchanged.

## 7. Confirmations

- No push, merge, deploy; local checkpoint commits only (§8).
- No scorer / protected-pipeline edits; no scoring changes.
- No hint-coach import; no model training/replacement; no fabricated
  reviews; no new follow-ups.
- `REVIEWED_BUNDLES_ONLY` still off; experimental evaluator disabled.
- Tree 2, Phase 0, Phase 1A, Phase 1B, coding-practice, and phase-b
  worktrees untouched (Phase 1B tip re-verified: `a5b7492`).

## 8. Completion addendum — interview topic selection (checkpoint)

Content checkpoint: `cc77372c4d3ee1d544b302cd2f662a99e0df96b1`
(backend, frontend, tests, and docs complete at this commit; this
record added by the tip commit).

### Topic-picker behavior

- Standalone Interview and every Interview block in the custom builder
  offer an optional Topic dropdown scoped to the selected skills
  (union, case-insensitive) from `GET /session/practice-bank`
  `interview_topics`: skill → topic names from the same cached
  structured-bank rows runtime selection filters first. Names only;
  no questions, references, or grading content cross.
- Default "All topics" omits the field (unrestricted); the client
  never sends a literal `"general"` pin, and the server maps the
  reserved default to unrestricted everywhere.
- Explicit topics are per-block: repeated Interview blocks keep
  independent topics through start, progression, drafts, presets, and
  resume (JSON plan columns; no migration). Older configurations
  without the field validate, save, and start unchanged.
- Changing skills clears a topic the new skills no longer offer, with
  a visible note; stale saved topics reconcile the same way when
  metadata loads. A failed metadata load degrades to unrestricted
  without destroying selections.
- Server contract: `Block.topic` (interview only, ≤120 chars) becomes
  the round's recorded sub-domain and guides legacy selection;
  gate-ON reviewed pins are strict per skill (422, no substitution).
  Legacy relaxation within the skill is unchanged (protected
  selection code untouched); rounds always record what was served.

### Verified topic journeys (API)

- Standalone DBMS/transactions: probe available → start → exact topic
  served → submit → complete → report retains the topic.
- OA → Interview[transactions] → SQL completes in order with the
  interview round pinned.
- Repeated Interview[transactions] + Interview[joins]: distinct ids,
  each round serves its own block's topic.
- Gate ON (isolated): matching pin selects the pinned bundle;
  `Sockets` pin → probe unavailable + start 422 naming Sockets, no
  session write, no substitution; literal `"general"` stays
  unrestricted; difficulty pins checked per skill.
- Draft/preset round-trips preserve topics; topic-less legacy drafts
  still work; availability and start agree on identical bodies.

### Final verification (this run)

```
.venv/bin/python -m pytest tests/ -q
→ 637 passed, 1 skipped, 85 warnings in 112.86s
  (626 prior + 11 topic tests; the skip is inherited)

.venv/bin/python scripts/scoring_regression.py → 2/8 failed
  (same two known guard-label mismatches; unchanged)

.venv/bin/python scripts/replay_scorer_v1_baseline.py
→ Replay matched 8 frozen items and asset hashes.

docs/human_baseline_report.md sha256 (unchanged):
eb69fdb59cbf35250bdfe96492ba6b37fe8ac4bce9994fd71f25d57c65d3d2ea

cd frontend && npm test -- --run → 100/100 pass
tsc --noEmit → exit 0; production build → ✓ built
```

TestClient/API suites do not verify rendered UI (stated, not implied).

### Browser verification: PENDING (environment)

No browser tooling is installed and the sandbox rejects binds, so no
rendered pass was possible. Pending QA steps for a local machine:

```bash
# Terminal 1 — backend (in-memory DB; disposable data)
cd ".worktrees/cursor-ai-design-phase2/interViv_best"
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 JOBS_LIVE_FETCH=0 LLM_LIVE_FETCH=0 \
QUESTION_GENERATION_MODE=csv QUESTION_REQUIRE_LLM=false \
OPENAI_API_KEY= OPENROUTER_API_KEY= \
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — frontend (proxies /api → :8000)
cd ".worktrees/cursor-ai-design-phase2/interViv_best/frontend"
npm run dev -- --host 127.0.0.1
# open http://127.0.0.1:5173 — sign up a throwaway account
```

1. `/practice?mode=interview`, skills `DBMS`: topic dropdown lists
   bank topics; pick `transactions`, start, answer, submit, open the
   report; confirm the block retained the topic.
2. Change skills to `OOP`: confirm the DBMS topic clears with the
   visible note; pick an OOP topic and start.
3. `mode=custom`: two Interview blocks (DBMS/transactions,
   DBMS/joins); confirm independent topics, order, and per-block
   report cards with no blended overall.
4. Request an unsatisfiable MCQ count (OA/OOP/15): confirm the
   availability notice names found/need and starts nothing.
5. Keyboard-only run of add/select/start/submit; 375px and desktop
   widths; sign out from Account and confirm per-account drafts.
6. Stop both servers with Ctrl+C.

### Remaining activation dependencies

- Real human reviews (0 reviewed bundles); reviewed topics stay
  test-synthetic until then.
- Rendered browser QA of the notice, topic picker, and per-block
  cards (steps above).
- Held-out n=50 assets / form workbook still absent from this tree.
- Hint-coach comparison not run; stock coach unchanged.
- Candidate-row note: a build-time 422 after candidate creation
  (e.g., adaptive difficulty mismatch under the gate) can leave a
  session-less candidate row — same as pre-existing generation
  failures; sessions are never written on failure.
