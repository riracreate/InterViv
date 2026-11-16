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
import re
import sys
from pathlib import Path

import numpy as np
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_PATH = ROOT / "artifacts" / "scorer_feature_experiment.json"


def _corr(x: np.ndarray, y: np.ndarray) -> dict:
    return {
        "pearson": round(float(pearsonr(x, y).statistic), 4),
        "spearman": round(float(spearmanr(x, y).statistic), 4),
        "n": int(len(x)),
    }


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

    tune = {"capped_length_ratio": [], "clause_coverage": []}
    tune_sem, tune_y = [], []
    for i, row in enumerate(tune_rows):
        ans_len = len(row["student_answer"].split())
        ref_len = max(len(row["instructor_answer"].split()), 1)
        tune["capped_length_ratio"].append(min(ans_len / ref_len, 1.0))
        if row["id"] not in clause_cache:
            clause_cache[row["id"]] = _clause_coverage(row["student_answer"], row["instructor_answer"], scorer)
            if (i + 1) % 300 == 0:
                print(f"tune clause {i + 1}/{len(tune_rows)}", flush=True)
                clause_cache_path.write_text(json.dumps(clause_cache))
        tune["clause_coverage"].append(float(clause_cache[row["id"]]))
        tune_sem.append(tune_feats[row["id"]]["semantic_score"])
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

    dev = {"capped_length_ratio": [], "clause_coverage": []}
    dev_sem, dev_y = [], []
    for srow in sys_rows:
        krow = key_rows[int(srow["row_id"])]
        ideal = (v6.get(krow["question"]) or {}).get("ideal_answer") or ""
        ans_len = len(krow["answer"].split())
        ref_len = max(len(ideal.split()), 1)
        dev["capped_length_ratio"].append(min(ans_len / ref_len, 1.0))
        feats = n50_cache[str(srow["form_position"])]
        dev["clause_coverage"].append(float(feats["ref_sentence_coverage"]))
        dev_sem.append(float(feats["semantic_score"]))
        dev_y.append(float(human_means[int(srow["form_position"]) - 1]))

    result: dict = {"tune": {}, "n50_dev": {}, "stop_rule": "Spearman >= 0.6 on n=50-dev required to continue scorer feature work"}
    for name, tune_vals, dev_vals in [
        ("capped_length_ratio", tune["capped_length_ratio"], dev["capped_length_ratio"]),
        ("clause_coverage", tune["clause_coverage"], dev["clause_coverage"]),
    ]:
        t_arr, d_arr = np.array(tune_vals), np.array(dev_vals)
        result["tune"][name] = _corr(t_arr, np.array(tune_y))
        result["n50_dev"][name] = _corr(d_arr, np.array(dev_y))
        result["tune"][f"{name}_x_semantic"] = _corr(t_arr * np.array(tune_sem), np.array(tune_y))
        result["n50_dev"][f"{name}_x_semantic"] = _corr(d_arr * np.array(dev_sem), np.array(dev_y))

    best_dev = max(v["spearman"] for v in result["n50_dev"].values())
    result["best_n50_dev_spearman"] = best_dev
    result["stop_rule_triggered"] = bool(best_dev < 0.6)
    OUT_PATH.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
