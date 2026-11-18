"""measure_mohler_and_human_baseline.py — WS3 Step 1 baseline measurement (read-only).

Scores every Mohler ASAG row (data/external/mohler_asag/) with the current
deterministic pipeline without altering any scorer code, reports signal
correlations and guard behavior against Mohler human grades, inspects
data/interViv — Answer Rating (Responses).xlsx structurally (zero PII), and
summarizes the same signals on the n=50 human-rated validation set.

Usage:
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python scripts/measure_mohler_and_human_baseline.py
"""

from __future__ import annotations

import os

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import openpyxl
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.scoring.pipeline import (  # noqa: E402
    _CLASSIFIER_LABEL_SCORE,
    _compute_server_side_metrics,
    _server_word_count,
    run_scoring_pipeline,
)
from modules import answer_guard as ag  # noqa: E402

MOHLER_DIR = ROOT / "data" / "external" / "mohler_asag"
XLSX_PATH = ROOT / "data" / "interViv — Answer Rating (Responses).xlsx"
SYS_SCORES_PATH = ROOT / "data" / "baseline_v2_system_scores.csv"
KEY_PATH = ROOT / "data" / "baseline_v2_key.csv"
V6_PATH = ROOT / "data" / "interview_dataset_v6.csv"
ML_DATA_PATH = ROOT / "data" / "ml_training_data.csv"
LR_PATH = ROOT / "modules" / "answer_quality_lr.joblib"
OUT_JSON = ROOT / "artifacts" / "ws3_step1_baseline_measurements.json"

_ORDINAL_LABEL = {"Poor": 0, "Average": 1, "Good": 2}


def _norm_ws(text: str) -> str:
    return " ".join(str(text or "").split())


def _safe_corr(x: list[float], y: list[float]) -> dict[str, Any]:
    ax = np.asarray(x, dtype=float)
    ay = np.asarray(y, dtype=float)
    mask = np.isfinite(ax) & np.isfinite(ay)
    ax, ay = ax[mask], ay[mask]
    n = int(len(ax))
    if n < 3 or np.std(ax) == 0.0 or np.std(ay) == 0.0:
        return {"n": n, "pearson_r": None, "pearson_p": None, "spearman_rho": None, "spearman_p": None}
    pr, pp = pearsonr(ax, ay)
    sr, sp = spearmanr(ax, ay)
    return {
        "n": n,
        "pearson_r": round(float(pr), 4),
        "pearson_p": float(f"{pp:.4e}"),
        "spearman_rho": round(float(sr), 4),
        "spearman_p": float(f"{sp:.4e}"),
    }


def _score_mohler_rows(rows: list[dict[str, Any]], strip_br: bool = False) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in rows:
        ans = row["student_answer"]
        if strip_br:
            ans = re.sub(r"<br\s*/?>", " ", ans, flags=re.I)
        ref = row["instructor_answer"]
        q = row["question"]
        res = run_scoring_pipeline(
            answer_text=ans,
            question_context={
                "question": q,
                "ideal_answer": ref,
                "ideal_keywords": "",
                "skill": "DSA",
            },
            difficulty="medium",
        )
        sb = res["scoring_breakdown"]
        fb = sb["formula_breakdown"]
        unguarded = max(
            0.0,
            min(
                float(fb["base_score"])
                + float(fb["kg_bonus"])
                + float(fb["ner_bonus"])
                - float(fb["brevity_penalty"]),
                100.0,
            ),
        )
        sem = sb["semantic_score"]
        tfidf = float(sb["tfidf_score"])
        blended_cos = (0.40 * tfidf + 0.60 * float(sem)) if sem is not None else tfidf
        wc = int(sb["server_word_count"])
        srv_cos, srv_len_ratio = _compute_server_side_metrics(ans, ref, wc)
        probs = sb.get("classifier_probabilities") or {}
        lbl = res["svm_label"]
        records.append({
            "id": row["id"],
            "qid": row["id"].rsplit(".", 1)[0],
            "subset": row["subset"],
            "question": q,
            "instructor_answer": ref,
            "student_answer": ans,
            "score_avg": float(row["score_avg"]),
            "score_grader_1": float(row["score_grader_1"]),
            "score_grader_2": float(row["score_grader_2"]),
            "final_score": float(res["final_score"]),
            "unguarded_final_score": round(unguarded, 4),
            "nlp_score": float(res["nlp_score"]),
            "semantic_score": float(sem) if sem is not None else np.nan,
            "semantic_score_zero_filled": float(sem) if sem is not None else 0.0,
            "semantic_available": bool(sb["semantic_scoring_available"]),
            "blended_cosine": blended_cos,
            "tfidf_score": tfidf,
            "server_token_overlap": srv_cos,
            "server_length_ratio": srv_len_ratio,
            "clarity_score": float(sb["clarity_score"]),
            "keyword_coverage": float(sb["keyword_coverage"]),
            "concept_coverage": float(sb["concept_coverage"]),
            "server_word_count": wc,
            "ref_word_count": _server_word_count(ref),
            "svm_label": lbl,
            "clf_weight": float(_CLASSIFIER_LABEL_SCORE.get(lbl, 0.50)),
            "clf_ordinal": float(_ORDINAL_LABEL.get(lbl, 1)),
            "clf_prob_good": float(probs.get("Good", 0.0)),
            "clf_expected_weight": (
                0.20 * float(probs.get("Poor", 0.0))
                + 0.50 * float(probs.get("Average", 0.0))
                + 0.75 * float(probs.get("Good", 0.0))
            ),
            "guard_applied": res["guard_applied"] or "none",
            "guard_cap": sb["guard"].get("score_cap"),
            "has_br_tag": bool(re.search(r"<br\s*/?>", row["student_answer"], re.I)),
        })
    return records


def _summarize_mohler_split(records: list[dict[str, Any]]) -> dict[str, Any]:
    y = [r["score_avg"] for r in records]
    signals = {
        "final_score_guarded": [r["final_score"] for r in records],
        "final_score_unguarded": [r["unguarded_final_score"] for r in records],
        "nlp_score": [r["nlp_score"] for r in records],
        "semantic_cosine_minilm_valid": [r["semantic_score"] for r in records],
        "semantic_cosine_minilm_zero_filled": [r["semantic_score_zero_filled"] for r in records],
        "blended_cosine_40tfidf_60sem": [r["blended_cosine"] for r in records],
        "server_token_overlap": [r["server_token_overlap"] for r in records],
        "tfidf_score": [r["tfidf_score"] for r in records],
        "server_word_count": [float(r["server_word_count"]) for r in records],
        "classifier_label_pipeline_weight": [r["clf_weight"] for r in records],
        "classifier_label_ordinal": [r["clf_ordinal"] for r in records],
        "classifier_prob_good": [r["clf_prob_good"] for r in records],
        "classifier_expected_weight": [r["clf_expected_weight"] for r in records],
    }
    correlations = {k: _safe_corr(v, y) for k, v in signals.items()}

    # Within-question correlations
    by_q: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_q[r["qid"]].append(r)

    within_q_keys = [
        "final_score",
        "unguarded_final_score",
        "semantic_score",
        "blended_cosine",
        "tfidf_score",
        "server_word_count",
        "clf_weight",
    ]
    within_q: dict[str, Any] = {}
    for key in within_q_keys:
        pr_vals: list[float] = []
        sr_vals: list[float] = []
        for q_rows in by_q.values():
            c = _safe_corr([float(x[key]) for x in q_rows], [x["score_avg"] for x in q_rows])
            if c["pearson_r"] is not None:
                pr_vals.append(c["pearson_r"])
                sr_vals.append(c["spearman_rho"])
        within_q[key] = {
            "questions_used": len(pr_vals),
            "mean_pearson_r": round(float(np.mean(pr_vals)), 4) if pr_vals else None,
            "mean_spearman_rho": round(float(np.mean(sr_vals)), 4) if sr_vals else None,
        }

    # Guard breakdown across all 10 rules + none
    all_guard_names = [
        "none",
        "too_short",
        "truncated_fragment",
        "repetition",
        "gibberish",
        "question_parroting",
        "off_topic",
        "keyword_stuffing",
        "entity_swap",
        "low_density",
        "empty",
    ]
    guard_stats: list[dict[str, Any]] = []
    by_guard: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        by_guard[r["guard_applied"]].append(r)
    for gname in all_guard_names:
        items = by_guard.get(gname, [])
        if not items:
            guard_stats.append({"guard": gname, "count": 0, "pct": 0.0})
            continue
        scores_h = [x["score_avg"] for x in items]
        caps = sorted({x["guard_cap"] for x in items if x["guard_cap"] is not None})
        guard_stats.append({
            "guard": gname,
            "count": len(items),
            "pct": round(100.0 * len(items) / len(records), 2),
            "cap": caps[0] if caps else None,
            "mean_human_grade": round(float(np.mean(scores_h)), 4),
            "median_human_grade": round(float(np.median(scores_h)), 4),
            "gte_4_0": sum(1 for s in scores_h if s >= 4.0),
            "eq_5_0": sum(1 for s in scores_h if s == 5.0),
            "mean_final_score": round(float(np.mean([x["final_score"] for x in items])), 2),
            "mean_unguarded_score": round(float(np.mean([x["unguarded_final_score"] for x in items])), 2),
            "mean_word_count": round(float(np.mean([x["server_word_count"] for x in items])), 2),
        })

    # Classifier breakdown
    clf_dist: dict[str, Any] = {}
    for lbl in ("Poor", "Average", "Good"):
        sub = [r for r in records if r["svm_label"] == lbl]
        clf_dist[lbl] = {
            "count": len(sub),
            "pct": round(100.0 * len(sub) / len(records), 2),
            "mean_human_grade": round(float(np.mean([x["score_avg"] for x in sub])), 4) if sub else None,
            "mean_word_count": round(float(np.mean([x["server_word_count"] for x in sub])), 2) if sub else None,
            "mean_semantic_score": round(float(np.nanmean([x["semantic_score"] for x in sub])), 4) if sub else None,
        }

    return {
        "n_rows": len(records),
        "n_questions": len(by_q),
        "human_score_avg": {
            "mean": round(float(np.mean(y)), 4),
            "median": round(float(np.median(y)), 4),
            "std": round(float(np.std(y)), 4),
            "min": float(np.min(y)),
            "max": float(np.max(y)),
        },
        "final_score_summary": {
            "mean": round(float(np.mean([r["final_score"] for r in records])), 2),
            "max": round(float(np.max([r["final_score"] for r in records])), 2),
            "gt_90_count": sum(1 for r in records if r["final_score"] > 90.0),
            "unguarded_max": round(float(np.max([r["unguarded_final_score"] for r in records])), 2),
            "semantic_unavailable_count": sum(1 for r in records if not r["semantic_available"]),
            "keyword_coverage_eq_0_5_count": sum(1 for r in records if r["keyword_coverage"] == 0.5),
            "has_br_tag_count": sum(1 for r in records if r["has_br_tag"]),
        },
        "correlations_vs_score_avg": correlations,
        "within_question_mean_correlations": within_q,
        "guard_breakdown": guard_stats,
        "classifier_distribution": clf_dist,
    }


def _audit_guard_subcauses(records: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    # 1. truncated_fragment
    tf_rows = [r for r in records if r["guard_applied"] == "truncated_fragment"]
    tf_causes: Counter[str] = Counter()
    tf_penult_words: Counter[str] = Counter()
    tf_last_words: Counter[str] = Counter()
    tf_examples: list[dict[str, Any]] = []
    for r in tf_rows:
        t = (r["student_answer"] or "").strip()
        if t and t[-1] in ",;:—":
            tf_causes["ends_punct"] += 1
        else:
            words = ag._word_tokens(t.rstrip(".!?…"))
            if words and words[-1] in ag._DANGLING_ENDINGS:
                tf_causes["last_word_dangling"] += 1
                tf_last_words[words[-1]] += 1
            elif len(words) >= 2 and words[-2] in ag._DANGLING_ENDINGS:
                tf_causes["penult_dangling_2_to_12"] += 1
                tf_penult_words[words[-2]] += 1
            else:
                tf_causes["other"] += 1
        if r["score_avg"] >= 4.5 and len(tf_examples) < 5:
            tf_examples.append({
                "id": r["id"],
                "score_avg": r["score_avg"],
                "unguarded": r["unguarded_final_score"],
                "final": r["final_score"],
                "answer": r["student_answer"][:140],
            })
    out["truncated_fragment"] = {
        "total": len(tf_rows),
        "sub_causes": dict(tf_causes),
        "top_penult_words": tf_penult_words.most_common(10),
        "top_last_words": tf_last_words.most_common(10),
        "high_grade_examples": tf_examples,
    }

    # 2. too_short
    ts_rows = [r for r in records if r["guard_applied"] == "too_short"]
    ts_causes: Counter[str] = Counter()
    ts_examples_high: list[dict[str, Any]] = []
    ts_examples_low: list[dict[str, Any]] = []
    for r in ts_rows:
        t = (r["student_answer"] or "").strip()
        tokens = ag._word_tokens(t)
        alpha = ag._alpha_tokens(t)
        known = ag._reference_vocabulary(r["question"], "", r["instructor_answer"])
        meaningful = [tok for tok in alpha if ag._is_meaningful_token(tok, known)]
        ref_len = len(ag._word_tokens(r["instructor_answer"]))
        if len(t) < 5:
            ts_causes["chars_lt_5"] += 1
        elif len(tokens) < 4:
            ts_causes["words_lt_4"] += 1
        elif len(tokens) < 8 and len(meaningful) < 4:
            ts_causes["words_4_to_7_meaningful_lt_4"] += 1
        elif r["instructor_answer"] and len(tokens) < 8 and len(tokens) < 0.5 * ref_len:
            ts_causes["words_4_to_7_under_half_ideal"] += 1
        else:
            ts_causes["other"] += 1
        if r["score_avg"] >= 4.5 and len(ts_examples_high) < 5:
            ts_examples_high.append({
                "id": r["id"],
                "score_avg": r["score_avg"],
                "ans_wc": len(tokens),
                "ref_wc": ref_len,
                "unguarded": r["unguarded_final_score"],
                "answer": r["student_answer"][:140],
            })
        if r["score_avg"] <= 1.5 and len(ts_examples_low) < 3:
            ts_examples_low.append({
                "id": r["id"],
                "score_avg": r["score_avg"],
                "ans_wc": len(tokens),
                "ref_wc": ref_len,
                "answer": r["student_answer"][:140],
            })
    out["too_short"] = {
        "total": len(ts_rows),
        "sub_causes": dict(ts_causes),
        "has_br_tag_count": sum(1 for r in ts_rows if r["has_br_tag"]),
        "high_grade_mean_ref_wc": round(
            float(np.mean([r["ref_word_count"] for r in ts_rows if r["score_avg"] >= 4.0])), 2
        ) if any(r["score_avg"] >= 4.0 for r in ts_rows) else None,
        "high_grade_examples": ts_examples_high,
        "low_grade_examples": ts_examples_low,
    }

    # 3. repetition
    rep_rows = [r for r in records if r["guard_applied"] == "repetition"]
    rep_causes: Counter[str] = Counter()
    rep_examples: list[dict[str, Any]] = []
    for r in rep_rows:
        tokens = ag._word_tokens(r["student_answer"])
        alpha = ag._alpha_tokens(r["student_answer"])
        repeated_char = [
            tok for tok in alpha
            if len(tok) >= 4 and (ag._max_char_run(tok) >= 4 or ag._repeated_pattern(tok))
        ]
        if len(tokens) >= 2 and repeated_char and len(repeated_char) / len(alpha or tokens) >= 0.60:
            rep_causes["repeated_char_token"] += 1
        elif len(tokens) == 2 and Counter(tokens).most_common(1)[0][1] == 1:
            rep_causes["len_2_distinct_tokens_bug_0.5_gt_0.4"] += 1
        else:
            mc = Counter(tokens).most_common(1)[0][1] if tokens else 0
            rep_causes[f"max_count_{mc}_of_{len(tokens)}"] += 1
        if len(rep_examples) < 4:
            rep_examples.append({
                "id": r["id"],
                "score_avg": r["score_avg"],
                "tokens": tokens,
                "answer": r["student_answer"][:120],
            })
    out["repetition"] = {
        "total": len(rep_rows),
        "sub_causes": dict(rep_causes),
        "examples": rep_examples,
    }

    # 4. gibberish
    gib_rows = [r for r in records if r["guard_applied"] == "gibberish"]
    gib_causes: Counter[str] = Counter()
    gib_examples: list[dict[str, Any]] = []
    for r in gib_rows:
        t = (r["student_answer"] or "").strip()
        tokens = ag._word_tokens(t)
        alpha = ag._alpha_tokens(t)
        known = ag._reference_vocabulary(r["question"], "", r["instructor_answer"])
        reasons = []
        if ag._vowel_ratio(t) < 0.24:
            reasons.append("vowel_ratio_lt_0.24")
        if ag._GIBBERISH_PATTERNS.search(t.lower()):
            reasons.append("gibberish_regex")
        if ag._nonsense_token_ratio(alpha, known) >= 0.50:
            reasons.append("nonsense_ratio_gte_0.50")
        if not reasons:
            reasons.append("tokens_gte_8_meaningful_lt_3")
        gib_causes["+".join(reasons)] += 1
        if len(gib_examples) < 5:
            gib_examples.append({
                "id": r["id"],
                "score_avg": r["score_avg"],
                "vowel_ratio": round(ag._vowel_ratio(t), 4),
                "has_br": r["has_br_tag"],
                "answer": t[:120],
            })
    out["gibberish"] = {
        "total": len(gib_rows),
        "sub_causes": dict(gib_causes),
        "has_br_tag_count": sum(1 for r in gib_rows if r["has_br_tag"]),
        "examples": gib_examples,
    }

    # 5. question_parroting
    qp_rows = [r for r in records if r["guard_applied"] == "question_parroting"]
    out["question_parroting"] = {
        "total": len(qp_rows),
        "examples": [
            {
                "id": r["id"],
                "score_avg": r["score_avg"],
                "question": r["question"][:100],
                "answer": r["student_answer"][:120],
            }
            for r in qp_rows[:4]
        ],
    }

    # 6. off_topic
    ot_rows = [r for r in records if r["guard_applied"] == "off_topic"]
    out["off_topic"] = {
        "total": len(ot_rows),
        "examples": [
            {
                "id": r["id"],
                "score_avg": r["score_avg"],
                "semantic_score": r["semantic_score"],
                "answer": r["student_answer"][:120],
            }
            for r in ot_rows[:4]
        ],
    }

    return out


def _inspect_xlsx_and_n50() -> dict[str, Any]:
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    sheet_names = list(wb.sheetnames)
    ws = wb[sheet_names[0]]
    all_rows = list(ws.iter_rows(values_only=True))
    wb.close()

    headers = [str(h or "") for h in all_rows[0]]
    data_rows = all_rows[1:]
    n_raters = len(data_rows)
    n_cols = len(headers)

    # Privacy/structure audit (no PII, zero cell dumps of rater rows)
    pii_header_hits = [
        h for h in headers
        if any(k in h.lower() for k in ("name", "email", "timestamp", "mail", "user", "id"))
        and not h.startswith("Q")
    ]
    non_numeric_cells = 0
    out_of_range_cells = 0
    missing_cells = 0
    matrix = np.zeros((n_raters, n_cols), dtype=float)
    row_tuples = set()
    for ri, row in enumerate(data_rows):
        row_tuples.add(tuple(row))
        for ci, val in enumerate(row):
            if val is None or val == "":
                missing_cells += 1
                continue
            try:
                num = float(val)
            except (TypeError, ValueError):
                non_numeric_cells += 1
                continue
            if not (0.0 <= num <= 100.0):
                out_of_range_cells += 1
            matrix[ri, ci] = num

    rater_means = matrix.mean(axis=1)
    rater_stds = matrix.std(axis=1, ddof=1)
    item_means = matrix.mean(axis=0)
    item_stds = matrix.std(axis=0, ddof=1)

    header_q_prefixes = []
    for idx, h in enumerate(headers):
        m = re.match(r"^Q?(\d+)\.\s*(.+)$", h)
        if m:
            header_q_prefixes.append((idx + 1, int(m.group(1)), _norm_ws(m.group(2))))

    # Join with baseline_v2_system_scores.csv, baseline_v2_key.csv, interview_dataset_v6.csv
    with SYS_SCORES_PATH.open("r", encoding="utf-8", newline="") as f:
        sys_rows = list(csv.DictReader(f))
    with KEY_PATH.open("r", encoding="utf-8", newline="") as f:
        key_by_id = {int(r["row_id"]): r for r in csv.DictReader(f)}

    v6_lookup: dict[tuple[str, str], dict[str, str]] = {}
    with V6_PATH.open("r", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            v6_lookup[(_norm_ws(r["question"]), _norm_ws(r["answer"]))] = r

    n50_scored: list[dict[str, Any]] = []
    matched_questions = 0
    matched_v6 = 0
    max_sys_diff = 0.0
    for idx, sr in enumerate(sys_rows):
        form_pos = int(sr["form_position"])
        rid = int(sr["row_id"])
        krow = key_by_id[rid]
        q_norm = _norm_ws(krow["question"])
        ans_norm = _norm_ws(krow["answer"])
        if idx < len(header_q_prefixes) and header_q_prefixes[idx][1] == form_pos and header_q_prefixes[idx][2] == q_norm:
            matched_questions += 1

        v6row = v6_lookup.get((q_norm, ans_norm))
        if v6row is not None:
            matched_v6 += 1
        ideal_ans = v6row["ideal_answer"] if v6row else ""
        ideal_kw = v6row["ideal_keywords"] if v6row else ""

        res = run_scoring_pipeline(
            answer_text=krow["answer"],
            question_context={
                "question": krow["question"],
                "ideal_answer": ideal_ans,
                "ideal_keywords": ideal_kw,
                "skill": krow["skill"],
            },
            difficulty=v6row["difficulty"].lower() if (v6row and v6row.get("difficulty")) else "medium",
        )
        sb = res["scoring_breakdown"]
        fb = sb["formula_breakdown"]
        unguarded = max(
            0.0,
            min(
                float(fb["base_score"])
                + float(fb["kg_bonus"])
                + float(fb["ner_bonus"])
                - float(fb["brevity_penalty"]),
                100.0,
            ),
        )
        sem = sb["semantic_score"]
        tfidf = float(sb["tfidf_score"])
        blended_cos = (0.40 * tfidf + 0.60 * float(sem)) if sem is not None else tfidf
        wc = int(sb["server_word_count"])
        _, srv_len_ratio = _compute_server_side_metrics(krow["answer"], ideal_ans, wc)
        probs = sb.get("classifier_probabilities") or {}
        lbl = res["svm_label"]

        max_sys_diff = max(max_sys_diff, abs(float(res["final_score"]) - float(sr["system_score"])))

        n50_scored.append({
            "form_position": form_pos,
            "row_id": rid,
            "dataset_label": krow["label"],
            "skill": krow["skill"],
            "human_mean": float(item_means[idx]),
            "human_std": float(item_stds[idx]),
            "final_score": float(res["final_score"]),
            "recorded_v2_system_score": float(sr["system_score"]),
            "unguarded_final_score": unguarded,
            "semantic_score": float(sem) if sem is not None else np.nan,
            "blended_cosine": blended_cos,
            "tfidf_score": tfidf,
            "server_word_count": float(wc),
            "server_length_ratio": srv_len_ratio,
            "clarity_score": float(sb["clarity_score"]),
            "keyword_coverage": float(sb["keyword_coverage"]),
            "has_ideal_keywords": bool(ideal_kw.strip()),
            "svm_label": lbl,
            "clf_weight": float(_CLASSIFIER_LABEL_SCORE.get(lbl, 0.50)),
            "clf_ordinal": float(_ORDINAL_LABEL.get(lbl, 1)),
            "clf_prob_good": float(probs.get("Good", 0.0)),
            "guard_applied": res["guard_applied"] or "none",
        })

    h_y = [r["human_mean"] for r in n50_scored]
    n50_corrs = {
        "final_score": _safe_corr([r["final_score"] for r in n50_scored], h_y),
        "unguarded_final_score": _safe_corr([r["unguarded_final_score"] for r in n50_scored], h_y),
        "semantic_score": _safe_corr([r["semantic_score"] for r in n50_scored], h_y),
        "blended_cosine": _safe_corr([r["blended_cosine"] for r in n50_scored], h_y),
        "tfidf_score": _safe_corr([r["tfidf_score"] for r in n50_scored], h_y),
        "server_word_count": _safe_corr([r["server_word_count"] for r in n50_scored], h_y),
        "server_length_ratio": _safe_corr([r["server_length_ratio"] for r in n50_scored], h_y),
        "clarity_score": _safe_corr([r["clarity_score"] for r in n50_scored], h_y),
        "classifier_label_pipeline_weight": _safe_corr([r["clf_weight"] for r in n50_scored], h_y),
        "classifier_label_ordinal": _safe_corr([r["clf_ordinal"] for r in n50_scored], h_y),
        "classifier_prob_good": _safe_corr([r["clf_prob_good"] for r in n50_scored], h_y),
    }

    by_dataset_lbl: dict[str, Any] = {}
    for dl in ("Good", "Average", "Poor"):
        sub = [r for r in n50_scored if r["dataset_label"] == dl]
        by_dataset_lbl[dl] = {
            "n": len(sub),
            "human_mean": round(float(np.mean([r["human_mean"] for r in sub])), 2),
            "human_max": round(float(np.max([r["human_mean"] for r in sub])), 2),
            "system_mean": round(float(np.mean([r["final_score"] for r in sub])), 2),
            "system_max": round(float(np.max([r["final_score"] for r in sub])), 2),
            "unguarded_mean": round(float(np.mean([r["unguarded_final_score"] for r in sub])), 2),
            "unguarded_max": round(float(np.max([r["unguarded_final_score"] for r in sub])), 2),
            "gt_90_count": sum(1 for r in sub if r["final_score"] > 90.0),
            "guarded_count": sum(1 for r in sub if r["guard_applied"] != "none"),
            "mean_word_count": round(float(np.mean([r["server_word_count"] for r in sub])), 2),
            "mean_length_ratio": round(float(np.mean([r["server_length_ratio"] for r in sub])), 3),
        }

    return {
        "xlsx_structure": {
            "file": str(XLSX_PATH.relative_to(ROOT)),
            "sheet_names": sheet_names,
            "total_rows": len(all_rows),
            "header_rows": 1,
            "rater_rows": n_raters,
            "question_columns": n_cols,
            "header_format_match_count": len(header_q_prefixes),
            "header_sample_pattern": "Q<1..50>. <exact question text>",
            "pii_columns": pii_header_hits,
            "ratings_per_answer_min": n_raters,
            "ratings_per_answer_max": n_raters,
            "missing_cells": missing_cells,
            "non_numeric_cells": non_numeric_cells,
            "out_of_range_cells": out_of_range_cells,
            "scale": "integer 0-100 (Poor 0-30, Average 31-60, Good 61-100 per docs/human_baseline_report.md)",
            "unique_rater_response_rows": len(row_tuples),
            "overall_cell_mean": round(float(matrix.mean()), 2),
            "overall_cell_std": round(float(matrix.std(ddof=0)), 2),
            "rater_mean_min": round(float(rater_means.min()), 2),
            "rater_mean_max": round(float(rater_means.max()), 2),
            "rater_std_min": round(float(rater_stds.min()), 2),
            "rater_std_max": round(float(rater_stds.max()), 2),
            "item_human_mean_min": round(float(item_means.min()), 2),
            "item_human_mean_median": round(float(np.median(item_means)), 2),
            "item_human_mean_max": round(float(item_means.max()), 2),
            "item_cross_rater_std_mean": round(float(item_stds.mean()), 2),
            "item_cross_rater_std_min": round(float(item_stds.min()), 2),
            "item_cross_rater_std_max": round(float(item_stds.max()), 2),
            "matched_headers_to_baseline_v2": matched_questions,
            "matched_items_to_v6": matched_v6,
        },
        "n50_pipeline_diagnostics": {
            "max_abs_diff_vs_baseline_v2_system_scores_csv": round(max_sys_diff, 4),
            "items_with_nonempty_ideal_keywords": sum(1 for r in n50_scored if r["has_ideal_keywords"]),
            "items_with_keyword_coverage_eq_0_5": sum(1 for r in n50_scored if r["keyword_coverage"] == 0.5),
            "items_gt_90": sum(1 for r in n50_scored if r["final_score"] > 90.0),
            "max_system_final_score": round(float(max(r["final_score"] for r in n50_scored)), 2),
            "correlations_vs_23rater_mean": n50_corrs,
            "by_dataset_label": by_dataset_lbl,
            "guard_counts": dict(Counter(r["guard_applied"] for r in n50_scored)),
        },
    }


def _inspect_classifier_and_keywords() -> dict[str, Any]:
    pipe = joblib.load(LR_PATH)
    scaler = pipe.named_steps["scaler"]
    clf = pipe.named_steps["clf"]
    feature_names = [
        "nlp_cosine_similarity",
        "clarity_score_train_vs_length_ratio_serve",
        "keyword_coverage",
        "word_count",
        "concept_coverage",
    ]
    coefs = {
        str(cls): {fname: round(float(val), 4) for fname, val in zip(feature_names, clf.coef_[ci])}
        for ci, cls in enumerate(clf.classes_)
    }
    scaler_stats = {
        fname: {"mean": round(float(m), 4), "std": round(float(s), 4)}
        for fname, m, s in zip(feature_names, scaler.mean_, scaler.scale_)
    }

    def _dataset_stats(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        empty_kw = sum(1 for r in rows if not (r.get("ideal_keywords") or "").strip())
        wcs = defaultdict(list)
        for r in rows:
            wcs[r.get("label", "")].append(_server_word_count(r.get("answer") or ""))
        return {
            "rows": len(rows),
            "empty_ideal_keywords": empty_kw,
            "pct_empty_ideal_keywords": round(100.0 * empty_kw / len(rows), 2) if rows else 0.0,
            "word_count_by_label": {
                k: {
                    "n": len(v),
                    "mean": round(float(np.mean(v)), 2),
                    "median": round(float(np.median(v)), 1),
                    "min": int(min(v)),
                    "max": int(max(v)),
                }
                for k, v in sorted(wcs.items())
            },
        }

    return {
        "lr_classes": [str(c) for c in clf.classes_],
        "lr_intercepts": {str(c): round(float(b), 4) for c, b in zip(clf.classes_, clf.intercept_)},
        "lr_standardized_coefs": coefs,
        "lr_scaler": scaler_stats,
        "v6_dataset_stats": _dataset_stats(V6_PATH),
        "ml_training_data_stats": _dataset_stats(ML_DATA_PATH),
    }


def main() -> None:
    with (MOHLER_DIR / "mohler_raw_all.csv").open("r", encoding="utf-8", newline="") as f:
        mohler_all = list(csv.DictReader(f))
    mohler_oe = [r for r in mohler_all if r["subset"] == "raw-oe"]

    all_records = _score_mohler_rows(mohler_all, strip_br=False)
    oe_records = [r for r in all_records if r["subset"] == "raw-oe"]
    ce_records = [r for r in all_records if r["subset"] == "raw-ce"]
    oe_br_stripped_records = _score_mohler_rows(mohler_oe, strip_br=True)

    summary = {
        "mohler_open_ended": _summarize_mohler_split(oe_records),
        "mohler_close_ended": _summarize_mohler_split(ce_records),
        "mohler_all": _summarize_mohler_split(all_records),
        "mohler_open_ended_br_stripped": _summarize_mohler_split(oe_br_stripped_records),
        "mohler_oe_guard_subcauses": _audit_guard_subcauses(oe_records),
        "mohler_all_guard_subcauses": _audit_guard_subcauses(all_records),
        "human_n50": _inspect_xlsx_and_n50(),
        "classifier_and_training_data": _inspect_classifier_and_keywords(),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
