"""Train scorer v4 regression + calibration on the Mohler TUNE split only.

Reads data/mohler_question_split_v1.json (locked, committed) and the
open-ended Mohler CSV. Held-out rows are never opened here. Features come
from modules/scoring_features.build_scoring_features (shared with serving).

Outputs:
  modules/scorer_v4_regression.joblib
  modules/scorer_v4_calibration.json
  artifacts/scorer_v4_training.json (ignored)

Usage:
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python scripts/train_scorer_v4.py
"""

from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import csv
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.scoring_features import FEATURE_NAMES, build_scoring_features, feature_vector

SPLIT_PATH = ROOT / "data" / "mohler_question_split_v1.json"
MOHLER_PATH = ROOT / "data" / "external" / "mohler_asag" / "mohler_raw_open_ended.csv"
REGRESSION_PATH = ROOT / "modules" / "scorer_v4_regression.joblib"
CALIBRATION_PATH = ROOT / "modules" / "scorer_v4_calibration.json"
REPORT_PATH = ROOT / "artifacts" / "scorer_v4_training.json"
FEATURE_CACHE = ROOT / "artifacts" / "mohler_tune_features.json"


def _question_key(row_id: str) -> str:
    return ".".join(row_id.split(".")[:2])


def _load_tune_rows() -> list[dict]:
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    tune = set(split["tune_questions"])
    with MOHLER_PATH.open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if _question_key(r["id"]) in tune]
    return rows


def _features_for(rows: list[dict]) -> list[dict]:
    cache: dict[str, dict] = {}
    if FEATURE_CACHE.exists():
        cache = json.loads(FEATURE_CACHE.read_text(encoding="utf-8"))
    out: list[dict] = []
    for i, row in enumerate(rows):
        if row["id"] in cache:
            out.append(cache[row["id"]])
            continue
        feats = build_scoring_features(
            answer_text=row["student_answer"],
            ideal_answer=row["instructor_answer"],
        )
        cache[row["id"]] = feats
        out.append(feats)
        if (i + 1) % 200 == 0:
            print(f"features {i + 1}/{len(rows)}", flush=True)
            FEATURE_CACHE.parent.mkdir(parents=True, exist_ok=True)
            FEATURE_CACHE.write_text(json.dumps(cache), encoding="utf-8")
    FEATURE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    FEATURE_CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return out


def _v4_base(features: dict, model_component: float | None) -> float:
    terms = {"semantic_or_lexical": (0.45, features["semantic_score"]), "tfidf": (0.10, features["tfidf_score"])}
    if model_component is not None:
        terms["model"] = (0.25, model_component)
    total_w = sum(w for w, _ in terms.values())
    return 100.0 * sum(w * v for w, v in terms.values()) / total_w


def main() -> int:
    rows = _load_tune_rows()
    print(f"tune rows: {len(rows)}")
    feats = _features_for(rows)
    X = np.array([feature_vector(f) for f in feats], dtype=float)
    y = np.array([float(r["score_avg"]) / 5.0 for r in rows], dtype=float)

    model = Ridge(alpha=1.0)
    model.fit(X, y)
    pred = np.clip(model.predict(X), 0.0, 1.0)

    base_with = np.array([_v4_base(f, float(p)) for f, p in zip(feats, pred)])
    base_without = np.array([_v4_base(f, None) for f in feats])

    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(base_with, y * 100.0)

    joblib.dump(
        {
            "model": model,
            "feature_names": list(FEATURE_NAMES),
            "trained_on": "mohler_question_split_v1 tune (53 questions)",
            "target": "score_avg/5 (shipped score_avg column)",
        },
        REGRESSION_PATH,
    )
    CALIBRATION_PATH.write_text(
        json.dumps(
            {
                "kind": "isotonic (monotonic), fitted on Mohler tune split only",
                "x": [round(float(v), 4) for v in iso.X_thresholds_],
                "y": [round(float(v), 4) for v in iso.y_thresholds_],
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )

    from scipy.stats import pearsonr

    report = {
        "n_tune": len(rows),
        "feature_names": list(FEATURE_NAMES),
        "ridge_coefficients": {n: round(float(c), 4) for n, c in zip(FEATURE_NAMES, model.coef_)},
        "ridge_intercept": round(float(model.intercept_), 4),
        "tune_pearson_model_pred_vs_human": round(float(pearsonr(pred * 5, y * 5).statistic), 4),
        "tune_pearson_v4_base_with_model": round(float(pearsonr(base_with, y * 5).statistic), 4),
        "tune_pearson_v4_base_without_model": round(float(pearsonr(base_without, y * 5).statistic), 4),
        "calibration_knots": len(iso.X_thresholds_),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
