"""Measure keyword_coverage contribution without touching production artifacts.

Retrains LogisticRegression three ways on ml_training_data.csv (seed 42):
  (a) all five features
  (b) four features, keyword_coverage removed
  (c) five features on rows where keyword_coverage != 0.5 default

Writes joblibs + metrics under research/keyword_feature_ablation/.
Optionally evaluates (a)/(b) on SciEntsBank + Beetle via grader_lab with a
temporary monkeypatch of the classifier loader / feature vector.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from retrain_ml_model import (  # noqa: E402
    _fit_with_balance,
    make_pipeline,
)
from modules.nlp_scorer import NLPScorer  # noqa: E402


def _clean_keywords(value: Any) -> str:
    """Match audit/production empty-keyword semantics (avoid str(NaN) == 'nan')."""
    if value is None:
        return ""
    try:
        if isinstance(value, float) and np.isnan(value):
            return ""
    except TypeError:
        pass
    text = str(value).strip()
    if text.lower() in {"", "nan", "none"}:
        return ""
    return text


def build_features_cleaned(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Same 5-feature layout as retrain_ml_model, with NaN keywords treated as empty."""
    scorer = NLPScorer()
    rows: list[list[float]] = []
    labels: list[str] = []
    for _, row in df.iterrows():
        answer_text = str(row.get("answer_text") or row.get("answer") or "")
        result = scorer.get_feature_scores(
            answer_text=answer_text,
            ideal_answer=str(row.get("ideal_answer", "") or ""),
            ideal_keywords=_clean_keywords(row.get("ideal_keywords", "")),
        )
        rows.append(
            [
                result["cosine_similarity"],
                result["clarity_score"],
                result["keyword_coverage"],
                len(answer_text.split()),
                result["concept_coverage"],
            ]
        )
        labels.append(str(row.get("label", "Average")))
    return np.array(rows), np.array(labels)

OUT_DIR = Path(__file__).resolve().parent / "keyword_feature_ablation"
FEATURE_NAMES_5 = [
    "cosine_similarity",
    "clarity_score",
    "keyword_coverage",
    "word_count",
    "concept_coverage",
]
FEATURE_NAMES_4 = [
    "cosine_similarity",
    "clarity_score",
    "word_count",
    "concept_coverage",
]
SEED = 42
KW_IDX = 2


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _cv_metrics(
    X: np.ndarray,
    y: np.ndarray,
    *,
    model_type: str = "lr",
    balanced: bool = True,
    n_splits: int = 5,
) -> dict[str, Any]:
    classes = sorted(np.unique(y).tolist())
    # simplification: drop folds if a class has fewer samples than n_splits
    min_class = int(min(np.bincount([classes.index(v) for v in y])))
    splits = min(n_splits, min_class)
    if splits < 2:
        return {
            "n_splits": splits,
            "error": "too_few_samples_for_stratified_cv",
            "label_counts": {c: int((y == c).sum()) for c in classes},
        }

    cv = StratifiedKFold(n_splits=splits, shuffle=True, random_state=SEED)
    y_pred = cross_val_predict(make_pipeline(model_type, balanced), X, y, cv=cv)
    acc = float((y_pred == y).mean())
    macro = float(f1_score(y, y_pred, average="macro", labels=classes, zero_division=0))
    report = classification_report(
        y, y_pred, labels=classes, output_dict=True, zero_division=0
    )
    per_class = {
        cls: {
            "precision": float(report[cls]["precision"]),
            "recall": float(report[cls]["recall"]),
            "f1": float(report[cls]["f1-score"]),
            "support": int(report[cls]["support"]),
        }
        for cls in classes
    }
    return {
        "n_splits": splits,
        "n_rows": int(len(y)),
        "accuracy": round(acc, 4),
        "macro_f1": round(macro, 4),
        "per_class_f1": {cls: per_class[cls]["f1"] for cls in classes},
        "per_class": per_class,
        "label_counts": {c: int((y == c).sum()) for c in classes},
    }


def _fit_full(
    X: np.ndarray,
    y: np.ndarray,
    *,
    model_type: str = "lr",
    balanced: bool = True,
) -> Any:
    pipe = make_pipeline(model_type, balanced)
    _fit_with_balance(pipe, X, y, model_type, balanced)
    return pipe


def _lr_coefficients(pipe: Any, feature_names: list[str]) -> dict[str, Any]:
    clf = pipe.named_steps["clf"]
    classes = [str(c) for c in clf.classes_]
    # One-vs-rest rows for multinomial LR
    coef = clf.coef_
    out: dict[str, Any] = {
        "classes": classes,
        "intercept": {classes[i]: float(clf.intercept_[i]) for i in range(len(classes))},
        "coef_by_class": {
            classes[i]: {
                feature_names[j]: float(coef[i, j]) for j in range(len(feature_names))
            }
            for i in range(len(classes))
        },
        "mean_abs_coef": {
            feature_names[j]: float(np.mean(np.abs(coef[:, j])))
            for j in range(len(feature_names))
        },
    }
    return out


def train_variants(dataset: Path) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(dataset)
    X, y = build_features_cleaned(df)
    assert X.shape == (len(df), 5), X.shape

    kw = X[:, KW_IDX]
    # Audit: 805 pinned at empty-keyword default 0.5; 86 rows with non-default coverage.
    real_mask = ~np.isclose(kw, 0.5)
    n_default = int((~real_mask).sum())
    n_real = int(real_mask.sum())
    nonempty_kw = df["ideal_keywords"].map(_clean_keywords).astype(bool)
    n_with_keywords = int(nonempty_kw.sum())

    variants: dict[str, dict[str, Any]] = {}

    # (a) five features, all 891
    X_a = X
    y_a = y
    names_a = FEATURE_NAMES_5
    cv_a = _cv_metrics(X_a, y_a)
    # same seed/split as retrain_ml_model for held-out report
    X_tr, X_te, y_tr, y_te = train_test_split(
        X_a, y_a, test_size=0.2, stratify=y_a, random_state=SEED
    )
    pipe_a_hold = _fit_full(X_tr, y_tr)
    pipe_a = _fit_full(X_a, y_a)
    path_a = OUT_DIR / "answer_quality_lr_5feat.joblib"
    joblib.dump(pipe_a, path_a)
    coef_a = _lr_coefficients(pipe_a, names_a)
    variants["a_all_five"] = {
        "description": "all five features on 891 rows",
        "feature_names": names_a,
        "n_rows": int(len(y_a)),
        "cv": cv_a,
        "held_out_macro_f1": round(
            float(
                f1_score(
                    y_te,
                    pipe_a_hold.predict(X_te),
                    average="macro",
                    zero_division=0,
                )
            ),
            4,
        ),
        "coefficients": coef_a,
        "keyword_coverage_mean_abs_coef": coef_a["mean_abs_coef"]["keyword_coverage"],
        "artifact": str(path_a.relative_to(PROJECT_ROOT)),
        "artifact_sha256": _sha256(path_a),
    }

    # (b) drop keyword_coverage
    X_b = np.delete(X, KW_IDX, axis=1)
    names_b = FEATURE_NAMES_4
    cv_b = _cv_metrics(X_b, y)
    pipe_b = _fit_full(X_b, y)
    path_b = OUT_DIR / "answer_quality_lr_4feat_no_keyword.joblib"
    joblib.dump(pipe_b, path_b)
    coef_b = _lr_coefficients(pipe_b, names_b)
    variants["b_no_keyword"] = {
        "description": "four features, keyword_coverage removed, 891 rows",
        "feature_names": names_b,
        "n_rows": int(len(y)),
        "cv": cv_b,
        "coefficients": coef_b,
        "artifact": str(path_b.relative_to(PROJECT_ROOT)),
        "artifact_sha256": _sha256(path_b),
    }

    # (c) five features on non-default keyword rows only
    X_c = X[real_mask]
    y_c = y[real_mask]
    cv_c = _cv_metrics(X_c, y_c)
    pipe_c = _fit_full(X_c, y_c) if len(y_c) >= 3 else None
    path_c = OUT_DIR / "answer_quality_lr_5feat_real_keyword_only.joblib"
    if pipe_c is not None:
        joblib.dump(pipe_c, path_c)
        coef_c = _lr_coefficients(pipe_c, names_a)
    else:
        coef_c = None
    variants["c_real_keyword_rows"] = {
        "description": (
            "five features trained only on rows with keyword_coverage != 0.5 "
            f"(n={n_real}; {n_with_keywords} rows have non-empty ideal_keywords)"
        ),
        "feature_names": names_a,
        "n_rows": n_real,
        "n_pinned_at_0.5": n_default,
        "n_with_nonempty_keywords": n_with_keywords,
        "cv": cv_c,
        "coefficients": coef_c,
        "artifact": str(path_c.relative_to(PROJECT_ROOT)) if pipe_c is not None else None,
        "artifact_sha256": _sha256(path_c) if pipe_c is not None and path_c.exists() else None,
        "note": "n too small for a strong conclusion",
    }

    summary = {
        "training_date": date.today().isoformat(),
        "dataset": str(dataset),
        "dataset_sha256": _sha256(dataset),
        "seed": SEED,
        "model_type": "LogisticRegression",
        "balanced": True,
        "feature_build": (
            "retrain_ml_model layout with NaN/empty ideal_keywords cleaned to '' "
            "so empty-keyword default score 0.5 matches docs/keyword_coverage_audit.md"
        ),
        "n_pinned_keyword_coverage_0.5": n_default,
        "n_real_keyword_coverage": n_real,
        "n_with_nonempty_keywords": n_with_keywords,
        "variants": variants,
        "production_artifact_untouched": "modules/answer_quality_lr.joblib",
    }
    metrics_path = OUT_DIR / "cv_metrics.json"
    metrics_path.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def _install_classifier_patch(
    *,
    artifact: Path,
    drop_keyword: bool,
) -> tuple[Any, Any]:
    """Monkeypatch pipeline classifier load + feature build for research eval."""
    from backend.scoring import pipeline

    model = joblib.load(artifact)
    original_load = pipeline._load_classifier_model
    original_features = pipeline._classifier_features

    def _load() -> Any:
        return model

    def _features(
        cos_similarity: float,
        length_ratio: float,
        keyword_coverage: float,
        word_count: int,
        concept_coverage: float = 0.5,
    ) -> list[list[float]]:
        if drop_keyword:
            # Match training (b): cos, clarity/length proxy, word_count, concept
            return [[
                cos_similarity,
                length_ratio,
                float(word_count),
                concept_coverage,
            ]]
        return original_features(
            cos_similarity=cos_similarity,
            length_ratio=length_ratio,
            keyword_coverage=keyword_coverage,
            word_count=word_count,
            concept_coverage=concept_coverage,
        )

    pipeline._load_classifier_model = _load  # type: ignore[assignment]
    pipeline._classifier_features = _features  # type: ignore[assignment]
    # clear lru caches so locate/load are not sticky from a prior run
    if hasattr(pipeline._load_classifier_model, "cache_clear"):
        pass
    pipeline._locate_classifier_model_file.cache_clear()
    # original_load is lru_cached; replace the cached function object entirely
    return original_load, original_features


def _restore_classifier_patch(
    original_load: Any,
    original_features: Any,
) -> None:
    from backend.scoring import pipeline

    pipeline._load_classifier_model = original_load
    pipeline._classifier_features = original_features
    pipeline._locate_classifier_model_file.cache_clear()
    if hasattr(original_load, "cache_clear"):
        original_load.cache_clear()


def eval_ood(
    *,
    variant_key: str,
    artifact: Path,
    drop_keyword: bool,
    results_subdir: str,
    max_examples: int | None = None,
) -> dict[str, Any]:
    import os

    from research.grader_lab.baselines import InterVivCurrentBaseline
    from research.grader_lab.datasets import DEFAULT_DATA_DIR, load_registered_datasets
    from research.grader_lab.metrics import calculate_metrics

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    originals = _install_classifier_patch(artifact=artifact, drop_keyword=drop_keyword)
    try:
        datasets = load_registered_datasets(DEFAULT_DATA_DIR)
        baseline = InterVivCurrentBaseline(enable_semantic=True)
        out: dict[str, Any] = {"variant": variant_key, "artifact": str(artifact)}
        for name in ("scientsbank", "beetle"):
            ds = datasets[name]
            if ds.status != "loaded":
                out[name] = {"status": ds.status, "note": ds.note}
                continue
            examples = ds.examples
            if max_examples is not None:
                examples = examples[:max_examples]
            preds = baseline.predict_many(examples)
            metrics = {m.metric: m.value for m in calculate_metrics(examples, preds)}
            out[name] = {
                "n": len(examples),
                "grading_accuracy": metrics.get("grading_accuracy"),
                "macro_f1": metrics.get("macro_f1"),
                "off_topic_detection_rate": metrics.get("off_topic_detection_rate"),
                "off_topic_false_positive_rate": metrics.get(
                    "off_topic_false_positive_rate"
                ),
                "off_topic_precision": metrics.get("off_topic_precision"),
            }
        return out
    finally:
        _restore_classifier_patch(*originals)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "data" / "ml_training_data.csv",
    )
    parser.add_argument(
        "--skip-ood",
        action="store_true",
        help="Only run CV / train; skip SciEntsBank/Beetle eval",
    )
    parser.add_argument(
        "--ood-only",
        action="store_true",
        help="Skip retrain; evaluate existing artifacts on SciEntsBank/Beetle",
    )
    parser.add_argument("--max-examples-per-dataset", type=int)
    args = parser.parse_args()

    if args.ood_only:
        metrics_path = OUT_DIR / "cv_metrics.json"
        summary = json.loads(metrics_path.read_text())
    else:
        summary = train_variants(args.dataset)
        print(json.dumps({k: summary["variants"][k]["cv"] for k in summary["variants"]}, indent=2))
        print(
            "keyword_coverage mean |coef| (a):",
            summary["variants"]["a_all_five"]["keyword_coverage_mean_abs_coef"],
        )
        print("n real keyword rows (c):", summary["n_real_keyword_coverage"])

    if not args.skip_ood:
        ood_results = []
        for key, drop in (("a_all_five", False), ("b_no_keyword", True)):
            art = PROJECT_ROOT / summary["variants"][key]["artifact"]
            print(f"OOD eval {key} …", flush=True)
            ood_results.append(
                eval_ood(
                    variant_key=key,
                    artifact=art,
                    drop_keyword=drop,
                    results_subdir=key,
                    max_examples=args.max_examples_per_dataset,
                )
            )
            print(json.dumps(ood_results[-1], indent=2), flush=True)
        ood_path = OUT_DIR / "ood_metrics.json"
        ood_path.write_text(json.dumps(ood_results, indent=2) + "\n")
        print("wrote", ood_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
