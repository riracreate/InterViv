"""Phase D learning hub: notebook, retry sets, bookmarks, assistance, next steps.

Every surface here is derived from recorded evidence only:

- The mistakes notebook contains misses backed by submitted rounds.
- Retry sets draw from genuinely missed topics.
- Assisted and unassisted attempts stay separated in every claim.
- Coding rounds contribute no scored evidence while execution is
  unavailable; they are disclosed as unavailable, never as zeros and
  never silently omitted.
- Phase I spaced-review schedules sit on notebook misses (plus coding
  unavailable attempts). Reviews are practice, not measured mastery.
- No answer keys, restricted explanations, reference solutions, hidden
  tests, or private execution metadata leave through these responses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.evidence_kind import is_self_reported_round
from backend.review_schedule import (
    INTERVAL_LADDER,
    advance_after_outcome,
    is_due,
    ladder_days_at,
)
from backend.routes.auth import require_authenticated, require_user
from backend.routes.session import StartSessionRequest, start_session

router = APIRouter(tags=["learning"], dependencies=[Depends(require_authenticated)])

ITEM_TYPES = ("mcq", "sql", "coding")
ASSISTANCE_KINDS = ("hint", "explanation", "solution", "editorial")
GOOD_SCORE_CUTOFF = 61.0  # Report bands: Good is a final score above 60.
MAX_RETRY_ITEMS = 10
MAX_BOOKMARK_ITEMS = 200
MAX_REVIEW_START_ITEMS = 10
SPACED_REVIEW_PURPOSE = "spaced_review"


class RetrySetRequest(BaseModel):
    name: str | None = None
    max_items: int = 5
    skills: list[str] = Field(default_factory=list)


class ReviewStartRequest(BaseModel):
    max_items: int = 5
    include_unavailable: bool = False
    skills: list[str] = Field(default_factory=list)


class BookmarkRequest(BaseModel):
    item_type: str
    item_id: str


class AssistanceRequest(BaseModel):
    item_type: str
    item_id: str
    kind: str
    session_id: str | None = None
    round: int | None = None


# ---------------------------------------------------------------------------
# Bank lookups (linear scans match existing session-bank access patterns)
# ---------------------------------------------------------------------------

def _find_mcq(question_id: str) -> dict[str, Any] | None:
    from backend.db.phase2_content_bank import PHASE2_MCQ_BANK
    from backend.db.phase21_verbal_bank import PHASE21_VERBAL_BANK

    for bank in (PHASE2_MCQ_BANK, PHASE21_VERBAL_BANK):
        for question in bank:
            if question.get("id") == question_id:
                return question
    return None


def _find_sql(problem_id: str) -> dict[str, Any] | None:
    from backend.db.phase2_content_bank import PHASE2_SQL_BANK

    for problem in PHASE2_SQL_BANK:
        if problem.get("id") == problem_id:
            return problem
    return None


def _find_coding(problem_id: str) -> dict[str, Any] | None:
    from backend.db.phase_c_coding_bank import get_coding_problem

    return get_coding_problem(problem_id)


def _find_item(item_type: str, item_id: str) -> dict[str, Any] | None:
    if item_type == "mcq":
        return _find_mcq(item_id)
    if item_type == "sql":
        return _find_sql(item_id)
    if item_type == "coding":
        return _find_coding(item_id)
    return None


def _item_title(item_type: str, item: dict[str, Any]) -> str:
    if item_type == "mcq":
        stem = str(item.get("stem") or "")
        return stem if len(stem) <= 120 else stem[:117] + "..."
    if item_type == "sql":
        prompt = str(item.get("prompt") or "")
        return prompt.split("\n", 1)[0].lstrip("# ").strip() or str(item.get("id"))
    return str(item.get("title") or item.get("id"))


def _item_skill(item_type: str, item: dict[str, Any]) -> str:
    if item_type == "mcq":
        return str(item.get("skill") or "General")
    if item_type == "sql":
        return "SQL"
    topics = item.get("topics") or []
    return str(topics[0]) if topics else "DSA"


def _resources_for_skill(skill: str) -> list[dict[str, Any]]:
    """Existing local resource records only; never fetched or embedded."""
    try:
        from modules.learning_resources import list_resources

        payload = list_resources(skill_id=skill)
    except Exception:
        return []
    resources = (payload or {}).get("resources") or []
    return [
        {
            "title": r.get("title"),
            "url": r.get("url"),
            "source": r.get("source"),
            "level": r.get("level"),
        }
        for r in resources[:5]
    ]


# ---------------------------------------------------------------------------
# Attempt evidence
# ---------------------------------------------------------------------------

def _owned_sessions(db: Any, user_id: str) -> list[dict[str, Any]]:
    try:
        return list(db["sessions"].find({"user_id": user_id}))
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Practice history is temporarily unavailable.",
            ) from exc
        raise


def _round_items(round_doc: dict[str, Any]) -> list[tuple[str, str]]:
    """Item identities a round evaluated, by round type."""
    round_type = round_doc.get("round_type", "technical_short_answer")
    if round_type == "mcq":
        questions = (round_doc.get("question_context") or {}).get("questions") or []
        return [("mcq", str(q.get("id"))) for q in questions if q.get("id")]
    if round_type in ("sql", "coding"):
        config = round_doc.get("config_json") or {}
        context = round_doc.get("question_context") or {}
        problem_id = config.get("problem_id") or context.get("problem_id")
        if problem_id:
            return [(round_type, str(problem_id))]
    return []


def _has_submitted_attempt(
    sessions: list[dict[str, Any]], item_type: str, item_id: str
) -> bool:
    for session in sessions:
        for round_doc in session.get("rounds") or []:
            if round_doc.get("final_score") is None:
                continue
            if (item_type, item_id) in _round_items(round_doc):
                return True
    return False


def _attempted_item_ids(
    sessions: list[dict[str, Any]], item_type: str
) -> set[str]:
    attempted: set[str] = set()
    for session in sessions:
        for round_doc in session.get("rounds") or []:
            if round_doc.get("final_score") is None:
                continue
            for kind, item_id in _round_items(round_doc):
                if kind == item_type:
                    attempted.add(item_id)
    return attempted


def _assistance_for(
    db: Any, user_id: str, items: list[tuple[str, str]]
) -> dict[tuple[str, str], list[str]]:
    """Assistance kinds recorded for each item (any session, any time)."""
    found: dict[tuple[str, str], list[str]] = {}
    try:
        events = list(db["assistance_events"].find({"user_id": user_id}))
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Assistance history is temporarily unavailable.",
            ) from exc
        raise
    wanted = set(items)
    for event in events:
        key = (str(event.get("item_type")), str(event.get("item_id")))
        if key in wanted:
            kinds = found.setdefault(key, [])
            kind = str(event.get("kind") or "")
            if kind and kind not in kinds:
                kinds.append(kind)
    return found


def assistance_breakdown_for_user(user_id: str) -> dict[str, Any]:
    """Per-skill assisted/unassisted scored-round counts (read-time join).

    Existing mastery figures are unchanged; this sits alongside them so
    no surface silently mixes the two populations. Spaced-review practice
    rounds are excluded — they are not measured attempts.
    """
    from backend.evidence_kind import is_practice_review_round

    db = get_database()
    sessions = _owned_sessions(db, user_id)
    per_skill: dict[str, dict[str, int]] = {}
    totals = {"assisted_rounds": 0, "unassisted_rounds": 0}
    for session in sessions:
        if (session.get("round_config") or {}).get("purpose") == SPACED_REVIEW_PURPOSE:
            continue
        for round_doc in session.get("rounds") or []:
            if round_doc.get("final_score") is None:
                continue
            if is_practice_review_round(round_doc) or is_self_reported_round(round_doc):
                continue
            skill = str(
                round_doc.get("skill")
                or (session.get("skills") or ["General"])[0]
            )
            bucket = per_skill.setdefault(
                skill, {"assisted_rounds": 0, "unassisted_rounds": 0}
            )
            if round_doc.get("assisted"):
                bucket["assisted_rounds"] += 1
                totals["assisted_rounds"] += 1
            else:
                bucket["unassisted_rounds"] += 1
                totals["unassisted_rounds"] += 1
    return {"per_skill": per_skill, **totals}


# ---------------------------------------------------------------------------
# Mistakes notebook
# ---------------------------------------------------------------------------

def _notebook_entries(
    sessions: list[dict[str, Any]], db: Any, user_id: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    coding_rounds = 0
    scored_rounds = 0
    for session in sessions:
        session_id = session.get("session_id")
        # Spaced-review practice sessions are not measured misses.
        if (session.get("round_config") or {}).get("purpose") == SPACED_REVIEW_PURPOSE:
            continue
        for round_doc in session.get("rounds") or []:
            round_type = round_doc.get("round_type", "technical_short_answer")
            final_score = round_doc.get("final_score")
            if round_type == "coding":
                # No scored evidence exists while execution is unavailable;
                # disclosed in coverage, never listed as a miss or a solve.
                coding_rounds += 1
                continue
            if final_score is None:
                continue
            if is_self_reported_round(round_doc) or round_type == "system_design":
                # Self-assessment is labeled elsewhere; it is not a measured
                # miss and must not seed retry topics or mastery signals.
                continue
            scored_rounds += 1
            assisted = bool(round_doc.get("assisted"))
            kinds = list(round_doc.get("assistance_kinds") or [])
            base = {
                "session_id": session_id,
                "round": round_doc.get("round"),
                "round_type": round_type,
                "block_id": round_doc.get("block_id"),
                "block_category": round_doc.get("block_category"),
                "assisted": assisted,
                "assistance_kinds": kinds,
                "submitted_at": round_doc.get("submitted_at"),
            }
            if round_type == "mcq":
                artifact = round_doc.get("artifact_json") or {}
                for answered in artifact.get("questions") or []:
                    if answered.get("is_correct"):
                        continue
                    question = _find_mcq(str(answered.get("question_id")))
                    if question is None:
                        continue
                    entries.append({
                        **base,
                        "kind": "mcq_miss",
                        "item_type": "mcq",
                        "item_id": question["id"],
                        "title": _item_title("mcq", question),
                        "skill": str(question.get("skill") or "General"),
                        "sub_domain": question.get("sub_domain"),
                        "difficulty": question.get("difficulty"),
                        # The candidate's own response only: options are
                        # public, the key and explanation stay restricted.
                        "options": [
                            {"id": o.get("id"), "text": o.get("text")}
                            for o in question.get("options", [])
                        ],
                        "selected_option_ids": list(
                            answered.get("selected_option_ids") or []
                        ),
                        "raw_marks": answered.get("raw_marks"),
                    })
            elif round_type == "sql":
                artifact = round_doc.get("artifact_json") or {}
                total = artifact.get("total_cases") or artifact.get("evaluation_cases") or 0
                passed = artifact.get("passed_cases") or artifact.get("cases_passed") or 0
                if total and passed >= total:
                    continue
                config = round_doc.get("config_json") or {}
                problem = _find_sql(str(config.get("problem_id") or ""))
                entries.append({
                    **base,
                    "kind": "sql_miss",
                    "item_type": "sql",
                    "item_id": config.get("problem_id"),
                    "title": _item_title("sql", problem) if problem else None,
                    "skill": "SQL",
                    "difficulty": problem.get("difficulty") if problem else None,
                    # Counts only: no reference query, no hidden cases.
                    "cases_passed": passed,
                    "cases_total": total,
                    "final_score": final_score,
                })
            else:
                if float(final_score) >= GOOD_SCORE_CUTOFF:
                    continue
                entries.append({
                    **base,
                    "kind": "interview_miss",
                    "item_type": "interview",
                    "item_id": None,
                    "title": str(round_doc.get("question") or "")[:200],
                    "skill": str(round_doc.get("skill") or "General"),
                    "difficulty": round_doc.get("difficulty"),
                    # The candidate's own feedback only.
                    "missing_concepts": list(round_doc.get("missing_concepts") or []),
                    "final_score": final_score,
                })
    entries.sort(
        key=lambda e: (str(e.get("submitted_at") or ""), str(e.get("session_id") or "")),
        reverse=True,
    )
    coverage = {
        "sessions_scanned": len(sessions),
        "scored_rounds_scanned": scored_rounds,
        "excluded_coding_rounds": coding_rounds,
        "excluded_coding_reason": (
            "Code execution is unavailable, so coding rounds produce no "
            "scored evidence and are excluded from the notebook."
            if coding_rounds
            else None
        ),
    }
    return entries, coverage


@router.get("/learning/notebook/me")
def get_my_notebook(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    user_id = str(user["id"])
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    sessions = _owned_sessions(db, user_id)
    entries, coverage = _notebook_entries(sessions, db, user_id)
    if not entries:
        if coverage["scored_rounds_scanned"] == 0:
            return {
                "entries": [],
                "counts": None,
                "coverage": coverage,
                "empty_reason": "no_scored_attempts",
            }
        return {
            "entries": [],
            "counts": {
                "total": 0,
                "assisted": 0,
                "unassisted": 0,
                "scored_rounds_scanned": coverage["scored_rounds_scanned"],
            },
            "coverage": coverage,
            "empty_reason": "no_misses_recorded",
        }
    assisted = sum(1 for e in entries if e["assisted"])
    return {
        "entries": entries,
        "counts": {
            "total": len(entries),
            "assisted": assisted,
            "unassisted": len(entries) - assisted,
            "scored_rounds_scanned": coverage["scored_rounds_scanned"],
        },
        "coverage": coverage,
        "empty_reason": None,
    }


# ---------------------------------------------------------------------------
# Retry sets
# ---------------------------------------------------------------------------

def _candidate_mcq_pool(
    missed_skills: set[str],
) -> list[dict[str, Any]]:
    from backend.db.phase2_content_bank import PHASE2_MCQ_BANK
    from backend.db.phase21_verbal_bank import PHASE21_VERBAL_BANK

    pool = []
    for question in list(PHASE2_MCQ_BANK) + list(PHASE21_VERBAL_BANK):
        if str(question.get("skill") or "General") in missed_skills:
            pool.append(question)
    return pool


def _generate_retry_items(
    entries: list[dict[str, Any]],
    attempted_mcq: set[str],
    attempted_sql: set[str],
    *,
    max_items: int,
    only_skills: set[str] | None,
) -> list[dict[str, Any]]:
    """Deterministic selection from genuinely missed topics.

    Unseen same-topic items come first (cleaner re-evidence); the exact
    missed items fill the remainder. Unassisted misses outrank assisted
    ones as evidence; interview misses contribute their skill only.
    """
    missed_mcq: list[dict[str, Any]] = []
    missed_sql: list[dict[str, Any]] = []
    missed_skills: set[str] = set()
    for entry in entries:
        skill = str(entry.get("skill") or "General")
        if only_skills and skill not in only_skills:
            continue
        missed_skills.add(skill)
        if entry.get("kind") == "mcq_miss" and entry.get("item_id"):
            missed_mcq.append(entry)
        elif entry.get("kind") == "sql_miss" and entry.get("item_id"):
            missed_sql.append(entry)
    if not missed_skills:
        return []

    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def _add(item_type: str, item_id: str, skill: str, reason: str,
             miss_assisted: bool | None) -> None:
        if len(items) >= max_items or (item_type, item_id) in seen:
            return
        seen.add((item_type, item_id))
        items.append({
            "item_type": item_type,
            "item_id": item_id,
            "skill": skill,
            "reason": reason,
            "miss_assisted": miss_assisted,
        })

    # Unseen same-topic MCQ questions first, deterministic by skill then id.
    pool = sorted(
        _candidate_mcq_pool(missed_skills),
        key=lambda q: (str(q.get("skill")), str(q.get("id"))),
    )
    for question in pool:
        if question.get("id") in attempted_mcq:
            continue
        _add("mcq", str(question["id"]), str(question.get("skill")),
             f"missed-topic:{question.get('skill')}", None)
    # Unseen SQL problems on missed SQL evidence.
    if "SQL" in missed_skills:
        from backend.db.phase2_content_bank import PHASE2_SQL_BANK

        for problem in sorted(PHASE2_SQL_BANK, key=lambda p: str(p.get("id"))):
            if problem.get("id") in attempted_sql:
                continue
            _add("sql", str(problem["id"]), "SQL", "missed-topic:SQL", None)
    # Fall back to the exact missed items (unassisted misses first).
    for entry in sorted(missed_mcq, key=lambda e: (bool(e.get("assisted")), str(e.get("item_id")))):
        _add("mcq", str(entry["item_id"]), str(entry.get("skill")),
             "retry-missed-item", bool(entry.get("assisted")))
    for entry in sorted(missed_sql, key=lambda e: (bool(e.get("assisted")), str(e.get("item_id")))):
        _add("sql", str(entry["item_id"]), "SQL",
             "retry-missed-item", bool(entry.get("assisted")))
    return items


@router.post("/learning/retry-sets")
def create_retry_set(
    request: RetrySetRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    user_id = str(user["id"])
    max_items = int(request.max_items or 5)
    if max_items < 1 or max_items > MAX_RETRY_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"max_items must be 1-{MAX_RETRY_ITEMS}.",
        )
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    sessions = _owned_sessions(db, user_id)
    entries, _ = _notebook_entries(sessions, db, user_id)
    only_skills = {s.strip() for s in request.skills if s.strip()} or None
    items = _generate_retry_items(
        entries,
        _attempted_item_ids(sessions, "mcq"),
        _attempted_item_ids(sessions, "sql"),
        max_items=max_items,
        only_skills=only_skills,
    )
    if not items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No missed topics with retryable items. Retry sets are "
            "generated from recorded misses only.",
        )
    name = (request.name or "").strip() or f"Retry {len(items)} missed-topic items"
    doc = {
        "id": str(uuid4()),
        "user_id": user_id,
        "name": name[:120],
        "items": items,
        "source": "missed-topics",
        "created_at": datetime.now(timezone.utc),
    }
    try:
        db["retry_sets"].insert_one(doc)
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    return {"retry_set": _public_retry_set(doc)}


def _public_retry_set(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": doc.get("id"),
        "name": doc.get("name"),
        "items": list(doc.get("items") or []),
        "source": doc.get("source"),
        "created_at": doc.get("created_at"),
    }


def _owned_retry_set(db: Any, user_id: str, set_id: str) -> dict[str, Any]:
    doc = db["retry_sets"].find_one({"id": set_id})
    if not doc or str(doc.get("user_id")) != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Retry set not found."
        )
    return doc


@router.get("/learning/retry-sets/me")
def list_my_retry_sets(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        db = get_database()
        docs = list(db["retry_sets"].find({"user_id": str(user["id"])}))
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    docs.sort(key=lambda d: str(d.get("created_at") or ""), reverse=True)
    return {"retry_sets": [_public_retry_set(d) for d in docs]}


@router.get("/learning/retry-sets/{set_id}")
def get_retry_set(
    set_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        db = get_database()
        doc = _owned_retry_set(db, str(user["id"]), set_id)
    except HTTPException:
        raise
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    return {"retry_set": _public_retry_set(doc)}


@router.delete("/learning/retry-sets/{set_id}")
def delete_retry_set(
    set_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        db = get_database()
        _owned_retry_set(db, str(user["id"]), set_id)
        db["retry_sets"].delete_one({"id": set_id})
    except HTTPException:
        raise
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    return {"deleted": set_id}


@router.post("/learning/retry-sets/{set_id}/start")
def start_retry_set(
    set_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        db = get_database()
        doc = _owned_retry_set(db, str(user["id"]), set_id)
    except HTTPException:
        raise
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    items = list(doc.get("items") or [])
    if not items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This retry set has no items.",
        )
    # Group into blocks: Verbal MCQs stay distinct from technical OA.
    from backend.db.phase21_verbal_bank import PHASE21_VERBAL_BANK

    verbal_ids = {q.get("id") for q in PHASE21_VERBAL_BANK}
    verbal_items = [i for i in items if i.get("item_type") == "mcq" and i.get("item_id") in verbal_ids]
    oa_items = [i for i in items if i.get("item_type") == "mcq" and i.get("item_id") not in verbal_ids]
    sql_items = [i for i in items if i.get("item_type") == "sql"]
    blocks: list[dict[str, Any]] = []
    if verbal_items:
        blocks.append({
            "round_type": "mcq",
            "category": "verbal",
            "skills": ["Verbal Ability"],
            "count": len(verbal_items),
            "question_ids": [i["item_id"] for i in verbal_items],
            "duration_minutes": 20,
        })
    if oa_items:
        skills = sorted({str(i.get("skill") or "General") for i in oa_items})
        blocks.append({
            "round_type": "mcq",
            "category": "oa",
            "skills": [s for s in skills if s != "Verbal Ability"] or ["DBMS"],
            "count": len(oa_items),
            "question_ids": [i["item_id"] for i in oa_items],
            "duration_minutes": 20,
        })
    if sql_items:
        blocks.append({
            "round_type": "sql",
            "category": "sql",
            "skills": ["SQL"],
            "count": len(sql_items),
            "problem_ids": [i["item_id"] for i in sql_items],
            "duration_minutes": 25,
        })
    if not blocks:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This retry set has no runnable MCQ or SQL items.",
        )
    request = StartSessionRequest(**{"blocks": blocks})
    session = start_session(request, authorization=authorization)
    return {
        **session,
        "navigate": f"/interview/{session.get('session_id')}",
        "retry_set_id": set_id,
    }


# ---------------------------------------------------------------------------
# Bookmarks
# ---------------------------------------------------------------------------

def _validate_item(item_type: str, item_id: str) -> dict[str, Any]:
    if item_type not in ITEM_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"item_type must be one of {list(ITEM_TYPES)}.",
        )
    item = _find_item(item_type, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown {item_type} item '{item_id}'.",
        )
    return item


@router.put("/learning/bookmarks")
def put_bookmark(
    request: BookmarkRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    user_id = str(user["id"])
    item = _validate_item(request.item_type, request.item_id)
    try:
        db = get_database()
        existing = db["bookmarks"].find_one({
            "user_id": user_id,
            "item_type": request.item_type,
            "item_id": request.item_id,
        })
        if existing:
            created = False
            created_at = existing.get("created_at")
        else:
            if db["bookmarks"].count_documents({"user_id": user_id}) >= MAX_BOOKMARK_ITEMS:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Bookmark limit reached ({MAX_BOOKMARK_ITEMS}).",
                )
            created_at = datetime.now(timezone.utc)
            db["bookmarks"].insert_one({
                "user_id": user_id,
                "item_type": request.item_type,
                "item_id": request.item_id,
                "created_at": created_at,
            })
            created = True
    except HTTPException:
        raise
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    return {
        "bookmarked": True,
        "created": created,
        "item_type": request.item_type,
        "item_id": request.item_id,
        "title": _item_title(request.item_type, item),
        "created_at": created_at,
    }


@router.delete("/learning/bookmarks")
def delete_bookmark(
    item_type: str = Query(...),
    item_id: str = Query(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    if item_type not in ITEM_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"item_type must be one of {list(ITEM_TYPES)}.",
        )
    try:
        db = get_database()
        db["bookmarks"].delete_one({
            "user_id": str(user["id"]),
            "item_type": item_type,
            "item_id": item_id,
        })
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    return {"bookmarked": False, "item_type": item_type, "item_id": item_id}


@router.get("/learning/bookmarks/me")
def list_my_bookmarks(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        db = get_database()
        docs = list(db["bookmarks"].find({"user_id": str(user["id"])}))
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    items = []
    for doc in docs:
        item = _find_item(str(doc.get("item_type")), str(doc.get("item_id")))
        if item is None:
            continue
        items.append({
            "item_type": doc.get("item_type"),
            "item_id": doc.get("item_id"),
            "title": _item_title(str(doc.get("item_type")), item),
            "skill": _item_skill(str(doc.get("item_type")), item),
            "difficulty": item.get("difficulty"),
            "created_at": doc.get("created_at"),
        })
    items.sort(key=lambda b: str(b.get("created_at") or ""), reverse=True)
    return {"bookmarks": items}


# ---------------------------------------------------------------------------
# Assistance recording, hints, explanations
# ---------------------------------------------------------------------------

def _record_assistance(
    db: Any,
    *,
    user_id: str,
    item_type: str,
    item_id: str,
    kind: str,
    session_id: str | None = None,
    round_number: int | None = None,
) -> dict[str, Any]:
    session_doc = None
    if session_id:
        try:
            session_doc = db["sessions"].find_one({"session_id": session_id})
        except Exception:
            session_doc = {"session_id": session_id, "user_id": user_id}
    from modules.teaching_exposures import record_teaching_exposure

    exposure = record_teaching_exposure(
        db,
        kind=kind,
        item_type=item_type,
        item_id=item_id,
        session=session_doc or {"session_id": session_id, "user_id": user_id},
        user_id=user_id,
        round_number=round_number,
        also_legacy_assistance=True,
    )
    if exposure:
        return {
            "id": exposure.get("id"),
            "user_id": user_id,
            "item_type": item_type,
            "item_id": item_id,
            "kind": kind,
            "session_id": session_id,
            "round": round_number,
            "created_at": exposure.get("created_at"),
            "delivery_id": exposure.get("delivery_id"),
        }
    event = {
        "id": str(uuid4()),
        "user_id": user_id,
        "item_type": item_type,
        "item_id": item_id,
        "kind": kind,
        "session_id": session_id,
        "round": round_number,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        db["assistance_events"].insert_one(event)
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    return event


@router.post("/learning/assistance")
def post_assistance(
    request: AssistanceRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    user_id = str(user["id"])
    if request.kind not in ASSISTANCE_KINDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"kind must be one of {list(ASSISTANCE_KINDS)}.",
        )
    _validate_item(request.item_type, request.item_id)
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    if request.session_id:
        session = db["sessions"].find_one({"session_id": request.session_id})
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
            )
        if str(session.get("user_id") or "") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot record assistance on another user's session.",
            )
    event = _record_assistance(
        db,
        user_id=user_id,
        item_type=request.item_type,
        item_id=request.item_id,
        kind=request.kind,
        session_id=request.session_id,
        round_number=request.round,
    )
    return {"recorded": True, "id": event["id"]}


@router.get("/learning/hint")
def get_hint(
    item_type: str = Query(...),
    item_id: str = Query(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Public hint plus local resources; the view is recorded as assistance.

    Hint content is restricted to facts already visible to the candidate
    (skills, topics, signatures, example counts) plus existing local
    resource records. Nothing here reveals answers, keys, or solutions.
    """
    user = require_user(authorization)
    item = _validate_item(item_type, item_id)
    skill = _item_skill(item_type, item)
    if item_type == "mcq":
        hint = {
            "skill": skill,
            "sub_domain": item.get("sub_domain"),
            "difficulty": item.get("difficulty"),
            "selection_mode": item.get("selection_mode", "single"),
            "negative_marking": float(item.get("negative_marking", 0.0)),
            "guidance": (
                "Review the topic resources below, eliminate options "
                "against the stem, then retry."
            ),
        }
    elif item_type == "sql":
        hint = {
            "skill": skill,
            "difficulty": item.get("difficulty"),
            "has_schema": bool(item.get("schema_ddl")),
            "guidance": (
                "Study the schema and the visible sample case, then build "
                "the query incrementally with Run."
            ),
        }
    else:
        hint = {
            "skill": skill,
            "topics": list(item.get("topics") or []),
            "difficulty": item.get("difficulty"),
            "function": item.get("function"),
            "visible_example_count": len(item.get("visible_tests") or []),
            "guidance": (
                "Re-read the constraints and trace the visible examples by "
                "hand before coding."
            ),
        }
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    _record_assistance(
        db, user_id=str(user["id"]),
        item_type=item_type, item_id=item_id, kind="hint",
    )
    return {
        "item_type": item_type,
        "item_id": item_id,
        "title": _item_title(item_type, item),
        "hint": hint,
        "editorial": None,
        "editorial_reason": "No editorial is published for this item.",
        "resources": _resources_for_skill(skill),
    }


@router.get("/learning/explanation")
def get_explanation(
    item_type: str = Query(...),
    item_id: str = Query(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Serve one bank explanation after a recorded attempt; record the view.

    Explanations unlock per item once the requesting user has a submitted
    round evaluating that item. Nothing is served for unattempted items,
    and SQL/coding banks publish no editorials (honest absence + local
    resources instead). The served view is recorded as solution use.
    """
    user = require_user(authorization)
    user_id = str(user["id"])
    item = _validate_item(item_type, item_id)
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    skill = _item_skill(item_type, item)
    if item_type != "mcq":
        return {
            "item_type": item_type,
            "item_id": item_id,
            "available": False,
            "reason": "no_editorial_available",
            "resources": _resources_for_skill(skill),
        }
    sessions = _owned_sessions(db, user_id)
    if not _has_submitted_attempt(sessions, item_type, item_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This explanation unlocks after you submit an attempt "
            "on this question.",
        )
    _record_assistance(
        db, user_id=user_id,
        item_type=item_type, item_id=item_id, kind="explanation",
    )
    return {
        "item_type": item_type,
        "item_id": item_id,
        "available": True,
        "explanation": item.get("explanation"),
        "resources": _resources_for_skill(skill),
    }


# ---------------------------------------------------------------------------
# Item status (untried / attempted / solved, honestly split for coding)
# ---------------------------------------------------------------------------

def _mcq_item_outcomes(
    sessions: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    from backend.evidence_kind import is_practice_review_round

    outcomes: dict[str, dict[str, Any]] = {}
    for session in sessions:
        if (session.get("round_config") or {}).get("purpose") == SPACED_REVIEW_PURPOSE:
            continue
        for round_doc in session.get("rounds") or []:
            if round_doc.get("round_type") != "mcq":
                continue
            if round_doc.get("final_score") is None:
                continue
            if is_practice_review_round(round_doc):
                continue
            for answered in (round_doc.get("artifact_json") or {}).get("questions") or []:
                item_id = str(answered.get("question_id"))
                slot = outcomes.setdefault(
                    item_id, {"attempts": 0, "solved": False, "assisted": False}
                )
                slot["attempts"] += 1
                if answered.get("is_correct"):
                    slot["solved"] = True
                if round_doc.get("assisted"):
                    slot["assisted"] = True
    return outcomes


def _problem_outcomes(
    sessions: list[dict[str, Any]], round_type: str
) -> dict[str, dict[str, Any]]:
    from backend.evidence_kind import is_practice_review_round

    outcomes: dict[str, dict[str, Any]] = {}
    for session in sessions:
        if (session.get("round_config") or {}).get("purpose") == SPACED_REVIEW_PURPOSE:
            continue
        for round_doc in session.get("rounds") or []:
            if round_doc.get("round_type") != round_type:
                continue
            if round_doc.get("final_score") is None:
                continue
            if is_practice_review_round(round_doc):
                continue
            config = round_doc.get("config_json") or {}
            item_id = str(config.get("problem_id") or "")
            if not item_id:
                continue
            slot = outcomes.setdefault(
                item_id,
                {"attempts": 0, "solved": False, "assisted": False,
                 "best_score": None},
            )
            slot["attempts"] += 1
            score = float(round_doc.get("final_score"))
            if slot["best_score"] is None or score > slot["best_score"]:
                slot["best_score"] = score
            if score >= 100.0:
                slot["solved"] = True
            if round_doc.get("assisted"):
                slot["assisted"] = True
    return outcomes


@router.get("/learning/item-status/me")
def get_my_item_status(
    item_type: str = Query(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Per-item attempt states for one bank.

    Coding states distinguish attempted-without-score (execution
    unavailable) from scored attempts; nothing is ever marked solved
    without a recorded score of 100.
    """
    user = require_user(authorization)
    if item_type not in ITEM_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"item_type must be one of {list(ITEM_TYPES)}.",
        )
    user_id = str(user["id"])
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    sessions = _owned_sessions(db, user_id)
    if item_type == "mcq":
        from backend.db.phase2_content_bank import PHASE2_MCQ_BANK
        from backend.db.phase21_verbal_bank import PHASE21_VERBAL_BANK

        bank_ids = [q.get("id") for q in list(PHASE2_MCQ_BANK) + list(PHASE21_VERBAL_BANK)]
        outcomes = _mcq_item_outcomes(sessions)
    elif item_type == "sql":
        from backend.db.phase2_content_bank import PHASE2_SQL_BANK

        bank_ids = [p.get("id") for p in PHASE2_SQL_BANK]
        outcomes = _problem_outcomes(sessions, "sql")
    else:
        from backend.db.phase_c_coding_bank import CODING_PROBLEMS

        bank_ids = [p.get("id") for p in CODING_PROBLEMS]
        outcomes = _problem_outcomes(sessions, "coding")
        # Unevaluated coding submits are attempts without scores.
        try:
            submissions = list(db["coding_submissions"].find({"user_id": user_id}))
        except Exception as exc:
            if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
                ) from exc
            raise
        for row in submissions:
            item_id = str(row.get("problem_id") or "")
            if not item_id:
                continue
            slot = outcomes.setdefault(
                item_id,
                {"attempts": 0, "solved": False, "assisted": False,
                 "best_score": None},
            )
            if row.get("status") == "scored" and row.get("score") is not None:
                slot["attempts"] += 1
                score = float(row["score"])
                if slot["best_score"] is None or score > slot["best_score"]:
                    slot["best_score"] = score
                if score >= 100.0:
                    slot["solved"] = True
            else:
                slot["attempts"] += 1
                slot["unscored_attempts"] = int(slot.get("unscored_attempts") or 0) + 1
    states: dict[str, dict[str, Any]] = {}
    for item_id in bank_ids:
        outcome = outcomes.get(str(item_id))
        if not outcome:
            states[str(item_id)] = {"state": "untried", "attempts": 0}
        elif outcome.get("solved"):
            states[str(item_id)] = {
                "state": "solved",
                "attempts": outcome["attempts"],
                "assisted": bool(outcome.get("assisted")),
                "best_score": outcome.get("best_score"),
            }
        elif outcome.get("unscored_attempts") and outcome.get("best_score") is None:
            states[str(item_id)] = {
                "state": "attempted_unscored",
                "attempts": outcome["attempts"],
                "reason": "execution_unavailable",
            }
        else:
            states[str(item_id)] = {
                "state": "attempted",
                "attempts": outcome["attempts"],
                "assisted": bool(outcome.get("assisted")),
                "best_score": outcome.get("best_score"),
            }
    return {"item_type": item_type, "states": states}


# ---------------------------------------------------------------------------
# Next steps
# ---------------------------------------------------------------------------

@router.get("/learning/next-steps/me")
def get_my_next_steps(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Evidence-backed next-practice suggestions.

    Every suggestion cites the recorded evidence behind it (miss counts,
    weak areas, target role). With no evidence, the response is an empty
    state, not invented recommendations.
    """
    user = require_user(authorization)
    user_id = str(user["id"])
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    sessions = _owned_sessions(db, user_id)
    entries, coverage = _notebook_entries(sessions, db, user_id)
    suggestions: list[dict[str, Any]] = []

    # Missed topics first: each cites miss counts and the split.
    by_skill: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        by_skill.setdefault(str(entry.get("skill") or "General"), []).append(entry)
    for skill in sorted(by_skill, key=lambda s: (-len(by_skill[s]), s)):
        group = by_skill[skill]
        assisted = sum(1 for e in group if e["assisted"])
        suggestions.append({
            "id": f"retry-topic:{skill}",
            "kind": "retry_topic",
            "title": f"Retry {skill}",
            "detail": (
                f"{len(group)} recorded miss{'es' if len(group) != 1 else ''} "
                f"({len(group) - assisted} unassisted, {assisted} assisted)."
            ),
            "evidence": {
                "misses": len(group),
                "unassisted_misses": len(group) - assisted,
                "assisted_misses": assisted,
                "entry_kinds": sorted({str(e.get("kind")) for e in group}),
            },
            "action": {"type": "retry_set", "skills": [skill]},
            "resources": _resources_for_skill(skill),
        })

    # Target weak areas next (only when a target role is set and the gap
    # engine can compute it); each cites tested/untested evidence.
    context = db["target_contexts"].find_one({"user_id": user_id}) or {}
    role_id = context.get("role_id") or user.get("target_role_id")
    if role_id:
        try:
            from modules.gap_analysis import GapAnalyzer

            report = GapAnalyzer().compute_gap(user_id, role_id).to_dict()
        except Exception:
            report = None
        if report:
            for weak in (report.get("ranked_weak_areas") or [])[:3]:
                skill = str(weak.get("skill"))
                if any(s["id"] == f"retry-topic:{skill}" for s in suggestions):
                    continue
                suggestions.append({
                    "id": f"weak-area:{skill}",
                    "kind": "weak_area",
                    "title": f"Close the {weak.get('display_name') or skill} gap",
                    "detail": (
                        f"Severity {weak.get('gap_severity')} for role "
                        f"{report.get('role_title')}; "
                        + (
                            "no attempts recorded yet."
                            if not weak.get("tested")
                            else f"current level {weak.get('student_level')} "
                            f"against required {weak.get('required_level')}."
                        )
                    ),
                    "evidence": {
                        "role_id": role_id,
                        "tested": bool(weak.get("tested")),
                        "student_level": weak.get("student_level"),
                        "required_level": weak.get("required_level"),
                        "gap_severity": weak.get("gap_severity"),
                    },
                    "action": {"type": "practice", "skills": [skill]},
                    "resources": _resources_for_skill(skill),
                })

    if not suggestions:
        return {
            "suggestions": [],
            "coverage": coverage,
            "empty_reason": (
                "no_scored_attempts"
                if coverage["scored_rounds_scanned"] == 0
                else "no_actionable_gaps"
            ),
        }
    return {"suggestions": suggestions, "coverage": coverage, "empty_reason": None}


# ---------------------------------------------------------------------------
# Phase I: spaced-review schedule
# ---------------------------------------------------------------------------


def _public_schedule(doc: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    when = now or datetime.now(timezone.utc)
    available = bool(doc.get("review_available", True))
    return {
        "id": doc.get("id"),
        "item_type": doc.get("item_type"),
        "item_id": doc.get("item_id"),
        "skill": doc.get("skill"),
        "title": doc.get("title"),
        "miss_reason": doc.get("miss_reason"),
        "originating_assisted": doc.get("originating_assisted"),
        "interval_days": doc.get("interval_days"),
        "interval_index": doc.get("interval_index"),
        "interval_ladder": list(INTERVAL_LADDER),
        "due_at": doc.get("due_at"),
        "is_due": is_due(doc, now=when),
        "review_count": doc.get("review_count") or 0,
        "last_reviewed_at": doc.get("last_reviewed_at"),
        "last_outcome": doc.get("last_outcome"),
        "last_review_assisted": doc.get("last_review_assisted"),
        "review_available": available,
        "unavailable_reason": doc.get("unavailable_reason"),
        "status": (
            "due_but_unavailable"
            if (is_due(doc, now=when) and not available)
            else ("due" if is_due(doc, now=when) else "scheduled")
        ),
    }


def _miss_reason_for_entry(entry: dict[str, Any]) -> str:
    kind = entry.get("kind")
    if kind == "mcq_miss":
        return "Missed MCQ"
    if kind == "sql_miss":
        return "Missed SQL problem"
    if kind == "interview_miss":
        return "Interview score below Good band"
    return "Recorded miss"


def _sync_schedules_for_user(db: Any, user_id: str) -> dict[str, Any]:
    """Ensure schedule rows exist for notebook misses + coding attempts.

    Existing rows keep their interval state. New rows are due now (honest for
    pre-feature history — no invented past schedule).
    """
    sessions = _owned_sessions(db, user_id)
    entries, coverage = _notebook_entries(sessions, db, user_id)
    existing = {
        (str(d.get("item_type")), str(d.get("item_id"))): d
        for d in db["review_schedules"].find({"user_id": user_id})
    }
    now = datetime.now(timezone.utc)
    created = 0
    for entry in entries:
        item_type = entry.get("item_type")
        item_id = entry.get("item_id")
        if not item_type or not item_id:
            continue  # interview_miss has no stable item_id
        key = (str(item_type), str(item_id))
        if key in existing:
            continue
        doc = {
            "id": str(uuid4()),
            "user_id": user_id,
            "item_type": str(item_type),
            "item_id": str(item_id),
            "skill": entry.get("skill"),
            "title": (entry.get("title") or "")[:255] or None,
            "source_session_id": entry.get("session_id"),
            "source_round": entry.get("round"),
            "originating_assisted": bool(entry.get("assisted")),
            "miss_reason": _miss_reason_for_entry(entry),
            "interval_days": ladder_days_at(0),
            "interval_index": 0,
            "due_at": now,
            "review_count": 0,
            "last_reviewed_at": None,
            "last_outcome": None,
            "last_review_assisted": None,
            "review_available": True,
            "unavailable_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        db["review_schedules"].insert_one(doc)
        existing[key] = doc
        created += 1

    # Coding attempts: scheduled as due-but-unavailable (never scored here).
    for session in sessions:
        if (session.get("round_config") or {}).get("purpose") == SPACED_REVIEW_PURPOSE:
            continue
        for round_doc in session.get("rounds") or []:
            if round_doc.get("round_type") != "coding":
                continue
            ctx = round_doc.get("question_context") or {}
            config = round_doc.get("config_json") or {}
            item_id = (
                ctx.get("problem_id")
                or config.get("problem_id")
                or (ctx.get("id") if isinstance(ctx.get("id"), str) else None)
            )
            if not item_id:
                continue
            key = ("coding", str(item_id))
            if key in existing:
                continue
            title = (ctx.get("title") or str(item_id))[:255]
            doc = {
                "id": str(uuid4()),
                "user_id": user_id,
                "item_type": "coding",
                "item_id": str(item_id),
                "skill": "DSA",
                "title": title,
                "source_session_id": session.get("session_id"),
                "source_round": round_doc.get("round"),
                "originating_assisted": bool(round_doc.get("assisted")),
                "miss_reason": "Coding attempt (execution unavailable)",
                "interval_days": ladder_days_at(0),
                "interval_index": 0,
                "due_at": now,
                "review_count": 0,
                "last_reviewed_at": None,
                "last_outcome": None,
                "last_review_assisted": None,
                "review_available": False,
                "unavailable_reason": "execution_unavailable",
                "created_at": now,
                "updated_at": now,
            }
            db["review_schedules"].insert_one(doc)
            existing[key] = doc
            created += 1

    return {
        "created": created,
        "total": len(existing),
        "notebook_entries_considered": len(entries),
        "coding_rounds_disclosed": coverage.get("excluded_coding_rounds") or 0,
    }


@router.post("/learning/reviews/sync")
def sync_review_schedules(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        db = get_database()
        result = _sync_schedules_for_user(db, str(user["id"]))
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    return {"synced": True, **result, "interval_ladder": list(INTERVAL_LADDER)}


@router.get("/learning/reviews/due")
def list_due_reviews(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    user_id = str(user["id"])
    try:
        db = get_database()
        _sync_schedules_for_user(db, user_id)
        docs = list(db["review_schedules"].find({"user_id": user_id}))
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    now = datetime.now(timezone.utc)
    due = [_public_schedule(d, now=now) for d in docs if is_due(d, now=now)]
    due.sort(key=lambda d: (not d.get("review_available", True), str(d.get("due_at") or "")))
    available_due = sum(1 for d in due if d.get("review_available"))
    unavailable_due = sum(1 for d in due if not d.get("review_available"))
    empty_reason = None
    if not due:
        empty_reason = (
            "no_scheduled_items"
            if not docs
            else "nothing_due"
        )
    return {
        "due_count": len(due),
        "available_due_count": available_due,
        "unavailable_due_count": unavailable_due,
        "items": due,
        "interval_ladder": list(INTERVAL_LADDER),
        "empty_reason": empty_reason,
        "note": (
            None
            if unavailable_due == 0
            else (
                f"{unavailable_due} coding item(s) are due but cannot be reviewed "
                "while execution is unavailable. They are not scores and not zeros."
            )
        ),
    }


@router.get("/learning/reviews/me")
def list_my_review_schedules(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    user_id = str(user["id"])
    try:
        db = get_database()
        _sync_schedules_for_user(db, user_id)
        docs = list(db["review_schedules"].find({"user_id": user_id}))
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    now = datetime.now(timezone.utc)
    items = [_public_schedule(d, now=now) for d in docs]
    items.sort(key=lambda d: str(d.get("due_at") or ""))
    return {
        "items": items,
        "count": len(items),
        "interval_ladder": list(INTERVAL_LADDER),
        "empty_reason": None if items else "no_scheduled_items",
    }


def _blocks_from_schedule_items(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from backend.db.phase21_verbal_bank import PHASE21_VERBAL_BANK

    verbal_ids = {q.get("id") for q in PHASE21_VERBAL_BANK}
    runnable = [
        i for i in items
        if i.get("review_available") and i.get("item_type") in ("mcq", "sql")
    ]
    verbal_items = [
        i for i in runnable
        if i.get("item_type") == "mcq" and i.get("item_id") in verbal_ids
    ]
    oa_items = [
        i for i in runnable
        if i.get("item_type") == "mcq" and i.get("item_id") not in verbal_ids
    ]
    sql_items = [i for i in runnable if i.get("item_type") == "sql"]
    blocks: list[dict[str, Any]] = []
    if verbal_items:
        blocks.append({
            "round_type": "mcq",
            "category": "verbal",
            "skills": ["Verbal Ability"],
            "count": len(verbal_items),
            "question_ids": [i["item_id"] for i in verbal_items],
            "duration_minutes": 20,
        })
    if oa_items:
        skills = sorted({str(i.get("skill") or "General") for i in oa_items})
        blocks.append({
            "round_type": "mcq",
            "category": "oa",
            "skills": [s for s in skills if s != "Verbal Ability"] or ["DBMS"],
            "count": len(oa_items),
            "question_ids": [i["item_id"] for i in oa_items],
            "duration_minutes": 20,
        })
    if sql_items:
        blocks.append({
            "round_type": "sql",
            "category": "sql",
            "skills": ["SQL"],
            "count": len(sql_items),
            "problem_ids": [i["item_id"] for i in sql_items],
            "duration_minutes": 25,
        })
    return blocks, runnable


@router.post("/learning/reviews/start")
def start_due_reviews(
    request: ReviewStartRequest | None = None,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Start a normal block session composed of due, reviewable items."""
    user = require_user(authorization)
    user_id = str(user["id"])
    body = request or ReviewStartRequest()
    max_items = int(body.max_items or 5)
    if max_items < 1 or max_items > MAX_REVIEW_START_ITEMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"max_items must be 1-{MAX_REVIEW_START_ITEMS}.",
        )
    try:
        db = get_database()
        _sync_schedules_for_user(db, user_id)
        docs = list(db["review_schedules"].find({"user_id": user_id}))
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        raise
    now = datetime.now(timezone.utc)
    due_docs = [d for d in docs if is_due(d, now=now)]
    # Unassisted originating misses first, then assisted; skip unavailable unless asked.
    def _sort_key(d: dict[str, Any]) -> tuple:
        return (
            0 if d.get("review_available") else 1,
            1 if d.get("originating_assisted") else 0,
            str(d.get("due_at") or ""),
        )

    due_docs.sort(key=_sort_key)
    if not body.include_unavailable:
        candidates = [d for d in due_docs if d.get("review_available")]
    else:
        candidates = list(due_docs)
    chosen = candidates[:max_items]
    blocks, runnable = _blocks_from_schedule_items(chosen)
    if not blocks:
        unavailable_only = bool(due_docs) and not any(d.get("review_available") for d in due_docs)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Due items are coding-only and cannot be reviewed while "
                "execution is unavailable."
                if unavailable_only
                else "No due reviewable items. Sync from recorded misses first."
            ),
        )
    # Persist a retry_set-shaped doc so we reuse the same start path machinery,
    # then tag the session as spaced_review so scoring cannot raise mastery.
    set_doc = {
        "id": str(uuid4()),
        "user_id": user_id,
        "name": f"Spaced review ({len(runnable)} items)",
        "items": [
            {
                "item_type": d["item_type"],
                "item_id": d["item_id"],
                "skill": d.get("skill"),
                "reason": "spaced-review-due",
                "miss_assisted": d.get("originating_assisted"),
                "schedule_id": d.get("id"),
            }
            for d in runnable
        ],
        "source": "spaced-review",
        "created_at": now,
    }
    db["retry_sets"].insert_one(set_doc)
    session = start_session(
        StartSessionRequest(**{"blocks": blocks}),
        authorization=authorization,
    )
    sid = session.get("session_id")
    # Map expanded rounds to schedule ids by item identity.
    stored = db["sessions"].find_one({"session_id": sid}) or {}
    review_map: dict[str, str] = {}
    by_item = {(i["item_type"], i["item_id"]): i["schedule_id"] for i in set_doc["items"]}
    for round_doc in stored.get("rounds") or []:
        rtype = round_doc.get("round_type")
        ctx = round_doc.get("question_context") or {}
        config = round_doc.get("config_json") or {}
        if rtype == "mcq":
            questions = (ctx.get("questions") or [])
            # One MCQ block may hold many questions in one round.
            for q in questions:
                qid = str(q.get("id") or "")
                sid_sched = by_item.get(("mcq", qid))
                if sid_sched:
                    review_map.setdefault(str(round_doc.get("round")), sid_sched)
                    # Also store multi-question map under round config later.
            # Prefer listing all schedule ids for the round.
            ids = [
                by_item[("mcq", str(q.get("id")))]
                for q in questions
                if ("mcq", str(q.get("id"))) in by_item
            ]
            if ids:
                review_map[str(round_doc.get("round"))] = ids[0] if len(ids) == 1 else ",".join(ids)
        elif rtype == "sql":
            pid = str(config.get("problem_id") or ctx.get("problem_id") or "")
            if ("sql", pid) in by_item:
                review_map[str(round_doc.get("round"))] = by_item[("sql", pid)]
    existing_cfg = dict(stored.get("round_config") or {})
    existing_cfg["purpose"] = SPACED_REVIEW_PURPOSE
    existing_cfg["review_map"] = review_map
    existing_cfg["review_set_id"] = set_doc["id"]
    from backend.db.sqlalchemy_store import SessionWriteConflict

    try:
        db["sessions"].update_one(
            {"session_id": sid},
            {"$set": {"round_config": existing_cfg}},
            expected_revision=stored.get("revision"),
        )
    except SessionWriteConflict:
        # Someone committed on this just-created session first (only
        # possible across workers): re-merge the review stamp onto the
        # fresh config once rather than clobbering their write.
        fresh = db["sessions"].find_one({"session_id": sid}) or {}
        if not fresh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
            ) from None
        fresh_cfg = dict(fresh.get("round_config") or {})
        fresh_cfg["purpose"] = SPACED_REVIEW_PURPOSE
        fresh_cfg["review_map"] = review_map
        fresh_cfg["review_set_id"] = set_doc["id"]
        try:
            db["sessions"].update_one(
                {"session_id": sid},
                {"$set": {"round_config": fresh_cfg}},
                expected_revision=fresh.get("revision"),
            )
        except SessionWriteConflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Concurrent session update; retry the request.",
            ) from None
    return {
        **session,
        "navigate": f"/interview/{sid}",
        "purpose": SPACED_REVIEW_PURPOSE,
        "review_set_id": set_doc["id"],
        "review_item_count": len(runnable),
        "interval_ladder": list(INTERVAL_LADDER),
    }


def apply_review_outcome_for_session_round(
    db: Any,
    session: dict[str, Any],
    round_doc: dict[str, Any],
    *,
    assisted: bool,
) -> list[dict[str, Any]]:
    """Update schedule rows after a spaced-review submit. No mastery changes."""
    from backend.review_schedule import OUTCOME_CORRECT, OUTCOME_INCORRECT, review_correct_for_round

    cfg = session.get("round_config") or {}
    if cfg.get("purpose") != SPACED_REVIEW_PURPOSE:
        return []
    correct = review_correct_for_round(round_doc)
    if correct is None:
        return []
    outcome = OUTCOME_CORRECT if correct else OUTCOME_INCORRECT
    review_map = cfg.get("review_map") or {}
    raw = review_map.get(str(round_doc.get("round")))
    if not raw:
        return []
    schedule_ids = [s for s in str(raw).split(",") if s]
    # Multi-question MCQ: refine per question when possible.
    updates: list[dict[str, Any]] = []
    artifact = round_doc.get("artifact_json") or {}
    per_q = {
        str(q.get("question_id") or q.get("id")): bool(q.get("is_correct"))
        for q in (artifact.get("questions") or [])
        if isinstance(q, dict)
    }
    now = datetime.now(timezone.utc)
    for schedule_id in schedule_ids:
        doc = db["review_schedules"].find_one({"id": schedule_id})
        if not doc:
            continue
        if str(doc.get("user_id")) != str(session.get("user_id")):
            continue
        if not doc.get("review_available", True):
            continue
        item_outcome = outcome
        if doc.get("item_type") == "mcq" and doc.get("item_id") in per_q:
            item_outcome = (
                OUTCOME_CORRECT if per_q[str(doc["item_id"])] else OUTCOME_INCORRECT
            )
        nxt = advance_after_outcome(
            interval_index=int(doc.get("interval_index") or 0),
            outcome=item_outcome,
            now=now,
        )
        patch = {
            **nxt,
            "review_count": int(doc.get("review_count") or 0) + 1,
            "last_review_assisted": bool(assisted),
            "updated_at": now,
        }
        db["review_schedules"].update_one({"id": schedule_id}, {"$set": patch})
        updates.append({**doc, **patch})
    return updates
