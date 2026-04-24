"""
Smoke test for Change 5: Human baseline evaluation scripts.

Verifies:
  1. human_baseline.py generates a CSV with the right columns
  2. The CSV has system_score values in a sensible range
  3. baseline_analysis.py produces a report without errors given filled data

Run with:  python -m pytest tests/test_change5_baseline.py -v
"""

import sys, os, pathlib, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_baseline_sheet_exists_and_has_correct_columns():
    """human_baseline.py must have created data/human_baseline_sheet.csv with required columns."""
    import pandas as pd
    sheet = ROOT / "data" / "human_baseline_sheet.csv"
    assert sheet.exists(), f"human_baseline_sheet.csv not found at {sheet}"

    df = pd.read_csv(sheet)
    required = {"question", "answer", "system_score", "annotator_1", "annotator_2", "annotator_3", "annotator_4"}
    missing = required - set(df.columns)
    assert not missing, f"Missing columns: {missing}"


def test_baseline_sheet_row_count():
    """Sheet must have at least 40 rows (50 questions × 4 answers each)."""
    import pandas as pd
    df = pd.read_csv(ROOT / "data" / "human_baseline_sheet.csv")
    assert len(df) >= 40, f"Expected ≥40 rows, got {len(df)}"


def test_baseline_system_scores_in_range():
    """system_score must be 0–100 for every row."""
    import pandas as pd
    df = pd.read_csv(ROOT / "data" / "human_baseline_sheet.csv")
    df["system_score"] = pd.to_numeric(df["system_score"], errors="coerce")
    bad = df[(df["system_score"] < 0) | (df["system_score"] > 100)]
    assert len(bad) == 0, f"{len(bad)} rows have system_score out of [0,100]"


def test_analysis_produces_report():
    """baseline_analysis.py must run without error and write docs/human_baseline_report.md."""
    report = ROOT / "docs" / "human_baseline_report.md"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "baseline_analysis.py")],
        capture_output=True, text=True
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
