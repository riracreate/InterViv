"""Measure concept_evaluator_v2 vs concept_evaluator_v3 across all stored bundles.

Reads all seed YAML bundles under ``data/question_bundles/`` and read-only SQLite rows
from ``interviv.db`` and ``local-data/interviv-local.sqlite3``.

Usage:
    # Step 1: Calibrate threshold on Calibration Split only (never inspects Held-Out):
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python scripts/measure_concept_evaluators.py --cal-only

    # Step 2: Run full evaluation (Benchmark A + Cal sweep + Held-Out frozen report)
    # and write report artifacts under data/baselines/concept_evaluator_v3/:
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python scripts/measure_concept_evaluators.py
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import concept_evaluator_v2 as v2
from modules import concept_evaluator_v3 as v3

THRESHOLD_GRID: tuple[float, ...] = (0.45, 0.50, 0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70)
OUT_DIR = ROOT / "data" / "baselines" / "concept_evaluator_v3"


@dataclass(frozen=True)
class LoadedBundle:
    bundle_id: str
    source: str
    content: dict[str, Any]


@dataclass(frozen=True)
class EvalSample:
    kind: str
    polarity: int  # 1 positive, 0 negative
    bundle_id: str
    concept_id: str
    answer_text: str
    bundle_content: dict[str, Any]
    exclude_examples: dict[str, list[str]] | None = None


def _flatten_yaml_docs(raw_docs: list[Any]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for doc in raw_docs:
        if isinstance(doc, dict):
            docs.append(doc)
        elif isinstance(doc, list):
            for item in doc:
                if isinstance(item, dict):
                    docs.append(item)
    return docs


def load_all_stored_bundles() -> tuple[list[LoadedBundle], dict[str, Any]]:
    """Load all YAML seed bundles and read-only SQLite bundle rows."""
    bundles: list[LoadedBundle] = []
    yaml_files = sorted((ROOT / "data" / "question_bundles").rglob("*.yaml"))
    yaml_count = 0
    for yaml_path in yaml_files:
        with yaml_path.open("r", encoding="utf-8") as fh:
            raw_docs = list(yaml.safe_load_all(fh))
        best_by_id: dict[str, dict[str, Any]] = {}
        for doc in _flatten_yaml_docs(raw_docs):
            if not doc.get("required_concepts"):
                continue
            bid = str(doc.get("bundle_id") or yaml_path.stem)
            prev = best_by_id.get(bid)
            if prev is None or int(doc.get("version", 0)) > int(prev.get("version", 0)):
                best_by_id[bid] = doc
        for bid, doc in sorted(best_by_id.items()):
            rel = yaml_path.relative_to(ROOT)
            bundles.append(LoadedBundle(bundle_id=bid, source=f"yaml:{rel}", content=doc))
            yaml_count += 1

    db_counts: dict[str, int] = {}
    for rel_db in ("interviv.db", "local-data/interviv-local.sqlite3"):
        db_path = ROOT / rel_db
        if not db_path.exists():
            db_counts[rel_db] = 0
            continue
        conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT bundle_id, version, status, content_json "
                "FROM question_bundle_versions ORDER BY bundle_id, version"
            ).fetchall()
        finally:
            conn.close()
        kept = 0
        for bid, ver, _status, cj in rows:
            doc = json.loads(cj)
            if isinstance(doc, dict) and doc.get("required_concepts"):
                bundles.append(
                    LoadedBundle(
                        bundle_id=f"{bid}@db_v{ver}",
                        source=f"sqlite:{rel_db}",
                        content=doc,
                    )
                )
                kept += 1
        db_counts[rel_db] = kept

    bundles.sort(key=lambda b: b.bundle_id)

    n_req = sum(len(b.content.get("required_concepts") or []) for b in bundles)
    n_opt = sum(len(b.content.get("optional_concepts") or []) for b in bundles)
    n_pos_ex = sum(
        len(c.get("positive_examples") or [])
        for b in bundles
        for c in (b.content.get("required_concepts") or [])
    )
    n_neg_ex = sum(
        len(c.get("negative_cases") or [])
        for b in bundles
        for c in (b.content.get("required_concepts") or [])
    )
    bundles_with_pos = [
        b.bundle_id
        for b in bundles
        if any((c.get("positive_examples") or []) for c in (b.content.get("required_concepts") or []))
    ]
    inventory = {
        "total_bundles": len(bundles),
        "yaml_bundles": yaml_count,
        "sqlite_bundles": db_counts,
        "required_concepts": n_req,
        "optional_concepts": n_opt,
        "positive_examples": n_pos_ex,
        "negative_cases": n_neg_ex,
        "bundles_with_positive_examples": bundles_with_pos,
    }
    return bundles, inventory


def _v2_match_type(concept_res: dict[str, Any]) -> str | None:
    if concept_res.get("state") != "supported":
        return None
    evidence = concept_res.get("evidence") or []
    for ev in evidence:
        if isinstance(ev, dict):
            kind = ev.get("kind") or ev.get("type") or ""
            if "prop" in str(kind).lower():
                return "proposition"
            if "term" in str(kind).lower() or "alias" in str(kind).lower():
                return "alias"
        elif isinstance(ev, str):
            if ev.startswith("prop:"):
                return "proposition"
    if concept_res.get("mentions"):
        return "alias"
    return "proposition"


def _compute_metrics(tp: int, fp: int, fn: int, tn: int) -> dict[str, Any]:
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
    }


def _evaluate_samples(
    samples: list[EvalSample],
    *,
    evaluator: str,
    semantic_threshold: float | None = None,
    enabled_tiers: tuple[str, ...] = v3.ALL_TIERS,
) -> dict[str, Any]:
    """Evaluate a list of samples with v2 or v3 (overall and per match_type)."""
    tp = fp = fn = tn = 0
    tier_counts: dict[str, dict[str, int]] = {
        "proposition": {"tp": 0, "fp": 0},
        "alias": {"tp": 0, "fp": 0},
        "semantic": {"tp": 0, "fp": 0},
    }
    details: list[dict[str, Any]] = []
    n_pos = sum(1 for s in samples if s.polarity == 1)
    n_neg = sum(1 for s in samples if s.polarity == 0)

    for sample in samples:
        if evaluator == "v2":
            res = v2.evaluate_answer(
                answer_text=sample.answer_text,
                bundle_content=sample.bundle_content,
            )
        else:
            res = v3.evaluate_answer(
                answer_text=sample.answer_text,
                bundle_content=sample.bundle_content,
                exclude_examples=sample.exclude_examples,
                semantic_threshold=semantic_threshold,
                enabled_tiers=enabled_tiers,
            )
        c_res = next(
            (c for c in res.get("concepts", []) if c["concept_id"] == sample.concept_id),
            None,
        )
        supported = bool(c_res and c_res.get("state") == "supported")
        m_type = (
            _v2_match_type(c_res)
            if (evaluator == "v2" and c_res)
            else (c_res.get("match_type") if c_res else None)
        )
        if sample.polarity == 1:
            if supported:
                tp += 1
                if m_type in tier_counts:
                    tier_counts[m_type]["tp"] += 1
            else:
                fn += 1
        else:
            if supported:
                fp += 1
                if m_type in tier_counts:
                    tier_counts[m_type]["fp"] += 1
            else:
                tn += 1
        details.append(
            {
                "kind": sample.kind,
                "polarity": sample.polarity,
                "bundle_id": sample.bundle_id,
                "concept_id": sample.concept_id,
                "supported": supported,
                "state": c_res.get("state") if c_res else None,
                "match_type": m_type,
                "semantic_score": c_res.get("semantic_score") if c_res else None,
                "matched_text": c_res.get("matched_text") if c_res else None,
            }
        )

    overall = _compute_metrics(tp, fp, fn, tn)
    attribution: dict[str, dict[str, Any]] = {}
    for tier, counts in tier_counts.items():
        t_tp = counts["tp"]
        t_fp = counts["fp"]
        t_prec = t_tp / (t_tp + t_fp) if (t_tp + t_fp) else 0.0
        t_rec_share = t_tp / n_pos if n_pos else 0.0
        attribution[tier] = {
            "TP": t_tp,
            "FP": t_fp,
            "precision": round(t_prec, 4),
            "recall_contribution": round(t_rec_share, 4),
            "total_positives": n_pos,
            "total_negatives": n_neg,
        }

    return {
        "overall": overall,
        "waterfall_attribution": attribution,
        "details": details,
    }


def _evaluate_isolated_tiers(
    samples: list[EvalSample],
    *,
    semantic_threshold: float,
) -> dict[str, dict[str, Any]]:
    """Run each v3 tier standalone to compute per-tier TP/FP/FN/TN/P/R."""
    out: dict[str, dict[str, Any]] = {}
    for tier in v3.ALL_TIERS:
        res = _evaluate_samples(
            samples,
            evaluator="v3",
            semantic_threshold=semantic_threshold,
            enabled_tiers=(tier,),
        )
        out[tier] = res["overall"]
    return out


def build_authored_examples_dataset(bundles: list[LoadedBundle]) -> list[EvalSample]:
    """Benchmark A: all bundles' positive_examples (LOO) vs negative_cases."""
    samples: list[EvalSample] = []
    for bundle in bundles:
        for concept in bundle.content.get("required_concepts") or []:
            cid = str(concept.get("id") or "")
            for pos in concept.get("positive_examples") or []:
                pos_str = str(pos)
                samples.append(
                    EvalSample(
                        kind="POS_EX",
                        polarity=1,
                        bundle_id=bundle.bundle_id,
                        concept_id=cid,
                        answer_text=pos_str,
                        bundle_content=bundle.content,
                        exclude_examples={cid: [pos_str]},
                    )
                )
            for neg in concept.get("negative_cases") or []:
                samples.append(
                    EvalSample(
                        kind="NEG_EX",
                        polarity=0,
                        bundle_id=bundle.bundle_id,
                        concept_id=cid,
                        answer_text=str(neg),
                        bundle_content=bundle.content,
                    )
                )
    return samples


def build_split_benchmark(split_bundles: list[LoadedBundle]) -> list[EvalSample]:
    """Benchmark B: all-bundle concept-level evaluation dataset within one split."""
    samples: list[EvalSample] = []
    for idx, bundle in enumerate(split_bundles):
        reqs = bundle.content.get("required_concepts") or []
        ref = str(bundle.content.get("reference_answer") or "").strip()
        if ref:
            for concept in reqs:
                samples.append(
                    EvalSample(
                        kind="REF",
                        polarity=1,
                        bundle_id=bundle.bundle_id,
                        concept_id=str(concept["id"]),
                        answer_text=ref,
                        bundle_content=bundle.content,
                    )
                )
        for ce in bundle.content.get("calibration_examples") or []:
            lvl = ce.get("author_level")
            txt = str(ce.get("answer") or ce.get("answer_text") or "").strip()
            if not txt:
                continue
            if lvl == 3:
                for concept in reqs:
                    samples.append(
                        EvalSample(
                            kind="CAL_L3",
                            polarity=1,
                            bundle_id=bundle.bundle_id,
                            concept_id=str(concept["id"]),
                            answer_text=txt,
                            bundle_content=bundle.content,
                        )
                    )
            elif lvl == 0:
                for concept in reqs:
                    samples.append(
                        EvalSample(
                            kind="CAL_L0",
                            polarity=0,
                            bundle_id=bundle.bundle_id,
                            concept_id=str(concept["id"]),
                            answer_text=txt,
                            bundle_content=bundle.content,
                        )
                    )
        for concept in reqs:
            cid = str(concept["id"])
            for pos in concept.get("positive_examples") or []:
                pos_str = str(pos)
                samples.append(
                    EvalSample(
                        kind="POS_EX",
                        polarity=1,
                        bundle_id=bundle.bundle_id,
                        concept_id=cid,
                        answer_text=pos_str,
                        bundle_content=bundle.content,
                        exclude_examples={cid: [pos_str]},
                    )
                )
            for neg in concept.get("negative_cases") or []:
                samples.append(
                    EvalSample(
                        kind="NEG_EX",
                        polarity=0,
                        bundle_id=bundle.bundle_id,
                        concept_id=cid,
                        answer_text=str(neg),
                        bundle_content=bundle.content,
                    )
                )

        # Within-split cross-domain negative: pick next bundle in split from a different prefix
        my_prefix = bundle.bundle_id.split(".")[0]
        other = None
        for offset in range(1, len(split_bundles)):
            cand = split_bundles[(idx + offset) % len(split_bundles)]
            if cand.bundle_id.split(".")[0] != my_prefix and str(cand.content.get("reference_answer") or "").strip():
                other = cand
                break
        if other is not None:
            other_ref = str(other.content.get("reference_answer") or "")
            for concept in reqs:
                samples.append(
                    EvalSample(
                        kind="XDOM_REF",
                        polarity=0,
                        bundle_id=bundle.bundle_id,
                        concept_id=str(concept["id"]),
                        answer_text=other_ref,
                        bundle_content=bundle.content,
                    )
                )
    return samples


def _sweep_thresholds(samples: list[EvalSample]) -> dict[str, list[dict[str, Any]]]:
    full_sweep: list[dict[str, Any]] = []
    sem_only_sweep: list[dict[str, Any]] = []
    for thr in THRESHOLD_GRID:
        full_res = _evaluate_samples(samples, evaluator="v3", semantic_threshold=thr)
        full_sweep.append({"threshold": thr, **full_res["overall"]})
        sem_res = _evaluate_samples(
            samples,
            evaluator="v3",
            semantic_threshold=thr,
            enabled_tiers=("semantic",),
        )
        sem_only_sweep.append({"threshold": thr, **sem_res["overall"]})
    return {"full_v3": full_sweep, "semantic_only": sem_only_sweep}


def _fmt_metrics_row(label: str, m: dict[str, Any]) -> str:
    return (
        f"| {label} | {m['TP']} | {m['FP']} | {m['FN']} | {m['TN']} | "
        f"{m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} |"
    )


def _summarize_sample_kinds(samples: list[EvalSample]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    n_pos = 0
    n_neg = 0
    for sample in samples:
        by_kind[sample.kind] = by_kind.get(sample.kind, 0) + 1
        if sample.polarity == 1:
            n_pos += 1
        else:
            n_neg += 1
    return {
        "total": len(samples),
        "positives": n_pos,
        "negatives": n_neg,
        "by_kind": dict(sorted(by_kind.items())),
    }


def _split_counts_summary(
    sample_counts: dict[str, Any] | None,
    waterfall: dict[str, dict[str, Any]],
    fallback_total: int,
) -> tuple[int, int, int, str]:
    if isinstance(sample_counts, dict):
        n_pos = int(sample_counts.get("positives", 0))
        n_neg = int(sample_counts.get("negatives", 0))
        total = int(sample_counts.get("total", n_pos + n_neg))
        by_kind = sample_counts.get("by_kind") or {}
        kind_str = ", ".join(f"`{k}`={v}" for k, v in sorted(by_kind.items())) or "n/a"
        return n_pos, n_neg, total, kind_str
    first_attr = next(iter(waterfall.values()), {})
    n_pos = int(first_attr.get("total_positives", 0))
    n_neg = int(first_attr.get("total_negatives", 0))
    return n_pos, n_neg, fallback_total, "n/a"


def _append_waterfall_table(
    lines: list[str],
    heading: str,
    attribution: dict[str, dict[str, Any]],
    *,
    skip_semantic: bool = False,
) -> None:
    lines.extend([
        "",
        f"### {heading}",
        "",
        "| match_type | TP | FP | Precision | Recall Contribution |",
        "|---|---:|---:|---:|---:|",
    ])
    for tier, attr in attribution.items():
        if skip_semantic and tier == "semantic":
            continue
        lines.append(
            f"| `{tier}` | {attr['TP']} | {attr['FP']} | {attr['precision']:.4f} | {attr['recall_contribution']:.4f} |"
        )


def render_markdown_report(payload: dict[str, Any]) -> str:
    inv = payload["inventory"]
    n_bundles_with_examples = len(inv["bundles_with_positive_examples"])
    n_bundles_without_examples = inv["total_bundles"] - n_bundles_with_examples
    auth_pos, auth_neg, auth_tot, auth_kinds = _split_counts_summary(
        payload["benchmark_a"].get("sample_counts"),
        payload["benchmark_a"]["v3"]["waterfall_attribution"],
        payload["benchmark_a"]["n_samples"],
    )
    cal_pos, cal_neg, cal_tot, cal_kinds = _split_counts_summary(
        payload["benchmark_b"].get("calibration_sample_counts"),
        payload["benchmark_b"]["calibration_v3"]["waterfall_attribution"],
        payload["benchmark_b"]["calibration_n_samples"],
    )
    held_pos, held_neg, held_tot, held_kinds = _split_counts_summary(
        payload["benchmark_b"].get("heldout_sample_counts"),
        payload["benchmark_b"]["heldout"]["v3"]["waterfall_attribution"],
        payload["benchmark_b"]["heldout_n_samples"],
    )

    lines: list[str] = [
        "# Concept Evaluator v3 Measurement Report",
        "",
        f"- **Evaluator v3 version**: `{v3.EVALUATOR_VERSION}`",
        f"- **Frozen Semantic Threshold**: `{payload['frozen_threshold']}` (calibrated on Calibration Split prior to Held-Out evaluation)",
        "",
        "## 1. Stored Bundle Inventory (YAML + Read-Only SQLite)",
        "",
        f"- Total bundles with `required_concepts`: **{inv['total_bundles']}** "
        f"(YAML: `{inv['yaml_bundles']}`, SQLite `interviv.db`: `{inv['sqlite_bundles'].get('interviv.db', 0)}`, "
        f"`local-data/interviv-local.sqlite3`: `{inv['sqlite_bundles'].get('local-data/interviv-local.sqlite3', 0)}`)",
        f"- Required concepts: **{inv['required_concepts']}**, Optional concepts: **{inv['optional_concepts']}**",
        f"- Authored concept `positive_examples`: **{inv['positive_examples']}**, `negative_cases`: **{inv['negative_cases']}** "
        f"(populated only in {n_bundles_with_examples} bundles: `{', '.join(inv['bundles_with_positive_examples'])}`; "
        f"remaining {n_bundles_without_examples} bundles have `[]`)",
        f"- Bundle Split (sorted `bundle_id`, alternating index): "
        f"Calibration (`idx % 2 == 0`, n={len(payload['splits']['calibration_bundles'])}) = `{', '.join(payload['splits']['calibration_bundles'])}`; "
        f"Held-Out (`idx % 2 == 1`, n={len(payload['splits']['heldout_bundles'])}) = `{', '.join(payload['splits']['heldout_bundles'])}`",
        "",
        "### Benchmark Sample Provenance & Vocabulary Coupling",
        "",
        f"- **Authored concept examples (`Benchmark A`)**: Only **{n_bundles_with_examples}** stored bundles "
        f"(`{', '.join(inv['bundles_with_positive_examples'])}`) define concept-level `positive_examples` "
        f"(`{inv['positive_examples']}`) and `negative_cases` (`{inv['negative_cases']}`), yielding "
        f"**{auth_pos} pos / {auth_neg} neg** (`{auth_tot}` samples evaluated leave-one-out via `exclude_examples`).",
        f"- **Split benchmarks (`Benchmark B`: Calibration `{cal_pos} pos / {cal_neg} neg`, Held-Out `{held_pos} pos / {held_neg} neg`)**: "
        "Because the remaining stored bundles lack concept-level examples, `build_split_benchmark` pairs every bundle's "
        "`required_concepts` against: `REF` (the bundle's own `reference_answer`, positive), `CAL_L3` (`calibration_examples` with "
        "`author_level == 3`, positive), `POS_EX` (authored `positive_examples` leave-one-out, positive), `CAL_L0` (`calibration_examples` "
        "with `author_level == 0`, negative), `NEG_EX` (authored `negative_cases`, negative), and `XDOM_REF` (cross-domain "
        "`reference_answer` from another bundle in the same split with a different `bundle_id` domain prefix, negative).",
        "- **Vocabulary coupling disclosure**: `REF`, `CAL_L3`, and `CAL_L0` answers are drawn from the same bundle documents that "
        "define each concept's `expected_propositions` and `aliases`. Consequently, Tier 1 (`proposition`) and Tier 2 (`alias`) recall on "
        "`REF`/`CAL_L3` reflects same-document vocabulary coupling rather than independent candidate phrasing; use `XDOM_REF`/`CAL_L0` for "
        "cross-domain false-positive control, `v3 isolated semantic` for Tier 3 generalization, and Benchmark A + independent human-rated "
        "answers for uncoupled recall/precision.",
        "",
        "### Sample-Kind Breakdown by Split",
        "",
        "| Split | Positives | Negatives | Total | Sample-Kind Counts |",
        "|---|---:|---:|---:|---|",
        f"| Benchmark A (All Stored Authored) | {auth_pos} | {auth_neg} | {auth_tot} | {auth_kinds} |",
        f"| Benchmark B — Calibration Split | {cal_pos} | {cal_neg} | {cal_tot} | {cal_kinds} |",
        f"| Benchmark B — Held-Out Split | {held_pos} | {held_neg} | {held_tot} | {held_kinds} |",
        "",
        "## 2. Benchmark A: Authored `positive_examples` (Leave-One-Out) vs `negative_cases` (All Stored Bundles)",
        "",
        "| System / Mode | TP | FP | FN | TN | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        _fmt_metrics_row("v2 (overall)", payload["benchmark_a"]["v2"]["overall"]),
        _fmt_metrics_row(f"v3 @ {payload['frozen_threshold']} (overall)", payload["benchmark_a"]["v3"]["overall"]),
    ]
    for tier, m in payload["benchmark_a"]["v3_isolated_tiers"].items():
        lines.append(_fmt_metrics_row(f"v3 isolated `{tier}`", m))
    _append_waterfall_table(
        lines,
        "Benchmark A Waterfall `match_type` Attribution (v3)",
        payload["benchmark_a"]["v3"]["waterfall_attribution"],
    )
    _append_waterfall_table(
        lines,
        "Benchmark A Waterfall `match_type` Attribution (v2)",
        payload["benchmark_a"]["v2"]["waterfall_attribution"],
        skip_semantic=True,
    )

    lines.extend([
        "",
        "### Benchmark A Per-Sample Audit (4 `POS_EX` Leave-One-Out + 4 `NEG_EX`)",
        "",
        "| Kind | Polarity | Bundle | Concept | v2 (state) | v3 (state / match_type / score) |",
        "|---|---:|---|---|---|---|",
    ])
    for d2, d3 in zip(payload["benchmark_a"]["v2"]["details"], payload["benchmark_a"]["v3"]["details"]):
        v3_desc = f"{d3['state']} / {d3['match_type']}" + (
            f" ({d3['semantic_score']:.4f})" if d3["semantic_score"] is not None else ""
        )
        lines.append(
            f"| {d3['kind']} | {d3['polarity']} | `{d3['bundle_id']}` | `{d3['concept_id']}` | `{d2['state']}` | `{v3_desc}` |"
        )

    lines.extend([
        "",
        f"## 3. Benchmark B — Calibration Split Threshold Sweep (Calibration Split Only; `{cal_pos} pos / {cal_neg} neg`)",
        "",
        "| System / Mode | TP | FP | FN | TN | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        _fmt_metrics_row("v2 (calibration baseline)", payload["benchmark_b"]["calibration_v2"]["overall"]),
        _fmt_metrics_row(f"v3 @ {payload['frozen_threshold']} (calibration frozen)", payload["benchmark_b"]["calibration_v3"]["overall"]),
    ])
    for tier, m in payload["benchmark_b"]["calibration_v3_isolated_tiers"].items():
        lines.append(_fmt_metrics_row(f"v3 isolated `{tier}`", m))
    _append_waterfall_table(
        lines,
        "Calibration Split Waterfall `match_type` Attribution (v3)",
        payload["benchmark_b"]["calibration_v3"]["waterfall_attribution"],
    )
    _append_waterfall_table(
        lines,
        "Calibration Split Waterfall `match_type` Attribution (v2)",
        payload["benchmark_b"]["calibration_v2"]["waterfall_attribution"],
        skip_semantic=True,
    )

    lines.extend([
        "",
        "### Full 3-Tier v3 Sweep (Calibration Split)",
        "",
        "| Threshold | TP | FP | FN | TN | Precision | Recall | F1 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in payload["benchmark_b"]["calibration_sweep"]["full_v3"]:
        lines.append(_fmt_metrics_row(f"{row['threshold']:.2f}", row))

    lines.extend([
        "",
        "### Standalone Tier-3 (`semantic` only) Sweep (Calibration Split)",
        "",
        "| Threshold | TP | FP | FN | TN | Precision | Recall | F1 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in payload["benchmark_b"]["calibration_sweep"]["semantic_only"]:
        lines.append(_fmt_metrics_row(f"{row['threshold']:.2f}", row))

    lines.extend([
        "",
        f"## 4. Benchmark B — Held-Out Split Report (Frozen Threshold = `{payload['frozen_threshold']}`; `{held_pos} pos / {held_neg} neg`)",
        "",
        "| System / Mode | TP | FP | FN | TN | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        _fmt_metrics_row("v2 (overall)", payload["benchmark_b"]["heldout"]["v2"]["overall"]),
        _fmt_metrics_row(f"v3 @ {payload['frozen_threshold']} (overall)", payload["benchmark_b"]["heldout"]["v3"]["overall"]),
    ])
    for tier, m in payload["benchmark_b"]["heldout"]["v3_isolated_tiers"].items():
        lines.append(_fmt_metrics_row(f"v3 isolated `{tier}`", m))
    _append_waterfall_table(
        lines,
        "Held-Out Waterfall `match_type` Attribution (v3)",
        payload["benchmark_b"]["heldout"]["v3"]["waterfall_attribution"],
    )
    _append_waterfall_table(
        lines,
        "Held-Out Waterfall `match_type` Attribution (v2)",
        payload["benchmark_b"]["heldout"]["v2"]["waterfall_attribution"],
        skip_semantic=True,
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure concept_evaluator v2 vs v3.")
    parser.add_argument(
        "--cal-only",
        action="store_true",
        help="Run ONLY Calibration Split inspection & threshold sweep (never inspect Held-Out).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=v3.DEFAULT_SEMANTIC_THRESHOLD,
        help="Frozen semantic threshold to use for final v3 report (default: v3.DEFAULT_SEMANTIC_THRESHOLD).",
    )
    args = parser.parse_args()

    bundles, inventory = load_all_stored_bundles()
    cal_bundles = [b for idx, b in enumerate(bundles) if idx % 2 == 0]
    heldout_bundles = [b for idx, b in enumerate(bundles) if idx % 2 == 1]

    cal_samples = build_split_benchmark(cal_bundles)
    cal_v2 = _evaluate_samples(cal_samples, evaluator="v2")
    cal_sweep = _sweep_thresholds(cal_samples)

    if args.cal_only:
        print("=== INVENTORY ===")
        print(json.dumps(inventory, indent=2))
        print("=== CAL BUNDLES ===", [b.bundle_id for b in cal_bundles])
        print("=== HELD-OUT BUNDLES (UNTOUCHED) ===", [b.bundle_id for b in heldout_bundles])
        print("=== CAL v2 OVERALL ===", cal_v2["overall"])
        print("=== CAL SWEEP: FULL v3 ===")
        for row in cal_sweep["full_v3"]:
            print(row)
        print("=== CAL SWEEP: SEMANTIC ONLY ===")
        for row in cal_sweep["semantic_only"]:
            print(row)
        # Print a sample v2 supported item and any CAL misses/FPs at 0.55/0.60/0.62 for calibration inspection
        cal_v3_60 = _evaluate_samples(cal_samples, evaluator="v3", semantic_threshold=0.60)
        print("=== CAL Non-prop/Non-alias details (v3 @ 0.60) ===")
        for d in cal_v3_60["details"]:
            if d["match_type"] in (None, "semantic") or (d["polarity"] == 0 and d["supported"]):
                print(
                    f"pol={d['polarity']} {d['kind']:8s} {d['bundle_id']}:{d['concept_id']:22s} "
                    f"sup={d['supported']} mt={d['match_type']} sc={d['semantic_score']} txt={d['matched_text']!r}"
                )
        return

    frozen = float(args.threshold)
    authored_samples = build_authored_examples_dataset(bundles)
    heldout_samples = build_split_benchmark(heldout_bundles)

    bench_a_v2 = _evaluate_samples(authored_samples, evaluator="v2")
    bench_a_v3 = _evaluate_samples(authored_samples, evaluator="v3", semantic_threshold=frozen)
    bench_a_iso = _evaluate_isolated_tiers(authored_samples, semantic_threshold=frozen)

    cal_v3_frozen = _evaluate_samples(cal_samples, evaluator="v3", semantic_threshold=frozen)
    cal_iso = _evaluate_isolated_tiers(cal_samples, semantic_threshold=frozen)

    held_v2 = _evaluate_samples(heldout_samples, evaluator="v2")
    held_v3 = _evaluate_samples(heldout_samples, evaluator="v3", semantic_threshold=frozen)
    held_iso = _evaluate_isolated_tiers(heldout_samples, semantic_threshold=frozen)

    payload = {
        "evaluator_version": v3.EVALUATOR_VERSION,
        "frozen_threshold": frozen,
        "inventory": inventory,
        "splits": {
            "calibration_bundles": [b.bundle_id for b in cal_bundles],
            "heldout_bundles": [b.bundle_id for b in heldout_bundles],
        },
        "benchmark_a": {
            "n_samples": len(authored_samples),
            "sample_counts": _summarize_sample_kinds(authored_samples),
            "v2": {"overall": bench_a_v2["overall"], "waterfall_attribution": bench_a_v2["waterfall_attribution"], "details": bench_a_v2["details"]},
            "v3": {"overall": bench_a_v3["overall"], "waterfall_attribution": bench_a_v3["waterfall_attribution"], "details": bench_a_v3["details"]},
            "v3_isolated_tiers": bench_a_iso,
        },
        "benchmark_b": {
            "calibration_n_samples": len(cal_samples),
            "heldout_n_samples": len(heldout_samples),
            "calibration_sample_counts": _summarize_sample_kinds(cal_samples),
            "heldout_sample_counts": _summarize_sample_kinds(heldout_samples),
            "calibration_v2": {"overall": cal_v2["overall"], "waterfall_attribution": cal_v2["waterfall_attribution"]},
            "calibration_v3": {"overall": cal_v3_frozen["overall"], "waterfall_attribution": cal_v3_frozen["waterfall_attribution"]},
            "calibration_v3_isolated_tiers": cal_iso,
            "calibration_sweep": cal_sweep,
            "heldout": {
                "v2": {"overall": held_v2["overall"], "waterfall_attribution": held_v2["waterfall_attribution"]},
                "v3": {"overall": held_v3["overall"], "waterfall_attribution": held_v3["waterfall_attribution"]},
                "v3_isolated_tiers": held_iso,
            },
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_md = render_markdown_report(payload)
    (OUT_DIR / "report.md").write_text(report_md, encoding="utf-8")
    (OUT_DIR / "metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(report_md)


if __name__ == "__main__":
    main()
