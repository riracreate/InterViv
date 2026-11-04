"""Phase J: configured Hub-offline environment yields full SemanticScorer mode.

Does not modify the scorer. Asserts the operating configuration from
``backend.runtime_env`` keeps scoring in full mode when MiniLM is cached.
Skips when the local Hub cache is absent (cold install — fail-fast still open).
"""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest

# Apply before any hub import in this process.
from backend.runtime_env import apply_runtime_env

apply_runtime_env()

from huggingface_hub import is_offline_mode  # noqa: E402


def _hub_has_minilm() -> bool:
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    model = hub / "models--sentence-transformers--all-MiniLM-L6-v2"
    weights = model / "blobs" / "53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db"
    return weights.is_file() and weights.stat().st_size > 1_000_000


@pytest.mark.skipif(
    not _hub_has_minilm(),
    reason="all-MiniLM-L6-v2 not cached; Phase J env fix is warm-cache only",
)
def test_runtime_env_enables_hub_offline_mode() -> None:
    assert os.environ.get("HF_HUB_OFFLINE") == "1"
    assert is_offline_mode() is True


@pytest.mark.skipif(
    not _hub_has_minilm(),
    reason="all-MiniLM-L6-v2 not cached; Phase J env fix is warm-cache only",
)
def test_semantic_scorer_full_mode_under_configured_offline_env() -> None:
    """Fresh subprocess so module globals and hub constants re-read env."""
    import json
    import subprocess
    import sys

    code = r"""
import os, json, socket
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
from backend.runtime_env import apply_runtime_env
apply_runtime_env()

tcp = []
_real = socket.create_connection
def _wrap(address, *a, **kw):
    tcp.append(address)
    host = address[0] if isinstance(address, tuple) else address
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise OSError(f"BLOCKED_TCP {address}")
    return _real(address, *a, **kw)
socket.create_connection = _wrap

from huggingface_hub import is_offline_mode
from modules.semantic_scorer import SemanticScorer, fallback_reason, _get_model

model = _get_model()
score = SemanticScorer().score(
    "Docker containers isolate applications using namespaces.",
    "Containers isolate processes using namespaces and cgroups.",
)
print(json.dumps({
    "offline": is_offline_mode(),
    "loaded": model is not None,
    "fallback": fallback_reason(),
    "score": score,
    "tcp_count": len(tcp),
}))
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
    )
    assert proc.returncode == 0, proc.stderr
    # Last JSON line from stdout
    payload = None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            payload = json.loads(line)
    assert payload is not None, proc.stdout
    assert payload["offline"] is True
    assert payload["loaded"] is True
    assert payload["fallback"] is None
    assert payload["score"] is not None
    assert float(payload["score"]) > 0.0
    assert payload["tcp_count"] == 0
