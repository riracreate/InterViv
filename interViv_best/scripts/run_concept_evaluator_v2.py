#!/usr/bin/env python3
"""Offline CLI for the experimental concept evaluator v2.

Does not touch production scoring, mastery, Elo, or readiness.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.concept_evaluator_v2 import (  # noqa: E402
    EVALUATOR_VERSION,
    evaluate_answer,
    experimental_concept_evaluator_enabled,
)
from modules.question_bundles import content_hash, validate_bundle_doc  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Experimental concept evaluator v2 (offline)")
    parser.add_argument("--bundle", type=Path, required=True, help="YAML bundle file (v2 draft)")
    parser.add_argument("--answer", type=str, default="", help="Candidate answer text")
    parser.add_argument("--answer-file", type=Path, default=None)
    parser.add_argument("--version", type=int, default=None, help="Select version when YAML is a list")
    parser.add_argument("--require-gate", action="store_true",
                        help="Refuse unless EXPERIMENTAL_CONCEPT_EVALUATOR=1")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.require_gate and not experimental_concept_evaluator_enabled():
        print("EXPERIMENTAL_CONCEPT_EVALUATOR is off; refusing.", file=sys.stderr)
        return 2

    import yaml
    loaded = yaml.safe_load(args.bundle.read_text(encoding="utf-8"))
    docs = loaded if isinstance(loaded, list) else [loaded]
    if args.version is not None:
        docs = [d for d in docs if int(d.get("version", -1)) == args.version]
        if not docs:
            print(f"No document with version={args.version}", file=sys.stderr)
            return 1
    # Prefer highest version when unspecified
    doc = max(docs, key=lambda d: int(d.get("version") or 0))
    validated = validate_bundle_doc(doc)
    answer = args.answer
    if args.answer_file:
        answer = args.answer_file.read_text(encoding="utf-8")

    result = evaluate_answer(
        answer_text=answer,
        bundle_content=validated["content"],
        bundle_content_hash=validated["content_hash"],
    )
    result["cli_note"] = (
        f"{EVALUATOR_VERSION} offline result; not a production score; "
        f"hash_check={content_hash(validated['content']) == validated['content_hash']}"
    )
    blob = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(blob + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(blob)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
