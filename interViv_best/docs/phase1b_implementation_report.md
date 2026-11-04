# Phase 1B implementation report

Branch `phase1b/reviewed-evaluator`, worktree `.worktrees/cursor-ai-design-phase1b`,
based on Phase 1A tip `3170eabb7b555a9f4c1606942ea786802b591f27`.

Scope: remove pre-answer grading-reference exposure, wire reviewed selection
**without activating it**, stop frozen-report rewrite in tests, author pilot v2
concept drafts, ship an experimental concept evaluator (gated off), and inventory
the existing Gemma 2 hint-coach artifacts.

**Stopped before** production activation, Phase 2, scorer promotion, hint-coach
integration, push, merge, or deploy.

## Task summary

### A — Pre-answer reference exposure

- `backend/serializers/round_serializer.py`: `technical_short_answer` now rebuilds
  `question_context` from an explicit allowlist (`modules/bundle_scoring.candidate_technical_context`).
- `modules/bundle_scoring.py`: server-side `scoring_context_from_round` resolves
  pinned `bundle_id`/`version`/`content_hash` from the store; hash mismatch →
  `BundleReferenceUnavailable` (no silent substitute). Legacy rounds keep the
  server-side ideal snapshot for scoring only.
- `backend/routes/session.py`: start responses include sanitized technical
  `question_context`; reviewed-bundle normalization persists identity only
  (no `ideal_answer` on the issued pin).
- `backend/routes/answer.py`: scoring uses resolved context; `next_question_context`
  is sanitized.
- `backend/routes/dashboard.py`: completed reports resolve ideals server-side.
- Client override of grading fields remains rejected by `SubmitAnswerRequest`
  allowlist (422 on extras).

### B — Reviewed selection wired, gate OFF

- `_get_next_question` calls `select_reviewed_question` only when
  `REVIEWED_BUNDLES_ONLY` is true.
- Default / runtime remain **false**. Empty or draft-only inventory raises
  `ReviewedInventoryUnavailable` → `IntegrationError` (no scored fallback).
- Synthetic reviewed records appear only in tests.

### C — Frozen report isolation

- `tests/test_change5_baseline.py` writes via `--output` to `tmp_path`.
- `tests/test_scorer_v1_baseline_hashes.py` no longer skips
  `docs/human_baseline_report.md`.
- Intentional CLI default (`scripts/baseline_analysis.py` → docs path) unchanged.

### D — Pilot v2 drafts

- Each of the 12 YAML files lists immutable **v1** (CSV, empty concepts) and
  **v2** (developer-authored concepts, misconceptions, depth markers, rubric
  descriptors, calibration examples).
- All remain **draft**. Author `phase1b-dev:concept-authorship`; attribution
  records original CSV provenance separately.
- Human checklist: `docs/phase1b_human_review_checklist.md`.

### E — Experimental concept evaluator

- `modules/concept_evaluator_v2.py` + `scripts/run_concept_evaluator_v2.py`.
- Gate: `EXPERIMENTAL_CONCEPT_EVALUATOR` (default false).
- Output: evaluator/config versions, per-concept states
  (`supported` / `contradicted` / `not_demonstrated` / `uncertain`) with original
  spans, coverage 0–3 mapping, Accuracy/Depth/Clarity nullable, **no headline total**.
- Not imported by `modules.scoring`, mastery, Elo, or readiness paths.

### F — Gemma inventory

- `docs/gemma_hintcoach_inventory.md` — stock `gemma2:2b` vs fine-tuned adapter
  vs absent Gemma 4; paths; train-v2 adapter facts; SQL coverage absent; nothing
  imported.

## Migrations

None. Migration head remains `20260913_0010` from Phase 1A.

## Flags (production activation still blocked)

| Flag | Default | Wired? | Active? |
| --- | --- | --- | --- |
| `REVIEWED_BUNDLES_ONLY` | false | yes | **no** |
| `EXPERIMENTAL_CONCEPT_EVALUATOR` | false | yes (gate helper) | **no** |
| `LENGTH_RATIO_MULTIPLIER_ENABLED` | false | unchanged | no |
| `LLM_LIVE_FETCH` | unchanged | unchanged | not enabled here |

## Remaining blockers before activation / Phase 2

- Real human reviews (0 reviewed bundles).
- Frontend/UX for assessment-unavailable when the gate is eventually ON.
- Held-out n=50 assets / form workbook still absent from this tree.
- Experimental evaluator is development-only; no promotion path executed.
- Hint-coach comparison study not run; do not replace stock coding coach yet.

## Confirmations

- No push, merge, deploy.
- No scorer / protected pipeline edits.
- No hint-coach import.
- Tree 2, Phase 0, Phase 1A, coding-practice, phase-b worktrees left untouched by this work.
- `REVIEWED_BUNDLES_ONLY` still off.

## Phase-boundary verification (this run)

```
.venv/bin/python -m pytest tests/ -q
→ 593 passed, 1 skipped, 74 warnings in 101.46s

docs/human_baseline_report.md sha256 unchanged across the suite:
eb69fdb59cbf35250bdfe96492ba6b37fe8ac4bce9994fd71f25d57c65d3d2ea

.venv/bin/python scripts/scoring_regression.py
→ 6 PASS, 2 FAIL (known: gibberish→repetition, keyword_stuffing→gibberish)

.venv/bin/python scripts/replay_scorer_v1_baseline.py
→ Replay matched 8 frozen items and asset hashes (25 files, 0 mismatches).

cd frontend && npm test -- --run
→ # tests 85 / # pass 85 / # fail 0
```
