# AI design status

Living phase tracker for the Cursor implementation plan. This is not a chat log.

| Phase | Status |
| --- | --- |
| 0 Verify, freeze, fix, report | **Verified** on `phase0/cursor-ai-design`. Stopped before Phase 1. |
| 1A Reviewed-bundle infrastructure | **Implemented + verified (engineering)** on `phase1a/reviewed-bundles`; **awaiting real human review** (0 bundles reviewed). |
| 1B Concept evaluator / reference contract | **Implemented + verified (engineering)** on `phase1b/reviewed-evaluator`; gate OFF; **awaiting real human review**. Stopped before activation and Phase 2. |
| 2 Standalone and composed practice | **Implemented + verified (engineering)** on `phase2/modular-practice`; gates OFF; **awaiting real human review**. Stopped before activation and Phase 3. |
| 3 Persistence, feedback, shared UI | **3A + 3B + 3C implemented** on `phase3c/ui-reports`; gates OFF; live narration off |
| 4 Follow-ups, assistance policies | **4A implemented + verified (engineering)** on `phase4a/assistance-followups`; gates OFF; browser QA pending |
| Research Completeness / evaluation | Deferred; held-out ratings absent |

Status vocabulary: implemented, verified, blocked by environment, awaiting real human review, deferred. Synthetic tests are not human or live-provider validation.

## Phase 0

See prior checkpoint on `phase0/cursor-ai-design`. Frozen v1 baseline, selective Phase B ports, UI/data fixes. Scorer not promoted. Hint-coach not imported.

## Phase 1A

Design: `docs/phase1a_reviewed_bundles.md`. Bundle tables, immutable versions, admin review routes, selector (unwired in 1A), pilot v1 drafts with empty concepts. `REVIEWED_BUNDLES_ONLY` default false and not wired because technical `question_context` leaked `ideal_answer`.

## Phase 1B

Design and evidence: `docs/phase1b_implementation_report.md`,
`docs/gemma_hintcoach_inventory.md`, `docs/phase1b_human_review_checklist.md`.
Worktree `.worktrees/cursor-ai-design-phase1b`, branch `phase1b/reviewed-evaluator`,
base `3170eabb7b555a9f4c1606942ea786802b591f27` (Phase 1A tip).

| Item | Status | Evidence |
| --- | --- | --- |
| Technical `question_context` allowlist (no pre-answer reference material) | verified | serializer + `tests/test_phase1b_reference_and_evaluator.py` |
| Server-side pin resolve for scoring; hash mismatch → unavailable | verified | `modules/bundle_scoring.py` |
| `REVIEWED_BUNDLES_ONLY` wired; default OFF; ON + empty → unavailable | verified | `_get_next_question` + selector tests |
| Frozen `docs/human_baseline_report.md` not rewritten by pytest | verified | `--output` to tmp; hash test covers report |
| Pilot v2 concept/rubric drafts (12); v1 preserved; all draft | implemented | 24 draft versions on import |
| Experimental `concept_evaluator_v2` (gated; isolated) | verified | module + tests; not imported by scoring/mastery |
| Gemma 2 hint-coach read-only inventory | verified | `docs/gemma_hintcoach_inventory.md`; not imported |
| Production reviewed-only activation | deferred | gate stays false |
| Real human reviews | awaiting real human review | 0 reviewed |
| Hint-coach integration / Phase 2 | deferred | not started |

### Decisions

- Persist legacy ideal answers on the server round for scoring, but never deliver them pre-answer; reviewed rounds persist identity only and resolve at score time.
- Experimental evaluator uses conservative whole-word proposition windows; quoting a misconception then correcting it must not auto-fail the later claim.
- v2 authorship is developer-labelled (`phase1b-dev:concept-authorship`), not human review.

### Acceptance this run (not human validation)

- See phase-boundary command output in `docs/phase1b_implementation_report.md` (filled after suites).
- No push, merge, deploy, scorer promotion, flag activation, or hint-coach import.

## Phase 2

Design and evidence: `docs/phase2_implementation_report.md`.
Worktree `.worktrees/cursor-ai-design-phase2`, branch `phase2/modular-practice`,
base `a5b7492f584215c2f6991c74addeaa0dc5ce2032` (Phase 1B tip).

Reused without rebuilding: block contract (`MAX_BLOCKS`/`MAX_TOTAL_ROUNDS`
preserved), Practice builder, session lifecycle, round components, dashboard
API shape (additive fields only). No new follow-ups; no scoring changes.

| Item | Status | Evidence |
| --- | --- | --- |
| Standalone Verbal / OA / SQL / Interview journeys | verified | `tests/test_phase2_standalone.py` (4 completions + reports) |
| Composed order incl. repeated OA, stable identities | verified | Phase B suites + `tests/test_phase2_reports.py` |
| Server caps (10 blocks / 50 rounds) | verified | standalone caps tests + availability shape test |
| Refresh/resume/duplicate-submission reliability | verified | `tests/test_phase2_resume.py` + Phase B.1/AB suites |
| `POST /session/availability` pre-commit probe (no writes) | verified | `tests/test_phase2_availability.py` (11) |
| Gate OFF + zero reviewed → legacy practice unaffected | verified | availability + standalone suites |
| Gate ON (isolated) → clear pre-commit unavailable, no writes, no silent switch | verified | availability suite incl. pin/exhaustion cases |
| Pre-start availability notice in Practice | verified | `summarizeAvailability` + mapping tests; tsc + build |
| Per-block reports (own metric, attempted/scored/unscored) | verified | reports suite + `dashboardMapping` tests |
| No blended overall for mixed sessions; legacy rendering preserved | verified | mapping tests + additive API fields |
| Access matrix (anonymous start, 401/403, isolation) | verified | `tests/test_phase2_access.py` (6) + existing matrices |
| Per-block interview topics (picker, metadata, strict pins) | verified | `tests/test_phase2_topics.py` (11) + builder helper tests |
| Keyboard/mobile usability of required flows | verified | inspection + aria-label fixes; no drag-only or hover-only paths |
| `REVIEWED_BUNDLES_ONLY` / experimental evaluator activation | deferred | gates stay false |
| Real human reviews | awaiting real human review | 0 reviewed |
| Browser-rendered e2e | blocked by environment | sandbox bind rejected; API journeys + unit suites instead |

### Decisions

- Availability failures are 422 with the selector's message (unsatisfiable
  content under the pinned policy), never 503 and never a silent switch.
- The legacy `general` sub-domain does not pin reviewed selection; only an
  explicit non-default sub-domain narrows by topic, and that pin is strict.
- Mixed-metric sessions show per-block cards and no single overall
  percentage; single-block and legacy sessions render exactly as before.
- No unscored-practice alternative is offered under reviewed-only
  unavailability (none is supported); the outcome is a clear notice, and
  nothing is started or consumed.
- Interview topics are per-block pins from served-bank vocabulary;
  unrestricted omits the field (never `"general"`); legacy relaxation
  within the skill is unchanged and rounds record what was served.

### Acceptance this run (not human validation)

- See phase-boundary command output in `docs/phase2_implementation_report.md`.
- No push, merge, deploy, scorer promotion, flag activation, hint-coach
  import, or production activation.

## Phase 3A / 3B / 3C

- **3A** tip: `3c073a5` — atomic start/attempt, snapshots, narration jobs, topic contract.
  Report: `docs/phase3a_implementation_report.md`. Rollback: `alembic downgrade 20260913_0010`.
- **3B** branch `phase3b/feedback-delivery` tip `3790073` (verification `89f22bb`).
  Ownership-consistent answer/continue/feedback; disclosure timing; blocked continue;
  snapshot v2 provenance; allowlisted feedback + validator + fake provider; Interview poll.
  Report: `docs/phase3b_implementation_report.md`. Migration `20260915_0013`.
- **Adzuna** on `jobs/adzuna-integration` tip `c498d6f` (merged onto 3B).
  Report: `docs/adzuna_integration_report.md`.
- **3C** branch `phase3c/ui-reports` in `.worktrees/cursor-ai-design-phase3c`.
  Hub consistency (Jobs/Gap/Roadmap), Interview media gate + deadline notice + collapsible camera,
  dashboard MCQ review under completed+after_session, report presentation polish.
  Report: `docs/phase3c_implementation_report.md`.
  Gates remain off; no Phase 4.

## Phase 4A

Branch `phase4a/assistance-followups`, worktree `.worktrees/cursor-ai-design-phase4a`,
base `e591f0b9` (Phase 3C), tip `62a74ba`. Policy: `docs/phase4a_assistance_policy.md`.
Report: `docs/phase4a_implementation_report.md`. Migration `20260917_0014`.

Teaching exposures, versioned eligibility (`assistance_v1`), primary-metric
gating, bounded optional follow-ups, focused Practice/Interview/report UI.
Gates remain off; 0 reviewed bundles → unscored clarification follow-ups only.
Browser-rendered QA pending (checklist in 4A report). Stopped before roadmap/coach.
