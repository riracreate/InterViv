"""Strict-mode live re-run of the question check (Phase 0.A.4).

Runs on a fresh /tmp copy of the demo SQLite DB; the demo DB itself is only
read (sha256 + mtime are checked before and after). NVIDIA writes, Groq
checks, and every blind check uses concept_evaluator_v3 strict mode (v3.1).

Groups:
- part_a: the 5 earlier cells, generated fresh (force=True).
- part_b: the 12 imported drafts (v2), plus python.lists-vs-tuples v3 from
  the repo YAML (0.B), which the demo DB does not hold yet.
- part_c: the 12 auto_checked demo bundles.

Every item runs the real Step E pipeline: first pass = the initial strict
blind check; after retry = Step E.3 (one audit, then demotion or one
regeneration, then a fresh blind answer). Existing content (parts B and C)
is re-checked as a shadow copy ``<bundle_id>.sc`` imported as ``generated``
into the /tmp DB only, so the stored versions are never touched.

Contains no API keys and never prints values from .env.
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

WORKTREE_APP_ROOT = Path(__file__).resolve().parents[1]
if str(WORKTREE_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKTREE_APP_ROOT))

from scripts.live_check_direct_providers import (  # noqa: E402
    DEFAULT_SOURCE_DB,
    PART_A_TARGETS,
    _DispatchCaptureHandler,
    _load_env_without_printing,
    _sha256,
    assert_safe_tmp_db_path,
)

DEFAULT_TMP_DB = Path("/tmp/interviv-demo-strict-check.sqlite3")
DEFAULT_TMP_JOURNAL = Path("/tmp/interviv-strict-check-limits.json")
DEFAULT_RESULTS_PATH = Path("/tmp/live_check_results_strict.json")
SHADOW_SUFFIX = ".sc"
PER_ITEM_MAX_REQUESTS = 10


def concept_rows(eval_res: dict[str, Any] | None) -> list[dict[str, Any]]:
    """One row per required concept: how (or whether) it was matched."""
    rows: list[dict[str, Any]] = []
    for c in (eval_res or {}).get("concepts") or []:
        state = c.get("state")
        if state == "supported":
            match = str(c.get("match_type"))
        elif state == "mentioned":
            match = "alias-mentioned"
        else:
            match = f"none ({state})"
        rows.append({
            "concept_id": c.get("concept_id"),
            "state": state,
            "match": match,
            "semantic_score": c.get("semantic_score"),
        })
    return rows


def shadow_doc(version_doc: dict[str, Any]) -> dict[str, Any]:
    content = copy.deepcopy(version_doc["content_json"])
    original = f"{version_doc['bundle_id']}@{version_doc['version']}"
    content["bundle_id"] = f"{version_doc['bundle_id']}{SHADOW_SUFFIX}{version_doc['version']}"
    attribution = dict(version_doc.get("attribution_json") or {})
    for key in ("auto_check", "auto_check_ran"):
        attribution.pop(key, None)
    attribution["strict_recheck_of"] = original
    return {
        **content,
        "version": 1,
        "source": version_doc["source"],
        "author": version_doc.get("author_id") or "unknown",
        "attribution": attribution,
    }


def run(
    *,
    source_db: Path,
    tmp_db: Path,
    tmp_journal: Path,
    results_path: Path,
    only: set[str] | None = None,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    import shutil

    safe_tmp_db = assert_safe_tmp_db_path(tmp_db, real_demo_db=source_db)
    safe_journal = assert_safe_tmp_db_path(tmp_journal, real_demo_db=source_db)
    src = Path(source_db).expanduser().resolve()
    before_sha, before_mtime = _sha256(src), src.stat().st_mtime_ns
    shutil.copy2(src, safe_tmp_db)
    safe_journal.unlink(missing_ok=True)
    safe_journal.with_suffix(".lock").unlink(missing_ok=True)
    rejected_audit = Path("/tmp/strict_check_rejected.jsonl")
    demoted_audit = Path("/tmp/strict_check_demoted.jsonl")
    rejected_audit.unlink(missing_ok=True)
    demoted_audit.unlink(missing_ok=True)

    _load_env_without_printing(WORKTREE_APP_ROOT / ".env")
    db_url = f"sqlite:////{str(safe_tmp_db).lstrip('/')}"
    if not db_url.startswith(("sqlite:////tmp/", "sqlite:////private/tmp/")):
        raise RuntimeError(f"Refusing non-/tmp DATABASE_URL: {db_url}")
    os.environ.update({
        "DATABASE_URL": db_url,
        "AI_INTERVIEW_ROUTING_ENABLED": "1",
        "INTERVIEW_DIRECT_PROVIDERS_ENABLED": "1",
        "INTERVIEW_CONTENT_PROVIDER": "nvidia",
        "INTERVIEW_CHECK_PROVIDER": "groq",
        "LLM_LIVE_FETCH": "1",
        "LLM_LIVE_CONSUMERS": "questions",
        "INTERVIEW_LLM_STATE_PATH": str(safe_journal),
    })

    from backend.config import get_settings
    get_settings.cache_clear()
    from modules import bundle_generator, bundle_store, interview_llm, question_bundles, role_skills

    assert bundle_generator.BLIND_CHECK_STRICT is True

    capture = _DispatchCaptureHandler()
    interview_llm.LOGGER.addHandler(capture)
    interview_llm.LOGGER.setLevel(logging.INFO)
    interview_llm._router.cache_clear()

    # Record every evaluator call so first-pass concept rows survive a retry.
    evals: list[dict[str, Any]] = []
    original_score = bundle_generator._score_with_concept_evaluator

    def recording_score(**kwargs):
        res = original_score(**kwargs)
        evals.append({
            "bundle_id": (kwargs.get("bundle_content") or {}).get("bundle_id"),
            "content_hash": kwargs.get("bundle_content_hash"),
            "eval": res,
        })
        return res

    bundle_generator._score_with_concept_evaluator = recording_score

    def call_with_rate_wait(fn):
        for attempt in range(6):
            try:
                return fn()
            except interview_llm.DispatchDeferred as exc:
                if exc.reason in {"groq_rate_limit", "nvidia_minute", "rpm", "content_pacing", "concurrency"} and exc.retry_at and attempt < 5:
                    wait_s = max(1.0, min(65.0, float(exc.retry_at) - time.time() + 1.0))
                    print(f"  rate-limit wait ({exc.reason}): {wait_s:.1f}s", flush=True)
                    time.sleep(wait_s)
                    continue
                raise

    router_budget = interview_llm.get_router().budget
    run_tag = str(int(time.time()))

    def run_item(group: str, label: str, fn) -> dict[str, Any] | None:
        if labels and not any(part in label for part in labels):
            return None
        with router_budget._state() as (account_state, _):
            account_state["models"].clear()
        ev_start, eval_start = len(capture.events), len(evals)
        t0 = time.monotonic()
        item: dict[str, Any] = {"group": group, "label": label}
        try:
            with interview_llm.batch_scope(f"strict-{run_tag}-{group}-{label}", max_requests=PER_ITEM_MAX_REQUESTS):
                res = call_with_rate_wait(fn)
            item_evals = evals[eval_start:]
            first_eval = item_evals[0]["eval"] if item_evals else None
            final_eval = res.get("blind_eval")
            passed = res["status"] == "auto_checked"
            retried = bool(res.get("retried")) or bool(res.get("demoted_concept"))
            item.update({
                "bundle_id": res["bundle_id"],
                "final_version": res["version"],
                "status": res["status"],
                "passed_first_pass": bool(passed and not retried),
                "passed_after_retry": bool(passed and retried),
                "repair": (
                    "demotion" if res.get("demoted_concept")
                    else "regeneration" if res.get("retried") else None
                ),
                "demoted_concept": res.get("demoted_concept"),
                "evaluator_version": (final_eval or {}).get("evaluator_version"),
                "verdict_evaluator_version": ((res["bundle"].get("attribution_json") or {}).get("auto_check") or {}).get("evaluator_version"),
                "first_pass_coverage": (first_eval or {}).get("coverage"),
                "first_pass_concepts": concept_rows(first_eval),
                "final_coverage": (final_eval or {}).get("coverage"),
                "final_concepts": concept_rows(final_eval),
                "question": res["bundle"]["content_json"].get("question"),
                "final_content": res["bundle"]["content_json"],
                "audit": res.get("audit"),
            })
        except Exception as exc:  # report and continue
            item_evals = evals[eval_start:]
            first_eval = item_evals[0]["eval"] if item_evals else None
            item.update({"status": "error", "error": f"{type(exc).__name__}: {exc}",
                         "passed_first_pass": False, "passed_after_retry": False,
                         "first_pass_coverage": (first_eval or {}).get("coverage"),
                         "first_pass_concepts": concept_rows(first_eval)})
        item["elapsed_s"] = round(time.monotonic() - t0, 2)
        item["dispatch"] = [
            {k: e.get(k) for k in ("purpose", "provider", "returned_model", "message") if e.get(k) is not None}
            for e in capture.events[ev_start:]
        ]
        fp = "PASS" if item.get("passed_first_pass") else ("retry-PASS" if item.get("passed_after_retry") else item["status"])
        print(f"{group} {label}: {fp} first={item.get('first_pass_coverage')} final={item.get('final_coverage')} {item['elapsed_s']}s", flush=True)
        if item.get("error"):
            print(f"  error: {item['error'][:600]}", flush=True)
        return item

    def recheck_existing(version_doc: dict[str, Any]):
        content = version_doc["content_json"]

        def _run():
            stored = bundle_store.import_bundle(
                shadow_doc(version_doc),
                actor_id="strict_recheck",
                initial_status="generated",
                audit_reason=f"Phase 0.A.4 strict re-check of {version_doc['bundle_id']}@{version_doc['version']}",
            )["version"]
            return _step_e(stored)

        canonical_skill, _ = role_skills.resolve_skill_identity(str(content["skill"]), register=True)
        gen_provider, gen_model = bundle_generator.resolve_generation_provider_and_model()
        check_provider, check_model = bundle_generator.resolve_checker_provider_and_model()
        _step_e = lambda stored: bundle_generator._run_step_e_for_version(
            stored_version=stored,
            canonical_skill=canonical_skill,
            canonical_topic=str(content.get("topic") or canonical_skill),
            difficulty=str(version_doc.get("difficulty") or content.get("difficulty")),
            role=None,
            gen_provider=gen_provider,
            gen_model=gen_model,
            check_provider=check_provider,
            check_model=check_model,
            allow_live=True,
            cache_hit=False,
            rejected_audit_path=rejected_audit,
            demoted_audit_path=demoted_audit,
        )
        return _run

    results: dict[str, list[dict[str, Any]]] = {"part_a": [], "part_b": [], "part_c": []}
    # Snapshot before Part A adds new auto_checked bundles to the /tmp copy.
    source_auto_checked = list(bundle_store.list_versions(status="auto_checked"))

    if not only or "a" in only:
        for skill, diff, topic in PART_A_TARGETS:
            label = bundle_generator.build_bundle_id_for_cell(skill, topic, diff)
            results["part_a"].append(run_item("A", label, lambda s=skill, t=topic, d=diff: bundle_generator.generate_and_check_bundle(
                skill=s, topic=t, difficulty=d, allow_live=True, force=True,
                rejected_audit_path=rejected_audit, demoted_audit_path=demoted_audit,
            )))

    if not only or "b" in only:
        draft_ids = sorted({
            question_bundles.validate_bundle_doc(doc)["content"]["bundle_id"]
            for _, doc in question_bundles.iter_bundle_files()
        })
        for bid in draft_ids:
            v2 = bundle_store.get_version(bid, 2)
            results["part_b"].append(run_item("B", f"{bid}@v2", recheck_existing(v2)))
        # 0.B: lists-vs-tuples v3 from the repo YAML (not yet in the demo DB).
        for _, doc in question_bundles.iter_bundle_files():
            if doc["bundle_id"] == "python.lists-vs-tuples" and doc["version"] == 3:
                v3 = bundle_store.import_bundle(doc, actor_id="strict_recheck", audit_reason="0.B v3 into /tmp copy")["version"]
                results["part_b"].append(run_item("B", "python.lists-vs-tuples@v3 (0.B)", recheck_existing(v3)))

    if not only or "c" in only:
        latest: dict[str, dict[str, Any]] = {}
        for v in source_auto_checked:
            if SHADOW_SUFFIX in v["bundle_id"]:
                continue
            if v["bundle_id"] not in latest or v["version"] > latest[v["bundle_id"]]["version"]:
                latest[v["bundle_id"]] = v
        for bid in sorted(latest):
            v = latest[bid]
            results["part_c"].append(run_item("C", f"{bid}@v{v['version']}", recheck_existing(v)))

    results = {k: [i for i in v if i is not None] for k, v in results.items()}
    bundle_generator._score_with_concept_evaluator = original_score
    after_sha, after_mtime = _sha256(src), src.stat().st_mtime_ns
    if (before_sha, before_mtime) != (after_sha, after_mtime):
        raise RuntimeError("Demo DB was unexpectedly modified during the strict check.")

    def counts(items):
        return {
            "total": len(items),
            "first_pass": sum(1 for i in items if i.get("passed_first_pass")),
            "after_retry": sum(1 for i in items if i.get("passed_after_retry")),
            "passed": sum(1 for i in items if i.get("status") == "auto_checked"),
            "errors": sum(1 for i in items if i.get("status") == "error"),
        }

    payload = {
        "demo_db_sha256_before": before_sha,
        "demo_db_sha256_after": after_sha,
        "demo_db_untouched": True,
        "tmp_db": str(safe_tmp_db),
        "summary": {k: counts(v) for k, v in results.items()},
        **results,
        "budget_journal": json.loads(safe_journal.read_text(encoding="utf-8")) if safe_journal.exists() else None,
    }
    Path(results_path).write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print("SUMMARY:", json.dumps(payload["summary"]), flush=True)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE_DB)
    parser.add_argument("--tmp-db", type=Path, default=DEFAULT_TMP_DB)
    parser.add_argument("--tmp-journal", type=Path, default=DEFAULT_TMP_JOURNAL)
    parser.add_argument("--out", type=Path, default=DEFAULT_RESULTS_PATH)
    parser.add_argument("--only", default="", help="subset of a,b,c")
    parser.add_argument("--labels", default="", help="comma-separated label substrings to run")
    args = parser.parse_args(argv)
    run(
        source_db=args.source_db,
        tmp_db=args.tmp_db,
        tmp_journal=args.tmp_journal,
        results_path=args.out,
        only={p.strip() for p in args.only.split(",") if p.strip()} or None,
        labels=[p.strip() for p in args.labels.split(",") if p.strip()] or None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
