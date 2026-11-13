#!/usr/bin/env python3
"""Development-only launcher: preview system follow-ups in the local app.

Usage:
  .venv/bin/python scripts/dev_system_follow_ups.py

Runs ``scripts/run_local.py`` (same flags, same local SQLite) with two
differences for the backend process it starts:

- ``SYSTEM_FOLLOW_UPS_ENABLED=true``;
- uvicorn serves ``scripts.dev_system_follow_ups:create_app`` (``--factory``),
  which returns ``backend.main.app`` after registering the preview trigger
  below in that one process.

That factory is the only registration path outside the tests. No setting or
environment variable names a trigger, nothing under ``backend/`` or
``modules/`` calls ``register_trigger``, and the production image
(``backend/Dockerfile``) copies neither ``scripts/`` nor ``tests/``. The
factory also refuses to run unless the backend is a development backend bound
to loopback, the same rule as the trusted local runner.

The preview trigger proposes one fixed neutral question after every question.
The shipped Slice 1 rules still decide whether it is inserted: Coached practice
with "Allow optional follow-ups" ticked, one follow-up per parent, two per
Interview block, never after the final question, and the prompt must pass
``modules.system_follow_ups.validate_system_prompt``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PREVIEW_PROMPT = "Could you walk through a concrete example of that idea?"
BACKEND_APP = ("--factory", "scripts.dev_system_follow_ups:create_app")
EXTRA_ENV = {"SYSTEM_FOLLOW_UPS_ENABLED": "true"}


def preview_trigger(context: dict[str, Any]):
    """Synchronous, pure and fast, as the trigger contract requires."""
    from modules.system_follow_ups import SystemFollowUpProposal

    return SystemFollowUpProposal(prompt=PREVIEW_PROMPT)


def require_local_development() -> None:
    """Raise unless this is a development backend bound to loopback."""
    from backend.config import get_settings
    from backend.local_runner import BIND_HOST_VAR, LOOPBACK_HOSTS

    environment = get_settings().environment
    if environment != "development":
        raise RuntimeError(
            f"The system follow-up preview is development-only (ENVIRONMENT={environment!r})."
        )
    host = os.environ.get(BIND_HOST_VAR, "").strip().lower()
    if host not in LOOPBACK_HOSTS:
        raise RuntimeError(
            f"The system follow-up preview needs a loopback backend ({BIND_HOST_VAR}={host!r})."
        )


def create_app():
    """uvicorn ``--factory`` target: the real app plus the preview trigger."""
    require_local_development()
    from backend.main import app
    from modules import system_follow_ups

    system_follow_ups.register_trigger(preview_trigger)
    return app


def main() -> int:
    from scripts import run_local

    print("Development preview: system follow-ups are ON for this local backend only.", flush=True)
    print('Start Coached practice with "Allow optional follow-ups" ticked to see one.', flush=True)
    return run_local.main(backend_app=BACKEND_APP, extra_env=EXTRA_ENV)


if __name__ == "__main__":
    raise SystemExit(main())
