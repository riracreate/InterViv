"""
retrain_ml_model.py — Retrain answer-quality classifier for interViv scoring
==============================================================

What changed in v11:
  • Feature vector expanded from 4 → 5 features
  • New feature: `concept_coverage` (bigram/trigram overlap with ideal)
  • Labels (Good / Average / Poor) are the same

Default dataset is now the 891-row balanced ml_training_data.csv (297/297/297).

Run:
    python retrain_ml_model.py
        --dataset data/ml_training_data.csv
        --model_type lr
        --output modules/answer_quality_lr.joblib
        --balanced true
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import logging
from datetime import date
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.utils.class_weight import compute_sample_weight

# Import the v11 NLP scorer to compute features from the dataset
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
        PROJECT_ROOT / "data",
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
    Compute v11 feature vectors for every row.

    Expected columns: answer_text (or answer), ideal_answer, ideal_keywords, label.
    """
    df = df.fillna("")
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
            result["cosine_similarity"],
            result["clarity_score"],
            result["keyword_coverage"],
            len(answer_text.split()),
            result["concept_coverage"],
        ]
        rows.append(features)
        labels.append(str(row.get("label", "Average")))

    return np.array(rows), np.array(labels)


def split_by_question(df: pd.DataFrame):
    """Reserve unseen questions; run CV only within the remaining questions."""
    if "question" not in df.columns:
        raise ValueError("Grouped evaluation requires a question column.")
    groups = df["question"].fillna("").map(lambda q: " ".join(str(q).casefold().split())).to_numpy()
    if any(not q for q in groups):
        raise ValueError("Every training row must have a nonempty question.")
    labels = df["label"].to_numpy()
    train, test = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42).split(df, labels, groups))
    if len(set(groups[train])) < 5:
        raise ValueError("At least five training question groups are required for cross-validation.")
    if set(labels[train]) != set(labels):
        raise ValueError("The grouped training split must contain every label.")
    cv = list(StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42).split(
        np.zeros(len(train)), labels[train], groups[train]
    ))
    return train, test, cv, groups


# ── Model factory ─────────────────────────────────────────────────────────────

def make_pipeline(model_type: str, balanced: bool = True) -> Pipeline:
    """Return a sklearn Pipeline (scaler + classifier).

    GradientBoostingClassifier does not accept `class_weight`, so balancing for
    `gb` is applied via sample_weight at fit time. LR/RF/SVM consume
    `class_weight='balanced'` directly.
    """
    if model_type == "lr":
        clf = LogisticRegression(
            C=1.0,
            max_iter=2000,
            solver="lbfgs",
            class_weight="balanced" if balanced else None,
            random_state=42,
        )
    elif model_type == "svm":
        clf = SVC(
            kernel="rbf",
            C=1.0,
            gamma="scale",
            probability=True,
            class_weight="balanced" if balanced else None,
        )
    elif model_type == "gb":
        clf = GradientBoostingClassifier(
            n_estimators=120,
            max_depth=2,
            learning_rate=0.08,
            random_state=42,
        )
    elif model_type == "rf":
        clf = RandomForestClassifier(
            n_estimators=200,
            max_depth=6,
            min_samples_leaf=5,
            random_state=42,
            class_weight="balanced" if balanced else None,
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}. Choose 'lr', 'svm', 'rf', or 'gb'.")

    return Pipeline([("scaler", StandardScaler()), ("clf", clf)])


def _fit_with_balance(
    pipeline: Pipeline,
    X: np.ndarray,
    y: np.ndarray,
    model_type: str,
    balanced: bool,
) -> None:
    """Fit pipeline; for GB, apply sample_weight balancing manually."""
    if model_type == "gb" and balanced:
        sw = compute_sample_weight(class_weight="balanced", y=y)
        pipeline.fit(X, y, clf__sample_weight=sw)
    else:
        pipeline.fit(X, y)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        default=str(_default_path("ml_training_data.csv")),
        help="Path to training CSV (default: data/ml_training_data.csv — 891-row balanced set)",
    )
    parser.add_argument("--model_type", default="lr", choices=["lr", "svm", "rf", "gb"])
    parser.add_argument(
        "--output",
        default=str(_default_path("answer_quality_lr.joblib")),
    )
    parser.add_argument(
        "--balanced",
        default="true",
        choices=["true", "false"],
        help="Use class_weight/sample_weight balancing (default: true)",
    )
    parser.add_argument(
        "--metadata_out",
        default=str(PROJECT_ROOT / "modules" / "model_metadata.json"),
        help="Where to write model_metadata.json",
    )
    parser.add_argument("--evaluate-only", action="store_true", help="Write a research evaluation without replacing the production model or metadata.")
    parser.add_argument("--report-out", default=str(PROJECT_ROOT / "research" / "grouped_evaluation.json"))
    args = parser.parse_args()
    balanced = args.balanced == "true"

    log.info("Loading dataset from %s", args.dataset)
    df = pd.read_csv(args.dataset)
    log.info("Rows: %d", len(df))

    log.info("Computing v11 features …")
    X, y = build_features(df)
    label_dist = dict(zip(*np.unique(y, return_counts=True)))
    label_dist = {str(k): int(v) for k, v in label_dist.items()}
    log.info("Feature matrix: %s  |  Label distribution: %s", X.shape, label_dist)

    classes = sorted(np.unique(y).tolist())

    # Reserve entire questions before model selection. Answers to a question
    # must never cross the train/validation boundary.
    train, test, cv, groups = split_by_question(df)
    X_train, X_test, y_train, y_test = X[train], X[test], y[train], y[test]

    cv_acc = cross_val_score(make_pipeline(args.model_type, balanced), X_train, y_train, cv=cv, scoring="accuracy")
    cv_f1 = cross_val_score(make_pipeline(args.model_type, balanced), X_train, y_train, cv=cv, scoring="f1_macro")
    cv_f1w = cross_val_score(make_pipeline(args.model_type, balanced), X_train, y_train, cv=cv, scoring="f1_weighted")

    log.info("5-fold CV accuracy:    %.4f ± %.4f", cv_acc.mean(), cv_acc.std())
    log.info("5-fold CV F1 macro:    %.4f ± %.4f", cv_f1.mean(), cv_f1.std())
    log.info("5-fold CV F1 weighted: %.4f ± %.4f", cv_f1w.mean(), cv_f1w.std())

    # ── Held-out evaluation for confusion matrix + per-class numbers ─────────
    eval_pipeline = make_pipeline(args.model_type, balanced=balanced)
    _fit_with_balance(eval_pipeline, X_train, y_train, args.model_type, balanced)

    y_pred = eval_pipeline.predict(X_test)
    train_acc = float(eval_pipeline.score(X_train, y_train))
    val_acc = float(eval_pipeline.score(X_test, y_test))
    val_f1_macro = float(f1_score(y_test, y_pred, average="macro"))
    val_f1_weighted = float(f1_score(y_test, y_pred, average="weighted"))

    report_dict = classification_report(
        y_test, y_pred, labels=classes, output_dict=True, zero_division=0
    )
    cm = confusion_matrix(y_test, y_pred, labels=classes).tolist()

    print("\n=== Per-class metrics (held-out 20% test) ===")
    print(classification_report(y_test, y_pred, labels=classes, zero_division=0))
    print("=== Confusion matrix (rows=true, cols=pred), labels:", classes, "===")
    for row in cm:
        print(" ", row)

    per_class = {
        cls: {
            "precision": float(report_dict[cls]["precision"]),
            "recall": float(report_dict[cls]["recall"]),
            "f1": float(report_dict[cls]["f1-score"]),
            "support": int(report_dict[cls]["support"]),
        }
        for cls in classes
    }

    evaluation = {
        "evaluation_protocol": "question-grouped-holdout-v1",
        "random_seed": 42,
        "dataset_sha256": hashlib.sha256(Path(args.dataset).read_bytes()).hexdigest(),
        "dataset_rows": len(df),
        "question_groups": len(set(groups)),
        "train_rows": len(train),
        "validation_rows": len(test),
        "train_question_groups": len(set(groups[train])),
        "validation_question_groups": len(set(groups[test])),
        "overlapping_question_groups": len(set(groups[train]) & set(groups[test])),
        "validation_accuracy": val_acc,
        "validation_f1_macro": val_f1_macro,
        "cv_training_groups_f1_macro_mean": float(cv_f1.mean()),
        "cv_training_groups_f1_macro_std": float(cv_f1.std()),
        "per_class": per_class,
        "confusion_matrix": cm,
        "labels": classes,
        "sklearn_version": sklearn.__version__,
        "feature_extractor": "current NLPScorer.get_feature_scores; empty CSV fields normalized to empty strings",
        "limitations": "Classifier agreement with dataset labels, not human agreement or interview readiness. No production artifact changed in evaluate-only mode.",
    }
    if args.evaluate_only:
        report_path = Path(args.report_out)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(evaluation, indent=2) + "\n")
        log.info("Grouped evaluation saved → %s; production model unchanged", report_path)
        return

    # ── Final fit on FULL dataset for the saved artifact ──────────────────────
    final_pipeline = make_pipeline(args.model_type, balanced=balanced)
    _fit_with_balance(final_pipeline, X, y, args.model_type, balanced)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_pipeline, out_path)
    log.info("Model saved → %s", out_path)

    # ── Hashes for traceability ───────────────────────────────────────────────
    dataset_bytes = Path(args.dataset).read_bytes()
    dataset_hash = "sha256:" + hashlib.sha256(dataset_bytes).hexdigest()
    artifact_hash = "sha256:" + hashlib.sha256(out_path.read_bytes()).hexdigest()

    metadata = {
        "model_type": type(final_pipeline.named_steps["clf"]).__name__,
        "version": "1.1.0",
        "training_date": date.today().isoformat(),
        "dataset": args.dataset,
        "dataset_hash": dataset_hash,
        "dataset_rows": int(len(df)),
        "label_distribution": label_dist,
        "balanced": balanced,
        "train_accuracy": round(train_acc, 4),
        "val_accuracy": round(val_acc, 4),
        "val_f1_macro": round(val_f1_macro, 4),
        "val_f1_weighted": round(val_f1_weighted, 4),
        "cv_5fold_accuracy_mean": round(float(cv_acc.mean()), 4),
        "cv_5fold_accuracy_std": round(float(cv_acc.std()), 4),
        "cv_5fold_f1_macro_mean": round(float(cv_f1.mean()), 4),
        "cv_5fold_f1_macro_std": round(float(cv_f1.std()), 4),
        "cv_5fold_f1_weighted_mean": round(float(cv_f1w.mean()), 4),
        "per_class_precision_recall": per_class,
        "confusion_matrix_2d": cm,
        "confusion_matrix_labels": classes,
        "sklearn_version": sklearn.__version__,
        "artifact_sha256": artifact_hash,
        "artifact_file": out_path.name,
        "feature_order": [
            "nlp_cosine_similarity",
            "clarity_score",
            "keyword_coverage",
            "server_word_count",
            "concept_coverage",
        ],
        "evaluation_note": (
            f"{type(final_pipeline.named_steps['clf']).__name__} retrained on the "
            f"{len(df)}-row dataset; balancing={balanced}. "
            "5-fold question-grouped CV on the training partition and a disjoint-question holdout reported."
        ),
        "evaluation": evaluation,
    }

    metadata_path = Path(args.metadata_out)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2))
    log.info("Metadata saved → %s", metadata_path)


if __name__ == "__main__":
    main()


# ─────────────────────────────────────────────────────────────────────────────
# RETRAINING NOTES
# ─────────────────────────────────────────────────────────────────────────────
#
# 1. LABEL QUALITY MATTERS MORE THAN ALGORITHM
#    Audit the training CSV labels before retraining. Inconsistent
#    Good/Average/Poor labels cap accuracy regardless of architecture.
#
# 2. SYNTHETIC DATA AUGMENTATION
#    For <500 rows per class, augment by paraphrasing ideal answers and
#    generating intentionally vague / repetitive "Poor" examples.
#
# 3. FEATURE VECTOR CONTRACT
#    Order is: [cos_sim, clarity, kw_cov, word_count, concept_cov].
#    If you reorder, update _run_classifier() in pipeline.py to match.
#
# 4. WHEN TO RETRAIN
#    - After every 500+ new labelled answers
#    - After adding a new skill/domain to the question bank
#    - When CV F1 drops below 0.70
