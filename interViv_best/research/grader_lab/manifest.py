"""Reproducibility manifest embedded in every grader-lab report."""

from __future__ import annotations

import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from .datasets import DATASET_PROVENANCE, DatasetLoadResult, file_sha256

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    generated_at_utc: str
    git_commit: str
    git_dirty: bool
    dataset_versions: dict[str, dict[str, str]]
    model_versions: dict[str, dict[str, str]]
    runtime_versions: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "generated_at_utc": self.generated_at_utc,
            "git_commit": self.git_commit,
            "git_dirty": self.git_dirty,
            "dataset_versions": self.dataset_versions,
            "model_versions": self.model_versions,
            "runtime_versions": self.runtime_versions,
        }


def build_manifest(
    datasets: dict[str, DatasetLoadResult], baseline_versions: dict[str, dict[str, str]]
) -> RunManifest:
    now = datetime.now(timezone.utc)
    dataset_versions: dict[str, dict[str, str]] = {}
    for name, result in sorted(datasets.items()):
        dataset_versions[name] = {
            "version": result.version,
            "status": result.status,
            "examples": str(len(result.examples)),
            "sha256": file_sha256(result.path) if result.path.exists() else "not_present",
            "source": DATASET_PROVENANCE[name]["source"],
            "license_status": DATASET_PROVENANCE[name]["license_status"],
        }
    return RunManifest(
        run_id=now.strftime("grader-lab-%Y%m%dT%H%M%SZ"),
        generated_at_utc=now.isoformat(),
        git_commit=_git("rev-parse", "HEAD", default="unknown"),
        git_dirty=bool(_git("status", "--porcelain", default="")),
        dataset_versions=dataset_versions,
        model_versions=baseline_versions,
        runtime_versions={
            "python": platform.python_version(),
            "numpy": _package_version("numpy"),
            "scikit-learn": _package_version("scikit-learn"),
            "sentence-transformers": _package_version("sentence-transformers"),
            "torch": _package_version("torch"),
        },
    )


def _git(*args: str, default: str) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return default


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not_installed"
