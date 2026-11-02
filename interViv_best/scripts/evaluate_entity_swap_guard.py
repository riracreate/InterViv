"""Evaluate the entity-swap guard in modules/answer_guard.py.

Measures, on comparison-style questions from data/interview_dataset_v6.csv:
  * false-positive rate: how often the guard fires on real answers, by label
    (Good answers firing is the number that matters);
  * recall: how often it fires on synthetic swaps, made by exchanging the two
    compared entity names inside a Good answer that did not fire.

Thresholds are chosen on 80% of question groups and reported on the held-out
20%, so the held-out numbers are not tuned on.

Run:
    python scripts/evaluate_entity_swap_guard.py
    python scripts/evaluate_entity_swap_guard.py --out research/entity_swap_guard_eval.json
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import answer_guard as guard  # noqa: E402

DATASET = ROOT / "data" / "interview_dataset_v6.csv"
POOLED = (DATASET, ROOT / "data" / "ml_training_data.csv")
GRID_MIN_CROSSED = (1, 2, 3)
GRID_RATIO = (1.0, 1.5, 2.0, 3.0)
MAX_GOOD_FP_RATE = 0.01
SEED = 42


def _fires(evidence: dict | None, min_crossed: int, ratio: float) -> bool:
    return guard.entity_swap_fires(evidence, min_crossed=min_crossed, ratio=ratio)


def _surface(replacement: str, original: str) -> str:
    word = replacement
    if guard._swap_stem(original.lower()) != original.lower():
        word = word + ("es" if word.endswith(("s", "x", "ch", "sh")) else "s")
    if original.isupper():
        return word.upper()
    if original[:1].isupper():
        return word[:1].upper() + word[1:]
    return word


def synthetic_swap(answer: str, ident_a: set[str], ident_b: set[str]) -> str | None:
    """Exchange the two single-token entity names everywhere in the answer."""
    if len(ident_a) != 1 or len(ident_b) != 1:
        return None
    (a,), (b,) = tuple(ident_a), tuple(ident_b)

    def repl(match: re.Match) -> str:
        token = match.group(0)
        stem = guard._swap_stem(token.lower())
        if stem == a:
            return _surface(b, token)
        if stem == b:
            return _surface(a, token)
        return token

    swapped = re.sub(r"[A-Za-z0-9+#]+", repl, answer)
    return swapped if swapped != answer else None


def build_rows() -> list[dict]:
    df = pd.read_csv(DATASET)
    rows = []
    for rec in df.to_dict("records"):
        question = str(rec.get("question") or "")
        ideal = str(rec.get("ideal_answer") or "")
        answer = str(rec.get("answer") or "")
        pair = guard._contrast_pair(question)
        if pair is None:
            continue
        evidence = guard.entity_swap_evidence(answer, question, ideal)
        swap_text = synthetic_swap(answer, pair[0], pair[1]) if str(rec.get("label")) == "Good" else None
        rows.append({
            "question": question,
            "label": str(rec.get("label")),
            "evidence": evidence,
            "applicable": evidence is not None,
            "swap_evidence": guard.entity_swap_evidence(swap_text, question, ideal) if swap_text else None,
        })
    return rows


def metrics(rows: list[dict], min_crossed: int, ratio: float) -> dict:
    by_label: dict[str, dict[str, int]] = {}
    for row in rows:
        stats = by_label.setdefault(row["label"], {"n": 0, "applicable": 0, "fired": 0})
        stats["n"] += 1
        stats["applicable"] += int(row["applicable"])
        stats["fired"] += int(_fires(row["evidence"], min_crossed, ratio))
    for stats in by_label.values():
        stats["fire_rate"] = round(stats["fired"] / stats["n"], 4) if stats["n"] else 0.0

    swap_pool = [
        r for r in rows
        if r["label"] == "Good"
        and r["swap_evidence"] is not None
        and not _fires(r["evidence"], min_crossed, ratio)
    ]
    caught = sum(_fires(r["swap_evidence"], min_crossed, ratio) for r in swap_pool)
    good = by_label.get("Good", {"n": 0, "fired": 0})
    return {
        "min_crossed": min_crossed,
        "ratio": ratio,
        "by_label": by_label,
        "good_fp_rate": round(good["fired"] / good["n"], 4) if good["n"] else 0.0,
        "synthetic_swaps": len(swap_pool),
        "swap_recall": round(caught / len(swap_pool), 4) if swap_pool else 0.0,
    }


def pooled_false_positives() -> dict:
    """Fire counts on every unique real answer to a comparison question."""
    df = pd.concat([pd.read_csv(p) for p in POOLED]).drop_duplicates(subset=["question", "answer"])
    out: dict[str, dict] = {}
    for rec in df.to_dict("records"):
        question = str(rec.get("question") or "")
        if guard._contrast_pair(question) is None:
            continue
        evidence = guard.entity_swap_evidence(str(rec.get("answer") or ""), question, str(rec.get("ideal_answer") or ""))
        stats = out.setdefault(str(rec.get("label")), {"n": 0, "applicable": 0, "fired": 0, "fired_examples": []})
        stats["n"] += 1
        stats["applicable"] += int(evidence is not None)
        if guard.entity_swap_fires(evidence):
            stats["fired"] += 1
            stats["fired_examples"].append({"question": question, "answer": str(rec.get("answer"))[:200]})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, help="Write the JSON report here")
    args = parser.parse_args()

    rows = build_rows()
    questions = sorted({r["question"] for r in rows})
    random.Random(SEED).shuffle(questions)
    cut = int(len(questions) * 0.8)
    tune_q = set(questions[:cut])
    tune = [r for r in rows if r["question"] in tune_q]
    held = [r for r in rows if r["question"] not in tune_q]

    grid = [metrics(tune, m, r) for m in GRID_MIN_CROSSED for r in GRID_RATIO]
    eligible = [g for g in grid if g["good_fp_rate"] <= MAX_GOOD_FP_RATE]
    chosen = max(eligible, key=lambda g: (g["swap_recall"], g["min_crossed"], g["ratio"])) if eligible else None

    shipped = metrics(held, guard.ENTITY_SWAP_MIN_CROSSED, guard.ENTITY_SWAP_RATIO)
    report = {
        "dataset": str(DATASET.relative_to(ROOT)),
        "seed": SEED,
        "comparison_rows": len(rows),
        "comparison_questions": len(questions),
        "tune_questions": len(tune_q),
        "heldout_questions": len(questions) - len(tune_q),
        "selection_rule": f"max swap recall on tune split with Good FP rate <= {MAX_GOOD_FP_RATE}",
        "tune_grid": grid,
        "chosen_on_tune": None if chosen is None else {"min_crossed": chosen["min_crossed"], "ratio": chosen["ratio"]},
        "shipped_thresholds": {"min_crossed": guard.ENTITY_SWAP_MIN_CROSSED, "ratio": guard.ENTITY_SWAP_RATIO},
        "heldout_with_shipped_thresholds": shipped,
        "pooled_real_answers_shipped_thresholds": pooled_false_positives(),
        "notes": [
            "Synthetic swaps exchange the two entity names, so they are symmetric by construction; real one-directional misattributions are not measured.",
            "v2 rules (both-direction requirement, pronoun openers, no parenthesis split, shared-head exclusion) were added after inspecting two false positives in the pooled data, which includes the held-out questions. Held-out numbers are therefore not fully untouched.",
            "Small samples: an observed 0 false positives on n Good answers bounds the true rate at about 3/n (95%).",
        ],
    }

    print(f"comparison rows: {len(rows)}  questions: {len(questions)}  (tune {len(tune_q)} / held-out {len(questions) - len(tune_q)})")
    print("tune grid  (min_crossed, ratio): good_fp_rate  swap_recall  [n swaps]")
    for g in grid:
        print(f"  ({g['min_crossed']}, {g['ratio']:.1f}): {g['good_fp_rate']:.4f}  {g['swap_recall']:.4f}  [{g['synthetic_swaps']}]")
    print("chosen on tune:", report["chosen_on_tune"])
    print("shipped:", report["shipped_thresholds"])
    print("held-out, shipped thresholds:")
    for label, stats in sorted(shipped["by_label"].items()):
        print(f"  {label:8s} n={stats['n']:4d} applicable={stats['applicable']:4d} fired={stats['fired']:3d} rate={stats['fire_rate']:.4f}")
    print(f"  synthetic swap recall: {shipped['swap_recall']:.4f} over {shipped['synthetic_swaps']} swaps")
    print("pooled real answers (both datasets, unique), shipped thresholds:")
    for label, stats in sorted(report["pooled_real_answers_shipped_thresholds"].items()):
        print(f"  {label:8s} n={stats['n']:4d} applicable={stats['applicable']:4d} fired={stats['fired']:3d}")
        for ex in stats["fired_examples"]:
            print("     fired:", ex["question"][:70], "|", ex["answer"][:90])

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
