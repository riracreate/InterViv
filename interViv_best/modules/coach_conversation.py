"""Multi-turn guidance coach with deterministic fallback (Phase 4B).

Planning clarification is not automatically teaching exposure. Structured
goals stay separate from transcript text. A typed planning task may rewrite
wording via a fake/gated provider; invented gaps/scores/resources/plan
mutations are rejected and the deterministic reply is retained.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from modules.guidance_coach import (
    MAX_INPUT_CHARS,
    map_phrase_to_skills,
    sanitize_user_text,
)
from modules.roadmap_plans import (
    DEFAULT_HOURS_PER_WEEK,
    complete_task,
    ensure_plan,
    get_active_plan,
)

CONVERSATION_SCHEMA = "coach_conversation_v1"
MAX_MESSAGES = 40
MAX_MESSAGE_CHARS = 2000
PLANNING_TASK = "plan_explanation_v1"

_MEMORY_CONVOS: dict[str, dict[str, Any]] = {}  # conversation_id -> doc
_MEMORY_BY_OWNER: dict[str, str] = {}  # owner_key -> conversation_id

# Injected fake provider for tests: (task, payload) -> structured dict | raise
_PLANNING_PROVIDER: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None


def set_planning_provider(fn: Callable[[str, dict[str, Any]], dict[str, Any]] | None) -> None:
    global _PLANNING_PROVIDER
    _PLANNING_PROVIDER = fn


def reset_memory_store() -> None:
    _MEMORY_CONVOS.clear()
    _MEMORY_BY_OWNER.clear()


def snapshot_memory_store() -> dict[str, Any]:
    return {
        "convos": copy.deepcopy(_MEMORY_CONVOS),
        "by_owner": copy.deepcopy(_MEMORY_BY_OWNER),
    }


def restore_memory_store(snapshot: dict[str, Any] | None) -> None:
    if not snapshot:
        return
    _MEMORY_CONVOS.clear()
    _MEMORY_CONVOS.update(copy.deepcopy(snapshot.get("convos") or {}))
    _MEMORY_BY_OWNER.clear()
    _MEMORY_BY_OWNER.update(copy.deepcopy(snapshot.get("by_owner") or {}))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _using_sqlalchemy() -> bool:
    from backend.config import get_settings

    return bool(get_settings().database_url)


def owner_key(user_id: str | None, guest_session_id: str | None = None) -> str:
    if user_id:
        return f"user:{user_id}"
    if guest_session_id:
        return f"guest:{guest_session_id}"
    raise ValueError("owner required")


def _clip(text: str, limit: int = MAX_MESSAGE_CHARS) -> str:
    return sanitize_user_text(text)[:limit]


def classify_action_kind(action: str | None, *, delivers_help: bool = False) -> str:
    """Trusted application classification — never trust a model-provided flag."""
    if delivers_help:
        return "teaching"
    action = (action or "").strip().lower()
    if action in {"hint", "explanation", "solution", "reveal"}:
        return "teaching"
    return "planning"


def _deterministic_reply(
    *,
    goals: dict[str, Any],
    plan: dict[str, Any] | None,
    user_text: str,
) -> dict[str, Any]:
    text = (user_text or "").lower()
    clarifying: list[str] = []
    actions: list[dict[str, Any]] = []
    kind = "planning"

    if not goals.get("confirmed_goal") and not goals.get("role_id"):
        clarifying.append("What role or interview goal should we plan for?")
    if goals.get("hours_per_week") is None:
        clarifying.append(
            f"How many hours per week can you study? (default {DEFAULT_HOURS_PER_WEEK})"
        )

    if plan is None:
        body = (
            "I can build a starter study plan from your confirmed goal. "
            "No readiness percentage is invented without eligible assessment evidence."
        )
        actions.append({"type": "create_plan", "label": "Build starter plan"})
    else:
        meta = plan.get("meta") or {}
        tasks = plan.get("tasks") or []
        pending = [t for t in tasks if t.get("status") != "completed"]
        next_task = pending[0] if pending else None
        body_parts = [
            f"Plan v{plan.get('version')} ({meta.get('plan_kind', 'plan')}).",
            str(meta.get("readiness_note") or ""),
        ]
        if next_task:
            body_parts.append(
                f"Next task: {next_task.get('title')} — {next_task.get('rationale')}"
            )
            actions.append(
                {
                    "type": "start_task",
                    "label": "Start recommended practice",
                    "task_id": next_task.get("task_id"),
                    "href": next_task.get("practice_href"),
                    "skill": next_task.get("skill"),
                }
            )
            actions.append(
                {
                    "type": "complete_task",
                    "label": "Mark task complete",
                    "task_id": next_task.get("task_id"),
                }
            )
        if "time" in text or "hour" in text:
            body_parts.append(
                "Say how many hours per week you can study and I will version "
                "the plan without dropping completion history."
            )
            actions.append({"type": "update_hours", "label": "Update study time"})
        if "explain" in text or "why" in text:
            if next_task:
                body_parts.append(
                    f"Why this task: {next_task.get('rationale')} "
                    f"(evidence population: {next_task.get('population')})."
                )
        if meta.get("plan_kind") == "assisted_practice":
            body_parts.append(
                "Assistance-only evidence supports practice labels only. "
                "Assess independently before treating skills as mastered."
            )
            actions.append(
                {
                    "type": "assess_independently",
                    "label": "Start independent assessment",
                    "href": "/practice?mode=full&practice_mode=assessment",
                }
            )
        body = " ".join(p for p in body_parts if p).strip()

    if clarifying and not plan:
        body = (
            "Before locking a plan, I need a little more detail. "
            + " ".join(clarifying)
        )

    return {
        "kind": kind,
        "mode": "deterministic",
        "message": body,
        "clarifying_questions": clarifying[:3],
        "actions": actions,
        "plan_id": (plan or {}).get("plan_id"),
        "plan_version": (plan or {}).get("version"),
    }


def _validate_provider_output(
    raw: dict[str, Any],
    *,
    plan: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Reject invented gaps/scores/resources/plan mutations."""
    if not isinstance(raw, dict):
        return None
    message = raw.get("message")
    if not isinstance(message, str) or not message.strip():
        return None
    # Invented assessment claims.
    banned = [
        r"\breadiness\s*(?:is|=)?\s*\d",
        r"\bscore\s*(?:is|=)?\s*\d",
        r"\belo\b",
        r"\bmastery\s*(?:is|=)?\s*\d",
        r"guaranteed\s+offer",
        r"will\s+get\s+hired",
    ]
    lower = message.lower()
    for pat in banned:
        if re.search(pat, lower):
            return None
    if raw.get("mutate_plan") or raw.get("mark_complete") or raw.get("new_tasks"):
        return None
    if "invented_gap" in raw or raw.get("gap_score") is not None:
        return None
    allowed_task_ids = {t.get("task_id") for t in (plan or {}).get("tasks") or []}
    for action in raw.get("actions") or []:
        if not isinstance(action, dict):
            return None
        tid = action.get("task_id")
        if tid and tid not in allowed_task_ids:
            return None
        href = action.get("href")
        if href and not str(href).startswith("/"):
            return None
        # Unsupported external resources.
        url = action.get("url") or (action.get("resource") or {}).get("url")
        if url and not _resource_allowed(url, plan):
            return None
    return {
        "kind": "planning",
        "mode": "provider",
        "message": message.strip()[:MAX_MESSAGE_CHARS],
        "clarifying_questions": list(raw.get("clarifying_questions") or [])[:3],
        "actions": list(raw.get("actions") or [])[:6],
        "plan_id": (plan or {}).get("plan_id"),
        "plan_version": (plan or {}).get("version"),
    }


def _resource_allowed(url: str, plan: dict[str, Any] | None) -> bool:
    allowed = set()
    for task in (plan or {}).get("tasks") or []:
        res = task.get("resource") or {}
        if res.get("url"):
            allowed.add(str(res["url"]))
    return str(url) in allowed


def _maybe_provider_rewrite(
    deterministic: dict[str, Any],
    *,
    plan: dict[str, Any] | None,
    goals: dict[str, Any],
    evidence_digest: str | None,
) -> dict[str, Any]:
    if _PLANNING_PROVIDER is None:
        return deterministic
    payload = {
        "task": PLANNING_TASK,
        "owner_goals": goals,
        "evidence_digest": evidence_digest,
        "plan_id": (plan or {}).get("plan_id"),
        "plan_version": (plan or {}).get("version"),
        "deterministic_message": deterministic.get("message"),
        "schema_version": CONVERSATION_SCHEMA,
    }
    try:
        raw = _PLANNING_PROVIDER(PLANNING_TASK, payload)
    except Exception:
        return {**deterministic, "provider_error": "provider_failed"}
    validated = _validate_provider_output(raw if isinstance(raw, dict) else {}, plan=plan)
    if validated is None:
        return {**deterministic, "provider_rejected": True}
    return validated


def get_or_create_conversation(
    *,
    user_id: str,
    role_id: str | None = None,
    guest_session_id: str | None = None,
) -> dict[str, Any]:
    key = owner_key(user_id, guest_session_id)
    if _using_sqlalchemy():
        existing = _sql_get_by_owner(key)
        if existing:
            return existing
    else:
        cid = _MEMORY_BY_OWNER.get(key)
        if cid and cid in _MEMORY_CONVOS:
            return copy.deepcopy(_MEMORY_CONVOS[cid])

    doc = {
        "conversation_id": str(uuid.uuid4()),
        "schema_version": CONVERSATION_SCHEMA,
        "owner_key": key,
        "user_id": user_id,
        "role_id": role_id,
        "goals": {
            "confirmed_goal": None,
            "role_id": role_id,
            "hours_per_week": None,
            "planning_context_skills": [],
            "adzuna_context": None,
        },
        "messages": [],
        "created_at": _now().isoformat(),
        "updated_at": _now().isoformat(),
    }
    _save_conversation(doc)
    return doc


def _save_conversation(doc: dict[str, Any]) -> None:
    doc = copy.deepcopy(doc)
    doc["updated_at"] = _now().isoformat()
    # Bound retained history.
    msgs = list(doc.get("messages") or [])
    if len(msgs) > MAX_MESSAGES:
        doc["messages"] = msgs[-MAX_MESSAGES:]
    if _using_sqlalchemy():
        _sql_save(doc)
        return
    _MEMORY_CONVOS[doc["conversation_id"]] = doc
    _MEMORY_BY_OWNER[doc["owner_key"]] = doc["conversation_id"]


def get_conversation(conversation_id: str, *, owner: str) -> dict[str, Any] | None:
    if _using_sqlalchemy():
        doc = _sql_get(conversation_id)
    else:
        doc = _MEMORY_CONVOS.get(conversation_id)
    if not doc:
        return None
    if doc.get("owner_key") != owner:
        return None
    return copy.deepcopy(doc)


def clear_conversation(conversation_id: str, *, owner: str) -> bool:
    doc = get_conversation(conversation_id, owner=owner)
    if not doc:
        return False
    if _using_sqlalchemy():
        _sql_delete(conversation_id)
    else:
        _MEMORY_CONVOS.pop(conversation_id, None)
        if _MEMORY_BY_OWNER.get(owner) == conversation_id:
            _MEMORY_BY_OWNER.pop(owner, None)
    return True


def update_goals(
    conversation_id: str,
    *,
    owner: str,
    confirmed_goal: str | None = None,
    role_id: str | None = None,
    hours_per_week: int | None = None,
    planning_context_skills: list[str] | None = None,
    adzuna_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc = get_conversation(conversation_id, owner=owner)
    if not doc:
        raise KeyError("conversation not found")
    goals = dict(doc.get("goals") or {})
    if confirmed_goal is not None:
        goals["confirmed_goal"] = _clip(confirmed_goal, 500) or None
    if role_id is not None:
        goals["role_id"] = role_id or None
        doc["role_id"] = role_id or None
    if hours_per_week is not None:
        goals["hours_per_week"] = max(1, min(40, int(hours_per_week)))
    if planning_context_skills is not None:
        cleaned = []
        for phrase in planning_context_skills:
            cleaned.extend(map_phrase_to_skills(phrase) or ([phrase] if phrase else []))
        goals["planning_context_skills"] = list(dict.fromkeys(cleaned))[:12]
    if adzuna_context is not None:
        # Candidate-confirmed context only; snippets remain incomplete descriptions.
        goals["adzuna_context"] = {
            "job_id": adzuna_context.get("job_id"),
            "role_title": adzuna_context.get("role_title"),
            "company": adzuna_context.get("company"),
            "snippet_is_incomplete": bool(
                adzuna_context.get("snippet_is_incomplete", True)
            ),
            "confirmed_skills": list(adzuna_context.get("confirmed_skills") or [])[:12],
            "full_jd_provided": bool(adzuna_context.get("full_jd_provided")),
        }
        for skill in goals["adzuna_context"]["confirmed_skills"]:
            if skill not in goals["planning_context_skills"]:
                goals["planning_context_skills"].append(skill)
    doc["goals"] = goals
    _save_conversation(doc)
    return doc


def post_message(
    conversation_id: str,
    *,
    owner: str,
    user_id: str,
    text: str,
    action: str | None = None,
    action_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc = get_conversation(conversation_id, owner=owner)
    if not doc:
        raise KeyError("conversation not found")
    action_kind = classify_action_kind(action, delivers_help=False)
    if action_kind == "teaching":
        # Planning coach does not deliver answer-revealing help.
        raise PermissionError("Teaching actions are not available on the planning coach.")

    goals = dict(doc.get("goals") or {})
    payload = action_payload or {}
    user_text = _clip(text)

    # Explicit validated application actions (not LLM tools).
    plan = None
    if action == "create_plan" or (
        not action and user_text and ("plan" in user_text.lower() or "roadmap" in user_text.lower())
    ):
        plan = ensure_plan(
            user_id,
            role_id=goals.get("role_id") or doc.get("role_id"),
            days=int(payload.get("days") or 30),
            hours_per_week=goals.get("hours_per_week"),
            confirmed_goal=goals.get("confirmed_goal") or user_text,
            planning_context_skills=goals.get("planning_context_skills"),
            regenerate=bool(payload.get("regenerate")),
        )
        if not goals.get("confirmed_goal") and user_text:
            goals["confirmed_goal"] = user_text[:500]
            doc["goals"] = goals
    elif action == "update_hours":
        hours = int(payload.get("hours_per_week") or goals.get("hours_per_week") or DEFAULT_HOURS_PER_WEEK)
        goals["hours_per_week"] = max(1, min(40, hours))
        doc["goals"] = goals
        plan = ensure_plan(
            user_id,
            role_id=goals.get("role_id") or doc.get("role_id"),
            days=int(payload.get("days") or 30),
            hours_per_week=goals["hours_per_week"],
            confirmed_goal=goals.get("confirmed_goal"),
            planning_context_skills=goals.get("planning_context_skills"),
            regenerate=True,
        )
    elif action == "complete_task":
        task_id = str(payload.get("task_id") or "")
        plan = complete_task(
            user_id,
            task_id,
            role_id=goals.get("role_id") or doc.get("role_id"),
            confirmed_goal=goals.get("confirmed_goal"),
            completed=True,
        )
    elif action == "update_goal":
        goals["confirmed_goal"] = _clip(str(payload.get("confirmed_goal") or user_text), 500)
        doc["goals"] = goals
        plan = ensure_plan(
            user_id,
            role_id=goals.get("role_id") or doc.get("role_id"),
            days=int(payload.get("days") or 30),
            hours_per_week=goals.get("hours_per_week"),
            confirmed_goal=goals["confirmed_goal"],
            planning_context_skills=goals.get("planning_context_skills"),
            regenerate=True,
        )
    else:
        plan = get_active_plan(
            user_id,
            role_id=goals.get("role_id") or doc.get("role_id"),
            confirmed_goal=goals.get("confirmed_goal"),
        )

    deterministic = _deterministic_reply(goals=goals, plan=plan, user_text=user_text)
    reply = _maybe_provider_rewrite(
        deterministic,
        plan=plan,
        goals=goals,
        evidence_digest=(plan or {}).get("evidence_digest"),
    )

    messages = list(doc.get("messages") or [])
    if user_text or action:
        messages.append(
            {
                "id": str(uuid.uuid4()),
                "role": "user",
                "text": user_text,
                "action": action,
                "created_at": _now().isoformat(),
            }
        )
    messages.append(
        {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "text": reply["message"],
            "kind": reply.get("kind"),
            "mode": reply.get("mode"),
            "clarifying_questions": reply.get("clarifying_questions") or [],
            "actions": reply.get("actions") or [],
            "created_at": _now().isoformat(),
        }
    )
    doc["messages"] = messages
    doc["goals"] = goals
    doc["active_plan_id"] = (plan or {}).get("plan_id")
    doc["active_plan_version"] = (plan or {}).get("version")
    _save_conversation(doc)
    return {
        "conversation": get_conversation(conversation_id, owner=owner),
        "reply": reply,
        "plan": plan,
    }


def _sql_get_by_owner(owner: str) -> dict[str, Any] | None:
    from backend.db.sqlalchemy_models import CoachConversationRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        row = (
            session.query(CoachConversationRow)
            .filter_by(owner_key=owner)
            .order_by(CoachConversationRow.updated_at.desc())
            .first()
        )
        return copy.deepcopy(row.conversation_json) if row else None


def _sql_get(conversation_id: str) -> dict[str, Any] | None:
    from backend.db.sqlalchemy_models import CoachConversationRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        row = session.query(CoachConversationRow).filter_by(id=conversation_id).one_or_none()
        return copy.deepcopy(row.conversation_json) if row else None


def _sql_save(doc: dict[str, Any]) -> None:
    from backend.db.sqlalchemy_models import CoachConversationRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        row = session.query(CoachConversationRow).filter_by(id=doc["conversation_id"]).one_or_none()
        if row is None:
            session.add(
                CoachConversationRow(
                    id=doc["conversation_id"],
                    owner_key=doc["owner_key"],
                    user_id=doc.get("user_id"),
                    conversation_json=doc,
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
        else:
            if row.owner_key != doc["owner_key"]:
                raise PermissionError("owner mismatch")
            row.conversation_json = doc
            row.updated_at = _now()


def _sql_delete(conversation_id: str) -> None:
    from backend.db.sqlalchemy_models import CoachConversationRow
    from backend.db.sqlalchemy_store import session_scope

    with session_scope() as session:
        row = session.query(CoachConversationRow).filter_by(id=conversation_id).one_or_none()
        if row is not None:
            session.delete(row)
