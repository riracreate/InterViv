# Phase 4B implementation report

Deterministic versioned roadmaps and multi-turn planning coach on the Phase 4A
assistance checkpoint.

| Item | Value |
| --- | --- |
| Branch | `phase4b/roadmap-coach` |
| Worktree | `.worktrees/cursor-ai-design-phase4b` |
| Base | `ca55edfa1f9902b9b458024405913177edfc9f1e` (Phase 4A tip) |
| Ancestors verified | Phase 3C `e591f0b9…`, Adzuna `c498d6fe…` |
| App root | `interViv_best` |
| Branch tip | see `git rev-parse HEAD` at commit time |

## Prerequisite findings (section 2)

Inspected current Phase 4A code (older inventory superseded).

| Check | Inherited | Fixed on this branch |
| --- | --- | --- |
| Candidate Elo gated | Yes | — |
| Skill-graph write gated; SQL filter-before-limit | Yes (eligible/legacy) | Also exclude self-reported / spaced-review before last-five |
| Concept mastery / learning signals write-gated | Yes | Joined into attempt `atomic()` (+ memory global snapshot) |
| Session readiness / block averages eligible | Yes | — |
| Topic scores / progress / report averages | Used measured | Switched to `assessment_eligible` |
| Gap / Roadmap / Jobs read gated graph | Indirect yes | Added explicit planning-evidence adapter for plans |
| Learning effects post-commit best-effort | Documented gap | Moved into atomic; failure rolls back score+learning |
| Submit concurrency | Process lock only | + SQL/memory conditional claim; documented scope |
| Learn hints / coding coach / feedback exposures | Yes | — |
| Report review exposure | Missing | Idempotent `feedback_reveal` / `explanation` on completed report |
| Pre-release `followups` in candidate context / nextTopics | Leaked | Removed from allowlist; dashboard gated; UI nextTopics drop |

Scoring formulas and frozen pipeline assets unchanged.

## What shipped

1. **Planning evidence adapter** — `modules/planning_evidence.py`
2. **Versioned study plans** — `modules/roadmap_plans.py` + SQL `study_plans`
3. **Multi-turn coach** — `modules/coach_conversation.py` + routes; fake-provider rejection; deterministic fallback
4. **UI** — Coach conversation + study plan; Roadmap tasks / honest readiness; Jobs → Coach handoff with Adzuna context
5. **Migration** `20260918_0015` (downgrade → `20260917_0014`)

## Gates (unchanged / off)

`REVIEWED_BUNDLES_ONLY` inventory = **0** reviewed bundles (verified, not modified).
Experimental concept evaluator off; live question generation / live narration /
coach live-fetch off. Adzuna live fetch off. No scorer promotion.

## Verification (this run)

| Check | Result |
| --- | --- |
| Phase 4B + 4A + roadmap/coach/gap + Adzuna + 3C/3B/3A slice | **89 passed** |
| Phase 3A snapshots/narration + Phase D + scorer hashes | **38 passed** |
| `scripts/scoring_regression.py` | **6 PASS / 2 FAIL** (`gibberish`, `keyword_stuffing` — known) |
| `docs/human_baseline_report.md` SHA-256 | `eb69fdb59cbf35250bdfe96492ba6b37fe8ac4bce9994fd71f25d57c65d3d2ea` |
| `scripts/replay_scorer_v1_baseline.py` | **8/8 matched**; 0 asset mismatches |
| Frontend `tsc --noEmit` | pass |
| `npm run build` | pass |
| Frontend unit tests | **118 pass / 0 fail** |
| Migration upgrade/downgrade | `tests/test_phase4b_sql_persistence.py` (disposable SQLite) |

## Browser QA (pending — carry-forward)

Rendered acceptance not claimed. Manual checklist (~400px / ~1280px, keyboard):

- [ ] New user: goal → starter plan; readiness shows “Not assessed yet”
- [ ] Eligible history: tasks cite eligible population; coach explains next task
- [ ] Assistance-only: practice label + assess-independently action
- [ ] Change hours/week → new plan version; completion retained
- [ ] Jobs Prepare → Continue in Coach; snippet incomplete; optional full JD
- [ ] Start task without silent DSA substitution when skills empty
- [ ] Phase 4A: Assessment vs Coached; follow-ups; report labels
- [ ] Phase 3B: content_blocked continue; Adzuna Prepare preserved

## Stop line

Phase 4B complete for engineering verification. No push/merge/deploy, no
scorer promotion, no fabricated reviews, no model download/training.
Product browser acceptance and human bundle review remain separate decisions.
