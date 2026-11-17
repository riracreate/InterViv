"""CLI for role-aware YAML-v2 bundle pre-generation and Step E blind verification.

Usage:
    .venv/bin/python scripts/pregenerate_bundles.py --dry-run
    .venv/bin/python scripts/pregenerate_bundles.py \
        --roles "Backend Engineer,ML Engineer,Frontend Engineer" \
        --difficulties easy,medium,hard \
        --max-bundles 30 \
        --output-dir data/generated_bundles \
        --live

Exports generated bundles strictly under ``--output-dir`` (default:
``data/generated_bundles``) and NEVER modifies canonical files under
``data/question_bundles``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import uuid
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import get_settings  # noqa: E402
from backend.runtime_env import apply_runtime_env  # noqa: E402
from modules import (  # noqa: E402
    bundle_generator,
    bundle_store,
    interview_llm,
    llm_outbound_gate,
    llm_usage,
    role_skills,
)
from modules.llm_errors import LLMCreditExhaustedError  # noqa: E402
from modules.interview_llm_budget import DispatchDeferred  # noqa: E402
from modules.question_bundles import (  # noqa: E402
    DIFFICULTIES,
    safe_bundle_relative_path,
    validate_generated_bundle_doc,
)

DEFAULT_ROLES = [
    "Backend Engineer",
    "Data Analyst",
    "Product Marketing Manager",
]

_DRY_RUN_PREVIEW_PROFILES: dict[str, list[dict[str, Any]]] = {
    "backend engineer": [
        {"name": "Python", "topics": ["Concurrency", "Asyncio", "Memory Management"], "weight": 1.0},
        {"name": "SQL", "topics": ["Indexing", "Transactions", "Query Optimization"], "weight": 0.95},
        {"name": "API Design", "topics": ["Idempotency", "Rate Limiting", "Pagination"], "weight": 0.9},
        {"name": "Docker", "topics": ["Multi-Stage Builds", "Layer Caching", "Networking"], "weight": 0.8},
    ],
    "data analyst": [
        {"name": "SQL", "topics": ["Window Functions", "CTEs & Joins", "Cohort Retention"], "weight": 1.0},
        {"name": "Experimentation", "topics": ["A/B Testing", "Sample Size", "Metric Selection"], "weight": 0.95},
        {"name": "Data Modeling", "topics": ["Star Schema", "Data Quality", "Attribution"], "weight": 0.9},
        {"name": "Visualization", "topics": ["Executive Dashboards", "Funnel Diagnostics", "Storytelling"], "weight": 0.85},
    ],
    "product marketing manager": [
        {"name": "Product Positioning", "topics": ["Value Proposition", "Category Narrative", "Messaging"], "weight": 1.0},
        {"name": "Go-To-Market Strategy", "topics": ["Launch Tiers", "Sales Enablement", "Channel Mix"], "weight": 0.95},
        {"name": "Competitive Intelligence", "topics": ["Win-Loss Analysis", "Battlecards", "Differentiation"], "weight": 0.9},
        {"name": "Customer Segmentation", "topics": ["ICP Definition", "Buyer Personas", "Adoption Metrics"], "weight": 0.85},
    ],
}


@contextmanager
def _temporarily_set_live_fetch(allow_live: bool | None):
    if allow_live is None:
        yield
        return
    prev = os.environ.get("LLM_LIVE_FETCH")
    os.environ["LLM_LIVE_FETCH"] = "1" if allow_live else "0"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("LLM_LIVE_FETCH", None)
        else:
            os.environ["LLM_LIVE_FETCH"] = prev


_PROTECTED_LOCAL_DB_PATH = ROOT / "local-data" / "interviv-local.sqlite3"


def _protected_local_db_path() -> Path:
    return Path(_PROTECTED_LOCAL_DB_PATH).expanduser().resolve(strict=False)


def _resolve_sqlite_db_path(database_url: str | None) -> Path | None:
    """Resolve a SQLite DATABASE_URL to a canonical filesystem path, or None."""
    raw = (database_url or "").strip()
    if not raw:
        return None
    try:
        from sqlalchemy.engine import make_url

        parsed = make_url(raw)
        if parsed.get_backend_name() != "sqlite":
            return None
        db_str = (parsed.database or "").strip()
    except Exception:
        if not raw.lower().startswith("sqlite"):
            return None
        sep = raw.find(":///")
        if sep < 0:
            return None
        db_str = raw[sep + 4 :].split("?", 1)[0].strip()

    if not db_str or db_str == ":memory:":
        return None
    if db_str.startswith("file:"):
        from urllib.parse import unquote, urlparse

        db_str = unquote(urlparse(db_str).path or db_str.removeprefix("file:"))
    if not db_str or db_str == ":memory:":
        return None
    return Path(db_str).expanduser().resolve(strict=False)


def protected_local_db_error() -> str | None:
    """Unconditional refusal when DATABASE_URL resolves to the protected local DB."""
    url = get_settings().database_url
    resolved = _resolve_sqlite_db_path(url)
    protected = _protected_local_db_path()
    matched = False
    if resolved is not None:
        if resolved == protected:
            matched = True
        elif resolved.exists() and protected.exists():
            try:
                matched = os.path.samefile(resolved, protected)
            except OSError:
                matched = False
    if matched:
        return (
            f"Refusing to run: DATABASE_URL resolves to the protected local "
            f"database ({protected}). Point DATABASE_URL to a separate SQLite "
            f"file (for example sqlite:///<path>/interviv.db)."
        )
    return None


def describe_database_target() -> str:
    """Human-readable write target for the currently resolved database."""
    url = get_settings().database_url
    if not url:
        return "in-memory (DATABASE_URL unset; nothing will persist)"
    if url.startswith("sqlite:///"):
        return url.removeprefix("sqlite:///")
    if url.startswith("sqlite://"):
        return url
    try:
        from sqlalchemy.engine import make_url

        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "configured DATABASE_URL"


def live_on_memory_db_error() -> str | None:
    """Refusal message for a --live run that would write to volatile memory.

    Simulated runs (tests, offline doubles) may opt in explicitly with
    INTERVIV_ALLOW_LIVE_ON_MEMORY_DB=1; the real pilot command sets no
    such variable and is refused before any LLM call is made.
    """
    if get_settings().database_url:
        return None
    allow = (os.getenv("INTERVIV_ALLOW_LIVE_ON_MEMORY_DB") or "").strip().lower()
    if allow in {"1", "true", "yes", "on"}:
        return None
    return (
        "Refusing --live run: DATABASE_URL is unset, so bundles, role-skill "
        "cache rows, and LLM usage would be written to the in-memory "
        "database and lost when the process exits. Set DATABASE_URL to a "
        "persistent database (for example sqlite:///<path>/interviv.db) "
        "and rerun. INTERVIV_USE_MEMORY_DB does not select a database; "
        "only DATABASE_URL does."
    )


def _preview_skill_specs_for_dry_run(role: str) -> list[dict[str, Any]]:
    norm = " ".join(str(role or "").strip().lower().split())
    for key, specs in _DRY_RUN_PREVIEW_PROFILES.items():
        if key in norm or norm in key:
            return [dict(s) for s in specs]
    label = " ".join(str(role or "General").strip().split()) or "General"
    return [
        {"name": f"{label} Fundamentals", "topics": ["Core Principles", "Architecture & Design", "Failure Modes"], "weight": 1.0},
        {"name": f"{label} Execution", "topics": ["Prioritization", "Metrics & KPIs", "Tradeoff Analysis"], "weight": 0.9},
        {"name": f"{label} Collaboration", "topics": ["Stakeholder Alignment", "Review Workflows", "Risk Mitigation"], "weight": 0.8},
        {"name": f"{label} Optimization", "topics": ["Bottleneck Diagnosis", "Scaling Practices", "Quality Assurance"], "weight": 0.7},
    ]


def _parse_csv_list(values: list[str] | str | None, default: list[str]) -> list[str]:
    if values is None:
        return list(default)
    items: list[str] = []
    raw_list = [values] if isinstance(values, str) else list(values)
    for entry in raw_list:
        for part in str(entry or "").split(","):
            cleaned = " ".join(part.strip().split())
            if cleaned and cleaned not in items:
                items.append(cleaned)
    return items or list(default)


def _cached_role_profile(role: str) -> dict | None:
    """Read a prepared generic role profile; a content batch cannot extract it."""
    clean = " ".join(role_skills.sanitize_untrusted_text(role, max_chars=role_skills.MAX_ROLE_CHARS).split())
    key, _ = role_skills._compute_cache_key(clean, "")
    return role_skills._cache_get(key)


def plan_bundle_cells(
    *,
    roles: list[str],
    difficulties: list[str],
    max_bundles: int,
    dry_run: bool = False,
    cached_only: bool = False,
) -> list[dict[str, str]]:
    """Expand roles -> weighted skills/topics x difficulties balanced up to max_bundles."""
    per_role_cells: list[list[dict[str, str]]] = []
    with _temporarily_set_live_fetch(False if dry_run else None):
        for role in roles:
            extracted = _cached_role_profile(role) if cached_only else role_skills.extract_role_skills(role=role, max_skills=6)
            if extracted is None:
                raise ValueError("Routed content batches require cached generic role profiles; prepare paid extraction separately.")
            skill_specs = list(extracted.get("skill_specs") or [])
            if not skill_specs and extracted.get("skills"):
                skill_specs = [
                    {"name": s, "topics": [s], "weight": 1.0}
                    for s in (extracted.get("skills") or [])
                ]
            if dry_run and (extracted.get("offline_uncached") or not skill_specs):
                # Preview-only synthesis in memory; never writes to role_skill_cache.
                skill_specs = _preview_skill_specs_for_dry_run(role)
            cells_for_role: list[dict[str, str]] = []
            # Build cells iterating topics x difficulties so roles get broad skill coverage
            max_topics = max((len(sp.get("topics") or []) for sp in skill_specs), default=1)
            for t_idx in range(max(1, max_topics)):
                for sp in skill_specs:
                    skill_name = str(sp.get("name") or "").strip()
                    if not skill_name:
                        continue
                    topics = list(sp.get("topics") or [skill_name])
                    if t_idx >= len(topics):
                        continue
                    topic = str(topics[t_idx]).strip() or skill_name
                    for diff in difficulties:
                        cells_for_role.append(
                            {
                                "role": role,
                                "skill": skill_name,
                                "topic": topic,
                                "difficulty": diff,
                            }
                        )
            per_role_cells.append(cells_for_role)

    planned: list[dict[str, str]] = []
    seen_keys: set[tuple[str, str, str]] = set()
    cursors = [0 for _ in per_role_cells]
    while len(planned) < max_bundles:
        progressed = False
        for idx, role_cells in enumerate(per_role_cells):
            while cursors[idx] < len(role_cells):
                cand = role_cells[cursors[idx]]
                cursors[idx] += 1
                canon_skill, _ = role_skills.resolve_skill_identity(
                    cand["skill"], register=False
                )
                key = (
                    canon_skill.lower(),
                    cand["topic"].strip().lower(),
                    cand["difficulty"].lower(),
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                planned.append(cand)
                progressed = True
                break
            if len(planned) >= max_bundles:
                break
        if not progressed:
            break
    return planned


def export_bundle_yaml(version_doc: dict[str, Any], output_dir: Path) -> Path:
    """Write a generated bundle version as YAML under ``output_dir`` safely."""
    protected_dir = (ROOT / "data" / "question_bundles").resolve()
    target_root = output_dir.resolve()
    if target_root == protected_dir or protected_dir in target_root.parents:
        raise ValueError(
            f"Refusing to write generated bundles into canonical directory {protected_dir}"
        )

    content = dict(version_doc.get("content_json") or {})
    skill = str(content.get("skill") or "general")
    bundle_id = str(version_doc.get("bundle_id") or content.get("bundle_id") or "")
    rel_path = safe_bundle_relative_path(skill, bundle_id)
    dest = (target_root / rel_path).resolve()
    if target_root not in dest.parents and dest != target_root:
        raise ValueError(f"Unsafe YAML export path escaped output_dir: {dest}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    export_doc = {
        **content,
        "version": int(version_doc.get("version") or content.get("version") or 1),
        "source": str(version_doc.get("source") or content.get("source") or "llm_draft"),
        "author": str(version_doc.get("author_id") or content.get("author") or "llm"),
        "attribution": dict(
            version_doc.get("attribution_json")
            or content.get("attribution")
            or {}
        ),
    }
    export_doc.pop("status", None)
    export_doc.pop("content_hash", None)
    validate_generated_bundle_doc(export_doc)
    dest.write_text(
        yaml.safe_dump(export_doc, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return dest


def _count_uncached_roles(roles: list[str]) -> int:
    """Count roles that are not yet cached in role_skills (without hitting live LLMs)."""
    if role_skills._LLM_OVERRIDE is not None:
        return 0
    uncached = 0
    with _temporarily_set_live_fetch(False):
        for role in roles:
            extracted = role_skills.extract_role_skills(role=role, max_skills=6)
            if extracted.get("offline_uncached"):
                uncached += 1
    return uncached


def _classify_cached_cells(
    planned: list[dict[str, str]], *, force: bool = False
) -> tuple[int, int]:
    """Return (already_cached_count, remaining_count) without mutating bundle attribution."""
    if force:
        return 0, len(planned)
    cached_count = 0
    for cell in planned:
        canon_skill, _ = role_skills.resolve_skill_identity(
            cell["skill"], register=False
        )
        cached = bundle_store.find_cached_bundle(
            skill=canon_skill,
            topic=cell["topic"],
            difficulty=cell["difficulty"],
            role=None,
        )
        if cached is not None:
            attr = cached.get("attribution_json") or {}
            if cached.get("status") in {"reviewed", "auto_checked"} or attr.get("auto_check_ran"):
                cached_count += 1
    return cached_count, max(0, len(planned) - cached_count)


def _format_estimate_lines(est: dict[str, Any]) -> list[str]:
    remaining_usd = est.get("remaining_usd")
    rem_str = f"${remaining_usd:.6f}" if remaining_usd is not None else "unknown (no key/credit cap)"
    lines = [
        (
            f"Estimate: planned={est.get('planned_cells', 0)} "
            f"cached={est.get('cached_cells', 0)} "
            f"pending_check={est.get('pending_check_cells', 0)} "
            f"uncached={est.get('uncached_cells', 0)} "
            f"uncached_roles={est.get('uncached_roles', 0)} "
            f"est_calls={est.get('estimated_calls', 0)}"
        ),
        (
            f"  models: gen={est.get('gen_provider')}:{est.get('gen_model')} "
            f"| check={est.get('check_provider')}:{est.get('check_model')}"
        ),
    ]
    for m_name, p_info in (est.get("pricing") or {}).items():
        p_m = float(p_info.get("prompt_per_token", 0.0)) * 1_000_000
        c_m = float(p_info.get("completion_per_token", 0.0)) * 1_000_000
        lines.append(f"  pricing [{m_name}]: prompt=${p_m:.4f}/1M tokens, completion=${c_m:.4f}/1M tokens")
    lines.append(
        f"  cost: expected=${float(est.get('expected_cost_usd', 0.0)):.6f} "
        f"max_ceiling=${float(est.get('max_cost_usd', 0.0)):.6f} "
        f"| remaining_credit={rem_str} "
        f"| fits={bool(est.get('fits'))}"
    )
    return lines


REVIEW_CSV_COLUMNS = (
    "bundle_id",
    "version",
    "status",
    "role",
    "skill",
    "topic",
    "difficulty",
    "question",
    "reference_answer",
    "required_concepts",
    "optional_concepts",
    "followups",
    "calibration_good_words",
    "calibration_poor_words",
    "length_bias_usable",
    "demoted_concept",
    "reference correct (y/n)",
    "question clear (y/n)",
    "difficulty right (y/n)",
    "concepts sensible (y/n)",
    "notes",
)


def _format_concepts_cell(concepts: Any) -> str:
    if not isinstance(concepts, list):
        return ""
    parts: list[str] = []
    for entry in concepts:
        if isinstance(entry, dict):
            cid = str(entry.get("id") or "").strip()
            desc = str(entry.get("descriptor") or entry.get("description") or "").strip()
            if cid and desc:
                parts.append(f"{cid}: {desc}")
            elif cid or desc:
                parts.append(cid or desc)
        elif entry is not None and str(entry).strip():
            parts.append(str(entry).strip())
    return " | ".join(parts)


def _format_followups_cell(followups: Any) -> str:
    if not isinstance(followups, list):
        return ""
    parts: list[str] = []
    for entry in followups:
        if isinstance(entry, dict):
            target = str(entry.get("targets_concept") or "").strip()
            prompt = str(entry.get("prompt") or "").strip()
            if target and prompt:
                parts.append(f"[{target}] {prompt}")
            elif prompt or target:
                parts.append(prompt or target)
        elif entry is not None and str(entry).strip():
            parts.append(str(entry).strip())
    return " | ".join(parts)


def _extract_csv_row(item: dict[str, Any]) -> dict[str, Any]:
    bundle_obj = item.get("bundle") if isinstance(item.get("bundle"), dict) else None
    if bundle_obj is not None:
        content = bundle_obj.get("content_json") or {}
        attr = bundle_obj.get("attribution_json") or {}
        bundle_id = item.get("bundle_id") or bundle_obj.get("bundle_id") or content.get("bundle_id") or ""
        version = item.get("version") or bundle_obj.get("version") or content.get("version") or ""
        status = item.get("status") or bundle_obj.get("status") or ""
    elif isinstance(item.get("content_json"), dict):
        content = item.get("content_json") or {}
        attr = item.get("attribution_json") or {}
        bundle_id = item.get("bundle_id") or content.get("bundle_id") or ""
        version = item.get("version") or content.get("version") or ""
        status = item.get("status") or ""
    else:
        content = item
        attr = item.get("attribution") if isinstance(item.get("attribution"), dict) else {}
        bundle_id = item.get("bundle_id") or ""
        version = item.get("version") or ""
        status = item.get("status") or ""

    role_val = str(item.get("role") or "").strip()
    if not role_val:
        role_val = ", ".join(
            str(r).strip() for r in (attr.get("roles") or []) if str(r).strip()
        )

    good_words: int | str = ""
    poor_words: int | str = ""
    usable_flags: list[bool] = []
    for ex in content.get("calibration_examples") or []:
        if not isinstance(ex, dict):
            continue
        ans = str(ex.get("answer") or "").strip()
        wc = ex.get("word_count")
        if not isinstance(wc, int) or isinstance(wc, bool):
            wc = len(ans.split()) if ans else 0
        lvl = ex.get("author_level")
        band = str(ex.get("expected_band") or "").strip()
        if not isinstance(lvl, bool) and lvl == 3 and band == "Good":
            if good_words == "":
                good_words = wc
            flag = ex.get("length_bias_usable")
            if flag is None:
                flag = 0 < wc <= 35
            usable_flags.append(bool(flag))
        elif not isinstance(lvl, bool) and lvl == 0 and band == "Poor":
            if poor_words == "":
                poor_words = wc
            flag = ex.get("length_bias_usable")
            if flag is None:
                flag = wc >= 90
            usable_flags.append(bool(flag))

    length_bias_usable: bool | str = (
        all(usable_flags)
        if len(usable_flags) >= 2
        else (usable_flags[0] if usable_flags else "")
    )
    demoted_concept = (
        item.get("demoted_concept")
        or attr.get("demoted_concept")
        or (attr.get("auto_check") or {}).get("demoted_concept")
        or ""
    )

    return {
        "bundle_id": bundle_id,
        "version": version,
        "status": status,
        "role": role_val,
        "skill": item.get("skill") or content.get("skill") or "",
        "topic": item.get("topic") or content.get("topic") or "",
        "difficulty": item.get("difficulty") or content.get("difficulty") or "",
        "question": content.get("question") or "",
        "reference_answer": content.get("reference_answer") or "",
        "required_concepts": _format_concepts_cell(content.get("required_concepts")),
        "optional_concepts": _format_concepts_cell(content.get("optional_concepts")),
        "followups": _format_followups_cell(content.get("followups")),
        "calibration_good_words": good_words,
        "calibration_poor_words": poor_words,
        "length_bias_usable": length_bias_usable,
        "demoted_concept": demoted_concept,
        "reference correct (y/n)": "",
        "question clear (y/n)": "",
        "difficulty right (y/n)": "",
        "concepts sensible (y/n)": "",
        "notes": "",
    }


def export_bundles_review_csv(
    results_or_bundles: list[dict[str, Any]],
    csv_path: Path | str,
) -> Path:
    """Export generated/stored bundles into a human-review CSV with blank review columns."""
    out_path = Path(csv_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(REVIEW_CSV_COLUMNS))
        writer.writeheader()
        for item in results_or_bundles or []:
            if isinstance(item, dict):
                writer.writerow(_extract_csv_row(item))
    return out_path


def _usage_delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    by_model_before = before.get("by_model") or {}
    by_model_after = after.get("by_model") or {}
    by_model_delta: dict[str, dict[str, int]] = {}
    for model_name, after_stats in by_model_after.items():
        prev_stats = by_model_before.get(model_name) or {}
        cnt = max(0, int(after_stats.get("count", 0)) - int(prev_stats.get("count", 0)))
        pt = max(0, int(after_stats.get("prompt_tokens", 0)) - int(prev_stats.get("prompt_tokens", 0)))
        ct = max(0, int(after_stats.get("completion_tokens", 0)) - int(prev_stats.get("completion_tokens", 0)))
        tt = max(0, int(after_stats.get("total_tokens", 0)) - int(prev_stats.get("total_tokens", 0)))
        if cnt > 0 or tt > 0 or pt > 0 or ct > 0:
            by_model_delta[model_name] = {
                "count": cnt,
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "total_tokens": tt,
            }
    return {
        "count": max(0, int(after.get("count", 0)) - int(before.get("count", 0))),
        "prompt_tokens": max(0, int(after.get("prompt_tokens", 0)) - int(before.get("prompt_tokens", 0))),
        "completion_tokens": max(0, int(after.get("completion_tokens", 0)) - int(before.get("completion_tokens", 0))),
        "total_tokens": max(0, int(after.get("total_tokens", 0)) - int(before.get("total_tokens", 0))),
        "by_model": by_model_delta,
    }


def _lookup_model_pricing(
    model_name: str, pricing_by_model: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    if model_name in pricing_by_model:
        return pricing_by_model[model_name]
    cf = model_name.casefold()
    for key, val in pricing_by_model.items():
        if key.casefold() == cf:
            return val
    return None


def _compute_actual_cost(
    usage_delta: dict[str, Any], pricing_by_model: dict[str, dict[str, Any]]
) -> float | None:
    if not pricing_by_model:
        return None
    by_model = usage_delta.get("by_model") or {}
    if not by_model:
        return 0.0 if int(usage_delta.get("total_tokens") or 0) == 0 else None
    total_usd = 0.0
    priced_any = False
    for model_name, stats in by_model.items():
        p = _lookup_model_pricing(model_name, pricing_by_model)
        if p is None:
            if int(stats.get("total_tokens") or 0) > 0:
                return None
            continue
        priced_any = True
        pt = int(stats.get("prompt_tokens") or 0)
        ct = int(stats.get("completion_tokens") or 0)
        tt = int(stats.get("total_tokens") or 0)
        req_cost = int(stats.get("count") or 0) * float(p.get("request_cost", 0.0))
        if pt == 0 and ct == 0 and tt > 0:
            total_usd += tt * float(p.get("prompt_per_token", 0.0)) + req_cost
        else:
            total_usd += (
                pt * float(p.get("prompt_per_token", 0.0))
                + ct * float(p.get("completion_per_token", 0.0))
                + req_cost
            )
    return round(total_usd, 6) if priced_any else None


def _compute_pilot_metrics(
    results: list[dict[str, Any]],
    usage_delta: dict[str, Any],
    pricing_by_model: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    evaluated_results = [
        r for r in results if not r.get("cache_hit") or r.get("blind_eval") is not None
    ]
    evaluated_count = len(evaluated_results)
    first_time_pass_count = sum(
        1
        for r in evaluated_results
        if r.get("step_e_passed") and not r.get("retried") and not r.get("demoted_concept")
    )
    first_time_pass_rate = (
        round(first_time_pass_count / evaluated_count, 4) if evaluated_count else 0.0
    )
    demoted_count = sum(1 for r in results if r.get("demoted_concept"))
    demotion_rate = round(demoted_count / evaluated_count, 4) if evaluated_count else 0.0

    rejected_reasons: list[dict[str, Any]] = []
    tier_counts: dict[str, int] = {"proposition": 0, "alias": 0, "semantic": 0}
    for r in results:
        if r.get("status") == "rejected":
            bundle_doc = r.get("bundle") if isinstance(r.get("bundle"), dict) else {}
            auto_check = (bundle_doc.get("attribution_json") or {}).get("auto_check") or {}
            rejected_reasons.append(
                {
                    "bundle_id": r.get("bundle_id"),
                    "version": r.get("version"),
                    "reason": str(auto_check.get("reason") or "rejected"),
                    "missed_concepts": list(auto_check.get("missed_concepts") or []),
                    "misconception_hits": list(auto_check.get("misconception_hits") or []),
                    "issue_type": (r.get("audit") or {}).get("issue_type")
                    if isinstance(r.get("audit"), dict)
                    else None,
                }
            )
        blind_eval = r.get("blind_eval")
        if isinstance(blind_eval, dict):
            for concept in blind_eval.get("concepts") or []:
                if isinstance(concept, dict):
                    mt = concept.get("match_type")
                    if mt in tier_counts:
                        tier_counts[mt] += 1

    denom = evaluated_count if evaluated_count > 0 else len(results)
    total_tokens = int(usage_delta.get("total_tokens") or 0)
    tokens_per_bundle = round(total_tokens / denom, 2) if denom else 0.0
    actual_cost_usd = _compute_actual_cost(usage_delta, pricing_by_model)
    cost_per_bundle_usd = (
        round(actual_cost_usd / denom, 6)
        if (actual_cost_usd is not None and denom)
        else (0.0 if actual_cost_usd == 0.0 else None)
    )
    return {
        "evaluated": evaluated_count,
        "first_time_pass_count": first_time_pass_count,
        "first_time_pass_rate": first_time_pass_rate,
        "demotion_rate": demotion_rate,
        "rejected_reasons": rejected_reasons,
        "blind_match_tier_counts": tier_counts,
        "actual_tokens": {
            "prompt_tokens": int(usage_delta.get("prompt_tokens") or 0),
            "completion_tokens": int(usage_delta.get("completion_tokens") or 0),
            "total_tokens": total_tokens,
            "per_bundle": tokens_per_bundle,
        },
        "actual_cost_usd": actual_cost_usd,
        "cost_per_bundle_usd": cost_per_bundle_usd,
    }


def run_pregeneration(
    *,
    roles: list[str] | None = None,
    difficulties: list[str] | None = None,
    max_bundles: int = 30,
    dry_run: bool = False,
    estimate_only: bool = False,
    export_yaml: bool = True,
    output_dir: Path | None = None,
    allow_live: bool | None = None,
    force: bool = False,
    resume: bool = False,
    rejected_audit_path: Path | str | None = None,
    demoted_audit_path: Path | str | None = None,
    export_review_csv: Path | str | None = None,
    pricing_by_model: dict[str, dict[str, Any]] | None = None,
    max_requests: int | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    """Plan, generate/verify (unless dry_run/estimate_only), export, and summarize bundles."""
    role_list = _parse_csv_list(roles, DEFAULT_ROLES)
    diff_list = [
        bundle_generator.normalize_difficulty(d)
        for d in _parse_csv_list(difficulties, list(DIFFICULTIES))
    ]
    out_dir = output_dir or (ROOT / "data" / "generated_bundles")

    report: dict[str, Any] = {
        "dry_run": dry_run,
        "estimate_only": estimate_only,
        "resume": resume,
        "planned_count": 0,
        "planned": [],
        "cache_hits": 0,
        "already_cached": 0,
        "remaining_before_run": 0,
        "generated": 0,
        "auto_checked": 0,
        "reviewed": 0,
        "rejected": 0,
        "retried": 0,
        "demoted": 0,
        "evaluated": 0,
        "first_time_pass_count": 0,
        "first_time_pass_rate": 0.0,
        "demotion_rate": 0.0,
        "rejected_reasons": [],
        "blind_match_tier_counts": {"proposition": 0, "alias": 0, "semantic": 0},
        "actual_tokens": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "per_bundle": 0.0,
        },
        "actual_cost_usd": None,
        "cost_per_bundle_usd": None,
        "review_csv_path": None,
        "aborted": False,
        "abort_reason": None,
        "abort_error": None,
        "credit_info": {},
        "estimate": None,
        "completed_cells": 0,
        "remaining_cells": [],
        "errors": [],
        "exported_paths": [],
        "results": [],
    }

    protected_error = protected_local_db_error()
    if protected_error is not None:
        report["aborted"] = True
        report["abort_reason"] = "protected_local_database"
        report["abort_error"] = protected_error
        report["errors"].append({"error": protected_error})
        report["usage"] = {
            "count": 0,
            "ok_count": 0,
            "error_count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        return report

    if dry_run or estimate_only:
        with _temporarily_set_live_fetch(False):
            planned = plan_bundle_cells(
                roles=role_list,
                difficulties=diff_list,
                max_bundles=max(1, int(max_bundles)),
                dry_run=True,
            )
            report["planned_count"] = len(planned)
            report["planned"] = planned
            cached_count, remaining_count = _classify_cached_cells(planned, force=force)
            report["cache_hits"] = cached_count
            report["already_cached"] = cached_count
            report["remaining_before_run"] = remaining_count

            if estimate_only:
                uncached_roles = _count_uncached_roles(role_list)
                try:
                    est = bundle_generator.estimate_pregeneration_cost(
                        planned_cells=planned,
                        force=force,
                        uncached_role_count=uncached_roles,
                    )
                    report["estimate"] = est
                    report["cache_hits"] = est["cached_cells"]
                    report["already_cached"] = est["cached_cells"]
                    report["remaining_before_run"] = (
                        est["uncached_cells"] + est["pending_check_cells"]
                    )
                except Exception as exc:
                    report["aborted"] = True
                    report["abort_reason"] = "preflight_error"
                    report["abort_error"] = str(exc)
                    report["errors"].append({"error": str(exc)})
            report["usage"] = llm_usage.summarize_usage()
            return report

    routed = interview_llm.enabled()
    if routed:
        if type(max_requests) is not int or max_requests < 1:
            report.update(aborted=True, abort_reason="routing_budget_required",
                          abort_error="Routed pre-generation requires explicit --max-requests.")
            return report
        if any(_cached_role_profile(role) is None for role in role_list):
            report.update(aborted=True, abort_reason="cached_roles_required",
                          abort_error="Content-only batches require cached generic roles; paid role extraction is separate.")
            return report
        batch_id = batch_id or f"pregenerate:{uuid.uuid4().hex}"
        report.update(routing_batch_id=batch_id, routing_max_requests=max_requests)
    elif max_requests is not None or batch_id is not None:
        report.update(aborted=True, abort_reason="routing_disabled",
                      abort_error="--max-requests/--batch-id require AI_INTERVIEW_ROUTING_ENABLED=1.")
        return report

    if allow_live is True:
        db_error = live_on_memory_db_error()
        if db_error is not None:
            report["aborted"] = True
            report["abort_reason"] = "in_memory_database"
            report["abort_error"] = db_error
            report["errors"].append({"error": db_error})
            report["usage"] = llm_usage.summarize_usage()
            return report

    preflight_est: dict[str, Any] | None = None
    gen_provider, gen_model = bundle_generator.resolve_generation_provider_and_model()
    check_provider, check_model = bundle_generator.resolve_checker_provider_and_model()
    run_openrouter_preflight = (
        allow_live is True
        and bundle_generator._LLM_OVERRIDE is None
        and (gen_provider == "openrouter" or check_provider == "openrouter")
    )

    if run_openrouter_preflight:
        preview_planned = plan_bundle_cells(
            roles=role_list,
            difficulties=diff_list,
            max_bundles=max(1, int(max_bundles)),
            dry_run=True,
        )
        uncached_roles = 0 if routed else _count_uncached_roles(role_list)
        try:
            preflight_est = bundle_generator.estimate_pregeneration_cost(
                planned_cells=preview_planned,
                force=force,
                uncached_role_count=uncached_roles,
                gen_provider=gen_provider,
                gen_model=gen_model,
                check_provider=check_provider,
                check_model=check_model,
            )
        except Exception as exc:
            report["planned_count"] = len(preview_planned)
            report["planned"] = preview_planned
            report["aborted"] = True
            report["abort_reason"] = "preflight_error"
            report["abort_error"] = f"OpenRouter pre-flight check failed: {exc}"
            report["remaining_cells"] = list(preview_planned)
            report["errors"].append({"error": report["abort_error"]})
            report["usage"] = llm_usage.summarize_usage()
            return report

        report["estimate"] = preflight_est
        report["planned_count"] = len(preview_planned)
        report["planned"] = preview_planned
        report["already_cached"] = preflight_est["cached_cells"]
        report["remaining_before_run"] = (
            preflight_est["uncached_cells"] + preflight_est["pending_check_cells"]
        )
        if not preflight_est["fits"]:
            rem_usd = preflight_est.get("remaining_usd")
            max_usd = preflight_est.get("max_cost_usd", 0.0)
            report["aborted"] = True
            report["abort_reason"] = "insufficient_credits"
            report["abort_error"] = (
                f"Refusing --live run: estimated max cost ${max_usd:.6f} exceeds "
                f"remaining OpenRouter credit ${rem_usd:.6f}."
            )
            report["remaining_cells"] = list(preview_planned)
            report["errors"].append({"error": report["abort_error"]})
            report["usage"] = llm_usage.summarize_usage()
            return report

    usage_before = llm_usage.summarize_usage()

    def _finalize_metrics() -> None:
        usage_after = llm_usage.summarize_usage()
        report["usage"] = usage_after
        usage_delta = _usage_delta(usage_before, usage_after)
        pricing_map: dict[str, dict[str, Any]] = dict((preflight_est or {}).get("pricing") or {})
        if pricing_by_model:
            pricing_map.update(pricing_by_model)
        if (
            usage_delta["total_tokens"] > 0
            and bundle_generator._LLM_OVERRIDE is None
            and (
                allow_live is True
                or (allow_live is None and llm_outbound_gate.llm_live_fetch_enabled())
            )
            and (gen_provider == "openrouter" or check_provider == "openrouter")
        ):
            for m_name in (usage_delta.get("by_model") or {}):
                if _lookup_model_pricing(m_name, pricing_map) is None:
                    try:
                        pricing_map[m_name] = bundle_generator.fetch_openrouter_model_pricing(m_name)
                    except Exception:
                        pass
        report.update(_compute_pilot_metrics(report["results"], usage_delta, pricing_map))
        if export_review_csv is not None:
            written = export_bundles_review_csv(report["results"], Path(export_review_csv))
            report["review_csv_path"] = str(written)

    scope = interview_llm.batch_scope(batch_id, max_requests=max_requests) if routed else nullcontext()
    with _temporarily_set_live_fetch(allow_live), scope:
        try:
            planned = plan_bundle_cells(
                roles=role_list,
                difficulties=diff_list,
                max_bundles=max(1, int(max_bundles)),
                dry_run=False,
                cached_only=routed,
            )
        except LLMCreditExhaustedError as exc:
            report["aborted"] = True
            report["abort_reason"] = "credit_exhausted"
            report["abort_error"] = str(exc)
            report["credit_info"] = dict(getattr(exc, "credit_info", {}) or {})
            report["errors"].append({"error": str(exc)})
            _finalize_metrics()
            return report

        report["planned_count"] = len(planned)
        report["planned"] = planned
        cached_before, remaining_before = _classify_cached_cells(planned, force=force)
        report["already_cached"] = cached_before
        report["remaining_before_run"] = remaining_before

        if run_openrouter_preflight and preflight_est is not None:
            preflight_est = bundle_generator.estimate_pregeneration_cost(
                planned_cells=planned,
                force=force,
                uncached_role_count=0,
                gen_provider=gen_provider,
                gen_model=gen_model,
                check_provider=check_provider,
                check_model=check_model,
                credits_info=preflight_est.get("credits"),
                pricing_by_model=preflight_est.get("pricing"),
            )
            report["estimate"] = preflight_est
            if not preflight_est["fits"]:
                rem_usd = preflight_est.get("remaining_usd")
                max_usd = preflight_est.get("max_cost_usd", 0.0)
                report["aborted"] = True
                report["abort_reason"] = "insufficient_credits"
                report["abort_error"] = (
                    f"Refusing --live run after skill planning: estimated max cost "
                    f"${max_usd:.6f} exceeds remaining OpenRouter credit ${rem_usd:.6f}."
                )
                report["remaining_cells"] = list(planned)
                report["errors"].append({"error": report["abort_error"]})
                _finalize_metrics()
                return report

        for idx, cell in enumerate(planned):
            try:
                res = bundle_generator.generate_and_check_bundle(
                    skill=cell["skill"],
                    topic=cell["topic"],
                    difficulty=cell["difficulty"],
                    role=cell["role"],
                    allow_live=allow_live,
                    force=force,
                    rejected_audit_path=rejected_audit_path,
                    demoted_audit_path=demoted_audit_path,
                )
            except LLMCreditExhaustedError as exc:
                report["aborted"] = True
                report["abort_reason"] = "credit_exhausted"
                report["abort_error"] = str(exc)
                report["credit_info"] = dict(getattr(exc, "credit_info", {}) or {})
                report["remaining_cells"] = planned[idx:]
                report["errors"].append({**cell, "error": str(exc)})
                break
            except Exception as exc:
                deferred = exc
                while deferred is not None and not isinstance(deferred, DispatchDeferred):
                    deferred = deferred.__cause__
                if routed and isinstance(deferred, DispatchDeferred):
                    report.update(aborted=True, abort_reason=deferred.reason, abort_error=str(deferred),
                                  retry_at=deferred.retry_at, remaining_cells=planned[idx:])
                    report["errors"].append({**cell, "error": str(deferred)})
                    break
                report["errors"].append({**cell, "error": str(exc)})
                continue

            report["results"].append(res)
            report["completed_cells"] = len(report["results"])
            if res.get("cache_hit"):
                report["cache_hits"] += 1
            else:
                report["generated"] += 1
            if res.get("retried"):
                report["retried"] += 1
            if res.get("demoted_concept"):
                report["demoted"] += 1
            st = res.get("status")
            if st == "auto_checked":
                report["auto_checked"] += 1
            elif st == "reviewed":
                report["reviewed"] += 1
            elif st == "rejected":
                report["rejected"] += 1

            bundle_doc = res.get("bundle")
            if (
                export_yaml
                and isinstance(bundle_doc, dict)
                and st in {"reviewed", "auto_checked"}
            ):
                exported = export_bundle_yaml(bundle_doc, out_dir)
                report["exported_paths"].append(str(exported))

    _finalize_metrics()
    return report


def main(argv: list[str] | None = None) -> int:
    apply_runtime_env()
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--roles",
        action="append",
        default=None,
        help="Comma-separated or repeated target roles.",
    )
    parser.add_argument(
        "--difficulties",
        default="easy,medium,hard",
        help="Comma-separated difficulties (easy,medium,hard).",
    )
    parser.add_argument(
        "--max-bundles",
        type=int,
        default=30,
        help="Maximum number of bundles to process (default: 30).",
    )
    parser.add_argument("--max-requests", type=int, default=None,
                        help="Required routed content-only completion-attempt budget, including retries/checks.")
    parser.add_argument("--batch-id", default=None,
                        help="Reuse this ID to resume a durable routed budget; its max-requests cannot be increased.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan cells and report cache status without calling any LLM.",
    )
    parser.add_argument(
        "--estimate",
        action="store_true",
        help="Check OpenRouter credits/pricing and print estimated cost without running.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Report cached vs remaining cells and resume incomplete work.",
    )
    parser.add_argument(
        "--export-yaml",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Export auto_checked/reviewed bundles as YAML under --output-dir.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "data" / "generated_bundles"),
        help="Directory for exported YAML bundles (default: data/generated_bundles).",
    )
    parser.add_argument(
        "--rejected-audit-path",
        default=None,
        help="Optional override path for rejected bundles audit JSONL.",
    )
    parser.add_argument(
        "--demoted-audit-path",
        default=None,
        help="Optional override path for demoted concepts audit JSONL.",
    )
    parser.add_argument(
        "--export-review-csv",
        default=None,
        help="Optional path to write a human-review CSV for generated bundles.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Explicitly allow outbound LLM calls regardless of LLM_LIVE_FETCH.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if a cached bundle already exists.",
    )
    args = parser.parse_args(argv)

    if args.live and not args.dry_run and not args.estimate:
        print(f"Database: {describe_database_target()}")

    report = run_pregeneration(
        roles=args.roles,
        difficulties=[args.difficulties],
        max_bundles=args.max_bundles,
        dry_run=args.dry_run,
        estimate_only=args.estimate,
        export_yaml=args.export_yaml,
        output_dir=Path(args.output_dir),
        allow_live=True if args.live else None,
        force=args.force,
        resume=args.resume,
        rejected_audit_path=args.rejected_audit_path,
        demoted_audit_path=args.demoted_audit_path,
        export_review_csv=args.export_review_csv,
        max_requests=args.max_requests,
        batch_id=args.batch_id,
    )

    if report.get("abort_reason") == "protected_local_database":
        if not (args.live and not args.dry_run and not args.estimate):
            print(f"Database: {describe_database_target()}")
        print(f"ABORTED (protected_local_database): {report.get('abort_error')}")
        return 1

    if args.estimate:
        if report.get("estimate"):
            for line in _format_estimate_lines(report["estimate"]):
                print(line)
            if not report["estimate"].get("fits"):
                print("Status: INSUFFICIENT CREDITS (a --live run would refuse to start).")
            else:
                print("Status: SUFFICIENT CREDITS.")
        else:
            print(f"Estimate failed: {report.get('abort_error') or 'unknown error'}")
        return 1 if report.get("aborted") else 0

    if args.dry_run:
        print(f"DRY RUN: {report['planned_count']} planned cells ({report['cache_hits']} cached)")
        for idx, cell in enumerate(report["planned"], start=1):
            print(
                f"  {idx:02d}. role={cell['role']} | skill={cell['skill']} "
                f"| topic={cell['topic']} | difficulty={cell['difficulty']}"
            )
        return 0

    if args.resume:
        print(
            f"Resume status: {report['already_cached']}/{report['planned_count']} "
            f"already cached; {report['remaining_before_run']} remaining before run."
        )

    if report.get("estimate"):
        for line in _format_estimate_lines(report["estimate"]):
            print(line)

    if report.get("aborted"):
        reason = report.get("abort_reason")
        print(f"ABORTED ({reason}): {report.get('abort_error')}")
        if report.get("credit_info"):
            print(f"Credit info: {json.dumps(report['credit_info'], sort_keys=True)}")
        print(
            f"Progress: completed={report['completed_cells']}/{report['planned_count']} "
            f"(cache_hits={report['cache_hits']}, generated={report['generated']}, "
            f"remaining={len(report['remaining_cells'])})"
        )
        if reason == "credit_exhausted":
            print(
                "How to resume: completed bundles are cached in bundle_store; "
                "add credits and rerun the exact same command to skip cached cells and continue."
            )
        elif reason == "insufficient_credits":
            print(
                "How to proceed: add OpenRouter credits, reduce --max-bundles, "
                "or run with --estimate to inspect costs without running."
            )

    print(
        f"Summary: planned={report['planned_count']} generated={report['generated']} "
        f"cache_hits={report['cache_hits']} auto_checked={report['auto_checked']} "
        f"reviewed={report['reviewed']} rejected={report['rejected']} "
        f"retried={report['retried']} demoted={report['demoted']} "
        f"errors={len(report['errors'])} exported={len(report['exported_paths'])}"
    )
    print(
        f"Pilot metrics: evaluated={report['evaluated']} "
        f"first_time_pass={report['first_time_pass_count']} "
        f"({report['first_time_pass_rate']:.1%}) "
        f"demoted={report['demoted']} ({report['demotion_rate']:.1%}) "
        f"rejected={report['rejected']}"
    )
    for rr in report.get("rejected_reasons") or []:
        print(
            f"  REJECTED {rr.get('bundle_id')} v{rr.get('version')}: {rr.get('reason')}"
        )
    tiers = report.get("blind_match_tier_counts") or {}
    print(
        f"Blind match tiers: proposition={tiers.get('proposition', 0)} "
        f"alias={tiers.get('alias', 0)} semantic={tiers.get('semantic', 0)}"
    )
    for err in report["errors"]:
        label = (
            f"[{err.get('role')} | {err.get('skill')} | {err.get('topic')} | {err.get('difficulty')}]"
            if "skill" in err
            else "[preflight/planning]"
        )
        print(f"  ERROR {label}: {err['error']}")
    usage = report.get("usage") or {}
    actual_tok = report.get("actual_tokens") or {}
    cost_total = report.get("actual_cost_usd")
    cost_per = report.get("cost_per_bundle_usd")
    cost_str = (
        f"actual_cost=${cost_total:.6f} per_bundle=${cost_per:.6f}"
        if cost_total is not None and cost_per is not None
        else "actual_cost=unavailable"
    )
    print(
        f"Tokens: calls={usage.get('count', 0)} ok={usage.get('ok_count', 0)} "
        f"errors={usage.get('error_count', 0)} "
        f"prompt={usage.get('prompt_tokens', 0)} "
        f"completion={usage.get('completion_tokens', 0)} "
        f"total={usage.get('total_tokens', 0)} "
        f"| run_tokens={actual_tok.get('total_tokens', 0)} "
        f"per_bundle={actual_tok.get('per_bundle', 0.0):.1f} "
        f"{cost_str}"
    )
    for purpose, stats in (usage.get("by_purpose") or {}).items():
        print(
            f"  purpose={purpose}: calls={stats.get('count', 0)} "
            f"ok={stats.get('ok_count', 0)} "
            f"tokens={stats.get('total_tokens', 0)}"
        )
    if report.get("review_csv_path"):
        print(f"Review CSV: {report['review_csv_path']}")
    if report.get("aborted"):
        return 1
    return 1 if report["errors"] and not (report["auto_checked"] or report["reviewed"] or report["cache_hits"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
