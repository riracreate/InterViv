"""Role blueprints. Draft YAML is input, not reviewed question content."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from modules.interview_llm import batch_scope
from modules.resume_parser import TECH_SKILLS

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_DIR = ROOT / "data" / "role_blueprints"
RESEARCH_PATH = ROOT / "docs" / "research" / "role_catalog_research.md"

TYPES = frozenset({"technical", "role_scenario", "behavioural"})
FAMILIES = frozenset({"engineering", "data", "business", "product", "design"})
LEVELS = ("intern", "junior", "mid")
STATUSES = frozenset({"draft", "reviewed"})
TRACKS = frozenset({"coding", "sql", "none"})
SPOKEN_WORD_LIMIT = 40
SPOKEN_SENTENCE_LIMIT = 2

# Owner decisions, 2026-11-17. Data Engineer and Cybersecurity stay deferred.
MAPPING_DECISIONS = {
    "associate-product-manager": (
        "No O*NET product-manager occupation. Primary mapping is ESCO 1330.6 ICT product manager, "
        "verified 2026-11-17."
    ),
    "devops-cloud-engineer": (
        "O*NET 15-1299.08 Computer Systems Engineers/Architects, verified 2026-11-17. "
        "ESCO stays ICT system administrator; the owner did not replace that weak fit."
    ),
    "data-engineer": (
        "Deferred. Not a starter blueprint. ESCO maps this title onto data scientist (2511.3). "
        "O*NET 15-1243.00 Database Architects is the closer of the two."
    ),
    "cybersecurity-analyst": (
        "Deferred. Not a starter blueprint. ESCO ICT system administrator does not describe security analysis. "
        "O*NET 15-1212.00 Information Security Analysts is the closer code."
    ),
}

_ALIAS_TO_CANONICAL = {}
for _alias, _canonical in TECH_SKILLS:
    _ALIAS_TO_CANONICAL[_alias.lower()] = _canonical
    _ALIAS_TO_CANONICAL.setdefault(_canonical.lower(), _canonical)

BLUEPRINT_ALIASES: dict[str, str] = {
    "data-scientist-ml": "data-scientist",
}

_DRAFT_CACHE: dict[str, dict] = {}


class BlueprintError(ValueError):
    pass


def taxonomy_skill(raw: str) -> str | None:
    """Resolve a skill to the existing TECH_SKILLS taxonomy. Never registers a new one."""
    key = " ".join(str(raw or "").strip().lower().split())
    if not key:
        return None
    if key in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[key]
    if key.endswith("s") and key[:-1] in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[key[:-1]]
    words = key.split()
    if words and words[-1].endswith("s"):
        trimmed = " ".join([*words[:-1], words[-1][:-1]])
        if trimmed in _ALIAS_TO_CANONICAL:
            return _ALIAS_TO_CANONICAL[trimmed]
    return None


def question_speech_issues(text: str) -> list[str]:
    """Flag a question that is too long to speak. Callers do not reject existing bundles."""
    clean = " ".join(str(text or "").split())
    if not clean:
        return []
    issues = []
    words = clean.split()
    sentences = [part for part in re.split(r"[.!?]+", clean) if part.strip()]
    if len(words) > SPOKEN_WORD_LIMIT:
        issues.append(f"{len(words)} words")
    if len(sentences) > SPOKEN_SENTENCE_LIMIT:
        issues.append(f"{len(sentences)} sentences")
    return issues


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BlueprintError(message)


def validate_blueprint(doc: dict, *, source: str = "") -> dict:
    """Structural checks. Unresolved skills and long seeds are reported, not rejected."""
    where = source or str(doc.get("id") or "blueprint")
    _require(isinstance(doc, dict), f"{where}: blueprint must be a mapping")
    for key in ("id", "title", "family", "status", "version", "practical_track", "competencies"):
        _require(key in doc, f"{where}: missing {key}")
    _require(doc["status"] in STATUSES, f"{where}: status must be draft or reviewed")
    _require(doc["family"] in FAMILIES, f"{where}: unknown family {doc['family']}")
    _require(doc["practical_track"] in TRACKS, f"{where}: unknown practical track")
    _require(isinstance(doc["version"], int) and doc["version"] >= 1, f"{where}: version must be a positive integer")
    levels = doc.get("levels") or list(LEVELS)
    _require(list(levels) == list(LEVELS), f"{where}: levels must be intern, junior, mid")
    competencies = doc["competencies"]
    _require(isinstance(competencies, list) and competencies, f"{where}: competencies required")
    ids = []
    weight = 0.0
    unresolved = []
    long_seeds = []
    for item in competencies:
        _require(isinstance(item, dict), f"{where}: competency must be a mapping")
        _require(item.get("type") in TYPES, f"{where}: bad competency type {item.get('type')}")
        cid = str(item.get("id") or "")
        _require(cid and cid not in ids, f"{where}: competency ids must be unique ({cid or 'blank'})")
        ids.append(cid)
        value = float(item.get("weight") or 0)
        _require(value > 0, f"{where}: {cid} weight must be positive")
        weight += value
        skills = list(item.get("skills") or [])
        if item["type"] == "technical":
            for skill in skills:
                if taxonomy_skill(skill) is None:
                    unresolved.append(skill)
        for seed in item.get("draft_seeds") or []:
            text = seed.get("text") if isinstance(seed, dict) else str(seed)
            issues = question_speech_issues(text)
            if issues:
                long_seeds.append({"competency": cid, "issues": issues, "text": text})
    for seed in doc.get("draft_seeds") or []:
        text = seed.get("text") if isinstance(seed, dict) else str(seed)
        issues = question_speech_issues(text)
        if issues:
            long_seeds.append({"competency": seed.get("kind") or "seed", "issues": issues, "text": text})
    _require(abs(weight - 1.0) <= 0.001, f"{where}: competency weights sum to {weight:.3f}, not 1")
    return {"id": doc["id"], "unresolved_skills": unresolved, "long_seeds": long_seeds}


def load_blueprint(path: Path) -> dict:
    doc = yaml.safe_load(path.read_text())
    validate_blueprint(doc, source=str(path))
    return doc


def load_blueprints(directory: Path = BLUEPRINT_DIR) -> list[dict]:
    docs = []
    seen = set()
    for path in sorted(directory.glob("*.yaml")):
        doc = load_blueprint(path)
        _require(doc["id"] not in seen, f"duplicate blueprint id {doc['id']}")
        seen.add(doc["id"])
        docs.append(doc)
    return docs


def resolve_blueprint_id(role_id: str) -> str:
    """Resolve a blueprint ID or legacy role slug alias to the canonical blueprint ID."""
    key = " ".join(str(role_id or "").strip().lower().split())
    return BLUEPRINT_ALIASES.get(key, key)


def get_blueprint(role_id: str, directory: Path = BLUEPRINT_DIR) -> dict | None:
    """Return a loaded blueprint by canonical ID or alias, or None if not found."""
    target = resolve_blueprint_id(role_id)
    if not target:
        return None
    for doc in load_blueprints(directory):
        if doc["id"] == target:
            return doc
    return None


def blueprint_summary(docs: list[dict], *, bundle_skills: set[str] | None = None) -> list[dict]:
    """Per-role taxonomy hits, missing demo-DB bundles, and seeds that are too long to speak."""
    known = {skill.casefold() for skill in (bundle_skills or set())}
    rows = []
    for doc in docs:
        report = validate_blueprint(doc)
        resolved = []
        missing_bundles = []
        for item in doc["competencies"]:
            if item["type"] != "technical":
                continue
            for skill in item.get("skills") or []:
                canonical = taxonomy_skill(skill)
                if canonical is None:
                    continue
                resolved.append(canonical)
                if canonical.casefold() not in known:
                    missing_bundles.append(canonical)
        rows.append({
            "id": doc["id"],
            "resolved_skills": sorted(set(resolved)),
            "skills_without_bundles": sorted(set(missing_bundles)),
            "unresolved_skills": report["unresolved_skills"],
            "long_seeds": [
                {"where": item["competency"], "issues": item["issues"], "words": len(str(item["text"]).split())}
                for item in report["long_seeds"]
            ],
            "provenance": doc.get("provenance") or {},
        })
    return rows


def draft_unknown_blueprint(title: str, *, router, override) -> dict:
    """Draft a blueprint for a role that is not in the catalog. Offline override only in tests.

    The result is cached in memory and always labelled draft. No database schema is involved.
    """
    key = " ".join(str(title or "").split()).casefold()
    if not key:
        raise BlueprintError("A role title is required.")
    cached = _DRAFT_CACHE.get(key)
    if cached is not None:
        return cached
    prompt = (
        "Draft a role blueprint for this generic role title only. "
        "Do not use a resume or job description. Return JSON with id, title, family, "
        "competencies, and status draft. Title: " + " ".join(str(title).split())
    )
    with batch_scope(f"blueprint-draft:{key[:40]}", max_requests=1):
        completion = router.dispatch(
            purpose="bundle_generation",
            messages=[{"role": "user", "content": prompt}],
            personal_text=False,
            override=override,
        )
    try:
        payload = json.loads(completion.text)
    except json.JSONDecodeError as exc:
        raise BlueprintError("Draft blueprint override did not return JSON.") from exc
    if not isinstance(payload, dict):
        raise BlueprintError("Draft blueprint override must return a JSON object.")
    payload["status"] = "draft"
    payload["title"] = payload.get("title") or " ".join(str(title).split())
    _DRAFT_CACHE[key] = payload
    return payload


def register_unresolved_skills(docs: list[dict]) -> list[str]:
    """Register blueprint skills that are not already in the static taxonomy.

    Uses the existing new-canonical path, which appends an audit record.
    Similarity is set to 1 so a nearby embedding cannot merge the skill away.
    """
    from modules.role_skills import resolve_skill_identity

    registered = []
    seen = set()
    for doc in docs:
        for skill in validate_blueprint(doc)["unresolved_skills"]:
            key = skill.casefold()
            if key in seen:
                continue
            seen.add(key)
            canonical, match = resolve_skill_identity(skill, register=True, similarity_threshold=1.0)
            if match == "new_canonical":
                registered.append(canonical)
    return registered


def clear_draft_cache() -> None:
    _DRAFT_CACHE.clear()
