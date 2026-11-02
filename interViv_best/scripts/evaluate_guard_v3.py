"""Reproduce the scorer v3 guard measurements recorded in docs/scorer_versions.md.

1. Words: the per-word nonsense check on held-out real words from the question
   bank's reference text (table built from the other 80%), against uniformly
   random strings and keyboard-row mash. Current check vs the v2 check.
2. Answers: guard decisions on every answer in the two datasets, v2 vs current,
   grouped by dataset label. With --scores, also full-pipeline final scores for
   the answers whose decision changed (slower: loads the scoring models).

The v2 guard is read from git (default commit 071284b) into a temporary module;
nothing in the working tree is modified.

Run from interViv_best/:
    .venv/bin/python scripts/evaluate_guard_v3.py
    .venv/bin/python scripts/evaluate_guard_v3.py --scores
"""
from __future__ import annotations

import argparse
import importlib.util
import random
import re
import statistics
import string
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.runtime_env import apply_runtime_env  # noqa: E402

apply_runtime_env()

import pandas as pd  # noqa: E402

from modules import answer_guard as current  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from build_guard_bigrams import build as build_tables  # noqa: E402

DATASETS = ("data/interview_dataset_v6.csv", "data/ml_training_data.csv")


def load_old_guard(commit: str):
    source = subprocess.run(
        ["git", "show", f"{commit}:interViv_best/modules/answer_guard.py"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    tmp = Path(tempfile.mkdtemp()) / "answer_guard_v2.py"
    tmp.write_text(source)
    spec = importlib.util.spec_from_file_location("answer_guard_v2", tmp)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def word_level(old) -> None:
    data = pd.concat([pd.read_csv(ROOT / f).fillna("") for f in DATASETS])
    text = " ".join(data["ideal_answer"].astype(str)) + " " + " ".join(data["question"].astype(str))
    words = sorted({w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 6})
    train = [w for i, w in enumerate(words) if i % 5]
    test = [w for i, w in enumerate(words) if not i % 5]
    held_out_common, held_out_unseen = build_tables(set(train))

    rnd = random.Random(7)
    uniform = ["".join(rnd.choice(string.ascii_lowercase) for _ in range(rnd.randint(6, 10))) for _ in range(2000)]
    rows = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
    mash = []
    for _ in range(2000):
        row = rnd.choice(rows)
        pos, word = rnd.randrange(len(row)), ""
        for _ in range(rnd.randint(6, 10)):
            pos = max(0, min(len(row) - 1, pos + rnd.choice((-1, 1, 2, -2))))
            word += row[pos]
        mash.append(word)

    saved = (current._COMMON_BIGRAMS, current._UNSEEN_BIGRAMS)
    current._COMMON_BIGRAMS, current._UNSEEN_BIGRAMS = held_out_common, held_out_unseen
    try:
        def rate(tokens, fn):
            return sum(fn(t) for t in tokens) / len(tokens)

        print(f"Words ({len(test)} held-out real words; table from {len(train)} others)")
        print(f"  {'check':10s} {'real':>7s} {'random':>7s} {'keyboard':>9s}")
        for name, fn in (("v2", old._looks_like_nonsense_token), ("current", current._looks_like_nonsense_token)):
            print(f"  {name:10s} {rate(test, fn):7.1%} {rate(uniform, fn):7.1%} {rate(mash, fn):9.1%}")
    finally:
        current._COMMON_BIGRAMS, current._UNSEEN_BIGRAMS = saved


def decisions(old) -> list[dict]:
    out = []
    for name in DATASETS:
        for i, rec in enumerate(pd.read_csv(ROOT / name).fillna("").to_dict("records")):
            args = (str(rec["answer"]), str(rec["question"]), str(rec["ideal_keywords"]), str(rec["ideal_answer"]))
            before, after = old.check_answer_quality_v2(*args), current.check_answer_quality_v2(*args)
            out.append({"rec": rec, "label": str(rec["label"]),
                        "before": before["reason"] or "-", "after": after["reason"] or "-"})
    changed = [r for r in out if r["before"] != r["after"]]
    print(f"\nAnswers: {len(changed)} of {len(out)} guard decisions changed")
    for (label, b, a), n in Counter((r["label"], r["before"], r["after"]) for r in changed).most_common():
        print(f"  {label:8s} {b:20s} -> {a:20s} {n}")
    for label in ("Good", "Average", "Poor"):
        before = sum(1 for r in out if r["label"] == label and r["before"] != "-")
        after = sum(1 for r in out if r["label"] == label and r["after"] != "-")
        print(f"  capped {label:8s} {before} -> {after}")
    return changed


def final_scores(old, changed: list[dict]) -> None:
    from backend.scoring import pipeline

    original = pipeline.load_module

    def score(guard, rec):
        pipeline.load_module = lambda name, filename=None: guard if name == "answer_guard" else original(name, filename)
        try:
            result = pipeline.run_scoring_pipeline(
                answer_text=str(rec["answer"]), word_count=len(str(rec["answer"]).split()),
                engagement_label="Engaged", wpm=130.0, pause_count=0,
                question_context={"question": str(rec["question"]), "ideal_answer": str(rec["ideal_answer"]),
                                  "ideal_keywords": str(rec["ideal_keywords"]), "skill": str(rec["skill"])},
                difficulty=str(rec["difficulty"]) or "medium", candidate_baseline=50.0,
            )
        finally:
            pipeline.load_module = original
        return float(result["final_score"])

    groups = defaultdict(list)
    for r in changed:
        groups[(r["label"], r["before"], r["after"])].append((score(old, r["rec"]), score(current, r["rec"])))
    print("\nFinal scores for changed answers (mean before -> after)")
    for key, pairs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        b = statistics.mean(p[0] for p in pairs)
        a = statistics.mean(p[1] for p in pairs)
        print(f"  {key[0]:8s} {key[1]:20s} -> {key[2]:20s} n={len(pairs):3d}  {b:5.1f} -> {a:5.1f}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-commit", default="071284b")
    parser.add_argument("--scores", action="store_true")
    args = parser.parse_args()
    old = load_old_guard(args.old_commit)
    word_level(old)
    changed = decisions(old)
    if args.scores:
        final_scores(old, changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
