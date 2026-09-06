"""Tests for LENGTH_RATIO_MULTIPLIER_ENABLED (default OFF) and held-out evaluator."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_length_ratio_flag_defaults_false(monkeypatch):
    monkeypatch.delenv("LENGTH_RATIO_MULTIPLIER_ENABLED", raising=False)
    from backend import config

    config.get_settings.cache_clear()
    settings = config.get_settings()
    assert settings.length_ratio_multiplier_enabled is False

    mod = _load(
        "length_ratio_completeness",
        ROOT / "modules" / "length_ratio_completeness.py",
    )
    assert mod.length_ratio_multiplier_enabled() is False


def test_completeness_multiplier_matches_report_formula():
    mod = _load(
        "length_ratio_completeness",
        ROOT / "modules" / "length_ratio_completeness.py",
    )
    mult = mod.completeness_multiplier("six word fragment here now", " ".join(["word"] * 40))
    assert abs(mult - 0.3) < 1e-9

    long_ans = " ".join(["token"] * 40)
    long_ref = " ".join(["token"] * 40)
    assert abs(mod.completeness_multiplier(long_ans, long_ref) - 1.0) < 1e-9


def test_pipeline_flag_off_does_not_scale(monkeypatch):
    monkeypatch.delenv("LENGTH_RATIO_MULTIPLIER_ENABLED", raising=False)
    from backend.scoring.pipeline import run_scoring_pipeline

    result = run_scoring_pipeline(
        answer_text=(
            "A hash table maps keys to buckets with a hash function and handles "
            "collisions with chaining or open addressing."
        ),
        question_context={
            "question": "Explain how a hash table works.",
            "ideal_answer": (
                "A hash table maps keys to buckets using a hash function. "
                "Collisions are handled with chaining or open addressing. "
                "Average lookup is O(1) when the load factor is controlled."
            ),
            "ideal_keywords": "hash, table, bucket, collision, chaining",
        },
    )
    bd = result["scoring_breakdown"]
    assert bd.get("length_ratio_multiplier_enabled") is False
    assert bd.get("completeness_multiplier") is None


def test_heldout_evaluator_reports_absent():
    script = ROOT / "scripts" / "evaluate_length_ratio_heldout.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "HELD_OUT_ABSENT" in proc.stdout
