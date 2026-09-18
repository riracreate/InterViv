# interViv Phase 4B Status

Date: 2026-09-18

Phase 4B delivers deterministic versioned study plans and a multi-turn planning
coach with a deterministic no-live-generation path, on top of Phase 4A
assistance/eligibility.

## Current State

- Planning evidence adapter classifies eligible / assisted / legacy / unassessed /
  planning-context populations without changing scorer formulas.
- Versioned study plans with stable task IDs, editable hours/week default (6),
  regeneration that preserves history and completion.
- Multi-turn owned coach conversations (SQL reopen + memory process-local).
- Fake planning provider rejected on invented gaps/scores/resources/mutations;
  deterministic fallback remains useful.
- Prerequisite fixes: eligible topic/report/progress averages; rolling-mean
  self-reported/review filter; learning effects in atomic + memory snapshots;
  conditional round claim; followups removed from pre-release candidate context
  and dashboard nextTopics; report-review exposures recorded.

## Gates (unchanged defaults)

- `REVIEWED_BUNDLES_ONLY` — inventory 0 reviewed (unchanged)
- Experimental concept evaluator — off
- Live question generation / live narration / LLM live fetch — off
- Adzuna live fetch — off

## Migrations

- `20260918_0015` — `study_plans`, `coach_conversations`, follow-up parent unique index
- Downgrade target: `20260917_0014`

## Verification snapshot

See `docs/phase4b_implementation_report.md` for command evidence. Branch tip
is whatever `git rev-parse HEAD` reports on `phase4b/roadmap-coach` (avoid
self-stale SHA pins in this status file).

## Stop line

Engineering Phase 4B complete. Browser acceptance and human review remain pending.
