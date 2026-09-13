"""Import canonical YAML question bundles into the bundle store as drafts.

    .venv/bin/python scripts/import_question_bundles.py [--root data/question_bundles]
                                                        [--actor import_cli] [--check]

Idempotent: same version + same content hash is a no-op; same version with a
different hash is rejected (bump `version` in the YAML); new content is a new
draft version. Never touches reviewed content or recorded review decisions —
the store has no path for that.

Every question is checked against known evaluation items
(``modules/evaluation_overlap.py``): an exact match is rejected; a
near-duplicate is imported but flagged in the report and in
``attribution_json.evaluation_overlap`` for the reviewer.

``--check`` validates and reports without writing. Uses the memory store when
DATABASE_URL is absent, so ``--check`` works on a bare checkout.

Exit code 1 if any file failed validation, conflicted, or overlapped exactly.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import bundle_store  # noqa: E402
from modules.bundle_store import BundleStoreError  # noqa: E402
from modules.evaluation_overlap import check_overlap  # noqa: E402
from modules.question_bundles import BundleContentError, iter_bundle_files, validate_bundle_doc  # noqa: E402


def import_directory(root: Path, *, actor_id: str, check_only: bool = False) -> dict:
    report = {"valid": [], "created": [], "unchanged": [], "flagged": [], "failed": []}
    for path, doc in iter_bundle_files(root):
        label = f"{path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}"
        try:
            parsed = validate_bundle_doc(doc)
        except BundleContentError as exc:
            report["failed"].append((label, f"invalid: {exc}"))
            continue
        content = parsed["content"]
        label = f"{label} [{content['bundle_id']} v{parsed['version']}]"
        overlap = check_overlap(content["question"])
        if overlap["exact"]:
            hits = ", ".join(f"{h['source']}#{h['item_id']}" for h in overlap["exact"])
            report["failed"].append((label, f"evaluation overlap (exact): {hits}"))
            continue
        if overlap["paraphrase"]:
            hits = [f"{h['source']}#{h['item_id']} (jaccard {h['jaccard']})" for h in overlap["paraphrase"]]
            report["flagged"].append((label, "; ".join(hits)))
            doc = {**doc, "attribution": {**(doc.get("attribution") or {}),
                                          "evaluation_overlap": {"paraphrase": hits}}}
        if check_only:
            report["valid"].append((label, parsed["content_hash"]))
            continue
        try:
            result = bundle_store.import_bundle(doc, actor_id=actor_id)
        except BundleStoreError as exc:
            report["failed"].append((label, f"{exc.code}: {exc}"))
            continue
        report[result["result"]].append((label, result["version"]["content_hash"]))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=str(ROOT / "data" / "question_bundles"))
    parser.add_argument("--actor", default="import_cli",
                        help="identity recorded in the audit row (not the content author)")
    parser.add_argument("--check", action="store_true", help="validate and report only; write nothing")
    args = parser.parse_args()

    report = import_directory(Path(args.root), actor_id=args.actor, check_only=args.check)
    for key in ("valid", "created", "unchanged", "flagged", "failed"):
        for label, detail in report[key]:
            print(f"{key.upper():9} {label}  {detail}")
    print(
        f"\n{len(report['valid'])} valid, {len(report['created'])} created, {len(report['unchanged'])} unchanged, "
        f"{len(report['flagged'])} flagged for reviewer attention, {len(report['failed'])} failed"
        + ("  (check only, nothing written)" if args.check else "")
    )
    if not args.check:
        inv = bundle_store.inventory()
        print(f"status totals: {inv['status_totals']}  (reviewed bundles: {inv['reviewed_total']})")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
