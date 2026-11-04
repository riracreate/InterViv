# Dashboard Redesign

The `/dashboard` route now opens a professional student-focused dashboard home
instead of showing a "No session ID" error. The layout is intentionally
operational rather than marketing-heavy: clear header, direct CTAs, summary
stats, and an aligned card grid.

## Structure

Top section:

- Welcome message
- Primary CTA: Start Interview
- Secondary CTA: Resume Analysis

Main responsive card grid:

1. Overall Readiness Score
2. Company Practice
3. Role Practice
4. Skill Library
5. Weak Skills
6. Recent Sessions
7. Replay / Past Questions
8. Recommended Roadmap

## Product Orientation

The layout is inspired by structured practice platforms without copying any
Coderbyte branding, copy, or proprietary content. interViv remains a
student-focused Interview Readiness Platform with company-style, role-style,
resume-aware adaptive practice.

## Responsiveness

Cards use a one-column mobile layout, two columns on small screens, and four
columns on wide screens. Empty states are explicit for users who have not
completed an interview session yet.

## Report View

The session report exposes existing backend fields only:

- overall score
- content match
- semantic similarity
- keyword coverage
- structure score
- anti-gibberish warning when a guard fires
- missing concepts and missing keywords
- ideal answer
- follow-up prompts / next recommended topics
- reattempt CTA

No LLM scoring, LLM feedback, or LLM judging is introduced.

## Shared tokens (Track 3)

Light home (`/dashboard`) and dark session report (`/dashboard/:sessionId`) keep
different surfaces, but share tokens from `frontend/src/styles/theme.css`:

- type scale (`--text-*`)
- spacing (`--space-*`)
- status colours (`--color-success|warn|danger`)
- card / pill radius (`--radius-card`, `--radius-panel`, `--radius-pill`)

Session scope overrides status accents under `.dashboard-session`. Mapping logic
lives in `frontend/src/lib/dashboardMapping.js` (covered by
`frontend/tests/dashboardMapping.test.js`).

## Orphan component decisions (Track 3)

| Component | Decision | Reason |
|-----------|----------|--------|
| `ReviewSummary.tsx` | **Wired** after `ScoreHero` | Props are derived from existing `/dashboard/:id` session fields via `buildReviewSummaryProps` (scores, guards, word counts, topic scores, next_step). No new API fields. |
| `EloChart.tsx` | **Removed** | Duplicate of wired `PerformanceChart` (same recharts dual-line pattern). Keeping both would invent a third visual language for the same Elo/difficulty data. |
| `RoundTable.tsx` | **Removed** | Duplicate of wired `RoundTimeline`, which already owns the round-by-round slot with richer answer/ideal context. |

## face-api.js note

`face-api.js` is imported only from `frontend/src/lib/engagement.js` via
`import('face-api.js')` (lazy). Callers are limited to `Interview.jsx`.

Track 3 also route-splits Interview (`React.lazy` in `App.jsx`) and adds a
`face-api` manualChunk in `vite.config.ts`. Production build emits a separate
`face-api-*.js` (~664 kB) that is not part of the dashboard entry chunk.
No new computer-vision features were added.
