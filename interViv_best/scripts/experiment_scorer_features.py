"""Bounded feature experiment: tune + n=50-dev only. NOT implemented in v4.

Candidates: capped length ratio, clause-level semantic coverage, each
alone and multiplied by semantic_score. Stop rule (pre-registered): if
nothing reaches Spearman 0.6 on n=50-dev, scorer feature work stops.

Held-out is never read here.

Usage:
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python scripts/experiment_scorer_features.py
"""

from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import csv
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from scipy.stats import pearsonr, rankdata, spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_PATH = ROOT / "artifacts" / "scorer_feature_experiment.json"


def _corr(x: np.ndarray, y: np.ndarray) -> dict:
    return {
        "pearson": round(float(pearsonr(x, y).statistic), 4),
        "spearman": round(float(spearmanr(x, y).statistic), 4),
        "n": int(len(x)),
    }


def _partial_spearman(x: np.ndarray, y: np.ndarray, control: np.ndarray) -> float | None:
    rx = rankdata(x)
    ry = rankdata(y)
    rc = rankdata(control)
    if np.std(rx) == 0.0 or np.std(ry) == 0.0 or np.std(rc) == 0.0:
        return None
    r_xy = float(pearsonr(rx, ry).statistic)
    r_xc = float(pearsonr(rx, rc).statistic)
    r_yc = float(pearsonr(ry, rc).statistic)
    denom = math.sqrt(max(0.0, (1.0 - r_xc * r_xc) * (1.0 - r_yc * r_yc)))
    if denom <= 1e-12:
        return None
    val = (r_xy - r_xc * r_yc) / denom
    return round(float(max(-1.0, min(1.0, val))), 4)


def _clause_coverage(answer: str, ideal: str, scorer) -> float:
    ref = [s.strip() for s in re.split(r"(?<=[.!?])\s+", ideal or "") if s.strip()]
    ans = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer or "") if s.strip()]
    if not ref or not ans or scorer is None:
        return 0.0
    hits = 0
    for sentence in ref:
        sim = scorer.max_similarity(sentence, ans)
        if sim is not None and sim >= 0.5:
            hits += 1
    return hits / len(ref)


def main() -> int:
    from modules import nlp_scorer

    scorer = nlp_scorer._get_semantic_scorer()
    split = json.loads((ROOT / "data/mohler_question_split_v1.json").read_text(encoding="utf-8"))
    tune_keys = set(split["tune_questions"])

    def qk(rid: str) -> str:
        return ".".join(rid.split(".")[:2])

    tune_rows = [
        r for r in csv.DictReader(open(ROOT / "data/external/mohler_asag/mohler_raw_open_ended.csv", encoding="utf-8"))
        if qk(r["id"]) in tune_keys
    ]
    tune_feats = json.loads((ROOT / "artifacts/mohler_tune_features.json").read_text(encoding="utf-8"))

    clause_cache_path = ROOT / "artifacts/mohler_tune_clause_coverage.json"
    clause_cache = json.loads(clause_cache_path.read_text()) if clause_cache_path.exists() else {}

    tune = {"word_count": [], "semantic_score": [], "capped_length_ratio": [], "clause_coverage": []}
    tune_sem, tune_y = [], []
    for i, row in enumerate(tune_rows):
        ans_len = len(row["student_answer"].split())
        ref_len = max(len(row["instructor_answer"].split()), 1)
        tune["word_count"].append(float(ans_len))
        sem_val = float(tune_feats[row["id"]]["semantic_score"])
        tune["semantic_score"].append(sem_val)
        tune["capped_length_ratio"].append(min(ans_len / ref_len, 1.0))
        if row["id"] not in clause_cache:
            clause_cache[row["id"]] = _clause_coverage(row["student_answer"], row["instructor_answer"], scorer)
            if (i + 1) % 300 == 0:
                print(f"tune clause {i + 1}/{len(tune_rows)}", flush=True)
                clause_cache_path.write_text(json.dumps(clause_cache))
        tune["clause_coverage"].append(float(clause_cache[row["id"]]))
        tune_sem.append(sem_val)
        tune_y.append(float(row["score_avg"]))
    clause_cache_path.write_text(json.dumps(clause_cache))

    n50_cache = json.loads((ROOT / "artifacts/n50_features.json").read_text(encoding="utf-8"))
    sys_rows = list(csv.DictReader(open(ROOT / "data/baseline_v2_system_scores.csv", encoding="utf-8")))
    key_rows = {int(r["row_id"]): r for r in csv.DictReader(open(ROOT / "data/baseline_v2_key.csv", encoding="utf-8"))}
    v6 = {r["question"]: r for r in csv.DictReader(open(ROOT / "data/interview_dataset_v6.csv", encoding="utf-8"))}
    import openpyxl

    wb = openpyxl.load_workbook(ROOT / "data/interViv — Answer Rating (Responses).xlsx", read_only=True, data_only=True)
    xrows = list(wb["Form Responses 1"].iter_rows(values_only=True))
    human_means = np.array([[float(v) for v in r] for r in xrows[1:]], dtype=float).mean(axis=0)

    dev = {"word_count": [], "semantic_score": [], "capped_length_ratio": [], "clause_coverage": []}
    dev_sem, dev_y = [], []
    for srow in sys_rows:
        krow = key_rows[int(srow["row_id"])]
        ideal = (v6.get(krow["question"]) or {}).get("ideal_answer") or ""
        ans_len = len(krow["answer"].split())
        ref_len = max(len(ideal.split()), 1)
        dev["word_count"].append(float(ans_len))
        dev["capped_length_ratio"].append(min(ans_len / ref_len, 1.0))
        feats = n50_cache[str(srow["form_position"])]
        sem_val = float(feats["semantic_score"])
        dev["semantic_score"].append(sem_val)
        dev["clause_coverage"].append(float(feats["ref_sentence_coverage"]))
        dev_sem.append(sem_val)
        dev_y.append(float(human_means[int(srow["form_position"]) - 1]))

    tune_y_arr = np.array(tune_y, dtype=float)
    dev_y_arr = np.array(dev_y, dtype=float)
    tune_sem_arr = np.array(tune_sem, dtype=float)
    dev_sem_arr = np.array(dev_sem, dtype=float)
    dev_wc_arr = np.array(dev["word_count"], dtype=float)

    series = [
        ("word_count", "baseline", np.array(tune["word_count"], dtype=float), dev_wc_arr),
        ("semantic_score", "baseline", np.array(tune["semantic_score"], dtype=float), dev_sem_arr),
        ("capped_length_ratio", "candidate", np.array(tune["capped_length_ratio"], dtype=float), np.array(dev["capped_length_ratio"], dtype=float)),
        ("capped_length_ratio_x_semantic", "candidate", np.array(tune["capped_length_ratio"], dtype=float) * tune_sem_arr, np.array(dev["capped_length_ratio"], dtype=float) * dev_sem_arr),
        ("clause_coverage", "candidate", np.array(tune["clause_coverage"], dtype=float), np.array(dev["clause_coverage"], dtype=float)),
        ("clause_coverage_x_semantic", "candidate", np.array(tune["clause_coverage"], dtype=float) * tune_sem_arr, np.array(dev["clause_coverage"], dtype=float) * dev_sem_arr),
    ]

    result: dict = {
        "tune": {},
        "n50_dev": {},
        "table": [],
        "note": "Mohler tune (n=1484) and n=50-dev only; partial Spearman on n=50-dev controls for word_count.",
    }
    for name, role, t_arr, d_arr in series:
        t_corr = _corr(t_arr, tune_y_arr)
        d_corr = _corr(d_arr, dev_y_arr)
        d_partial = None if name == "word_count" else _partial_spearman(d_arr, dev_y_arr, dev_wc_arr)
        d_corr["partial_spearman_given_word_count"] = d_partial
        result["tune"][name] = {"role": role, **t_corr}
        result["n50_dev"][name] = {"role": role, **d_corr}
        result["table"].append({
            "feature": name,
            "role": role,
            "tune_spearman": t_corr["spearman"],
            "n50_dev_spearman": d_corr["spearman"],
            "n50_dev_partial_spearman_given_word_count": d_partial,
        })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
