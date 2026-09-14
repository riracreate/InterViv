"""
Smoke test for Change 5: Human baseline evaluation scripts.

Verifies:
  1. The real human baseline workbook has the right columns
  2. The workbook has system_score values in a sensible range
  3. baseline_analysis.py produces a report without errors given filled data

Run with:  python -m pytest tests/test_change5_baseline.py -v
"""

import sys, os, pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASELINE_SHEET = ROOT / "data" / "human_baseline_real_combined.xlsx"


def _read_baseline():
    from scripts.baseline_analysis import read_annotation_sheet
    return read_annotation_sheet(BASELINE_SHEET)


def test_baseline_sheet_exists_and_has_correct_columns():
    """The real human baseline workbook must have the required columns."""
    assert BASELINE_SHEET.exists(), f"human baseline workbook not found at {BASELINE_SHEET}"

    df = _read_baseline()
    required = {
        "row_id", "question", "ideal_answer", "candidate_answer",
        "system_score", "annotator_1", "annotator_2", "annotator_3",
        "ann_mean", "ann_std",
    }
    missing = required - set(df.columns)
    assert not missing, f"Missing columns: {missing}"


def test_baseline_sheet_row_count():
    """Sheet must contain the 30-row real human baseline sample."""
    df = _read_baseline()
    assert len(df) >= 30, f"Expected ≥30 rows, got {len(df)}"


def test_baseline_system_scores_in_range():
    """system_score must be 0–100 for every row."""
    import pandas as pd
    df = _read_baseline()
    df["system_score"] = pd.to_numeric(df["system_score"], errors="coerce")
    bad = df[(df["system_score"] < 0) | (df["system_score"] > 100)]
    assert len(bad) == 0, f"{len(bad)} rows have system_score out of [0,100]"


def test_analysis_produces_report(tmp_path):
    """baseline_analysis.py must run without error and write a report.

    Writes only to a temporary path so the frozen
    ``docs/human_baseline_report.md`` is never rewritten by the suite.
    """
    report = tmp_path / "human_baseline_report.md"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "baseline_analysis.py"),
            "--sheet", str(BASELINE_SHEET),
            "--output", str(report),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert result.returncode == 0, f"baseline_analysis.py failed:\n{result.stderr}"
    assert report.exists(), "Report file was not created"
    content = report.read_text(encoding="utf-8")
    # Check key sections are present
    for section in ["Inter-Rater Agreement", "Pearson r", "Confusion Matrix", "Top-5"]:
        assert section in content, f"Section '{section}' missing from report"


if __name__ == "__main__":
    tests = [
        test_baseline_sheet_exists_and_has_correct_columns,
        test_baseline_sheet_row_count,
        test_baseline_system_scores_in_range,
        test_analysis_produces_report,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed+failed} passed")
