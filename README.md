# InterViv workspace

The current application is in **`interViv_best/`**. Start development there.

With the existing Python and frontend dependencies installed:

```bash
cd interViv_best
.venv/bin/python scripts/run_local.py
```

Open <http://127.0.0.1:5173>. The launcher applies database migrations and saves
accounts and progress in `interViv_best/local-data/interviv-local.sqlite3`.
It uses offline questions; coding execution needs the optional local Piston
service or the trusted local runner below. Ctrl+C stops the backend and
frontend started by this launcher.

For coding execution and live job listings (with the local Adzuna credentials
configured), start it with:

```bash
cd interViv_best
.venv/bin/python scripts/run_local.py --with-executor --live-jobs
```

Without Docker, Python coding and NumPy ML Primitives rounds can run in a
local worker process on your own machine:

```bash
cd interViv_best
.venv/bin/python scripts/run_local.py --trusted-local-execution
```

This trusted local runner is for running your own code locally; it is not a
security sandbox. The backend accepts it only in development on 127.0.0.1.
Other languages still need Piston. Details:
[coding execution security](interViv_best/docs/coding_execution_security.md#trusted-local-runner-docker-free-demo-mode).

- [Application setup and architecture](interViv_best/README.md)
- [Maintenance record, 2026-11-02 (historical)](interViv_best/docs/maintenance_2026-11-02.md)
- [Researched improvement roadmap](interViv_best/docs/IMPROVEMENT_ROADMAP.md)
- [Overhaul acceptance record and manual checklist](interViv_best/docs/overhaul_acceptance.md)

## Folder layout

| Folder | Contents |
|---|---|
| `interViv_best/` | The application: source, migrations, datasets, model artifacts, tests, docs, and its `.venv` and `frontend/node_modules` |
| `output/` | Finished deliverables (reports, slides, project overview); not used at runtime |
| `private/` | Local recovery backups; must stay private |
| `.github/` | CI workflows |
| `.claude/`, `.cursor/` | Editor and assistant settings |

The old `archive/`, `interviv_colab_lab/`, `hint_coach_training/`, root
`scripts/` folders and the two `.worktrees/` checkouts were removed on
2026-11-04. Checksummed tarballs of the removed files are in
`private/overhaul-2026-11-03/phase8-cleanup/`. The `phase4b/roadmap-coach`
and `codex/phase-b-block-practice` branches remain in this repository. The
older `private/maintenance-2026-11-02/` backup was deleted the same day; every
commit it referred to is still on a branch.

This working copy has local changes beyond the older GitHub `main` snapshot.
Do not replace it with a clone of `main` until the changes are reconciled and
a clean checkout has been validated.
