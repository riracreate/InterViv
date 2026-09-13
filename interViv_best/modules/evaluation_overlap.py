"""Question-level overlap check against known evaluation items.

Bundles that enter the starter bank must not be evaluation items. Known
evaluation sources on this branch:

- ``data/baseline_v2_key.csv`` (n=100 key; ``row_id`` is the item id; the n=50
  form study drew from it — ``data/baseline_v2_system_scores.csv`` lists those
  row_ids)
- ``data/human_baseline_real_combined.xlsx`` (n=30 matched-pairs study)

Matching follows the established rule (``scripts/score_baseline_v2.py``,
``docs/baseline_v2_protocol.md``): exact text after whitespace normalisation.
We additionally casefold, so a capitalisation change cannot slip an evaluation
question into tuning. Exact matches are rejected; near-duplicates are flagged
for human review, never auto-accepted.
"""
from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_KEY = ROOT / "data" / "baseline_v2_key.csv"
BASELINE_FORM_SCORES = ROOT / "data" / "baseline_v2_system_scores.csv"
HUMAN_BASELINE_XLSX = ROOT / "data" / "human_baseline_real_combined.xlsx"

PARAPHRASE_JACCARD = 0.6
_STOP = {"a", "an", "the", "in", "of", "and", "or", "to", "is", "are", "what", "how",
         "do", "does", "you", "it", "its", "be", "with", "for", "on", "explain", "describe"}


def normalize_exact(text: str) -> str:
    return " ".join(str(text or "").split()).casefold()


def _tokens(text: str) -> set[str]:
    # simplification: token-set Jaccard flags obvious paraphrases (e.g. "a B-tree
    # index" vs "B-tree indexing"); it is a review flag, not a decision.
    toks = re.findall(r"[a-z0-9_#+.]+", normalize_exact(text))
    return {t.strip(".") for t in toks if t.strip(".") and t not in _STOP}


@lru_cache(maxsize=1)
def load_evaluation_items() -> tuple[dict, ...]:
    """``(source, item_id, question)`` for every known evaluation item."""
    items: list[dict] = []
    form_rows: set[str] = set()
    if BASELINE_FORM_SCORES.exists():
        with BASELINE_FORM_SCORES.open(newline="", encoding="utf-8") as fh:
            form_rows = {str(r["row_id"]) for r in csv.DictReader(fh)}
    if BASELINE_KEY.exists():
        with BASELINE_KEY.open(newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                items.append({
                    "source": "baseline_v2_key", "item_id": str(r["row_id"]),
                    "question": r["question"], "in_n50_form": str(r["row_id"]) in form_rows,
                })
    if HUMAN_BASELINE_XLSX.exists():
        try:
            import pandas as pd
            frame = pd.read_excel(HUMAN_BASELINE_XLSX)
            for row_id, question in zip(frame["row_id"], frame["question"]):
                items.append({"source": "human_baseline_real_combined", "item_id": str(row_id),
                              "question": str(question), "in_n50_form": False})
        except Exception:  # pragma: no cover - optional reader; caller sees fewer items
            pass
    return tuple(items)


def check_overlap(question: str, items: tuple[dict, ...] | None = None) -> dict:
    """Return ``{"exact": [...], "paraphrase": [...]}`` matches for a question."""
    items = load_evaluation_items() if items is None else items
    target = normalize_exact(question)
    target_tokens = _tokens(question)
    exact, paraphrase = [], []
    for item in items:
        if normalize_exact(item["question"]) == target:
            exact.append(item)
            continue
        other = _tokens(item["question"])
        if target_tokens and other:
            jaccard = len(target_tokens & other) / len(target_tokens | other)
            if jaccard >= PARAPHRASE_JACCARD:
                paraphrase.append({**item, "jaccard": round(jaccard, 3)})
    return {"exact": exact, "paraphrase": paraphrase}
