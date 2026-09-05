"""
build_baseline_v2.py — Build the annotation sheet for the expanded human baseline study.

Samples 100 answers from data/interview_dataset_v6.csv, stratified by label
(34 Good / 33 Average / 33 Poor) so annotators see the full quality range,
then writes:

  data/baseline_v2_blank.xlsx — goes to annotators. No label, no system
      score, no skill, no sub_domain. Nothing that hints at the expected score.
  data/baseline_v2_key.csv — stays internal. Maps row_id back to the gold
      label, skill, and sub_domain. Annotators never receive this.

Before writing anything, every sampled row passes an alignment check: the
(question, answer) pair must exist together in the source CSV. This guards
against the defect in the previous study, where an undocumented distractor
mechanism in scripts/human_baseline.py paired 9 of 30 rows with an answer
belonging to a different question.

Usage:  python scripts/build_baseline_v2.py
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

SEED = 24
DATA_PATH = ROOT / "data" / "interview_dataset_v6.csv"
BLANK_PATH = ROOT / "data" / "baseline_v2_blank.xlsx"
KEY_PATH = ROOT / "data" / "baseline_v2_key.csv"

N_PER_LABEL = {"Good": 34, "Average": 33, "Poor": 33}

# Exact columns of the annotator-facing sheet. Anything else (label, skill,
# sub_domain, system score) must never appear here.
BLANK_COLUMNS = [
    "row_id",
    "question",
    "reference_answer (for reference only — do NOT copy)",
    "candidate_answer",
    "your_score (0-100)",
    "notes (optional)",
]

KEY_COLUMNS = ["row_id", "question", "answer", "label", "skill", "sub_domain"]


class AlignmentError(Exception):
    """Raised when a sampled (question, answer) pair is not in the source CSV."""


def load_source() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH)
    for col in ("question", "answer", "ideal_answer", "label", "skill", "sub_domain"):
        if col not in df.columns:
            raise ValueError(f"source CSV is missing required column: {col!r}")
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["label"] = df["label"].str.strip()
    return df


def stratified_sample(df: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for label, n in N_PER_LABEL.items():
        pool = df[df["label"] == label]
        if len(pool) < n:
            raise ValueError(
                f"not enough {label!r} rows: need {n}, source has {len(pool)}"
            )
        parts.append(pool.sample(n=n, random_state=SEED))
    sample = pd.concat(parts, ignore_index=True)
    # Shuffle so quality bands are not grouped (grouping would hint at scores).
    sample = sample.sample(n=len(sample), random_state=SEED).reset_index(drop=True)
    sample.insert(0, "row_id", range(1, len(sample) + 1))
    return sample


def verify_alignment(sample: pd.DataFrame, source: pd.DataFrame) -> None:
    """Confirm every sampled (question, answer) pair exists together in source.

    Raises AlignmentError on the first failure. Callers must call this before
    writing any output file.
    """
    source_pairs = set(zip(source["question"], source["answer"]))
    for i, row in sample.iterrows():
        pair = (row["question"], row["answer"])
        if not row["question"] or not row["answer"]:
            raise AlignmentError(f"row {row['row_id']}: empty question or answer")
        if pair not in source_pairs:
            raise AlignmentError(
                f"row {row['row_id']}: (question, answer) pair not found together "
                "in source CSV — refusing to write any output"
            )


def check_pair_label_uniqueness(sample: pd.DataFrame, source: pd.DataFrame) -> None:
    """Report sampled pairs that carry more than one label in the source CSV.

    Diagnostic only (prints, never raises): the source contains identical
    (question, answer) pairs under conflicting labels, so the key's gold
    label for such rows is the sampled row's own label, not a unique truth.
    """
    labels_per_pair = source.groupby(["question", "answer"])["label"].nunique()
    ambiguous = sum(
        labels_per_pair.get((row["question"], row["answer"]), 0) > 1
        for _, row in sample.iterrows()
    )
    print(f"Pairs with conflicting labels in source: {ambiguous}/{len(sample)} "
          "(key records the sampled row's own label)")


def check_skill_coverage(sample: pd.DataFrame, source: pd.DataFrame) -> None:
    dist = sample["skill"].value_counts().sort_index()
    print("\nSkill distribution in sample:")
    for skill, count in dist.items():
        print(f"  {skill:<15} {count:>3}")
    missing = sorted(set(source["skill"].unique()) - set(sample["skill"].unique()))
    if missing:
        print(f"\nWARNING: skills with zero rows in sample: {', '.join(missing)}")
    else:
        print(f"\nSkill coverage: all {source['skill'].nunique()} skills represented.")
    top_share = dist.max() / len(sample)
    print(f"Largest single-skill share: {top_share:.0%} ({dist.idxmax()})")


def write_blank_sheet(sample: pd.DataFrame) -> None:
    blank = pd.DataFrame({
        "row_id": sample["row_id"],
        "question": sample["question"],
        "reference_answer (for reference only — do NOT copy)": sample["ideal_answer"],
        "candidate_answer": sample["answer"],
        "your_score (0-100)": "",
        "notes (optional)": "",
    }, columns=BLANK_COLUMNS)
    assert list(blank.columns) == BLANK_COLUMNS, "blank sheet columns changed!"
    leaked = {"label", "skill", "sub_domain", "system_score", "ideal_keywords"}
    assert not (leaked & set(blank.columns)), "leak column in blank sheet!"

    with pd.ExcelWriter(BLANK_PATH, engine="openpyxl") as writer:
        blank.to_excel(writer, index=False, sheet_name="annotate")
        ws = writer.sheets["annotate"]
        widths = {"A": 8, "B": 50, "C": 50, "D": 50, "E": 16, "F": 24}
        for col, width in widths.items():
            ws.column_dimensions[col].width = width
        ws.freeze_panes = "A2"


def write_key(sample: pd.DataFrame) -> None:
    key = sample[["row_id", "question", "answer", "label", "skill", "sub_domain"]]
    key.to_csv(KEY_PATH, index=False)


def main() -> None:
    print(f"Loading source: {DATA_PATH}")
    source = load_source()
    print(f"Source rows: {len(source)}")

    sample = stratified_sample(source)
    print(f"\nSampled rows: {len(sample)} (seed={SEED})")
    print("Label distribution in sample:")
    for label in ("Good", "Average", "Poor"):
        print(f"  {label:<8} {(sample['label'] == label).sum():>3}")

    check_skill_coverage(sample, source)

    # Alignment gate: raises before any file is written.
    verify_alignment(sample, source)
    print(f"\nAlignment check: PASSED ({len(sample)}/{len(sample)} "
          "(question, answer) pairs verified in source CSV)")

    check_pair_label_uniqueness(sample, source)

    write_blank_sheet(sample)
    write_key(sample)
    print(f"\nWrote annotator sheet: {BLANK_PATH} (CONFIDENTIAL key NOT included)")
    print(f"Wrote internal key:    {KEY_PATH} (confidential — do not distribute)")


if __name__ == "__main__":
    main()
