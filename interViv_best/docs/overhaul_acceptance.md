# Overhaul acceptance — reliable journey (November 2026)

Branch `overhaul/reliable-journey`. One commit per phase; nothing pushed or merged.

| Phase | Commit | What changed |
|---|---|---|
| 1 Persistence & planning | `d887379` | Role requirements reach Roadmap/Coach; SQL store keeps ATS snapshots, round metadata and ML results (migration `20261103_0017`). |
| 2 Round lifecycle | `6ed2c92` | Next round is prepared, opened only by `POST /session/{id}/rounds/{n}/activate`; refresh restores history; Save & Exit; no calibration gate. |
| 3 Execution & ML | `e76d29f` | `--trusted-local-execution` runs Python coding and NumPy ML locally (not a sandbox); ML graded by `v1-ml-primitives`. |
| 4 Navigation & auth | `1062f2e`, `aa4914c` | One confirmed 401 signs out, nothing else does; upload wizard in the URL and restored; safe Back; account menu everywhere. |
| 5 Evaluation & learning | `e234442` | System-design practice estimate (`v1-system-design-content`, not measured); curated hints, unrecorded guidance, editorials; offline Greenhouse samples. |
| 6 Interface & voice | `e3b7207` | Five-item nav, practice tracks and skill chips, report summary and tabs without invented numbers, read-aloud and resilient speech, one light theme. |
| 7 Acceptance | this record | End-to-end journey test and lifecycle smoke check. |

## Automated evidence

- `tests/test_full_journey.py` — on a freshly migrated SQLite file with the
  trusted local runner: sign up → real PDF resume parse → target → ATS score
  from the stored snapshot → gap analysis → roadmap → coach plan from role
  requirements → one session with all six round types (interview, MCQ, SQL,
  coding, ML primitives, system design). Every round is submitted, reviewed
  (next prompt hidden), refreshed, activated (idempotently) and completed; a
  simulated restart mid-session keeps the history; the report counts six
  scored rounds and Progress lists the session.
- `scripts/smoke_local.py` — against a running backend: account, practice,
  submission, progress, report, then a two-round submit → review → activate →
  submit check; `--after-restart` re-verifies persistence. Options:
  `--base-url` (loopback only) and `--state-file`.
- Suites: `.venv/bin/python -m pytest`, `cd frontend && npm test && npm run build`.

## Manual checklist (run in your own browser)

Start with `.venv/bin/python scripts/run_local.py --trusted-local-execution`
and open <http://127.0.0.1:5173>.

1. **Upload → plan:** upload a PDF, pick skills and a target, open readiness,
   press Back (browser and in-page): skills and target remain; refresh keeps them.
2. **Interview:** start a mixed session. After each submit the result stays on
   screen; the next question appears only after **Next Question**; refresh
   during review keeps the result; **Save & Exit** returns Home and the
   session is resumable.
3. **Coding & ML without Docker:** Run and submit Python on Coding Arena and
   in a session; an ML round shows per-case results.
4. **Voice:** turn on **Read aloud**; record, pause a few seconds and keep
   talking (recording continues); deny the microphone once and confirm typing
   still works.
5. **Navigation:** five primary items, Career & Resume and More menus,
   keyboard (Tab, Enter, Escape) and a narrow window; Sign out from the
   account menu; protected pages then require sign-in.
6. **Report:** summary, three tabs (also with arrow keys), collapsed scoring
   details, and no dark panels or serif headings.

Not covered by automation: real microphones and speech services, visual
layout, and live provider calls (jobs, LLM narration), which stay off by default.
