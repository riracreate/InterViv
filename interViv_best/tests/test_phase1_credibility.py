from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.scoring.pipeline import get_model_metadata


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def test_model_artifact_has_honest_metadata_and_verified_checksum():
    artifact = PROJECT_ROOT / "modules" / "answer_quality_lr.joblib"
    metadata_path = PROJECT_ROOT / "modules" / "model_metadata.json"

    assert artifact.exists()
    assert metadata_path.exists()

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["model_type"] == "LogisticRegression"
    assert metadata["artifact_sha256"] == _sha256(artifact)
    assert metadata["dataset_hash"].startswith("sha256:")
    assert isinstance(metadata["val_f1_macro"], float)

    loaded = get_model_metadata()
    assert loaded["artifact_checksum_verified"] is True
    assert loaded["model_type"] == "LogisticRegression"


def test_deprecated_svm_artifact_path_is_removed():
    old_path = PROJECT_ROOT / "modules" / "svm_model.joblib"

    assert not old_path.exists(), (
        "svm_model.joblib is a misleading name (the model is LogisticRegression); "
        "the artifact lives at answer_quality_lr.joblib"
    )


def test_dashboard_no_longer_contains_fake_percentile_metric():
    frontend_files = [
        PROJECT_ROOT / "frontend" / "src" / "pages" / "Dashboard.tsx",
        PROJECT_ROOT / "frontend" / "src" / "components" / "dashboard" / "ScoreHero.tsx",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in frontend_files)

    assert "topPercent" not in combined
    assert "Top {" not in combined
