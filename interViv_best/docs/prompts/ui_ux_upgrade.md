# interViv UI/UX upgrade

You are upgrading the interface of the current interViv app. Work only in `interViv_best/` on this checkout (`phase4c/target-slugs`). Do not open or edit `.worktrees/`, `ticket-f/integrate-demo`, or `/tmp/interviv-publish`.

Read `frontend/src/styles/theme.css` and `frontend/src/styles/hub.css` before changing any screen. Extend those tokens. Do not introduce a component library, a toast library, a state manager, or a new font.

## Do not change

- Scores, bands, feedback text, guard decisions, readiness, gap math, or roadmap content. The UI may display those values. It may not compute or reword them.
- Routes, API contracts, and session flow. A control may go to a clearer existing destination. It may not gain a new product feature.
- Protected scoring modules, datasets, and model files.
- `.env`. Do not print secrets.
- Uncommitted Jobs, Greenhouse, run-script, and coding-exit work. Build on it.

There is no password-reset API. Do not add a forgot-password link.

Cut a branch from this HEAD named `ui/hub-consistency`. Do not commit unless asked. Do not push.

## What to upgrade

The product already has a light hub (`hub-page`, ink pills, serif headings) and a dark session report (`#0a0a0a`). Landing, Login, Signup, Upload, and Interview still use one-off black pills and `#6F6F6F` / `#000`. Bring those screens onto the shared tokens without a redesign.

Fix the verified interface bugs first.

1. **Landing nav.** `Landing.jsx` always shows Login and Sign up. When a session exists, replace that pair with one control, "Go to Home", linking to `/home`. Anonymous visitors keep Login and Sign up.
2. **Session Complete logo.** In `Interview.jsx`, the finished-session logo navigates to `/`. Send it to `/home`. Keep View Dashboard → `/dashboard/:sessionId` and New Session → `/upload`.
3. **Resume size copy.** `Upload.jsx` says "Maximum file size 10MB". The server limit in `backend/routes/resume.py` is 5 MB. Say 5 MB, and reject a larger file in the browser before upload with a visible error.
4. **Share confirmation.** On the session report, Share Results copies the URL and gives no feedback. After a successful copy, show a short status message on the button or beside it. No toast library.
5. **Destructive confirms.** Custom-practice preset Delete, and the answer-draft reset control, act immediately. Preset Delete asks for confirmation. The reset control has a visible accessible name.
6. **Report error recovery.** The session-report error state only offers Start New Session. Add Try again, which refetches the same session.
7. **Print.** Download Report calls `window.print()` and the page stays dark with no print rules. Add a print stylesheet so the report prints as black text on white, with decorative motion and the nav hidden.

Then make the shared interface consistent.

8. **One button treatment.** Primary actions use the ink pill (`--color-ink` on `--color-card`). Secondary actions use the bordered pill. Apply this on Landing, Login, Signup, Upload, and the Interview header and Session Complete card. Do not restyle the coding Monaco workspace.
9. **One status language.** Errors use `--color-danger` and `--color-danger-soft`. Loading uses the existing `role="status"` text. Empty states that already exist keep their copy and gain one next action when the screen currently dead-ends (filter empty, report error). Do not invent new empty marketing.
10. **Login and Signup errors.** Keep the single error box. Tie it to the field with `aria-invalid` and `aria-describedby` when the message is about one field. Do not add a password-visibility control unless it is a few lines on the existing input.
11. **Focus.** Every new or touched control keeps a visible `:focus-visible` ring using `--color-accent`, including Landing and Interview, which today sit outside `.hub-page`.

## Leave alone

- Jobs source switch colors: Adzuna blue `#2563eb`, Greenhouse green `#16a34a`.
- Coding Exit → `/problems`. Other interview Exit → `/home`, behind `Exit? Progress will be lost.`
- Score colors on answer results (green ≥ 75, amber ≥ 50, red below).
- Dashboard panel order and labels.
- Copy that states a product rule (assessment vs coached practice, self-assessment not measured, Greenhouse disclaimer). You may fix a false limit. You may not rewrite headlines for tone.

## Done when

- `npm test` in `interViv_best/frontend` passes.
- The changed flows are exercised in the browser at `http://127.0.0.1:5173`: signed-in Landing, a too-large PDF on Upload, Session Complete logo, Share Results, report error Try again, and one Login validation error.
- Desktop and a narrow viewport both keep the primary action visible without horizontal scroll on Landing, Login, and Session Complete.
- `git diff --stat` shows only frontend files, plus this prompt if you leave it in place. No Python scoring files.
