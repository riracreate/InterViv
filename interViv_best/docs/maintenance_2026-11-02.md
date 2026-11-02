# Maintenance and local cleanup — 2 November 2026

Scope: the `mega 2 copy` workspace and the current `interViv_best` application.
Changes remain local and uncommitted. No GitHub branch was pushed or merged.

## Implemented

- Added `scripts/run_local.py`: starts the app on localhost with migrated SQLite
  storage, offline question selection, startup readiness checks, log files,
  and cleanup of only the child processes it starts.
- Fixed failed/unreadable resume extraction so it produces a useful error
  instead of inventing Python skills; readable resumes with no detected skills
  return an empty selection.
- Added authentication limits per client and account, with shared Redis counters
  when configured and a bounded local fallback. Configured Redis failure stops
  authentication temporarily rather than silently dropping the limits.
- New passwords use PBKDF2-SHA256 with 600,000 iterations. Long Unicode passwords
  work, and legacy hashes remain verifiable; invalid bcrypt inputs no longer
  cause server errors.
- Production requires a database. `/ready` checks migrations, database access,
  practice content, and configured Redis access separately from `/health`.
- Docker includes the ML exercise packs and stops when migrations fail. Local
  Compose database/cache/backend ports bind to loopback.
- Closed navigation links no longer receive keyboard focus; Escape closes the
  panel and returns focus to its trigger.
- Added Python environment constraints and a GitHub verification workflow.
- Changed classifier evaluation to separate question groups, added an evaluation
  mode that leaves production artifacts untouched, and saved its results.
- Added setup instructions, a folder guide, and a researched product roadmap.

## Verification

| Check | Result |
|---|---|
| Backend suite | 801 passed, 1 skipped; 110 existing/deprecation warnings |
| Frontend suite | 123 passed |
| Frontend production build | Passed; large editor/worker chunks still warned |
| Local API smoke | Signup → login → practice → submission → progress → report passed |
| Actual app restart | Same account, session and report recovered from SQLite |
| Browser | Login/progress view checked; closed/open menu and Escape focus checked |
| Earlier local work | All 13 files in the pre-change manifest retained byte-for-byte |
| Production model artifacts | Three classifiers and model metadata unchanged |
| Whitespace check | `git diff --check` passed |

The one skipped test needs a configured database for its unique-constraint
assertion. Local tests do not establish live PostgreSQL, Redis, Docker deployment,
coding executor, speech service, or external provider correctness. CI is prepared
but has not run on GitHub. The supported Vite upgrade remains pending because the
dependency-install request was declined; the installed 5.4.21 toolchain remains.

The grouped evaluation reported 92.86% accuracy and 0.928 macro F1 on 168 held-out
answers from 49 question groups. This measures existing dataset-label agreement,
not human grading agreement or interview readiness. See
[`research/grouped_evaluation.json`](../research/grouped_evaluation.json).

## Cleanup performed

Before deletion, a compressed backup preserved source, ignored configuration,
and generated review content. All 12 removed checkouts were rechecked for a
clean working tree, an unchanged head, and inclusion in the current branch's
history. Git removed them normally, without force; branch references remain.

Removed checkout names under `.worktrees/`: `coding-practice`,
`cursor-adzuna-integration`, `cursor-ai-design-acceptance`,
`cursor-ai-design-phase0`, `cursor-ai-design-phase1a`,
`cursor-ai-design-phase1b`, `cursor-ai-design-phase2`,
`cursor-ai-design-phase3a`, `cursor-ai-design-phase3b`,
`cursor-ai-design-phase3c`, `cursor-ai-design-phase4a`, and `phase4c-main`.

Also removed six `.chart-data-*` directories, `.ppt-sept-review`,
`.ppt-screenshot-review`, and `.interviv_model_lab_runtime`, after archiving
their content. No final presentations or trained-model archives were removed.

- Removed allocated data: **1,105.5 MiB**.
- Compressed cleanup backup: **167.8 MiB**, 7,121 members.
- Net reduction after accounting for that backup: **937.6 MiB** (about 0.92 GiB).
- Backup: `private/maintenance-2026-11-02/cleanup-backup.tar.gz`, relative to the
  workspace root. SHA-256:
  `9bbc28aed7371b453e34f951bc5e21af2bc1cc14af810901a8447c30986d4ba8`.
- The same private directory contains the original local-edit backup, hashes,
  cleanup plan/result, and records of the two repaired dependency links.

The backup excludes installed dependencies, generated build output, Git pointer
files and bytecode caches. Git history remains in `.git/`. To restore an old
checkout, recreate its worktree from the recorded branch/head, then recover
wanted local files from the archive into a separate recovery directory. Never
extract blindly over the active application. Keep this backup private because
it includes local configuration.

## Folders that remain

| Folder | Decision |
|---|---|
| `interViv_best/backend`, `modules`, `frontend/src`, `frontend/public`, `data`, `ml_primitives`, `alembic` | Required application source, assets, content and migrations |
| `interViv_best/tests`, `frontend/tests`, `scripts`, `docs`, `research`, root `.github` | Keep for maintenance, validation and reproducibility |
| `.git` | Keep shared history and branches |
| `interViv_best/.venv`, `frontend/node_modules` | Keep the working dependencies; removing these requires reinstalling before use |
| `interViv_best/local-data` | Keep local accounts/progress and optional coding runtime cache |
| `private/maintenance-2026-11-02` | Keep recovery backups privately |
| `.worktrees/cursor-ai-design-phase4b` | Keep: unique untracked plan |
| `.worktrees/phase-b-block-practice` | Keep: two commits not ancestors of the current branch |
| `archive`, `output`, `interviv_colab_lab` | Optional for app runtime; retained because they contain models, deliverables or research |

The retained worktrees now use the root frontend dependency directory directly;
one previously pointed through a deleted candidate, and the other through an
already missing checkout. Their Python environment links already point to the
root environment.

Further savings would come mainly from deleting reinstallable dependencies or
downloaded coding runtimes. Keeping them makes this local app immediately usable
and avoids another download. Reconcile the two remaining worktrees before any
further checkout cleanup.

## Run and follow up

From `interViv_best/`, run `.venv/bin/python scripts/run_local.py` and open
<http://127.0.0.1:5173>. Use Ctrl+C to stop. Accounts and progress stay in
`local-data/interviv-local.sqlite3`.

The next priorities and supporting research are in
[IMPROVEMENT_ROADMAP.md](IMPROVEMENT_ROADMAP.md).
