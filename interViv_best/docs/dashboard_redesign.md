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
