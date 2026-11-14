"""Project-local runtime environment defaults.

Must run before any ``huggingface_hub`` / ``sentence_transformers`` import so
``HF_HUB_OFFLINE`` is visible when hub constants are evaluated.

Phase J: prefer the locally cached MiniLM weights and do not open Hub sockets
during SemanticScorer warm-up. Override by setting the variables explicitly in
``.env`` or the process environment (``override=False`` for dotenv; setdefault
only fills blanks).

Phase O: default ``JOBS_LIVE_FETCH=0`` so Adzuna ``httpx`` cannot fire unless
deliberately enabled (same offline posture as Hub).

Phase Q: default ``LLM_LIVE_FETCH=0`` so OpenAI/OpenRouter chat ``urlopen``
cannot fire unless deliberately enabled (credentials alone are not a gate).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def dotenv_enabled() -> bool:
    """False when ``INTERVIV_SKIP_DOTENV`` is set: the process environment is
    then the only configuration. The test suite sets it, so a developer's
    ``.env`` (provider keys, live-fetch switches) cannot change a test run."""
    return os.getenv("INTERVIV_SKIP_DOTENV", "").strip().lower() not in {"1", "true", "yes", "on"}


def load_project_dotenv(root: Path) -> None:
    if dotenv_enabled():
        load_dotenv(root / ".env", override=False)


def apply_runtime_env() -> None:
    root = Path(__file__).resolve().parents[1]
    load_project_dotenv(root)
    # Recommended operating configuration when all-MiniLM-L6-v2 is cached.
    # A cold cache still fails load and sticky-degrades (fail-fast remains open).
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    # Jobs: keep Adzuna outbound gated off unless the owner opts in.
    os.environ.setdefault("JOBS_LIVE_FETCH", "0")
    # LLM chat completions: off unless the owner opts in (Phase Q).
    os.environ.setdefault("LLM_LIVE_FETCH", "0")
