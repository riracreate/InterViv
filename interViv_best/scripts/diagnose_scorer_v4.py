"""Scorer v4 diagnostics. Reuses stored feature predictions; no retraining."""
import os
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
import csv, json, sys
from pathlib import Path
import numpy as np, joblib
from scipy.stats import pearsonr, spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

split = json.loads((ROOT/"data/mohler_question_split_v1.json").read_text())
held_keys = set(split["heldout_questions"])
def qk(rid): return ".".join(rid.split(".")[:2])
def exam(rid): return rid.split(".")[0]
rows = [r for r in csv.DictReader(open(ROOT/"data/external/mohler_asag/mohler_raw_open_ended.csv", encoding="utf-8")) if qk(r["id"]) in held_keys]
feats_cache = json.loads((ROOT/"artifacts/mohler_heldout_features.json").read_text())
feats = [feats_cache[r["id"]] for r in rows]
y = np.array([float(r["score_avg"]) for r in rows])
model = joblib.load(ROOT/"modules/scorer_v4_regression.joblib")["model"]
from modules.scoring_features import feature_vector
X = np.array([feature_vector(f) for f in feats])
pred = np.clip(model.predict(X), 0, 1)
cal = json.loads((ROOT/"modules/scorer_v4_calibration.json").read_text())
def calib(s): return np.interp(s, cal["x"], cal["y"])
def base(f, m):
    t = [(0.45, f["semantic_score"]), (0.10, f["tfidf_score"])] + ([(0.25, m)] if m is not None else [])
    w = sum(a for a,_ in t); return 100*sum(a*b for a,b in t)/w
blended = np.array([0.4*f["tfidf_score"]+0.6*f["semantic_score"] for f in feats])*100
v4wo_raw = np.array([base(f, None) for f in feats]); v4w_raw = np.array([base(f, float(p)) for f,p in zip(feats,pred)])
v4wo, v4w = calib(v4wo_raw), calib(v4w_raw)

# v3 final scores (evaluation only, cached)
v3cache_path = ROOT/"artifacts/mohler_heldout_v3.json"
v3cache = json.loads(v3cache_path.read_text()) if v3cache_path.exists() else {}
missing = [r for r in rows if r["id"] not in v3cache]
if missing:
    os.environ.pop("SCORER_VERSION", None)
    from backend.scoring.pipeline import run_scoring_pipeline
    for i, r in enumerate(missing):
        out = run_scoring_pipeline(answer_text=r["student_answer"], question_context={
            "question": r["question"], "ideal_answer": r["instructor_answer"], "ideal_keywords": ""})
        v3cache[r["id"]] = out["final_score"]
        if (i+1) % 200 == 0:
            print(f"v3 {i+1}/{len(missing)}", flush=True); v3cache_path.write_text(json.dumps(v3cache))
    v3cache_path.write_text(json.dumps(v3cache))
v3 = np.array([v3cache[r["id"]] for r in rows])

def corr(s, yy):
    return {"pearson": round(float(pearsonr(s, yy).statistic),4), "spearman": round(float(spearmanr(s, yy).statistic),4), "n": int(len(yy))}
by_q = {}
for i,r in enumerate(rows): by_q.setdefault(qk(r["id"]), []).append(i)
rng = np.random.default_rng(7)
def paired_diff(sa, sb, yy, mask=None):
    qs = [q for q,idx in by_q.items() if mask is None or any(mask[i] for i in idx)]
    diffs=[]
    for _ in range(2000):
        samp = rng.choice(qs, size=len(qs), replace=True)
        idx = np.concatenate([by_q[q] for q in samp])
        if mask is not None: idx = np.array([i for i in idx if mask[i]])
        diffs.append(float(pearsonr(sa[idx], yy[idx]).statistic - pearsonr(sb[idx], yy[idx]).statistic))
    lo,hi = np.percentile(diffs,[2.5,97.5]); return [round(float(lo),4), round(float(hi),4)]
keep = np.array([exam(r["id"]) not in {"E11","E12"} for r in rows])
A = {"all": {}, "no_e11_e12": {}}
for name, s in [("v3_final_score", v3), ("blended_cosine", blended), ("v4_without_model", v4wo), ("v4_with_model", v4w)]:
    A["all"][name] = corr(s, y); A["no_e11_e12"][name] = corr(s[keep], y[keep])
A["diff_v4with_minus_blended_all"] = paired_diff(v4w, blended, y)
A["diff_v4with_minus_v3_all"] = paired_diff(v4w, v3, y)
def paired_diff_spearman(sa, sb, yy, mask=None):
    qs = [q for q,idx in by_q.items() if mask is None or any(mask[i] for i in idx)]
    diffs=[]
    for _ in range(2000):
        samp = rng.choice(qs, size=len(qs), replace=True)
        idx = np.concatenate([by_q[q] for q in samp])
        if mask is not None: idx = np.array([i for i in idx if mask[i]])
        diffs.append(float(spearmanr(sa[idx], yy[idx]).statistic - spearmanr(sb[idx], yy[idx]).statistic))
    lo,hi = np.percentile(diffs,[2.5,97.5]); return [round(float(lo),4), round(float(hi),4)]
A["spearman_diff_v4with_minus_blended_all"] = paired_diff_spearman(v4w, blended, y)
A["spearman_diff_v4with_minus_blended_no_e11_e12"] = paired_diff_spearman(v4w, blended, y, mask=keep)
A["compared_note"] = "blended cosine raw (0-100 rescale); v4 isotonic-calibrated on Mohler tune"

# ---- B guards ----
from modules import answer_guard as g3
from modules.answer_guard_v4 import check_answer_quality_v4
def variant_scores(fn):
    hi_c=hi=lo_c=lo=0; reasons={}
    for r in rows:
        capped, reason = fn(r)
        g = float(r["score_avg"])
        if g>=4.5:
            hi+=1; hi_c+=int(capped)
            if capped: reasons[reason]=reasons.get(reason,0)+1
        elif g<=1.0:
            lo+=1; lo_c+=int(capped)
    return {"fp_rate_gte4.5": round(hi_c/max(hi,1),4), "catch_lte1.0": round(lo_c/max(lo,1),4), "n_high":hi, "n_low":lo, "fp_by_guard": reasons}
def v4_fn(r):
    o = check_answer_quality_v4(r["student_answer"], question_text=r["question"], ideal_answer=r["instructor_answer"])
    return bool(o.get("cap_required")), o.get("reason") or ""
def v3_fn(r):
    o = g3.check_answer_quality_v2(r["student_answer"], question_text=r["question"], ideal_answer=r["instructor_answer"])
    return bool(o.get("cap_required")), o.get("reason") or ""
def nocap_fn(r):
    c, reason = v4_fn(r)
    return (c and reason not in {"too_short","truncated_fragment"}), reason
B = {"heldout_v4_chosen_ref_gating": variant_scores(v4_fn),
     "heldout_v3_hard_caps": variant_scores(v3_fn),
     "heldout_v4_no_short_caps": variant_scores(nocap_fn)}

# n50 missed Poor
import openpyxl
wb = openpyxl.load_workbook(ROOT/"data/interViv — Answer Rating (Responses).xlsx", read_only=True, data_only=True)
xrows = list(wb["Form Responses 1"].iter_rows(values_only=True))
human_means = np.array([[float(v) for v in r] for r in xrows[1:]], float).mean(axis=0)
sys_rows = list(csv.DictReader(open(ROOT/"data/baseline_v2_system_scores.csv", encoding="utf-8")))
key_rows = {int(r["row_id"]): r for r in csv.DictReader(open(ROOT/"data/baseline_v2_key.csv", encoding="utf-8"))}
v6 = {r["question"]: r for r in csv.DictReader(open(ROOT/"data/interview_dataset_v6.csv", encoding="utf-8"))}
missed=[]; caught=0; poor_n=0
n50_feats={}
for s in sys_rows:
    k = key_rows[int(s["row_id"])]; q, ans = k["question"], k["answer"]
    ideal = (v6.get(q) or {}).get("ideal_answer") or ""
    if s["label"]=="Poor":
        poor_n+=1
        o = check_answer_quality_v4(ans, question_text=q, ideal_answer=ideal)
        if o.get("cap_required"): caught+=1
        else: missed.append({"form_position": int(s["form_position"]), "words": len(ans.split()),
                             "human_mean": round(float(human_means[int(s["form_position"])-1]),1)})
B["n50_poor"] = {"n": poor_n, "v4_caught": caught, "missed": missed,
                 "missed_words_mean": round(float(np.mean([m["words"] for m in missed])),1) if missed else None,
                 "missed_human_mean": round(float(np.mean([m["human_mean"] for m in missed])),1) if missed else None}

# ---- C n50 features ----
from modules.scoring_features import build_scoring_features
from modules import nlp_scorer
n50_cache_path = ROOT/"artifacts/n50_features.json"
n50_cache = json.loads(n50_cache_path.read_text()) if n50_cache_path.exists() else {}
items=[]
scorer = nlp_scorer._get_semantic_scorer()
import re as _re
for s in sys_rows:
    k = key_rows[int(s["row_id"])]; q, ans = k["question"], k["answer"]
    ideal = (v6.get(q) or {}).get("ideal_answer") or ""
    key = str(s["form_position"])
    if key not in n50_cache:
        f = build_scoring_features(answer_text=ans, ideal_answer=ideal)
        # sentence coverage: share of reference sentences with matching answer sentence
        ref_sents = [t.strip() for t in _re.split(r"(?<=[.!?])\s+", ideal) if t.strip()]
        ans_sents = [t.strip() for t in _re.split(r"(?<=[.!?])\s+", ans) if t.strip()]
        cov = 0.0
        if ref_sents and ans_sents and scorer is not None:
            hit=0
            for rs in ref_sents:
                sim = scorer.max_similarity(rs, ans_sents)
                if sim is not None and sim >= 0.5: hit+=1
            cov = hit/len(ref_sents)
        f["ref_sentence_coverage"] = round(cov,4)
        n50_cache[key]=f
    f = n50_cache[key]
    p = float(np.clip(model.predict(np.array([feature_vector(f)]))[0],0,1))
    raw = base(f,p)
    items.append({"pos": int(s["form_position"]), "label": s["label"], "human": float(human_means[int(s["form_position"])-1]),
                  "feats": f, "v4_raw": float(raw), "v4_cal": float(calib(np.array([raw]))[0]), "words": len(ans.split())})
n50_cache_path.write_text(json.dumps(n50_cache))
hum = np.array([it["human"] for it in items])
C={"features":{}}
for fname in ["semantic_score","tfidf_score","concept_coverage","ideal_content_recall","max_sentence_semantic_sim","ref_sentence_coverage"]:
    vals = np.array([it["feats"][fname] for it in items]); C["features"][fname]=corr(vals, hum)
C["v4_before_calibration"]=corr(np.array([it["v4_raw"] for it in items]), hum)
C["v4_after_calibration"]=corr(np.array([it["v4_cal"] for it in items]), hum)
C["band_definition"]="bands from 23-rater mean: Poor 0-30, Average 31-60, Good 61-100 (docs/human_baseline_report.md); dataset label is separate"
C["bands"]={}
for band, lo, hi in [("Poor (human 0-30)",0,30),("Average (31-60)",31,60),("Good (61-100)",61,100)]:
    sel=[it for it in items if lo<=it["human"]<=hi]
    if sel:
        C["bands"][band]={"n":len(sel), "mean_v4_cal": round(float(np.mean([it["v4_cal"] for it in sel])),1),
            "mean_semantic": round(float(np.mean([it["feats"]["semantic_score"] for it in sel])),3),
            "mean_recall": round(float(np.mean([it["feats"]["ideal_content_recall"] for it in sel])),3),
            "mean_sentence_cov": round(float(np.mean([it["feats"]["ref_sentence_coverage"] for it in sel])),3),
            "mean_words": round(float(np.mean([it["words"] for it in sel])),1)}

D={"calibration_knots": {"x": cal["x"], "y": cal["y"]},
   "heldout_v4_raw_percentiles": {p: round(float(np.percentile(v4w_raw,p)),1) for p in [0,10,25,50,75,90,100]},
   "heldout_v4_cal_percentiles": {p: round(float(np.percentile(v4w,p)),1) for p in [0,10,25,50,75,90,100]},
   "heldout_cal_mean": round(float(v4w.mean()),1), "human_mean_x20": round(float((y*20).mean()),1)}
out={"A":A,"B":B,"C":C,"D":D}
(ROOT/"artifacts/scorer_v4_diagnostics.json").write_text(json.dumps(out,indent=1))
print(json.dumps({"A":A,"B":B,"D":{k:v for k,v in D.items() if k!="calibration_knots"}}, indent=1))
print("C:", json.dumps(C, indent=1))

# Per-row exports (post-diagnostics; zero impact on metrics above)
heldout_per_row = []
for r, v3_i, bl_i, wo_i, w_i in zip(rows, v3, blended, v4wo, v4w):
    g_out = check_answer_quality_v4(
        r["student_answer"],
        question_text=r["question"],
        ideal_answer=r["instructor_answer"],
    )
    heldout_per_row.append({
        "answer_id": r["id"],
        "human_grade": round(float(r["score_avg"]), 4),
        "v3": round(float(v3_i), 4),
        "blended_cosine": round(float(bl_i), 4),
        "v4_without_model": round(float(wo_i), 4),
        "v4_with_model": round(float(w_i), 4),
        "guard_decision": {
            "cap_required": bool(g_out.get("cap_required")),
            "reason": g_out.get("reason") or "",
            "score_cap": int(g_out.get("score_cap", 100)),
        },
    })
(ROOT / "artifacts/scorer_v4_heldout_per_row.json").write_text(
    json.dumps(heldout_per_row, indent=1) + "\n", encoding="utf-8"
)

os.environ.pop("SCORER_VERSION", None)
from backend.scoring.pipeline import run_scoring_pipeline as _run_v3_pipeline

n50_per_row = []
for s, it in zip(sys_rows, items):
    k = key_rows[int(s["row_id"])]
    q, ans = k["question"], k["answer"]
    v6_row = v6.get(q) or {}
    ideal = v6_row.get("ideal_answer") or ""
    kw = v6_row.get("ideal_keywords") or ""
    v3_out = _run_v3_pipeline(
        answer_text=ans,
        question_context={"question": q, "ideal_answer": ideal, "ideal_keywords": kw},
    )
    f = it["feats"]
    bl_n = float((0.4 * f["tfidf_score"] + 0.6 * f["semantic_score"]) * 100.0)
    wo_n = float(calib(np.array([base(f, None)]))[0])
    g_out = check_answer_quality_v4(ans, question_text=q, ideal_answer=ideal)
    n50_per_row.append({
        "answer_id": int(s["row_id"]),
        "form_position": int(s["form_position"]),
        "dataset_label": s["label"],
        "human_grade": round(float(it["human"]), 4),
        "v3": round(float(v3_out["final_score"]), 4),
        "baseline_v2_system_score": round(float(s["system_score"]), 4),
        "blended_cosine": round(bl_n, 4),
        "v4_without_model": round(wo_n, 4),
        "v4_with_model": round(float(it["v4_cal"]), 4),
        "guard_decision": {
            "cap_required": bool(g_out.get("cap_required")),
            "reason": g_out.get("reason") or "",
            "score_cap": int(g_out.get("score_cap", 100)),
        },
    })
(ROOT / "artifacts/scorer_v4_n50_dev_per_row.json").write_text(
    json.dumps(n50_per_row, indent=1) + "\n", encoding="utf-8"
)

