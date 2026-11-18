"""Scorer v4 held-out validation (run once; Mohler held-out split).

Reports, with question-cluster bootstrap 95% CIs:
- blended cosine baseline vs v4 without model vs v4 with model (calibrated)
- sensitivity excluding E11-E12 questions
- guard false-positive / catch analysis (tune design data + n=50 Poor +
  local-DB gibberish rounds, read-only, aggregate counts only)
- n=50 external scale check (never training data)

Writes artifacts/scorer_v4_validation.json (ignored).

Usage:
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python scripts/validate_scorer_v4.py
"""

from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import csv
import json
import sqlite3
import sys
from pathlib import Path

import joblib
import numpy as np
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import answer_guard as guard_v3
from modules.answer_guard_v4 import check_answer_quality_v4
from modules.scoring_features import build_scoring_features, feature_vector

SPLIT_PATH = ROOT / "data" / "mohler_question_split_v1.json"
MOHLER_PATH = ROOT / "data" / "external" / "mohler_asag" / "mohler_raw_open_ended.csv"
CALIBRATION_PATH = ROOT / "modules" / "scorer_v4_calibration.json"
REGRESSION_PATH = ROOT / "modules" / "scorer_v4_regression.joblib"
OUT_PATH = ROOT / "artifacts" / "scorer_v4_validation.json"
HELDOUT_CACHE = ROOT / "artifacts" / "mohler_heldout_features.json"
TUNE_CACHE = ROOT / "artifacts" / "mohler_tune_features.json"


def _qkey(row_id: str) -> str:
    return ".".join(row_id.split(".")[:2])


def _exam(row_id: str) -> str:
    return row_id.split(".")[0]


def _load_rows(keys: set[str]) -> list[dict]:
    with MOHLER_PATH.open(newline="", encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if _qkey(r["id"]) in keys]


def _calibrate(scores: np.ndarray) -> np.ndarray:
    data = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
    return np.interp(scores, data["x"], data["y"])


def _v4_base(features: dict, model_component: float | None) -> float:
    terms = {"s": (0.45, features["semantic_score"]), "t": (0.10, features["tfidf_score"])}
    if model_component is not None:
        terms["m"] = (0.25, model_component)
    total_w = sum(w for w, _ in terms.values())
    return 100.0 * sum(w * v for w, v in terms.values()) / total_w


def _corr(x: np.ndarray, y: np.ndarray) -> dict:
    return {
        "pearson_r": round(float(pearsonr(x, y).statistic), 4),
        "spearman_rho": round(float(spearmanr(x, y).statistic), 4),
        "n": int(len(x)),
    }


def _cluster_bootstrap(rows_idx_by_q: dict[str, list[int]], score: np.ndarray, y: np.ndarray,
                       rng: np.random.Generator, b: int = 2000) -> tuple[float, float]:
    questions = list(rows_idx_by_q)
    vals = []
    for _ in range(b):
        sampled = rng.choice(questions, size=len(questions), replace=True)
        idx = np.concatenate([rows_idx_by_q[q] for q in sampled])
        if np.std(score[idx]) == 0:
            continue
        vals.append(float(pearsonr(score[idx], y[idx]).statistic))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return round(float(lo), 4), round(float(hi), 4)


def main() -> int:
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8"))
    held_rows = _load_rows(set(split["heldout_questions"]))
    print(f"held-out rows: {len(held_rows)}", flush=True)

    cache: dict[str, dict] = {}
    if HELDOUT_CACHE.exists():
        cache = json.loads(HELDOUT_CACHE.read_text(encoding="utf-8"))
    feats: list[dict] = []
    for i, row in enumerate(held_rows):
        if row["id"] not in cache:
            cache[row["id"]] = build_scoring_features(
                answer_text=row["student_answer"], ideal_answer=row["instructor_answer"]
            )
            if (i + 1) % 200 == 0:
                print(f"held-out features {i + 1}/{len(held_rows)}", flush=True)
                HELDOUT_CACHE.write_text(json.dumps(cache), encoding="utf-8")
        feats.append(cache[row["id"]])
    HELDOUT_CACHE.write_text(json.dumps(cache), encoding="utf-8")

    payload = joblib.load(REGRESSION_PATH)
    model = payload["model"]
    X = np.array([feature_vector(f) for f in feats], dtype=float)
    model_pred = np.clip(model.predict(X), 0.0, 1.0)
    y = np.array([float(r["score_avg"]) for r in held_rows], dtype=float)

    blended = np.array([0.4 * f["tfidf_score"] + 0.6 * f["semantic_score"] for f in feats]) * 100.0
    v4_without_raw = np.array([_v4_base(f, None) for f in feats])
    v4_with_raw = np.array([_v4_base(f, float(p)) for f, p in zip(feats, model_pred)])
    v4_without = _calibrate(v4_without_raw)
    v4_with = _calibrate(v4_with_raw)

    by_q: dict[str, list[int]] = {}
    for i, r in enumerate(held_rows):
        by_q.setdefault(_qkey(r["id"]), []).append(i)
    rng = np.random.default_rng(20261116)

    result: dict = {"heldout": {}, "sensitivity_no_e11_e12": {}, "guards": {}, "n50": {}}
    for name, score in [
        ("blended_cosine", blended),
        ("v4_without_model", v4_without),
        ("v4_with_model", v4_with),
        ("model_pred_alone", model_pred * 100.0),
    ]:
        entry = _corr(score, y)
        lo, hi = _cluster_bootstrap(by_q, score, y, rng)
        entry["pearson_95ci_questions"] = [lo, hi]
        result["heldout"][name] = entry

    keep = np.array([_exam(r["id"]) not in {"E11", "E12"} for r in held_rows])
    by_q_sens = {q: [i for i in idxs if keep[i]] for q, idxs in by_q.items()}
    by_q_sens = {q: v for q, v in by_q_sens.items() if v}
    for name, score in [("blended_cosine", blended), ("v4_with_model", v4_with), ("v4_without_model", v4_without)]:
        entry = _corr(score[keep], y[keep])
        lo, hi = _cluster_bootstrap(by_q_sens, score, y, rng)
        entry["pearson_95ci_questions"] = [lo, hi]
        result["sensitivity_no_e11_e12"][name] = entry

    # Guard design data on TUNE (features/scores not needed; raw guard calls).
    split_tune = _load_rows(set(split["tune_questions"]))
    for label, fn in [
        ("v3", lambda r: guard_v3.check_answer_quality_v2(r["student_answer"], question_text=r["question"], ideal_answer=r["instructor_answer"])),
        ("v4", lambda r: check_answer_quality_v4(r["student_answer"], question_text=r["question"], ideal_answer=r["instructor_answer"])),
    ]:
        capped_high = capped_low = n_high = n_low = 0
        for r in split_tune:
            g = float(r["score_avg"])
            capped = bool(fn(r).get("cap_required"))
            if g >= 4.5:
                n_high += 1
                capped_high += int(capped)
            elif g <= 1.0:
                n_low += 1
                capped_low += int(capped)
        result["guards"][f"mohler_tune_{label}"] = {
            "false_positive_rate_grade_gte_4_5": round(capped_high / max(n_high, 1), 4),
            "catch_rate_grade_lte_1_0": round(capped_low / max(n_low, 1), 4),
            "n_high": n_high,
            "n_low": n_low,
        }

    # n=50 Poor catch + human scale check (external; never trained on).
    import openpyxl

    wb = openpyxl.load_workbook(ROOT / "data" / "interViv — Answer Rating (Responses).xlsx",
                                 read_only=True, data_only=True)
    ws = wb["Form Responses 1"]
    xrows = list(ws.iter_rows(values_only=True))
    human_means = np.array([[float(v) for v in r] for r in xrows[1:]], dtype=float).mean(axis=0)

    with (ROOT / "data" / "baseline_v2_system_scores.csv").open(newline="", encoding="utf-8") as fh:
        sys_rows = list(csv.DictReader(fh))
    with (ROOT / "data" / "baseline_v2_key.csv").open(newline="", encoding="utf-8") as fh:
        key_rows = {int(r["row_id"]): r for r in csv.DictReader(fh)}

    with (ROOT / "data" / "interview_dataset_v6.csv").open(newline="", encoding="utf-8") as fh:
        v6_by_q = {r["question"]: r for r in csv.DictReader(fh)}

    poor_caught = {"v3": 0, "v4": 0}
    poor_total = 0
    v4_scores, human_scores = [], []
    for srow in sys_rows:
        pos = int(srow["form_position"])
        krow = key_rows[int(srow["row_id"])]
        answer, question = krow["answer"], krow["question"]
        v6row = v6_by_q.get(question) or {}
        ideal = v6row.get("ideal_answer") or ""
        if srow["label"] == "Poor":
            poor_total += 1
            g3 = guard_v3.check_answer_quality_v2(answer, question_text=question, ideal_answer=ideal)
            g4 = check_answer_quality_v4(answer, question_text=question, ideal_answer=ideal)
            poor_caught["v3"] += int(bool(g3.get("cap_required")))
            poor_caught["v4"] += int(bool(g4.get("cap_required")))
        feats_n = build_scoring_features(answer_text=answer, ideal_answer=ideal)
        pred_n = float(np.clip(model.predict(np.array([feature_vector(feats_n)]))[0], 0.0, 1.0))
        v4_scores.append(float(_calibrate(np.array([_v4_base(feats_n, pred_n)]))[0]))
        human_scores.append(float(human_means[pos - 1]))
    result["guards"]["n50_poor_catch"] = {
        "v3": round(poor_caught["v3"] / max(poor_total, 1), 4),
        "v4": round(poor_caught["v4"] / max(poor_total, 1), 4),
        "n_poor": poor_total,
    }
    result["n50"]["note"] = "ideals joined from interview_dataset_v6 by question; external scale check only"
    result["n50"]["v4_vs_human_mean"] = _corr(np.array(v4_scores), np.array(human_scores))

    # Local-DB gibberish rounds (read-only; aggregate catch only).
    db_path = ROOT / "local-data" / "interviv-local.sqlite3"
    con = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    texts = [r[0] for r in con.execute(
        "SELECT answer_text FROM rounds WHERE guard_applied='gibberish' AND answer_text IS NOT NULL"
    )]
    con.close()
    caught = sum(1 for t in texts if check_answer_quality_v4(t).get("cap_required"))
    result["guards"]["local_db_gibberish"] = {
        "rows": len(texts),
        "v4_catch_rate": round(caught / max(len(texts), 1), 4),
    }

    OUT_PATH.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
