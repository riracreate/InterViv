"""Live direct-provider check script (NVIDIA writer + Groq checker) on a /tmp DB copy.

Safety invariants:
- Refuses to run against any database path outside /tmp (specifically blocks ~/interviv-demo/interviv-demo.sqlite3).
- Contains zero API keys and never prints secret values from .env.
- Intended only for manual verification on an isolated /tmp copy of the demo SQLite DB.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

WORKTREE_APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DB = Path.home() / "interviv-demo" / "interviv-demo.sqlite3"
DEFAULT_TMP_DB = Path("/tmp/interviv-demo-live-check.sqlite3")
DEFAULT_TMP_JOURNAL = Path("/tmp/interviv-live-check-limits.json")
DEFAULT_RESULTS_PATH = Path("/tmp/live_check_results_v2.json")

PART_A_TARGETS: tuple[tuple[str, str, str], ...] = (
    ("Statistics", "easy", "mean vs median with outliers"),
    ("SQL", "medium", "join fan-out"),
    ("Product Metrics", "medium", "guardrail metrics"),
    ("Statistics", "medium", "Simpson's paradox"),
    ("SQL", "easy", "LEFT JOIN vs INNER JOIN"),
)


def assert_safe_tmp_db_path(db_path: Path | str, *, real_demo_db: Path | None = None) -> Path:
    """Refuse any DB path that is not strictly inside /tmp (or matches the real demo DB)."""
    candidate = Path(db_path).expanduser()
    resolved = candidate.resolve(strict=False)
    demo_resolved = (real_demo_db or DEFAULT_SOURCE_DB).expanduser().resolve(strict=False)
    if resolved == demo_resolved or "interviv-demo" in resolved.parts[:-1]:
        raise RuntimeError(f"Refusing to run against protected demo DB path: {candidate}")
    tmp_roots = (Path("/tmp").resolve(), Path(tempfile.gettempdir()).resolve())
    in_tmp = any(resolved == root or root in resolved.parents for root in tmp_roots)
    # Require explicit /tmp (never workspace or home directory even if TEMPDIR were customized)
    if not str(resolved).startswith(("/tmp/", "/private/tmp/")) or not in_tmp:
        raise RuntimeError(f"Target DB path must be inside /tmp: {candidate} (resolved={resolved})")
    return resolved


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_env_without_printing(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        os.environ[k.strip()] = v.strip().strip("\"'")


class _DispatchCaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.events: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if msg.startswith(("interview_llm_dispatch ", "interview_llm_writer_fallback ")):
            self.events.append({
                "message": msg,
                "provider": getattr(record, "provider", None),
                "requested_model": getattr(record, "requested_model", None),
                "returned_model": getattr(record, "returned_model", None),
                "purpose": getattr(record, "purpose", None),
                "reasoning_tokens": getattr(record, "reasoning_tokens", None),
                "from_provider": getattr(record, "from_provider", None),
                "from_model": getattr(record, "from_model", None),
                "to_provider": getattr(record, "to_provider", None),
                "to_model": getattr(record, "to_model", None),
                "reason": getattr(record, "reason", None),
            })


def run_live_check(
    *,
    source_db: Path = DEFAULT_SOURCE_DB,
    tmp_db: Path = DEFAULT_TMP_DB,
    tmp_journal: Path = DEFAULT_TMP_JOURNAL,
    results_path: Path = DEFAULT_RESULTS_PATH,
) -> dict[str, Any]:
    safe_tmp_db = assert_safe_tmp_db_path(tmp_db, real_demo_db=source_db)
    safe_journal = assert_safe_tmp_db_path(tmp_journal, real_demo_db=source_db)
    src = Path(source_db).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source demo DB not found: {src}")

    before_sha = _sha256(src)
    before_mtime = src.stat().st_mtime_ns
    shutil.copy2(src, safe_tmp_db)
    safe_journal.unlink(missing_ok=True)
    safe_journal.with_suffix(".lock").unlink(missing_ok=True)
    Path("/tmp/live_check_rejected_v2.jsonl").unlink(missing_ok=True)
    Path("/tmp/live_check_demoted_v2.jsonl").unlink(missing_ok=True)

    _load_env_without_printing(WORKTREE_APP_ROOT / ".env")
    db_url = f"sqlite:////{str(safe_tmp_db).lstrip('/')}"
    if not db_url.startswith(("sqlite:////tmp/", "sqlite:////private/tmp/")):
        raise RuntimeError(f"Refusing non-/tmp DATABASE_URL: {db_url}")

    os.environ["DATABASE_URL"] = db_url
    os.environ["AI_INTERVIEW_ROUTING_ENABLED"] = "1"
    os.environ["INTERVIEW_DIRECT_PROVIDERS_ENABLED"] = "1"
    os.environ["INTERVIEW_CONTENT_PROVIDER"] = "nvidia"
    os.environ["INTERVIEW_CHECK_PROVIDER"] = "groq"
    os.environ["LLM_LIVE_FETCH"] = "1"
    os.environ["LLM_LIVE_CONSUMERS"] = "questions"
    os.environ["INTERVIEW_LLM_STATE_PATH"] = str(safe_journal)

    if str(WORKTREE_APP_ROOT) not in sys.path:
        sys.path.insert(0, str(WORKTREE_APP_ROOT))
    from backend.config import get_settings
    get_settings.cache_clear()

    from modules import bundle_generator, bundle_store, interview_llm, llm_usage, question_bundles

    capture = _DispatchCaptureHandler()
    interview_llm.LOGGER.addHandler(capture)
    interview_llm.LOGGER.setLevel(logging.INFO)
    interview_llm._router.cache_clear()

    schema_probe = interview_llm.check_nvidia_json_schema_support()
    print("SCHEMA_PROBE:", json.dumps(schema_probe))

    def _call_with_rate_wait(fn):
        for attempt in range(4):
            try:
                return fn()
            except interview_llm.DispatchDeferred as exc:
                if exc.reason in {"groq_rate_limit", "nvidia_minute", "rpm"} and exc.retry_at and attempt < 3:
                    wait_s = max(1.0, min(65.0, float(exc.retry_at) - time.time() + 1.0))
                    print(f"Rate-limit wait ({exc.reason}): sleeping {wait_s:.1f}s")
                    time.sleep(wait_s)
                    continue
                raise

    part_a: list[dict[str, Any]] = []
    router_budget = interview_llm.get_router().budget
    with interview_llm.batch_scope("live-check-part-a", max_requests=40):
        for skill, diff, topic in PART_A_TARGETS:
            with router_budget._state() as (account_state, _):
                account_state["models"].clear()
            ev_start = len(capture.events)
            t0 = time.monotonic()
            bid = bundle_generator.build_bundle_id_for_cell(skill, topic, diff)
            try:
                res = _call_with_rate_wait(
                    lambda s=skill, t=topic, d=diff: bundle_generator.generate_and_check_bundle(
                        skill=s,
                        topic=t,
                        difficulty=d,
                        allow_live=True,
                        force=True,
                        rejected_audit_path="/tmp/live_check_rejected_v2.jsonl",
                        demoted_audit_path="/tmp/live_check_demoted_v2.jsonl",
                    )
                )
                elapsed_s = round(time.monotonic() - t0, 2)
                events = capture.events[ev_start:]
                gen_calls = sum(1 for e in events if e.get("purpose") == "bundle_generation")
                regen_calls = sum(1 for e in events if e.get("purpose") == "bundle_regeneration")
                passed = res["status"] == "auto_checked"
                needed_retry = (
                    gen_calls > 1
                    or regen_calls > 0
                    or bool(res.get("retried"))
                    or bool(res.get("demoted_concept"))
                )
                usage_after = llm_usage.list_usage_events(limit=500)
                bid = res["bundle_id"]
                b_usage = [
                    {k: str(v) if k == "created_at" else v for k, v in u.items()}
                    for u in reversed(usage_after)
                    if u.get("bundle_id") == bid
                ]
                blind_text = ""
                if res.get("blind_eval") is None:
                    blind_text = ""
                item = {
                    "skill": skill,
                    "difficulty": diff,
                    "topic": topic,
                    "bundle_id": bid,
                    "version": res["version"],
                    "status": res["status"],
                    "passed_first_pass": bool(passed and not needed_retry),
                    "passed_after_retry": bool(passed and needed_retry),
                    "step_e1_retries": max(0, gen_calls - 1),
                    "step_e3_retried": bool(res.get("retried")),
                    "demoted_concept": res.get("demoted_concept"),
                    "elapsed_s": elapsed_s,
                    "bundle_content": res["bundle"]["content_json"],
                    "attribution": res["bundle"]["attribution_json"],
                    "blind_eval": res.get("blind_eval"),
                    "audit": res.get("audit"),
                    "dispatch_events": events,
                    "usage_events": b_usage,
                }
                part_a.append(item)
                print(
                    f"PART_A {bid} v{res['version']}: status={res['status']} "
                    f"first_pass={item['passed_first_pass']} after_retry={item['passed_after_retry']} "
                    f"elapsed={elapsed_s}s"
                )
            except Exception as exc:
                elapsed_s = round(time.monotonic() - t0, 2)
                events = capture.events[ev_start:]
                usage_after = llm_usage.list_usage_events(limit=500)
                b_usage = [
                    {k: str(v) if k == "created_at" else v for k, v in u.items()}
                    for u in reversed(usage_after)
                    if u.get("bundle_id") == bid
                ]
                part_a.append({
                    "skill": skill,
                    "difficulty": diff,
                    "topic": topic,
                    "bundle_id": bid,
                    "version": None,
                    "status": "error",
                    "passed_first_pass": False,
                    "passed_after_retry": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "elapsed_s": elapsed_s,
                    "dispatch_events": events,
                    "usage_events": b_usage,
                })
                print(f"PART_A {bid} ERROR: {type(exc).__name__}: {exc} elapsed={elapsed_s}s")

    bundle_ids = sorted({
        question_bundles.validate_bundle_doc(doc)["content"]["bundle_id"]
        for _, doc in question_bundles.iter_bundle_files()
    })
    check_provider, check_model = bundle_generator.resolve_checker_provider_and_model()
    part_b: list[dict[str, Any]] = []
    with interview_llm.batch_scope("live-check-part-b-12-drafts", max_requests=40):
        for bid in bundle_ids:
            v2 = bundle_store.get_version(bid, 2)
            c = v2["content_json"]
            ev_start = len(capture.events)
            t0 = time.monotonic()
            blind_answer, eval_res, passed, hits = _call_with_rate_wait(
                lambda v=v2, skill=str(c["skill"]), diff=str(v2["difficulty"]), b=bid: bundle_generator._evaluate_blind_answer(
                    stored_version=v,
                    canonical_skill=skill,
                    difficulty=diff,
                    check_provider=check_provider,
                    check_model=check_model,
                    bundle_id=b,
                    role=None,
                    allow_live=True,
                )
            )
            audit_diag = None
            if not passed:
                audit_raw = _call_with_rate_wait(
                    lambda content=c, ans=blind_answer, er=eval_res, b=bid: bundle_generator._call_bundle_llm(
                        purpose="bundle_check_audit",
                        provider=check_provider,
                        model=check_model,
                        messages=bundle_generator._build_audit_messages(
                            content_json=content,
                            blind_answer=ans,
                            eval_res=er,
                        ),
                        expect_json=True,
                        max_tokens=bundle_generator.DEFAULT_AUDIT_MAX_TOKENS,
                        temperature=0.15,
                        timeout_s=bundle_generator.DEFAULT_BLIND_CHECK_TIMEOUT_S,
                        bundle_id=b,
                        role=None,
                        allow_live=True,
                    )
                )
                try:
                    audit_diag = bundle_generator._parse_json_object(audit_raw)
                except bundle_generator.BundleGenerationError:
                    audit_diag = {"raw": audit_raw[:400]}

            elapsed_s = round(time.monotonic() - t0, 2)
            cov = eval_res.get("coverage") or {}
            missed = [
                str(item.get("concept_id"))
                for item in (eval_res.get("concepts") or [])
                if item.get("state") != "supported"
            ]
            usage_after = llm_usage.list_usage_events(limit=500)
            b_usage = [
                {k: str(v) if k == "created_at" else v for k, v in u.items()}
                for u in reversed(usage_after)
                if u.get("bundle_id") == bid
            ]
            part_b.append({
                "bundle_id": bid,
                "version": 2,
                "db_status": v2["status"],
                "passed": passed,
                "k_supported": cov.get("k_supported"),
                "n_required": cov.get("n_required"),
                "missed_concepts": missed,
                "misconception_hits": hits,
                "blind_answer_words": len(blind_answer.split()),
                "blind_answer": blind_answer,
                "audit_diag": audit_diag,
                "elapsed_s": elapsed_s,
                "dispatch_events": capture.events[ev_start:],
                "usage_events": b_usage,
            })
            print(
                f"PART_B {bid} v2: passed={passed} cov={cov.get('k_supported')}/{cov.get('n_required')} "
                f"missed={missed} elapsed={elapsed_s}s"
            )

    journal = json.loads(safe_journal.read_text(encoding="utf-8"))
    after_sha = _sha256(src)
    after_mtime = src.stat().st_mtime_ns
    if before_sha != after_sha or before_mtime != after_mtime:
        raise RuntimeError("Demo DB was unexpectedly modified during live check.")

    payload = {
        "demo_db_untouched": True,
        "demo_db_sha256": after_sha,
        "schema_probe": schema_probe,
        "summary": {
            "part_a_total": len(part_a),
            "part_a_first_pass": sum(1 for item in part_a if item.get("passed_first_pass")),
            "part_a_after_retry": sum(1 for item in part_a if item.get("passed_after_retry")),
            "part_a_total_passed": sum(1 for item in part_a if item.get("status") == "auto_checked"),
            "part_b_total": len(part_b),
            "part_b_passed": sum(1 for item in part_b if item.get("passed")),
        },
        "part_a": part_a,
        "part_b": part_b,
        "budget_journal": journal,
    }
    Path(results_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("SUMMARY:", json.dumps(payload["summary"]))
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run live direct-provider check against a /tmp DB copy.")
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE_DB)
    parser.add_argument("--tmp-db", type=Path, default=DEFAULT_TMP_DB)
    parser.add_argument("--tmp-journal", type=Path, default=DEFAULT_TMP_JOURNAL)
    parser.add_argument("--out", type=Path, default=DEFAULT_RESULTS_PATH)
    args = parser.parse_args(argv)
    run_live_check(
        source_db=args.source_db,
        tmp_db=args.tmp_db,
        tmp_journal=args.tmp_journal,
        results_path=args.out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
