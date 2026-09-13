# Phase 0 implementation report

First authorized Cursor execution of the interViv implementation plan. **Stop before Phase 1.**

## 1. Location and commits

| Item | Value |
| --- | --- |
| Worktree | `/Users/praneetsharma/Downloads/mega 2 copy/.worktrees/cursor-ai-design-phase0` |
| App root | `interViv_best/` |
| Branch | `phase0/cursor-ai-design` |
| Base | `6659feda31b2f27d687f609d59e397911285a6ff` (`codex/unify-shell`) |
| Merge-base vs phase-b | `d9924d6` |
| Phase B source | `cc905cfc7eb6da7b43b022ece213fc16be141b92` (selective port, not cherry-pick) |
| Runtime | Python 3.12.4 via symlinked `.venv`; Node v22.16.0; frontend `node_modules` symlink from coding-practice |
| Tag | `baseline/unify-shell-6659fed` → `6659fed` only (not moved) |

Commits on this branch (oldest first):

1. `81f3dc9` `docs(phase0): freeze unify-shell v1 scoring baseline at 6659fed`
2. `1b861ad` `fix(phase-ab): port Z-F03/Z-F02/Z-F01 onto unify-shell`
3. `dceb9e2` `fix(phase0): camera attach, branding, dashboard home, resource empty states`
4. `ec18028` `fix(phase0): include company/role in question cache; disclose health modes`
5. (docs + held-out pointer + in-suite hash skip for `human_baseline_report.md`)

No push. No merge to main. Tree 2 (`ticket-f/integrate-demo` @ `13ac259`, dirty) and source worktrees `.worktrees/coding-practice` (`6659fed`) and `.worktrees/phase-b-block-practice` (`cc905cf`) were not reset, cleaned, stashed, or committed.

## 2. What changed / user behavior

### Already on unify-shell (not redone)

Coding coach helpers, coding submit `language` without engagement fields, media gate treating coding as non-camera, `CodingRound key={`${sessionId}:${round}`}`, hamburger AppNav without profile/sign-out, resources `limit_per_level`, Piston/Gemma. `/dashboard` already routes to Progress with authenticated `GET /dashboard/progress`.

### A. Baseline freeze (before ports)

Captured flags: `LENGTH_RATIO_MULTIPLIER_ENABLED` **off**; semantic runtime **full** (MiniLM `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`); `LLM_LIVE_FETCH=0`. Artifacts under `data/baselines/v1/` and `tests/fixtures/scorer_v1_baseline.json` (append-protected). See `docs/phase0_baseline_report.md` and `docs/scorer_versions.md`.

### B. Phase AB port

- **Z-F03:** builder draft keyed per account; unscoped keys cleared on signin/signup/signout.
- **Z-F02:** null average renders as Not measured, not 0.
- **Z-F01:** SQLite timestamps restored with UTC tzinfo; technical `02:00` header only on `technical_short_answer`.

Unify `Interview.jsx` / `api.js` were merged, not overwritten.

### C. Remaining Phase 0 fixes (confirmed still present, then fixed)

| Issue | Finding | Fix |
| --- | --- | --- |
| Camera after calibration | One `videoRef` on two mutually exclusive `<video>`s | `attachVideoEl` callback ref + reattach effect |
| Title / Velorah / fonts | `Velorah Interview Studio`; hardcoded Inter / Instrument Serif while body uses CSS vars | Title `interViv`; `var(--font-body)` / `var(--font-display)`; Tailwind tokens use those vars. Google Fonts CDN stays off |
| Dashboard placeholders | Progress already real; dead `DashboardHome` still showed 0/8/8/13 catalog counts; session Back to Home went to `/`; missing `sessionId` first-painted a dark spinner | Reuse `fetchAccountOverview()`; Back to Home → `/home`; `useState(Boolean(sessionId))`. No new sessions endpoint |
| Blank resources | `ResourceLinks` returned null without `emptyMessage` | Always show loading / error / one-line empty |
| Question cache | Key omitted company/role (and other prompt inputs) | v2 key includes company, role, resume_skills, weak_skills |
| Health | Scoring mode only | `question_source` configured vs effective; **mode not changed** |

### Held-out

`docs/track2_heldout_protocol.md` is on this branch. Ratings file absent. `scripts/evaluate_length_ratio_heldout.py` prints `HELD_OUT_ABSENT`. Flag stays off.

## 3. Tests

### Phase-boundary (after ports and C)

**`.venv/bin/python -m pytest tests/ -q`** (after in-suite hash skip for `human_baseline_report.md`):

```
564 passed, 1 skipped, 67 warnings in 90.79s (0:01:30)
```

Exit 0. The skip is the existing semantic-model marker path. An earlier full run on the same tree failed `test_v1_sha256sums_match_working_tree` because `test_change5_baseline` rewrites `docs/human_baseline_report.md` in-process; that is a known suite side effect, not a scorer change. The in-suite hash check now skips that one path. Isolated hash tests after `git restore`: **2 passed**. Replay after restore still hashes the committed report bytes.

After pytest: restored `docs/human_baseline_report.md` → 230 lines, MD5 `5421f9f0fd6efad395666c545e5cf76a`.

**`.venv/bin/python scripts/scoring_regression.py`** (after C; identical to capture):

```
excellent                91.39 PASS
paraphrase               49.62 PASS
partial                  56.10 PASS
empty                     5.00 empty PASS
gibberish                 6.06 guard=repetition expected gibberish FAIL
excessive_repetition      8.40 PASS
keyword_stuffing         10.00 guard=gibberish expected keyword_stuffing FAIL
off_topic                12.50 PASS
2/8 case(s) failed.
```

Pre-existing unify-shell guard-label mismatches. Frozen, not retuned.

**`npm test` in `frontend/`:**

```
# tests 85
# pass 85
# fail 0
```

Capture had 54 pass / 1 fail (`interviewMediaGate` monaco ESM). The media-gate test now stubs `codingEditor.js` (same as the AB timer tests). Five new `phase0Shell` checks. AB frontend tests were already on the branch.

**Targeted after C (before full pytest):** `test_task8_hardening`, `test_phaseQ_llm_gate`, `test_phaseG_honesty`, `test_scorer_v1_baseline_hashes`, `test_adaptive_selector`, `test_phaseAB_deadlines_and_report` → **50 passed**.

**`.venv/bin/python scripts/replay_scorer_v1_baseline.py`:**

```
asset hashes: 25 files, 0 mismatch(es)
excellent 91.39 OK; paraphrase 49.62 OK; partial 56.1 OK; empty 5.0 OK
gibberish 6.06 guard=repetition OK; excessive_repetition 8.4 OK
keyword_stuffing 10.0 guard=gibberish OK; off_topic 12.5 OK
Replay matched 8 frozen items and asset hashes.
```

**`.venv/bin/python scripts/evaluate_length_ratio_heldout.py`:** `HELD_OUT_ABSENT` (exit 0).

Live camera, signed-in Home, and dashboard click-through were **not** run (no servers). Unavailable this run, not counted as passing.

## 4. Baseline reproducibility

| Claim | Status |
| --- | --- |
| Protected scoring blobs vs `6659fed` | Unchanged this phase (and were identical to `cc905cf` at inspection) |
| `LENGTH_RATIO_MULTIPLIER_ENABLED` | Off at capture and after C |
| Semantic mode | full |
| LR joblib sha256 | `2897c8cc6283cbdb4815a78182188ea60c17b39876feefa2d67919f065f16dd7` |
| Pipeline sha256 | `d07c790c88738d6385a11c40859b78310267bfd4ea71f930ae212dc94fdd1c8d` |
| Fixture | `tests/fixtures/scorer_v1_baseline.json` append-protected; not regenerated |
| Historical r=0.730 / κ=0.29 | Report claims in `human_baseline_report.md` until reproduced |
| n=50 form workbook / `verify_baseline_v2.py` | Not on this branch; not copied from Tree 2 |

No scorer promotion. No new formulas, weights, thresholds, or guards.

## 5. Confirmed vs already-fixed

**Confirmed present on unify-shell, then fixed:** camera ref, Velorah title, unused Inter fonts, session Back to Home `/`, DashboardHome catalog placeholders, loading flash when `sessionId` missing, ResourceLinks blank embeds, question cache missing company/role, health silent on question-source.

**Already fixed on unify-shell (left alone):** Progress `/dashboard` user-scoped history; coding media/Piston/Gemma; hamburger nav; `limit_per_level`.

**Ported from `cc905cf`:** Z-F03 / Z-F02 / Z-F01 plus tests.

**Not in scope / not done:** Interview Exit still goes to `/` (Landing). No `GET /dashboard/me/sessions`. No hint-coach. No rubric. No live-LLM enablement.

## 6. Remaining blockers / Phase 1 dependencies

- Human review of bundles and concept/rubric work (Phase 1). Engineering Phase 0 does not count as reviewed content.
- Held-out ratings file (`data/baseline_v2_heldout_ratings.xlsx|csv`) from real raters. Until then, length-ratio flag stays off.
- Form-response workbook if anyone needs to reproduce n=50 headline figures; missing here.
- Live camera/browser pass when a disposable frontend is running.
- Pre-existing scoring_regression guard-label fails (do not retune in Phase 1 unless that phase explicitly authorizes scoring work).
- Do not import Tree 2 `modules/hint_coach.py` or fine-tuned weights as incidental cleanup.

Phase 1 release dependencies (immutable bundles, human review tools, no draft scoring) are **not** met. That is expected.

## 7. Confirmations

- No `git push`
- No merge to main
- No scorer promotion
- No `LLM_LIVE_FETCH` / question-generation mode change
- No hint-coach
- Tree 2 and source worktrees untouched
- Protected scoring paths not edited
