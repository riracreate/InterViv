"""Project-local runtime environment defaults.

Must run before any ``huggingface_hub`` / ``sentence_transformers`` import so
``HF_HUB_OFFLINE`` is visible when hub constants are evaluated.

Phase J: prefer the locally cached MiniLM weights and do not open Hub sockets
during SemanticScorer warm-up. Override by setting the variables explicitly in
``.env`` or the process environment (``override=False`` for dotenv; setdefault
only fills blanks).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def apply_runtime_env() -> None:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", override=False)
    # Recommended operating configuration when all-MiniLM-L6-v2 is cached.
    # A cold cache still fails load and sticky-degrades (fail-fast remains open).
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
