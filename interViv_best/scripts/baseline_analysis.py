"""
baseline_analysis.py — Analyse human baseline annotation sheet.

Reads data/human_baseline_real_combined.xlsx by default. Older CSV sheets are
still supported through --sheet for compatibility.
Produces docs/human_baseline_report.md with:
  - Inter-rater agreement (Cohen's Kappa for each pair + average)
  - System vs human correlation (Pearson r + p-value)
  - Confusion matrix (Good/Average/Poor bands)
  - Top-5 cases of system-human disagreement

Usage:  python scripts/baseline_analysis.py [--sheet path/to/sheet.xlsx] [--output path/to/report.md]
"""

from __future__ import annotations

import argparse
import math
import pathlib
import sys
import zipfile
from itertools import combinations
from typing import Optional
from xml.etree import ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
from scipy.stats import pearsonr
from sklearn.metrics import cohen_kappa_score

DATA_PATH   = ROOT / "data"  / "human_baseline_real_combined.xlsx"
REPORT_PATH = ROOT / "docs"  / "human_baseline_report.md"


def _cell_col_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch.upper()) - ord("A") + 1)
    return max(index - 1, 0)


def _first_sheet_path(archive: zipfile.ZipFile) -> str:
    ns_main = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    ns_rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    try:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        first_sheet = workbook.find(f".//{ns_main}sheet")
        rel_id = first_sheet.attrib.get(f"{ns_rel}id") if first_sheet is not None else None
        if rel_id:
            rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            for rel in rels:
                if rel.attrib.get("Id") == rel_id:
                    target = rel.attrib.get("Target", "worksheets/sheet1.xml")
                    if target.startswith("/"):
                        return target.lstrip("/")
                    return "xl/" + target.lstrip("/")
    except Exception:
        pass
    return "xl/worksheets/sheet1.xml"


def _read_xlsx_without_openpyxl(path: pathlib.Path) -> pd.DataFrame:
    """Small read-only XLSX fallback for simple single-sheet annotation files."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall(f"{ns}si"):
                shared_strings.append("".join(item.itertext()))

        sheet_root = ET.fromstring(archive.read(_first_sheet_path(archive)))
        rows: list[list[object]] = []
        for row in sheet_root.findall(f".//{ns}row"):
            values_by_col: dict[int, object] = {}
            for cell in row.findall(f"{ns}c"):
                col_index = _cell_col_index(cell.attrib.get("r", "A"))
                cell_type = cell.attrib.get("t")
                value_node = cell.find(f"{ns}v")

                if cell_type == "inlineStr":
                    inline = cell.find(f"{ns}is")
                    value: object = "".join(inline.itertext()) if inline is not None else None
                elif value_node is None or value_node.text is None:
                    value = None
                elif cell_type == "s":
                    value = shared_strings[int(value_node.text)]
                elif cell_type == "b":
                    value = bool(int(value_node.text))
                elif cell_type in {"str", "e"}:
                    value = value_node.text
                else:
                    raw = value_node.text
                    try:
                        numeric = float(raw)
                        value = int(numeric) if numeric.is_integer() else numeric
                    except (TypeError, ValueError):
                        value = raw

                values_by_col[col_index] = value

            if values_by_col:
                rows.append([
                    values_by_col.get(i) for i in range(max(values_by_col) + 1)
                ])

    if not rows:
        return pd.DataFrame()

    headers = [
        str(value).strip() if value not in (None, "") else f"column_{i + 1}"
        for i, value in enumerate(rows[0])
    ]
    records = []
    for row in rows[1:]:
        records.append(row + [None] * (len(headers) - len(row)))
    return pd.DataFrame(records, columns=headers)


def read_annotation_sheet(path: pathlib.Path) -> pd.DataFrame:
    """Read CSV or Excel annotation sheets and normalize answer column names."""
    if not path.exists():
        raise FileNotFoundError(f"Annotation sheet not found: {path}")

    if path.suffix.lower() in {".xlsx", ".xls"}:
        try:
            df = pd.read_excel(path)
        except ImportError:
            df = _read_xlsx_without_openpyxl(path)
    elif path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    else:
        raise ValueError(f"Unsupported annotation sheet type: {path.suffix}")

    if "answer" not in df.columns and "candidate_answer" in df.columns:
        df["answer"] = df["candidate_answer"]
    return df


def score_to_band(score: float) -> str:
    """Bucket a 0–100 score into Good/Average/Poor."""
    if score >= 61:
        return "Good"
    if score >= 31:
        return "Average"
    return "Poor"


def cohen_kappa_bands(a: pd.Series, b: pd.Series) -> float:
    """Compute Cohen's Kappa between two annotator columns (band-level)."""
    valid = a.notna() & b.notna()
    if valid.sum() < 2:
        return float("nan")
    a_bands = a[valid].apply(score_to_band)
    b_bands = b[valid].apply(score_to_band)
    try:
        return cohen_kappa_score(a_bands, b_bands, labels=["Good", "Average", "Poor"])
    except Exception:
        return float("nan")


def confusion_matrix_bands(human_mean: pd.Series, system: pd.Series) -> dict:
    """Confusion matrix between human mean bands and system bands."""
    bands = ["Good", "Average", "Poor"]
    matrix = {actual: {pred: 0 for pred in bands} for actual in bands}
    for h, s in zip(human_mean, system):
        if pd.notna(h) and pd.notna(s):
            matrix[score_to_band(h)][score_to_band(s)] += 1
    return matrix


def top_disagreements(df: pd.DataFrame, human_mean: pd.Series, n: int = 5) -> pd.DataFrame:
    """Return the n rows where |system_score - human_mean| is largest."""
    df = df.copy()
    df["human_mean"] = human_mean
    df["delta"] = (df["system_score"] - df["human_mean"]).abs()
    return (
        df[df["human_mean"].notna()]
        .sort_values("delta", ascending=False)
        .head(n)[["question", "answer", "system_score", "human_mean", "delta"]]
        .reset_index(drop=True)
    )


def clean_report_text(value: object) -> str:
    """Clean common encoding artifacts before writing Markdown snippets."""
    text = str(value)
    replacements = {
        "‚Äî": "—",
        "‚Äì": "–",
        "‚Äô": "'",
        "‚Äú": '"',
        "‚Äù": '"',
        "‚Üí": "→",
        "â€”": "—",
        "â€“": "–",
        "â€™": "'",
        "â€œ": '"',
        "â€�": '"',
        "â†’": "→",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


def main(sheet_path: Optional[pathlib.Path] = None, output_path: Optional[pathlib.Path] = None) -> None:
    path = sheet_path or DATA_PATH
    print(f"Reading {path} ...")
    df = read_annotation_sheet(path)

    # Detect annotator columns dynamically
    annotator_cols = sorted([c for c in df.columns if c.startswith("annotator_")])
    if len(annotator_cols) < 2:
        sys.exit("Need at least 2 annotator columns")

    # Coerce annotator columns to float
    for col in annotator_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["system_score"] = pd.to_numeric(df["system_score"], errors="coerce")

    filled_annotators = [c for c in annotator_cols if df[c].notna().any()]
    if not filled_annotators:
        print("ERROR: No annotator columns have been filled in yet.")
        print(f"  Fill in {annotator_cols} in {path.name}, then re-run.")
        sys.exit(1)

    # Human mean across filled annotators
    human_mean = df[filled_annotators].mean(axis=1)

    # ── Inter-rater agreement ─────────────────────────────────────────────────
    kappa_pairs = {}
    for a, b in combinations(filled_annotators, 2):
        kappa_pairs[f"{a} vs {b}"] = cohen_kappa_bands(df[a], df[b])

    kappa_values = [v for v in kappa_pairs.values() if not math.isnan(v)]
    avg_kappa = float(np.mean(kappa_values)) if kappa_values else float("nan")

    # ── Pearson correlation ───────────────────────────────────────────────────
    valid_mask = df["system_score"].notna() & human_mean.notna()
    n_valid = valid_mask.sum()

    if n_valid >= 2:
        r, p_val = pearsonr(df.loc[valid_mask, "system_score"], human_mean[valid_mask])
    else:
        r, p_val = float("nan"), float("nan")

    per_annotator_r = {}
    for col in filled_annotators:
        annotator_mask = df["system_score"].notna() & df[col].notna()
        if annotator_mask.sum() >= 2:
            annotator_r, annotator_p = pearsonr(
                df.loc[annotator_mask, "system_score"],
                df.loc[annotator_mask, col],
            )
            per_annotator_r[col] = (annotator_r, annotator_p)

    # ── Confusion matrix ──────────────────────────────────────────────────────
    cm = confusion_matrix_bands(human_mean, df["system_score"])

    # ── Top-5 disagreements ───────────────────────────────────────────────────
    top5 = top_disagreements(df, human_mean, n=5)

    # ── Build report ──────────────────────────────────────────────────────────
    def kappa_interpret(k: float) -> str:
        if math.isnan(k): return "N/A"
        if k >= 0.80: return "Almost perfect"
        if k >= 0.60: return "Substantial"
        if k >= 0.40: return "Moderate"
        if k >= 0.20: return "Fair"
        return "Slight / poor"

    lines = [
        "# Human Baseline Report — interViv Scoring System",
        "",
        f"**Generated from:** `{path.name}`  ",
        f"**Rows analysed:** {n_valid}  ",
        f"**Annotators with data:** {', '.join(filled_annotators)}",
        "",
        "---",
        "",
        "## 1. Inter-Rater Agreement (Cohen's κ)",
        "",
        "| Pair | κ | Interpretation |",
        "|------|---|----------------|",
    ]
    for pair, k in kappa_pairs.items():
        k_str = f"{k:.3f}" if not math.isnan(k) else "N/A"
        lines.append(f"| {pair} | {k_str} | {kappa_interpret(k)} |")

    avg_kappa_str = f"{avg_kappa:.3f}" if not math.isnan(avg_kappa) else "N/A"
    lines += [
        f"| **Average** | **{avg_kappa_str}** | **{kappa_interpret(avg_kappa)}** |",
        "",
        "> κ interpretation: <0.20 Slight, 0.20–0.40 Fair, 0.40–0.60 Moderate, 0.60–0.80 Substantial, >0.80 Almost perfect",
        "",
        "---",
        "",
        "## 2. System vs Human Correlation (Pearson r)",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Pearson r | {f'{r:.4f}' if not math.isnan(r) else 'N/A'} |",
        f"| p-value   | {f'{p_val:.4f}' if not math.isnan(p_val) else 'N/A'} |",
        f"| n         | {n_valid} |",
        "",
    ]

    if not math.isnan(r):
        sig = "statistically significant (p < 0.05)" if p_val < 0.05 else "not statistically significant (p ≥ 0.05)"
        lines.append(f"> The system-human correlation is **{r:.3f}**, {sig}.")

    if per_annotator_r:
        lines += [
            "",
            "| Annotator | Pearson r with system | p-value |",
            "|-----------|----------------------|---------|",
        ]
        for col, (annotator_r, annotator_p) in per_annotator_r.items():
            lines.append(f"| {col} | {annotator_r:.3f} | {annotator_p:.4f} |")

    lines += [
        "",
        "---",
        "",
        "## 3. Confusion Matrix (Good / Average / Poor bands)",
        "",
        "Rows = Human mean band  ·  Columns = System predicted band",
        "",
        "| Human \\ System | Good | Average | Poor |",
        "|-----------------|------|---------|------|",
    ]
    for actual in ["Good", "Average", "Poor"]:
        row = cm[actual]
        lines.append(f"| **{actual}** | {row['Good']} | {row['Average']} | {row['Poor']} |")

    lines += [
        "",
        "---",
        "",
        "## 4. Top-5 System-Human Disagreements",
        "",
        "| # | Question (truncated) | Answer (truncated) | System | Human | Delta |",
        "|---|----------------------|--------------------|--------|-------|-------|",
    ]
    for i, row in top5.iterrows():
        q   = clean_report_text(row["question"])[:60].replace("|", "\\|")
        ans = clean_report_text(row["answer"])[:50].replace("|", "\\|")
        lines.append(
            f"| {i+1} | {q}... | {ans}... | {row['system_score']:.0f} | {row['human_mean']:.0f} | {row['delta']:.0f} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 5. Notes",
        "",
        "- **System score** is the NLP score from the 3-layer hybrid scorer (v11) without KG blending.",
        "- **Annotator scale**: 0–30 = Poor, 31–60 = Average, 61–100 = Good.",
        "- Band boundaries: score < 31 → Poor, 31–60 → Average, > 60 → Good.",
        "- `persona_validation_final.xlsx` is a separate persona simulation and is not used as the primary human baseline.",
    ]

    out = output_path or REPORT_PATH
    report = "\n".join(lines)
    out.write_text(report, encoding="utf-8")
    print(f"\nReport written to {out}")
    print(f"\nKey results:")
    print(f"  Average κ: {avg_kappa_str} ({kappa_interpret(avg_kappa)})")
    r_str = f"{r:.4f}" if not math.isnan(r) else "N/A"
    p_str = f"{p_val:.4f}" if not math.isnan(p_val) else "N/A"
    print(f"  Pearson r: {r_str}  (p={p_str})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet", type=pathlib.Path, default=None)
    parser.add_argument("--output", type=pathlib.Path, default=None)
    args = parser.parse_args()
    main(args.sheet, args.output)
