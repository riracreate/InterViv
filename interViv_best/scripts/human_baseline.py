"""
human_baseline.py — Generate inter-rater annotation sheet for interViv viva defence.

Loads 50 random questions from interview_dataset_v6.csv.
For each question, collects 4 candidate answers:
  - One Good-label answer from the dataset
  - One Average-label answer from the dataset
  - One Poor-label answer from the dataset
  - One distractor: a real answer from a DIFFERENT random question

All 4 answers are shuffled (annotators don't see the labels).

Writes data/human_baseline_sheet.csv with columns:
  question, ideal_answer, ideal_keywords, answer,
  system_score, annotator_1, annotator_2, annotator_3, annotator_4

system_score is computed via the NLPScorer (the 3-layer scorer, no KG).
annotator columns are left blank for human labelling (0=Poor, 50=Average, 100=Good).

Usage:  python scripts/human_baseline.py
"""

from __future__ import annotations

import os
import sys
import random
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from modules.nlp_scorer_patch import PatchedNLPScorer

random.seed(42)

MODEL_PATH = ROOT / "modules" / "svm_model.joblib"
DATA_PATH  = ROOT / "data" / "interview_dataset_v6.csv"
OUT_PATH   = ROOT / "data" / "human_baseline_sheet.csv"
N_QUESTIONS = 50


def compute_system_score(scorer: PatchedNLPScorer, answer: str, ideal: str, keywords: str) -> float:
    result = scorer.compute_overall_score(
        answer_text=answer,
        ideal_answer=ideal,
        ideal_keywords=keywords or "",
        difficulty="medium",
    )
    return round(float(result.get("overall_score", 0.0)), 1)


def main() -> None:
    print(f"Loading dataset from {DATA_PATH} ...")
    df = pd.read_csv(DATA_PATH)

    # Normalise label column
    df["label"] = df["label"].astype(str).str.strip()
    df["ideal_keywords"] = df["ideal_keywords"].fillna("").astype(str)
    df["ideal_answer"]   = df["ideal_answer"].fillna("").astype(str)
    df["answer"]         = df["answer"].fillna("").astype(str)

    # Group by question to find questions that have all three label bands
    grouped = df.groupby("question")
    eligible_questions = []
    for q, grp in grouped:
        labels = set(grp["label"].unique())
        if "Good" in labels and "Average" in labels and "Poor" in labels:
            eligible_questions.append(q)

    print(f"Found {len(eligible_questions)} questions with Good/Average/Poor variants.")
    if len(eligible_questions) < N_QUESTIONS:
        print(f"WARNING: only {len(eligible_questions)} eligible questions; using all of them.")

    selected = random.sample(eligible_questions, min(N_QUESTIONS, len(eligible_questions)))

    scorer = PatchedNLPScorer(model_path=str(MODEL_PATH))
    print(f"Scoring {len(selected)} questions × 4 answers each ...")

    rows = []
    for q in selected:
        grp = grouped.get_group(q)
        ideal    = grp["ideal_answer"].iloc[0]
        keywords = grp["ideal_keywords"].iloc[0]

        good_ans    = grp[grp["label"] == "Good"].sample(1, random_state=random.randint(0, 9999))
        average_ans = grp[grp["label"] == "Average"].sample(1, random_state=random.randint(0, 9999))
        poor_ans    = grp[grp["label"] == "Poor"].sample(1, random_state=random.randint(0, 9999))

        # Distractor: answer from a different question
        other_questions = [oq for oq in selected if oq != q]
        distractor_q = random.choice(other_questions)
        distractor_row = grouped.get_group(distractor_q).sample(1, random_state=random.randint(0, 9999))
        distractor_ans = distractor_row["answer"].iloc[0]

        candidate_answers = [
            good_ans["answer"].iloc[0],
            average_ans["answer"].iloc[0],
            poor_ans["answer"].iloc[0],
            distractor_ans,
        ]
        random.shuffle(candidate_answers)

        for ans in candidate_answers:
            score = compute_system_score(scorer, ans, ideal, keywords)
            rows.append({
                "question":        q,
                "ideal_answer":    ideal,
                "ideal_keywords":  keywords,
                "answer":          ans,
                "system_score":    score,
                "annotator_1":     "",
                "annotator_2":     "",
                "annotator_3":     "",
                "annotator_4":     "",
            })

    out_df = pd.DataFrame(rows, columns=[
        "question", "ideal_answer", "ideal_keywords", "answer",
        "system_score", "annotator_1", "annotator_2", "annotator_3", "annotator_4",
    ])
    out_df.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(out_df)} rows to {OUT_PATH}")
    print(f"system_score range: {out_df['system_score'].min()}–{out_df['system_score'].max()}")
    print(f"system_score mean:  {out_df['system_score'].mean():.1f}")
    print(f"\nNext step: open {OUT_PATH.name} and fill in annotator_1..4 columns")
    print("  Scoring guide: 0–30 = Poor, 31–60 = Average, 61–100 = Good")


if __name__ == "__main__":
    main()
