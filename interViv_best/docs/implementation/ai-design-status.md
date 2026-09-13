# AI design status

Living phase tracker for the Cursor implementation plan. This is not a chat log.

| Phase | Status |
| --- | --- |
| 0 Verify, freeze, fix, report | **Verified** on `phase0/cursor-ai-design`. Stopped before Phase 1. |
| 1A Reviewed-bundle infrastructure | **Implemented + verified (engineering)** on `phase1a/reviewed-bundles`; **awaiting real human review** (0 bundles reviewed). Stopped before evaluator and activation. |
| 1B Concept evaluator / rubric v2 | Deferred |
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

## Phase 1A

Design and evidence: `docs/phase1a_reviewed_bundles.md`. Worktree
`.worktrees/cursor-ai-design-phase1a`, branch `phase1a/reviewed-bundles`, base `0c259c1`.

| Item | Status | Evidence |
| --- | --- | --- |
| Alembic `20260913_0010`: `question_bundles`, `question_bundle_versions`, `bundle_review_decisions`, `bundle_status_audit` | verified | upgrade/import/re-import/downgrade on disposable SQLite; `test_phase1a_bundles.py` migration + constraint tests |
| Immutable versions (no content update path; DB uniqueness on version and hash) | verified | store tests on memory and SQLite |
| Canonical YAML under `data/question_bundles/<skill>/` (PyYAML already in `requirements.txt`) | implemented | validator rejects review-state keys in YAML |
| Import CLI `scripts/import_question_bundles.py` (idempotent; same-version/other-hash rejected; new content = new draft) | verified | 12 created → 12 unchanged on re-run; conflict tests |
| Pilot drafts: Python 2/2/2, DBMS 2/2/2 from `interview_dataset_v6.csv` (`imported_csv`, verbatim, source lines recorded) | implemented | all `draft`; empty concept lists by design |
| Admin review routes (`ENABLE_ADMIN_ENDPOINTS` + `ADMIN_USER_EMAILS`; reviewer id from token; blind view; two independent decisions; adjudication; retire; history) | verified | route tests 401/403/404/409/422; router absent by default |
| Evidence rejection: author≠reviewer, stale hash, placeholder/incomplete checklist or reasons, missing blind calibration, duplicate reviewer, approve without required_concepts | verified | store + route tests |
| Evaluation overlap (`baseline_v2_key`, n=50 form subset, `human_baseline_real_combined`): exact reject, paraphrase flag | verified | importer test; two pilot candidates dropped for paraphrase flags |
| `GET /admin/bundles/inventory` (reviewed by skill/topic/difficulty; drafts separately) | verified | route test |
| `modules/bundle_selector.py` rejects draft/in_review/rejected/retired; candidate payload has no reference material | verified | selector + payload tests |
| `REVIEWED_BUNDLES_ONLY` flag | implemented, **not wired** | default off; activation blocked by round-contract reference leak (see phase doc) |
| Any bundle reviewed | **awaiting real human review** | 0 reviewed; workflow ready |
| Concept evaluator / rubric v2 | deferred | Phase 1B |
| Admin UI page | deferred | backend + CLI prioritised |
| n=50 form workbook / `verify_baseline_v2.py` | blocked by environment | Tree 2 untracked only; inspected read-only, not imported |

### Decisions

- Version number is not part of the content hash, so identical content re-numbered is caught by `UNIQUE(bundle_id, content_hash)`.
- Admin identity is an env allowlist of signed-up user emails rather than a new `users` column; no schema change to `users`.
- Approval requires non-empty `required_concepts`; the CSV-derived pilot cannot be approved until a v2 authors them.
- Selector hook into `_get_next_question` deliberately not added: `sanitize_round_for_client` passes technical `question_context` (with `ideal_answer`) through, so activation needs the round to store a bundle reference first.
- `tests/test_phaseX_persistence.py` head assertion and downgrade target updated to name `20260908_0009` per `tests/alembic_helpers.py` convention (it had used `"head"`).

### Acceptance this run (not human validation)

- pytest `583 passed, 1 skipped`; scoring_regression same 2/8 guard-label fails; v1 replay matched 8 items and asset hashes; `npm test` not run (frontend unchanged).
- No push, merge, deploy, scorer change, flag activation, live-LLM gate change, or hint-coach import. Tree 2, source worktrees, and the Phase 0 checkpoint untouched.
