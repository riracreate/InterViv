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
service. Ctrl+C stops the backend and frontend started by this launcher.

- [Application setup and architecture](interViv_best/README.md)
- [Maintenance results and folder guide](interViv_best/docs/maintenance_2026-11-02.md)
- [Researched improvement roadmap](interViv_best/docs/IMPROVEMENT_ROADMAP.md)

Keep `.git/`, application source, migrations, datasets, model artifacts, and
current environments. `private/maintenance-2026-11-02/` holds local recovery
backups and must stay private. `archive/`, `output/`, and `interviv_colab_lab/`
hold historical models, deliverables, or research; they are not application
runtime folders. The two remaining `.worktrees/` checkouts contain work that
still needs reconciliation.

This working copy has local changes beyond the older GitHub `main` snapshot.
Do not replace it with a clone of `main` until the changes are reconciled and
a clean checkout has been validated.
