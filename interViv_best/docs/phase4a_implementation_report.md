# Phase 4A implementation report

Assistance tracking, assessment eligibility, and bounded optional follow-ups.

| Item | Value |
| --- | --- |
| Branch | `phase4a/assistance-followups` |
| Worktree | `.worktrees/cursor-ai-design-phase4a` |
| Base | `e591f0b9f0cf637d707aff516f6da054751c0483` (Phase 3C tip) |
| Final tip | `62a74bad1f8f4ba8c2b0881db9cf3d8786ca18cc` |
| Ancestors verified | Adzuna `c498d6fe…`, Phase 3B `379007314…` |
| App root | `interViv_best` |

## What shipped

1. **Teaching exposures** — `teaching_exposures` table + memory collection; idempotent `delivery_id`; dual-write to Phase D `assistance_events` for owned accounts. Wired through learning hints, coding coach, and feedback reveal (GET stays progression-read-only).
2. **Versioned eligibility** — `assistance_v1` frozen at submission acceptance (`modules/assistance_policy.py`). Follow-ups + same-item retries always excluded; related items use same-session + 24h owned cross-session window; incomplete history → unknown; legacy rows → `legacy_unknown`.
3. **Primary metric gating** — shared gate at Elo commit, learning-state updates, readiness mean, block averages, skill-graph SQL mean. Scoring formulas untouched.
4. **Optional follow-ups** — `POST /session/{id}/follow-ups`; caps 1/parent, 2/Interview block; capacity vs `MAX_TOTAL_ROUNDS=50`; unreviewed → null score even with `REVIEWED_BUNDLES_ONLY=false`.
5. **UI** — Practice mode (Assessment / Coached practice) + follow-up opt-in; Interview follow-up request with eligibility confirm; report labels via `eligibilityPracticeLabel`.

## Schema / rollback

Migration `20260917_0014`. Downgrade target: `20260915_0013` (drops exposures + eligibility columns; Phase D events remain).

## Gates (unchanged / off)

`REVIEWED_BUNDLES_ONLY=false`, experimental concept evaluator off, live narration/question-gen off, Adzuna live fetch off.

## Verification (this run)

| Check | Result |
| --- | --- |
| `pytest tests/test_phase4a_assistance.py tests/test_phase4a_sql_persistence.py` (+ 3A/3B/3C/2/Adzuna slice) | 53 passed |
| `pytest` 3A persistence + Phase D + 1B + scorer hashes | 36 passed |
| `scripts/scoring_regression.py` | 6 PASS / 2 FAIL (`gibberish`, `keyword_stuffing` — known) |
| `docs/human_baseline_report.md` SHA-256 | `eb69fdb59cbf35250bdfe96492ba6b37fe8ac4bce9994fd71f25d57c65d3d2ea` |
| `scripts/replay_scorer_v1_baseline.py` | 8/8 matched; 0 asset mismatches |
| Frontend `tsc --noEmit` | pass |
| `npm run build` | pass |
| Frontend unit tests | 118 pass / 0 fail |
| Migration upgrade/downgrade | covered in `test_phase4a_sql_persistence.py` (disposable SQLite) |

## Inventory limitation

0 human-reviewed bundles. Optional follow-ups use clarification / unscored path only. No production draft approvals.

## Browser QA (pending — carry-forward from 3C)

Rendered acceptance not claimed. Manual checklist (~400px / ~1280px, keyboard):

- [ ] Practice: Assessment vs Coached practice; follow-up checkbox disabled in Assessment
- [ ] Interview: hint/help labels; optional follow-up confirm; eligibility label after submit
- [ ] Report: eligible average vs Practiced with help; no fabricated zero when only assisted
- [ ] Phase 3B: content_blocked continue; after_session MCQ keys only when completed
- [ ] Adzuna Jobs Prepare → practice handoff; camera/timer/polling preserved
- [ ] Refresh/resume mid-session with scheduled follow-up

## Stop line

Phase 4A complete for engineering verification. No roadmap/coach expansion, no push/merge/deploy, no scorer promotion, no fabricated reviews.
