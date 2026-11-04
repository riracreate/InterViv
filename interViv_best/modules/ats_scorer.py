"""Deterministic ATS scoring.

ATS = 0.25*ParseHealth + 0.20*SectionComplete + 0.40*KeywordCoverage + 0.15*ContentHeuristics

See docs/ats_scoring.md for parser limits (no layout/CV model; no LLM).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from modules.company_graph import get_company_graph
from modules.resume_parser import (
    TECH_SKILLS,
    analyze_resume_text,
    extract_skills_from_text,
)

WEIGHT_PARSE = 0.25
WEIGHT_SECTION = 0.20
WEIGHT_KEYWORD = 0.40
WEIGHT_HEURISTIC = 0.15

# Role-profile short codes → resume lexicon / Phase 2 skill names
ROLE_SKILL_ALIASES: dict[str, str] = {
    "OS": "Operating Systems",
    "Operating System": "Operating Systems",
    "Operating Systems": "Operating Systems",
    "CN": "Computer Networks",
    "Computer Network": "Computer Networks",
    "Computer Networks": "Computer Networks",
    "HR": "HR/Professional Judgment",
    "HR/Professional Judgment": "HR/Professional Judgment",
    "DSA": "DSA",
    "OOP": "OOP",
    "DBMS": "DBMS",
    "SQL": "SQL",
    "Python": "Python",
    "System Design": "System Design",
    "Machine Learning": "Machine Learning",
}

ACTION_VERBS: frozenset[str] = frozenset(
    {
        "built",
        "designed",
        "developed",
        "implemented",
        "led",
        "owned",
        "created",
        "optimized",
        "improved",
        "reduced",
        "increased",
        "launched",
        "delivered",
        "architected",
        "automated",
        "migrated",
        "refactored",
        "scaled",
        "shipped",
        "analyzed",
        "engineered",
        "deployed",
        "integrated",
        "collaborated",
        "mentored",
        "resolved",
        "streamlined",
        "established",
        "drove",
        "spearheaded",
    }
)

DIGIT_RE = re.compile(r"\d")


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(value)))


def build_synonym_index() -> dict[str, set[str]]:
    """Map any alias/canonical (lower) → set of canonical display names."""
    index: dict[str, set[str]] = {}
    for alias, canonical in TECH_SKILLS:
        index.setdefault(alias.lower(), set()).add(canonical)
        index.setdefault(canonical.lower(), set()).add(canonical)
    for short, canonical in ROLE_SKILL_ALIASES.items():
        index.setdefault(short.lower(), set()).add(canonical)
        index.setdefault(canonical.lower(), set()).add(canonical)
    return index


_SYNONYM_INDEX = build_synonym_index()


def expand_skill_token(token: str) -> set[str]:
    raw = str(token or "").strip()
    if not raw:
        return set()
    out = {raw}
    out |= _SYNONYM_INDEX.get(raw.lower(), set())
    # Also map via ROLE_SKILL_ALIASES
    mapped = ROLE_SKILL_ALIASES.get(raw) or ROLE_SKILL_ALIASES.get(raw.upper())
    if mapped:
        out.add(mapped)
        out |= _SYNONYM_INDEX.get(mapped.lower(), set())
    return out


def expand_skill_set(skills: list[str] | set[str]) -> set[str]:
    expanded: set[str] = set()
    for skill in skills:
        expanded |= expand_skill_token(skill)
    return expanded


def jd_hash(jd_text: str) -> str:
    normalized = re.sub(r"\s+", " ", (jd_text or "").strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def parse_health_score(analysis: dict[str, Any]) -> tuple[float, list[str]]:
    """Extraction health. Layout is advisory: it adds flags, never points."""
    flags: list[str] = []
    score = 100.0
    if not analysis.get("extract_ok"):
        score -= 60
        flags.append("extract_failure")
    if analysis.get("likely_garbage"):
        score -= 25
        flags.append("non_selectable_or_garbage_text")
    # Layout is only checked for pdfplumber PDF extraction (not pasted text or
    # the PyMuPDF fallback); tables are never classified.
    if analysis.get("extract_ok") and not analysis.get("layout_checked"):
        flags.append("extract_layout_unchecked")
    if analysis.get("layout") == "two_column":
        flags.append("two_column_reconstructed")
    return _clamp(score), flags


def unsubstantiated_skills(analysis: dict[str, Any], present: list[str]) -> list[str] | None:
    """Matched skills never mentioned in Experience / Projects.

    Advisory only (no points). None when the resume has no Experience or
    Projects header, because absence can't be judged then.
    """
    if not analysis.get("evidence_sections_found"):
        return None
    evidence = expand_skill_set(list(analysis.get("evidence_skills") or []))
    return [skill for skill in present if not (expand_skill_token(skill) & evidence)]


def section_complete_score(analysis: dict[str, Any]) -> tuple[float, list[str]]:
    sections = analysis.get("sections") or {}
    flags: list[str] = []
    keys = ("contact", "experience", "education", "skills")
    present = sum(1 for k in keys if sections.get(k))
    score = (present / len(keys)) * 100.0
    for k in keys:
        if not sections.get(k):
            flags.append(f"missing_section_{k}")
    if analysis.get("section_order_ok") is False:
        score = max(0.0, score - 10)
        flags.append("section_order_unusual")
    return _clamp(score), flags


def keyword_coverage_score(
    resume_skills: list[str],
    must_have: list[str],
) -> tuple[float, list[str], list[str], list[str]]:
    """Return score, flags, present_skills, missing_skills (role/JD vocabulary)."""
    if not must_have:
        return 0.0, ["no_must_have_skills"], [], []

    resume_exp = expand_skill_set(resume_skills)
    present: list[str] = []
    missing: list[str] = []
    for req in must_have:
        req_exp = expand_skill_token(req)
        if resume_exp & req_exp:
            present.append(req)
        else:
            missing.append(req)
    coverage = len(present) / len(must_have)
    score = coverage * 100.0
    flags: list[str] = []
    if coverage == 0:
        flags.append("no_must_have_overlap")
    elif coverage < 0.5:
        flags.append("low_keyword_coverage")
    return _clamp(score), flags, present, missing


def content_heuristics_score(analysis: dict[str, Any]) -> tuple[float, list[str]]:
    bullets = analysis.get("experience_bullets") or []
    flags: list[str] = []
    if not bullets:
        flags.append("no_experience_bullets")
        return 0.0, flags

    verb_hits = 0
    metric_hits = 0
    for bullet in bullets:
        words = re.findall(r"[A-Za-z']+", bullet.lower())
        if words and words[0] in ACTION_VERBS:
            verb_hits += 1
        if DIGIT_RE.search(bullet):
            metric_hits += 1
    verb_frac = verb_hits / len(bullets)
    metric_frac = metric_hits / len(bullets)
    score = ((verb_frac + metric_frac) / 2.0) * 100.0
    if verb_frac < 0.3:
        flags.append("weak_action_verbs")
    if metric_frac < 0.2:
        flags.append("few_metrics")
    return _clamp(score), flags


def must_have_from_role(role_id: str) -> list[str]:
    reqs = get_company_graph().get_required_skills(role_id)
    return [r.skill for r in reqs]


def must_have_from_jd(jd_text: str) -> list[str]:
    """Deterministic: intersect JD text with known skill lexicon (same as resume_parser)."""
    return extract_skills_from_text(jd_text or "")


def score_ats(
    *,
    analysis: dict[str, Any],
    must_have: list[str],
    role_id: str | None = None,
    jd_text: str | None = None,
) -> dict[str, Any]:
    resume_skills = list(analysis.get("skills") or [])
    parse_score, parse_flags = parse_health_score(analysis)
    section_score, section_flags = section_complete_score(analysis)
    keyword_score, keyword_flags, present, missing = keyword_coverage_score(
        resume_skills, must_have
    )
    heuristic_score, heuristic_flags = content_heuristics_score(analysis)

    total = (
        WEIGHT_PARSE * parse_score
        + WEIGHT_SECTION * section_score
        + WEIGHT_KEYWORD * keyword_score
        + WEIGHT_HEURISTIC * heuristic_score
    )
    flags = parse_flags + section_flags + keyword_flags + heuristic_flags
    return {
        "total": round(_clamp(total), 2),
        "components": {
            "parse_health": round(parse_score, 2),
            "section_complete": round(section_score, 2),
            "keyword_coverage": round(keyword_score, 2),
            "content_heuristics": round(heuristic_score, 2),
        },
        "weights": {
            "parse_health": WEIGHT_PARSE,
            "section_complete": WEIGHT_SECTION,
            "keyword_coverage": WEIGHT_KEYWORD,
            "content_heuristics": WEIGHT_HEURISTIC,
        },
        "flags": flags,
        "present_skills": present,
        "missing_skills": missing,
        "unsubstantiated_skills": unsubstantiated_skills(analysis, present),
        "layout": analysis.get("layout"),
        "suggested_practice_skills": missing[:5],
        "resume_skills": resume_skills,
        "must_have": must_have,
        "role_id": role_id,
        "jd_hash": jd_hash(jd_text) if jd_text else None,
        "resume_hash": analysis.get("text_hash"),
    }
