"""Alembic revision helpers for persistence tests.

Convention: never use relative revision ids (``-1``, ``+1``) against HEAD.
Those move whenever a later phase adds a migration. Instead:

- Name the phase's own revision id as a constant.
- Downgrade to ``parent_revision(PHASE_REVISION)`` so the test remains valid
  after later heads advance.

Example::

    PHASE_D_REVISION = "20260907_0006"
    _run_alembic(url, "downgrade", parent_revision(PHASE_D_REVISION))
"""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def _script_directory() -> ScriptDirectory:
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    return ScriptDirectory.from_config(cfg)


def parent_revision(revision: str) -> str:
    """Absolute down_revision of ``revision`` (raises if missing/base)."""
    script = _script_directory()
    rev = script.get_revision(revision)
    if rev is None:
        raise ValueError(f"Unknown Alembic revision: {revision}")
    down = rev.down_revision
    if down is None:
        raise ValueError(f"Revision {revision} has no parent (base).")
    if isinstance(down, (tuple, list)):
        if len(down) != 1:
            raise ValueError(f"Revision {revision} has multiple parents: {down}")
        return str(down[0])
    return str(down)
