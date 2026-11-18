"""Curated study hints, general guidance and editorials (overhaul Phase 5).

Three kinds of help, with different recording rules:

* ``skill_guidance`` — general study guidance for a skill. Not tied to an
  item, so viewing it is never recorded as assistance and never changes
  assessment eligibility.
* ``item_hint`` — guidance for one question: concept cue, schema summary,
  SQL constructs, coding constraints and approach. Recorded as a hint under
  the existing assistance policy, whichever page asks for it.
* ``item_editorial`` — the worked solution for SQL and coding items, served
  only after the requester has a submitted attempt and recorded as solution
  use. Never includes hidden tests, checks or grading internals.

Templates live in data/learning/hint_templates.json and contain no answers.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

TEMPLATES_PATH = Path(__file__).resolve().parents[1] / "data" / "learning" / "hint_templates.json"


@lru_cache(maxsize=1)
def templates() -> dict[str, Any]:
    return json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))


def _skill_entry(skill: str | None) -> dict[str, Any] | None:
    return templates()["skills"].get(str(skill or "").strip().lower())


def skill_guidance(skill: str) -> dict[str, Any] | None:
    entry = _skill_entry(skill)
    if entry is None:
        return None
    return {"skill": skill, "overview": entry["overview"], "checklist": list(entry["checklist"])}


def known_guidance_skills() -> list[str]:
    return sorted(templates()["skills"])


# ── SQL ─────────────────────────────────────────────────────────────────

_CREATE = re.compile(r"create\s+table\s+(\w+)\s*\((.*?)\);", re.IGNORECASE | re.DOTALL)
_FK = re.compile(r"foreign\s+key\s*\((\w+)\)\s*references\s+(\w+)\s*\((\w+)\)", re.IGNORECASE)
_INLINE_FK = re.compile(r"^(\w+)\s+\w+.*references\s+(\w+)\s*\((\w+)\)", re.IGNORECASE)


def schema_summary(schema_ddl: str | None) -> dict[str, Any]:
    """Tables, columns and key relationships from the (public) schema DDL."""
    tables, relationships = [], []
    for name, body in _CREATE.findall(schema_ddl or ""):
        columns = []
        for raw in body.split(","):
            line = raw.strip()
            if not line:
                continue
            fk = _FK.search(line)
            if fk:
                relationships.append(f"{name}.{fk.group(1)} → {fk.group(2)}.{fk.group(3)}")
                continue
            if re.match(r"(primary|unique|check|constraint)\b", line, re.IGNORECASE):
                continue
            inline = _INLINE_FK.match(line)
            if inline:
                relationships.append(f"{name}.{inline.group(1)} → {inline.group(2)}.{inline.group(3)}")
            columns.append(line.split()[0])
        tables.append({"name": name, "columns": columns})
    names = {t["name"].lower() for t in tables}
    # Conventional ``<table>_id`` columns hint at joins even without FKs.
    for table in tables:
        for column in table["columns"]:
            stem = column.lower()[:-3] if column.lower().endswith("_id") else None
            if stem:
                target = next((n for n in names if n in (stem, stem + "s", stem + "es")), None)
                edge = f"{table['name']}.{column} → {target}.id" if target else None
                if edge and edge not in relationships:
                    relationships.append(edge)
    return {"tables": tables, "relationships": relationships}


def schema_construct_keys(summary: dict[str, Any]) -> list[str]:
    """Constructs a hint may name from the public schema summary alone.

    The reference query is not an input. A relationship the candidate can
    already see is the only technique the hint may mention.
    """
    if summary.get("relationships"):
        return ["join"]
    return []


def sql_constructs(query: str | None) -> list[str]:
    """Construct keys a solution needs (technique only, never the query)."""
    q = re.sub(r"\s+", " ", (query or "").lower())
    left_joins = len(re.findall(r"\bleft (?:outer )?join\b", q))
    all_joins = len(re.findall(r"\bjoin\b", q))
    found = []
    if all_joins > left_joins:
        found.append("join")
    if left_joins:
        found.append("left_join")
    for key, pattern in (
        ("window", r"\bover\s*\("),
        ("subquery", r"\(\s*select\b"),
        ("group_by", r"\bgroup by\b"),
        ("having", r"\bhaving\b"),
        ("aggregate", r"\b(?:count|sum|avg|min|max)\s*\("),
        ("distinct", r"\bdistinct\b"),
        ("order_by", r"\border by\b"),
    ):
        if re.search(pattern, q):
            found.append(key)
    return found


# ── item hints ──────────────────────────────────────────────────────────

def item_hint(item_type: str, item: dict[str, Any], skill: str) -> dict[str, Any]:
    t = templates()
    entry = _skill_entry(skill)
    if item_type == "mcq":
        return {
            "skill": skill,
            "sub_domain": item.get("sub_domain"),
            "difficulty": item.get("difficulty"),
            "selection_mode": item.get("selection_mode", "single"),
            "negative_marking": float(item.get("negative_marking", 0.0)),
            "concept": item.get("sub_domain") or skill,
            "approach": t["mcq_approach"],
            "checklist": list(entry["checklist"]) if entry else [],
            "guidance": (
                f"Focus on {item.get('sub_domain') or skill}. " + t["mcq_approach"]
            ),
        }
    if item_type == "sql":
        summary = schema_summary(item.get("schema_ddl"))
        constructs = [
            {"construct": key, "hint": t["sql_constructs"][key]}
            for key in schema_construct_keys(summary)
            if key in t["sql_constructs"]
        ]
        return {
            "skill": skill,
            "difficulty": item.get("difficulty"),
            "has_schema": bool(item.get("schema_ddl")),
            "tables": summary["tables"],
            "relationships": summary["relationships"],
            "constructs": constructs,
            "guidance": (
                "Read the tables and how they connect, then build the query one clause at a time with Run. "
                + (constructs[0]["hint"] if constructs else "")
            ).strip(),
        }
    topics = [str(x) for x in item.get("topics") or []]
    approaches = [
        {"topic": topic, "hint": t["coding_topics"][topic.lower()]}
        for topic in topics if topic.lower() in t["coding_topics"]
    ]
    return {
        "skill": skill,
        "topics": topics,
        "difficulty": item.get("difficulty"),
        "function": item.get("function"),
        "visible_example_count": len(item.get("visible_tests") or []),
        "constraints": [str(c) for c in item.get("constraints") or []],
        "approach": approaches,
        "guidance": (approaches[0]["hint"] + " " if approaches else "") + t["coding_general"],
    }


def item_editorial(item_type: str, item: dict[str, Any]) -> dict[str, Any] | None:
    """Worked solution for SQL/coding items; None when none is published."""
    t = templates()
    if item_type == "sql" and item.get("reference_query"):
        keys = sql_constructs(item["reference_query"])
        return {
            "kind": "sql",
            "solution_query": str(item["reference_query"]).strip(),
            "constructs": [{"construct": k, "hint": t["sql_constructs"][k]} for k in keys
                           if k in t["sql_constructs"]],
            "schema": schema_summary(item.get("schema_ddl")),
        }
    if item_type == "coding" and item.get("reference_solution"):
        topics = [str(x) for x in item.get("topics") or []]
        return {
            "kind": "coding",
            "solution_code": str(item["reference_solution"]).rstrip() + "\n",
            "language": "python",
            "approach": [t["coding_topics"][x.lower()] for x in topics if x.lower() in t["coding_topics"]],
            "constraints": [str(c) for c in item.get("constraints") or []],
        }
    return None
