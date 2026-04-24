"""
retrain_ml_model.py — Retrain SVM/RF for interViv v11 scoring
==============================================================

What changed in v11:
  • Feature vector expanded from 4 → 5 features
  • New feature: `concept_coverage` (bigram/trigram overlap with ideal)
  • Labels (Good / Average / Poor) are the same

Run this script once after deploying nlp_scorer_v11.py to produce
a new svm_model_v11.joblib that the pipeline will load automatically.

Usage:
    python retrain_ml_model.py \
        --dataset modules/interview_dataset_v4.csv \
        --model_type rf \
        --output modules/svm_model_v11.joblib
"""

from __future__ import annotations

import argparse
import importlib
import logging
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

# Import your new scorer to compute features from the dataset
PROJECT_ROOT = Path(__file__).resolve().parent
for candidate in (PROJECT_ROOT / "modules", PROJECT_ROOT / "backend", PROJECT_ROOT):
    candidate_str = str(candidate)
    if candidate.exists() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

NLPScorer = importlib.import_module("nlp_scorer").NLPScorer

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def _default_path(filename: str) -> Path:
    preferred_dirs = [
        PROJECT_ROOT / "modules",
        PROJECT_ROOT / "backend",
        PROJECT_ROOT,
    ]
    for base in preferred_dirs:
        candidate = base / filename
        if candidate.exists():
            return candidate
    for base in preferred_dirs:
        if base.exists():
            return base / filename
    return PROJECT_ROOT / filename


# ── Feature engineering ───────────────────────────────────────────────────────

def build_features(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute v11 feature vectors for every row in the dataset.

    Expected columns in dataset CSV:
        answer_text, ideal_answer, ideal_keywords, label
        (label values: Good / Average / Poor)
    """
    scorer = NLPScorer()
    rows: list[list[float]] = []
    labels: list[str] = []

    for _, row in df.iterrows():
        answer_text = str(row.get("answer_text") or row.get("answer") or "")
        result = scorer.get_feature_scores(
            answer_text=answer_text,
            ideal_answer=str(row.get("ideal_answer", "")),
            ideal_keywords=str(row.get("ideal_keywords", "")),
        )

        features = [
            result["cosine_similarity"],                    # f1
            result["clarity_score"],                        # f2 (was length_ratio)
            result["keyword_coverage"],                     # f3
            len(answer_text.split()),                       # f4 word count
            result["concept_coverage"],                     # f5 NEW
        ]
        rows.append(features)
        labels.append(str(row.get("label", "Average")))

    return np.array(rows), np.array(labels)


# ── Model factory ─────────────────────────────────────────────────────────────

def make_pipeline(model_type: str) -> Pipeline:
    """Return a sklearn Pipeline (scaler + classifier)."""
    if model_type == "svm":
        clf = SVC(kernel="rbf", C=1.0, gamma="scale", probability=True)
    elif model_type == "rf":
        clf = RandomForestClassifier(
            n_estimators=200,
            max_depth=6,
            min_samples_leaf=5,
            random_state=42,
            class_weight="balanced",   # handles class imbalance
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}. Choose 'svm' or 'rf'.")

    return Pipeline([("scaler", StandardScaler()), ("clf", clf)])


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        default=str(_default_path("interview_dataset_v4.csv")),
        help="Path to interview_dataset CSV",
    )
    parser.add_argument("--model_type", default="rf", choices=["svm", "rf"])
    parser.add_argument(
        "--output",
        default=str(_default_path("svm_model_v11.joblib")),
    )
    args = parser.parse_args()

    log.info("Loading dataset from %s", args.dataset)
    df = pd.read_csv(args.dataset)
    log.info("Rows: %d", len(df))

    log.info("Computing v11 features …")
    X, y = build_features(df)
    log.info("Feature matrix: %s  |  Label distribution: %s", X.shape, dict(zip(*np.unique(y, return_counts=True))))

    pipeline = make_pipeline(args.model_type)

    # Cross-validation sanity check
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(pipeline, X, y, cv=cv, scoring="f1_weighted")
    log.info("5-fold CV weighted F1: %.3f ± %.3f", cv_scores.mean(), cv_scores.std())

    # Final fit on full dataset
    pipeline.fit(X, y)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, out_path)
    log.info("Model saved → %s", out_path)


if __name__ == "__main__":
    main()


# ─────────────────────────────────────────────────────────────────────────────
# RETRAINING NOTES
# ─────────────────────────────────────────────────────────────────────────────
#
# 1. LABEL QUALITY MATTERS MORE THAN ALGORITHM
#    Before retraining, audit your interview_dataset_v4.csv labels.
#    If "Good" / "Average" / "Poor" were hand-labeled inconsistently,
#    model accuracy will plateau regardless of architecture.
#
# 2. SYNTHETIC DATA AUGMENTATION
#    If your dataset is small (<500 rows per class), augment by:
#    - paraphrasing ideal answers at different lengths
#    - generating intentionally vague / repetitive "Poor" examples
#
# 3. FEATURE VECTOR CONTRACT
#    The current order is: [cos_sim, clarity, kw_cov, word_count, concept_cov]
#    If you add or reorder features, update _run_svm_label() in pipeline_v11.py
#    to match exactly, or predictions will be garbage.
#
# 4. WHEN TO RETRAIN
#    - After every 500+ new labelled answers
#    - After adding a new skill/domain to the question bank
#    - When CV F1 drops below 0.70
