"""System-design evaluation: structured self-assessment only.

Does not judge diagrams, component lists, or keyword presence for
correctness. The candidate supplies per-criterion ratings; this module
aggregates them and labels the evaluation mode honestly.

Calibration (advisory): after a complete self-assessment, the design notes are
checked for concepts a design for that prompt usually mentions, per rubric
criterion. The result sits beside the self-rating so a candidate can see where
"I'd give myself 5" is not yet backed by what they wrote. It is a mention
check, not a correctness verdict, and it never changes the score.
"""

from __future__ import annotations

import re
from typing import Any

from backend.db.phase_e_system_design_bank import SYSTEM_DESIGN_EVIDENCE, SYSTEM_DESIGN_RUBRIC

EVALUATION_MODE = "structured_self_assessment"
ALLOWED_RATINGS = frozenset({1, 2, 3, 4, 5})
EVIDENCE_TARGET = 3          # concepts mentioned per criterion for a full 5
EVIDENCE_MIN_WORDS = 20      # below this the notes are too thin to compare
CALIBRATION_ALERT_GAP = 1.5


def evidence_coverage(answer_text: str | None, prompt_id: str | None) -> dict[str, Any]:
    """Per-criterion concept mentions in the design notes (advisory)."""
    concepts = SYSTEM_DESIGN_EVIDENCE.get(str(prompt_id or ""))
    if not concepts:
        return {"available": False, "reason": "No concept checklist for this prompt."}
    text = (answer_text or "").lower()
    if len(re.findall(r"[a-z0-9]+", text)) < EVIDENCE_MIN_WORDS:
        return {"available": False, "reason": "Design notes are too short to compare with your ratings."}
    criteria: dict[str, dict[str, Any]] = {}
    for cid, items in concepts.items():
        matched = [label for label, patterns in items if any(re.search(p, text) for p in patterns)]
        missing = [label for label, _ in items if label not in matched]
        level = 1.0 + 4.0 * min(1.0, len(matched) / EVIDENCE_TARGET)
        criteria[cid] = {"evidence_level": round(level, 1), "mentioned": matched, "not_mentioned": missing}
    return {"available": True, "criteria": criteria}


def _calibration(answer: str | None, question_context: dict[str, Any], ratings: dict[str, int]) -> dict[str, Any]:
    coverage = evidence_coverage(answer, (question_context or {}).get("id"))
    if not coverage.get("available"):
        return coverage
    rows = []
    for c in SYSTEM_DESIGN_RUBRIC:
        evidence = coverage["criteria"].get(c["id"])
        if evidence is None:
            continue
        gap = round(ratings[c["id"]] - evidence["evidence_level"], 1)
        rows.append({
            "id": c["id"],
            "name": c["name"],
            "self_rating": ratings[c["id"]],
            **evidence,
            "gap": gap,
            "overconfident": gap >= CALIBRATION_ALERT_GAP,
        })
    return {
        "available": True,
        "criteria": rows,
        "note": "Mention check against a per-prompt concept list. Advisory; not part of the score.",
    }


def score_system_design_round(
    *,
    answer: str | None = None,
    rubric_ratings: dict[str, Any] | None = None,
    question_context: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Aggregate self-ratings. Missing/invalid ratings yield no score."""
    _ = kwargs  # text is stored and mention-checked for calibration; never scored
    criteria_ids = [c["id"] for c in SYSTEM_DESIGN_RUBRIC]
    ratings_in = rubric_ratings or {}
    normalized: dict[str, int] = {}
    for cid in criteria_ids:
        raw = ratings_in.get(cid)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value in ALLOWED_RATINGS:
            normalized[cid] = value

    if len(normalized) != len(criteria_ids):
        return {
            "final_score": None,
            "evaluation_mode": EVALUATION_MODE,
            "rubric": [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "rating": normalized.get(c["id"]),
                }
                for c in SYSTEM_DESIGN_RUBRIC
            ],
            "incomplete": True,
            "boundary": (
                "No automatic diagram correctness. Incomplete self-assessment "
                "produces no score (not a zero)."
            ),
            "artifact_json": {
                "evaluation": "system_design",
                "evaluation_mode": EVALUATION_MODE,
                "incomplete": True,
            },
            "feedback": (
                "Complete every rubric rating (1–5) to record a "
                "self-assessment score. Diagrams are not auto-validated."
            ),
        }

    calibration = _calibration(answer, question_context or {}, normalized)
    avg = sum(normalized.values()) / len(normalized)
    # Map 1–5 average onto 0–100 for session aggregates without claiming
    # external correctness.
    final = round((avg - 1.0) / 4.0 * 100.0, 2)
    return {
        "final_score": final,
        "evaluation_mode": EVALUATION_MODE,
        "rubric": [
            {"id": c["id"], "name": c["name"], "rating": normalized[c["id"]]}
            for c in SYSTEM_DESIGN_RUBRIC
        ],
        "incomplete": False,
        "boundary": (
            "Score reflects structured self-assessment only. "
            "No automatic diagram or architecture correctness verdict."
        ),
        "artifact_json": {
            "evaluation": "system_design",
            "evaluation_mode": EVALUATION_MODE,
            "rubric": normalized,
            "incomplete": False,
            "calibration": calibration,
        },
        "feedback": (
            "Self-assessment recorded. Review the named criteria; "
            "diagrams were not auto-scored."
        ),
    }


# ── Content evaluation (overhaul Phase 5) ───────────────────────────────
#
# A deterministic *practice estimate* of what the written design covers.
# Versioned separately; never edits the self-assessment scorer above.
# Results are ``practice_review`` evidence: shown to the candidate, excluded
# from Elo, mastery, readiness and gap analysis. Heuristic only — concept
# mentions and explanation signals, not an architecture correctness verdict.

CONTENT_EVALUATION_MODE = "system_design_content_v1"
CONTENT_SCHEMA_VERSION = "v1-system-design-content"
CONTENT_WEIGHT = 0.7               # with all four valid self-ratings
SELF_RATING_WEIGHT = 0.3
COVERAGE_SHARE = 0.7               # within a criterion: coverage vs depth
DEPTH_SHARE = 0.3
CONTENT_MIN_WORDS = 20
EXCERPT_CHARS = 160

_REASONING = re.compile(
    r"\b(because|so that|since|to avoid|which means|therefore|instead of|rather than|"
    r"trade-?offs?|versus|vs\.?|at the cost|in exchange|otherwise|unless|if .{0,40} then)\b"
)
_QUANTITY = re.compile(r"\b\d[\d,.]*\s?(?:k|m|b|ms|s|%|qps|rps|gb|mb|tb|x|million|billion|per)\b")


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _criterion_evidence(sentences_lc: list[str], sentences: list[str], items) -> dict[str, Any]:
    mentioned, excerpts, deep = [], [], 0
    for label, patterns in items:
        index = next(
            (i for i, s in enumerate(sentences_lc) if any(re.search(p, s) for p in patterns)),
            None,
        )
        if index is None:
            continue
        mentioned.append(label)
        excerpts.append({"concept": label, "excerpt": sentences[index][:EXCERPT_CHARS]})
        if _REASONING.search(sentences_lc[index]) or _QUANTITY.search(sentences_lc[index]):
            deep += 1
    target = min(EVIDENCE_TARGET, len(items)) or 1
    coverage = min(1.0, len(mentioned) / target)
    depth = (deep / len(mentioned)) if mentioned else 0.0
    score = round(100.0 * (COVERAGE_SHARE * coverage + DEPTH_SHARE * depth), 2)
    return {
        "score": score,
        "coverage": round(coverage, 3),
        "depth": round(depth, 3),
        "mentioned": mentioned,
        "missing": [label for label, _ in items if label not in mentioned],
        "excerpts": excerpts,
    }


def _valid_ratings(rubric_ratings: dict[str, Any] | None) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in SYSTEM_DESIGN_RUBRIC:
        try:
            value = int((rubric_ratings or {}).get(c["id"]))
        except (TypeError, ValueError):
            continue
        if value in ALLOWED_RATINGS:
            out[c["id"]] = value
    return out


def score_system_design_content_v1(
    *,
    answer: str | None = None,
    rubric_ratings: dict[str, Any] | None = None,
    question_context: dict[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Practice estimate: 70% written content + 30% self-rating when all
    four valid ratings exist, otherwise content alone. Written content is
    required; notes under CONTENT_MIN_WORDS words produce no score."""
    _ = kwargs
    text = answer or ""
    prompt_id = str((question_context or {}).get("id") or "")
    concepts = SYSTEM_DESIGN_EVIDENCE.get(prompt_id)
    words = len(re.findall(r"[A-Za-z0-9]+", text))
    rubric_meta = [{"id": c["id"], "name": c["name"]} for c in SYSTEM_DESIGN_RUBRIC]
    if words < CONTENT_MIN_WORDS or not concepts:
        reason = (
            f"Write at least {CONTENT_MIN_WORDS} words of design notes to get a practice estimate."
            if concepts else "This prompt has no concept checklist, so it cannot be estimated."
        )
        return {
            "final_score": None,
            "evaluation_mode": CONTENT_EVALUATION_MODE,
            "scoring_schema_version": CONTENT_SCHEMA_VERSION,
            "rubric": rubric_meta,
            "incomplete": True,
            "boundary": "Practice estimate from written notes; nothing was recorded.",
            "artifact_json": {"evaluation": "system_design", "evaluation_mode": CONTENT_EVALUATION_MODE,
                              "incomplete": True},
            "feedback": reason,
        }

    sentences = _sentences(text)
    lowered = [s.lower() for s in sentences]
    criteria = []
    for c in SYSTEM_DESIGN_RUBRIC:
        evidence = _criterion_evidence(lowered, sentences, concepts.get(c["id"], []))
        criteria.append({"id": c["id"], "name": c["name"], **evidence})
    content_score = round(sum(c["score"] for c in criteria) / len(criteria), 2)

    ratings = _valid_ratings(rubric_ratings)
    self_score = None
    if len(ratings) == len(SYSTEM_DESIGN_RUBRIC):
        self_score = round((sum(ratings.values()) / len(ratings) - 1.0) / 4.0 * 100.0, 2)
        final = round(CONTENT_WEIGHT * content_score + SELF_RATING_WEIGHT * self_score, 2)
        formula = "70% written content + 30% self-rating"
    else:
        final = content_score
        formula = "written content only (self-ratings incomplete)"

    weakest = min(criteria, key=lambda c: c["score"])
    missing_all = [m for c in criteria for m in c["missing"]]
    feedback = {
        "content": [
            f"Practice estimate: {final:.0f}/100 ({formula}).",
            *(f"{c['name']}: {c['score']:.0f}/100 — mentioned {len(c['mentioned'])} of "
              f"{len(c['mentioned']) + len(c['missing'])} expected concepts." for c in criteria),
        ],
        "strengths": [c["name"] for c in criteria if c["score"] >= 70][:4],
        "weakness": [c["name"] for c in criteria if c["score"] < 50][:4],
        "next_step": (
            f"Strengthen {weakest['name'].lower()}: cover "
            + ", ".join(weakest["missing"][:3])
            + " and explain why."
            if weakest["missing"] else
            f"Explain the reasoning behind your {weakest['name'].lower()} choices (because / trade-off / numbers)."
        ),
        "missing_concepts": missing_all[:12],
    }
    calibration = _calibration(answer, question_context or {}, ratings) if self_score is not None else {
        "available": False, "reason": "Self-ratings were not all provided.",
    }
    artifact = {
        "evaluation": "system_design",
        "evaluation_mode": CONTENT_EVALUATION_MODE,
        "scoring_schema_version": CONTENT_SCHEMA_VERSION,
        "incomplete": False,
        "content_score": content_score,
        "self_rating_score": self_score,
        "formula": formula,
        "criteria": criteria,
        "rubric": ratings,
        "calibration": calibration,
        "boundary": "Heuristic practice estimate (concept mentions and explanation signals). "
                    "Not an architecture correctness verdict; diagrams are not auto-scored; "
                    "excluded from Elo and readiness.",
    }
    return {
        "final_score": final,
        "evaluation_mode": CONTENT_EVALUATION_MODE,
        "scoring_schema_version": CONTENT_SCHEMA_VERSION,
        "rubric": [{"id": c["id"], "name": c["name"], "rating": ratings.get(c["id"]),
                    "content_score": next(x["score"] for x in criteria if x["id"] == c["id"])}
                   for c in SYSTEM_DESIGN_RUBRIC],
        "incomplete": False,
        "boundary": artifact["boundary"],
        "artifact_json": artifact,
        "feedback": feedback,
        "scoring_breakdown": {"final_score": final, "system_design_breakdown": artifact,
                              "scoring_schema_version": CONTENT_SCHEMA_VERSION},
    }
