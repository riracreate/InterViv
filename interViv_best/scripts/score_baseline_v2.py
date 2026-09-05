"""
score_baseline_v2.py — Score the 50 Google Form baseline answers with the system pipeline.

Reads the form rows from the ROWS array in BuildForm.gs (default
~/Downloads/BuildForm.gs), matches each row against
data/interview_dataset_v6.csv by exact text match on BOTH question and answer
(after stripping whitespace; row_id is never used for matching), scores each
match with backend.scoring.pipeline.run_scoring_pipeline, and writes
data/baseline_v2_system_scores.csv.

Usage:
    python scripts/score_baseline_v2.py [--form PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.scoring.pipeline import run_scoring_pipeline  # noqa: E402

DATA_PATH = ROOT / "data" / "interview_dataset_v6.csv"
OUT_PATH = ROOT / "data" / "baseline_v2_system_scores.csv"
FORM_DEFAULT = pathlib.Path.home() / "Downloads" / "BuildForm.gs"

OUT_COLUMNS = [
    "form_position", "row_id", "skill", "label", "system_score",
    "nlp_score", "svm_label", "guard_applied",
    "layer1", "layer2", "layer3", "semantic", "tfidf",
]


def _matching_bracket(text: str, start: int, open_ch: str, close_ch: str) -> int:
    """Index of the bracket matching text[start]; string-aware for both quotes."""
    quote: str | None = None
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if quote is not None:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError(f"no matching {close_ch!r} for bracket at offset {start}")


def _decode_js_string(token: str) -> str:
    token = token.strip()
    if token.startswith('"'):
        return json.loads(token)
    if token.startswith("'"):
        body = token[1:-1]
        return body.replace("\\'", "'").replace("\\\\", "\\")
    raise ValueError(f"not a quoted string: {token[:40]!r}")


_STR = r"""("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')"""


def _parse_row_object(obj: str) -> dict:
    row_id = re.search(r"""["']?row_id["']?\s*:\s*(\d+)""", obj)
    q = re.search(r"""["']?q["']?\s*:\s*""" + _STR, obj, re.DOTALL)
    ans = re.search(r"""["']?ans["']?\s*:\s*""" + _STR, obj, re.DOTALL)
    if not (row_id and q and ans):
        raise ValueError(f"ROWS entry is missing row_id/q/ans: {obj[:80]!r}")
    return {
        "row_id": int(row_id.group(1)),
        "q": _decode_js_string(q.group(1)),
        "ans": _decode_js_string(ans.group(1)),
    }


def parse_rows(form_path: pathlib.Path) -> list[dict]:
    """Parse the ROWS array out of a BuildForm.gs file."""
    text = form_path.read_text(encoding="utf-8")
    anchor = text.find("ROWS")
    if anchor < 0:
        raise ValueError(f"no ROWS array found in {form_path}")
    start = text.find("[", anchor)
    if start < 0:
        raise ValueError(f"no ROWS array found in {form_path}")
    array_text = text[start:_matching_bracket(text, start, "[", "]") + 1]
    rows = []
    i = 0
    while True:
        j = array_text.find("{", i)
        if j < 0:
            break
        obj = array_text[j:_matching_bracket(array_text, j, "{", "}") + 1]
        rows.append(_parse_row_object(obj))
        i = j + len(obj)
    return rows


def load_dataset() -> tuple[dict[tuple[str, str], dict], int]:
    """Map (stripped question, stripped answer) to the first dataset row."""
    index: dict[tuple[str, str], dict] = {}
    dupes = 0
    with DATA_PATH.open(newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            key = ((record.get("question") or "").strip(),
                   (record.get("answer") or "").strip())
            if key in index:
                dupes += 1
                continue  # first match wins; duplicates reported by the caller
            index[key] = record
    return index, dupes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--form", default=str(FORM_DEFAULT))
    parser.add_argument("--out", default=str(OUT_PATH))
    args = parser.parse_args()

    rows = parse_rows(pathlib.Path(args.form))
    print(f"Parsed {len(rows)} form rows from {args.form}")

    dataset, _ = load_dataset()
    print(f"Dataset pairs indexed: {len(dataset)}")

    scored: list[dict] = []
    misses: list[tuple[int, int, str]] = []
    for position, entry in enumerate(rows, start=1):
        key = (entry["q"].strip(), entry["ans"].strip())
        match = dataset.get(key)
        if match is None:
            misses.append((position, entry["row_id"], entry["q"]))
            continue
        answer_text = entry["ans"]
        out = run_scoring_pipeline(
            answer_text=answer_text,
            word_count=len(answer_text.split()),
            difficulty=(match.get("difficulty") or "medium").strip() or "medium",
            question_context={
                "skill": match.get("skill") or "",
                "sub_domain": match.get("sub_domain") or "",
                "question": match.get("question") or "",
                "ideal_answer": match.get("ideal_answer") or "",
                "ideal_keywords": match.get("ideal_keywords") or "",
            },
        )
        breakdown = out.get("scoring_breakdown") or {}
        scored.append({
            "form_position": position,
            "row_id": entry["row_id"],
            "skill": match.get("skill") or "",
            "label": match.get("label") or "",
            "system_score": out.get("final_score"),
            "nlp_score": out.get("nlp_score"),
            "svm_label": out.get("svm_label"),
            "guard_applied": out.get("guard_applied") or "",
            "layer1": breakdown.get("layer1_score"),
            "layer2": breakdown.get("layer2_score"),
            "layer3": breakdown.get("layer3_score"),
            "semantic": breakdown.get("semantic"),
            "tfidf": breakdown.get("tfidf"),
        })
        print(f"  [{position:>2}/{len(rows)}] row_id={entry['row_id']:<4} "
              f"score={out.get('final_score')!s:>6} guard={out.get('guard_applied') or '-'}")

    print(f"\nMatched {len(scored)}/{len(rows)} form rows in {DATA_PATH.name}")
    for position, row_id, question in misses:
        print(f"NO MATCH form_position={position} row_id={row_id} question={question!r}")

    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUT_COLUMNS)
        writer.writeheader()
        writer.writerows(scored)
    print(f"Wrote {args.out} ({len(scored)} rows)")

    if scored:
        scores = [float(r["system_score"]) for r in scored]
        print(f"system_score mean={sum(scores) / len(scores):.2f} "
              f"min={min(scores):.2f} max={max(scores):.2f}")
        labels: dict[str, int] = {}
        for r in scored:
            labels[r["label"]] = labels.get(r["label"], 0) + 1
        print("label distribution: " + ", ".join(
            f"{label}={count}" for label, count in sorted(labels.items())))
        guards: dict[str, int] = {}
        for r in scored:
            if r["guard_applied"]:
                guards[r["guard_applied"]] = guards.get(r["guard_applied"], 0) + 1
        print("guards fired: " + (", ".join(
            f"{name}={count}" for name, count in sorted(guards.items()))
            if guards else "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
