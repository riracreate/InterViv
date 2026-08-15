from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = LAB_ROOT.parents[1]


def test_diagnosis_exists_and_has_definitive_cause():
    diagnosis = (LAB_ROOT / "SEMANTIC_RUNTIME_DIAGNOSIS.md").read_text(
        encoding="utf-8"
    )
    assert "Primary classification: `RESEARCH_ADAPTER_BUG`" in diagnosis
    assert "semantic_function_called: true" in diagnosis
    assert "fallback_called: false" in diagnosis
    assert "NO_SCHEMA_MISMATCH_FOUND" in diagnosis


def test_corrected_adapter_executes_actual_local_semantic_function():
    script = """
import json, os
os.environ.pop('DISABLE_SEMANTIC_SCORING', None)
from research.grader_lab.baselines import InterVivCurrentBaseline
from research.grader_lab.datasets import load_registered_datasets
example = next(x for x in load_registered_datasets()['internal_perturbation'].examples if x.example_id == 'internal:paraphrase-001')
prediction = InterVivCurrentBaseline().predict(example)
print(json.dumps(prediction.metadata))
"""
    environment = dict(os.environ)
    environment.update({"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
    environment.pop("DISABLE_SEMANTIC_SCORING", None)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    trace = json.loads(completed.stdout.strip().splitlines()[-1])
    assert trace["semantic_function_called"] is True
    assert trace["model_load_success"] is True
    assert trace["fallback_called"] is False
    assert trace["semantic_component_source"] == "semantic"
