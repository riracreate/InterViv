# AI design status

Living phase tracker for the Cursor implementation plan. This is not a chat log.

| Phase | Status |
| --- | --- |
| 0 Verify, freeze, fix, report | **Verified** on `phase0/cursor-ai-design`. Stopped before Phase 1. |
| 1A Reviewed-bundle infrastructure | **Implemented + verified (engineering)** on `phase1a/reviewed-bundles`; **awaiting real human review** (0 bundles reviewed). |
| 1B Concept evaluator / reference contract | **Implemented + verified (engineering)** on `phase1b/reviewed-evaluator`; gate OFF; **awaiting real human review**. Stopped before activation and Phase 2. |
| 2 Standalone and composed practice | **Implemented + verified (engineering)** on `phase2/modular-practice`; gates OFF; **awaiting real human review**. Stopped before activation and Phase 3. |
| 3 Persistence, feedback, shared UI | Deferred |
| 4 Follow-ups, assistance policies | Deferred |
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
