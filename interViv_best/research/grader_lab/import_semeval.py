"""CLI for converting the licensed SemEval Task 7 XML package to JSONL."""

from __future__ import annotations

import argparse
from pathlib import Path

from .datasets import DEFAULT_DATA_DIR, import_semeval_5way


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source_root",
        type=Path,
        help="Directory containing extracted beetle/ and sciEntsBank/ folders",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_DATA_DIR / "sem_eval_2013_task_7",
    )
    args = parser.parse_args()
    counts = import_semeval_5way(args.source_root, args.output_dir)
    for name, count in sorted(counts.items()):
        print(f"{name}: {count} examples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
