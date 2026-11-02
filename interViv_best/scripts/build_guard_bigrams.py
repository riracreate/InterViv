"""Rebuild the answer guard's letter-pair tables and check they are current.

Both tables in modules/answer_guard.py come only from the question bank's
reference text: every question and ideal answer in the two datasets below,
words of six or more letters. Candidate answers are never used.

  _COMMON_BIGRAMS  pairs found in at least MIN_WORDS distinct words
  _UNSEEN_BIGRAMS  pairs found in none of them

Run from interViv_best/:
    .venv/bin/python scripts/build_guard_bigrams.py          # exit 1 if stale
    .venv/bin/python scripts/build_guard_bigrams.py --print  # print both tables
"""
from __future__ import annotations

import argparse
import re
import string
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCES = ("data/interview_dataset_v6.csv", "data/ml_training_data.csv")
MIN_WORD_LENGTH = 6
MIN_WORDS = 10


def reference_words() -> set[str]:
    frames = [pd.read_csv(ROOT / name).fillna("") for name in SOURCES]
    data = pd.concat(frames)
    text = " ".join(data["ideal_answer"].astype(str)) + " " + " ".join(data["question"].astype(str))
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= MIN_WORD_LENGTH}


def build(words: set[str] | None = None) -> tuple[frozenset[str], frozenset[str]]:
    words = reference_words() if words is None else words
    counts = Counter(pair for w in words for pair in {w[i:i + 2] for i in range(len(w) - 1)})
    common = frozenset(pair for pair, n in counts.items() if n >= MIN_WORDS)
    letters = string.ascii_lowercase
    unseen = frozenset(a + b for a in letters for b in letters if a + b not in counts)
    return common, unseen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print", action="store_true", dest="show")
    args = parser.parse_args()
    common, unseen = build()
    if args.show:
        for name, table in (("_COMMON_BIGRAMS", common), ("_UNSEEN_BIGRAMS", unseen)):
            print(f"{name}: " + ", ".join(f'"{pair}"' for pair in sorted(table)))
        return 0
    from modules.answer_guard import _COMMON_BIGRAMS, _UNSEEN_BIGRAMS

    stale = False
    for name, built, frozen in (("_COMMON_BIGRAMS", common, _COMMON_BIGRAMS), ("_UNSEEN_BIGRAMS", unseen, _UNSEEN_BIGRAMS)):
        if built != frozen:
            stale = True
            print(f"{name} stale: {len(built - frozen)} pair(s) to add, {len(frozen - built)} to remove")
    if stale:
        return 1
    print(f"current: {len(common)} common pairs, {len(unseen)} unseen pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
