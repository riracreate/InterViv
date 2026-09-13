# AI design status

Living phase tracker for the Cursor implementation plan. This is not a chat log.

| Phase | Status |
| --- | --- |
| 0 Verify, freeze, fix, report | **Verified** on `phase0/cursor-ai-design`. Stopped before Phase 1. |
| 1 Reviewed bundles / concept foundation | Deferred |
| 2 Standalone and composed practice | Deferred |
| 3 Persistence, feedback, shared UI | Deferred |
| 4 Follow-ups, assistance policies | Deferred |
| Research Completeness / evaluation | Deferred; held-out ratings absent |

Status vocabulary: implemented, verified, blocked by environment, awaiting real human review, deferred. Synthetic tests are not human or live-provider validation.

## Phase 0

| Item | Status | Evidence |
| --- | --- | --- |
| Worktree from unify-shell `6659fed` | verified | `.worktrees/cursor-ai-design-phase0`, branch `phase0/cursor-ai-design` |
| v1 scoring baseline freeze | verified | `81f3dc9`, tag `baseline/unify-shell-6659fed` → `6659fed` only |
| Selective port of `cc905cf` (Z-F03/Z-F02/Z-F01) | verified | `1b861ad`; not a wholesale cherry-pick |
| Camera stream after calibration | implemented | callback ref + reattach effect; static tests pass; **live camera not exercised in a browser this run** |
| Typography / interViv title / Velorah chrome | verified | `index.html` title `interViv`; CSS variables; `npm test` phase0Shell |
| Dashboard user-scoped stats | implemented | `/dashboard` already uses `GET /dashboard/progress` (Progress page). Session report Back to Home → `/home`. Dead `DashboardHome` placeholders replaced; no new `/dashboard/me/sessions` |
| Resource empty states | verified | `ResourceLinks` always shows loading/error/empty |
| Question cache company/role | verified | `interviv:question:v2:` keys; pytest |
| Health configured vs effective question source | verified | `GET /health` `question_source`; mode not changed |
| Held-out workflow pointer | implemented | `docs/track2_heldout_protocol.md`; evaluator prints `HELD_OUT_ABSENT` |
| Frozen score replay | verified | `scripts/replay_scorer_v1_baseline.py` matched 8 items |
| Live camera / signed-in dashboard click-through | blocked by environment | no app servers started this run |
| Held-out ratings / n=50 form reproduction | awaiting real human review | ratings file and form workbook absent |
| Hint-coach / new rubric / bundle review | deferred | Phase 1+; Tree 2 WIP not imported |
| Scorer promotion / length-ratio flag | deferred | flag stays off; 2/8 guard-label mismatches frozen, not retuned |

### Decisions

- Selective merge of Phase B into unify-shell, preserving coding/Piston/Gemma, coding media gate, `limit_per_level`, hamburger AppNav without profile/sign-out.
- Reuse `GET /dashboard/progress` rather than add `GET /dashboard/me/sessions`.
- Question cache v2 prefix so Redis/memory entries cannot mix with v1 keys.
- Health discloses `llm_gated_off` when mode is `llm` and `LLM_LIVE_FETCH=0`; runtime mode unchanged.
- `7498cdb` Tree-2-inventory doc skipped; AA noted as historical other-checkout in `review_guide.md`.
- In-suite hash check skips `docs/human_baseline_report.md` because `test_change5_baseline` rewrites it; replay after `git restore` still hashes committed bytes.

### Acceptance this run (not human validation)

- pytest `564 passed, 1 skipped` (after hash-test skip); scoring_regression (same 2/8 guard-label fails as capture); npm test `85 passed`; v1 replay matched 8 items; held-out evaluator `HELD_OUT_ABSENT`.
- No push, merge, scorer promotion, live-LLM gate change, or hint-coach import.
