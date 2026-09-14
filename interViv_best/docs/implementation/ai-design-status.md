# AI design status

Living phase tracker for the Cursor implementation plan. This is not a chat log.

| Phase | Status |
| --- | --- |
| 0 Verify, freeze, fix, report | **Verified** on `phase0/cursor-ai-design`. Stopped before Phase 1. |
| 1A Reviewed-bundle infrastructure | **Implemented + verified (engineering)** on `phase1a/reviewed-bundles`; **awaiting real human review** (0 bundles reviewed). |
| 1B Concept evaluator / reference contract | **Implemented + verified (engineering)** on `phase1b/reviewed-evaluator`; gate OFF; **awaiting real human review**. Stopped before activation and Phase 2. |
| 2 Standalone and composed practice | Deferred |
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
