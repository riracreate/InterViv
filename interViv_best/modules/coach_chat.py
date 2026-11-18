"""Coach chat v1: bounded context, validated-then-streamed replies, caps.

Haiku only tonight. The Gemini paid lane is not built; see the TODO in
``coach_chat_provider`` / ``modules/interview_llm.py``. While
``COACH_CHAT_LLM_ENABLED`` is off (default) every reply is the existing
deterministic coach reply and no provider transport is called.
"""

from __future__ import annotations

import json
import os
import re
import socket
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from modules.interview_llm import PAID_CONVERSATION_MODEL

COACH_CHAT_PURPOSE = "coach_chat"
COACH_CHAT_PROVIDER = "openrouter"
MAX_CONTEXT_TOKENS = 3200
TARGET_CONTEXT_TOKENS = 3000
MAX_RECENT_MESSAGES = 6
REFUSAL_MESSAGE = (
    "I can't help with that while an assessment is open. "
    "Finish or close that assessment, then ask me again."
)
EXPLAIN_24H_NOTE = (
    "Viewing this explanation counts as teaching exposure. A new attempt on "
    "the same item within 24 hours will be marked as practised with help, "
    "not independent assessment."
)
# Anthropic Claude Haiku 4.5 via OpenRouter, checked 2026-11-18.
RATES: dict[str, dict[str, Any]] = {
    PAID_CONVERSATION_MODEL: {
        "model": PAID_CONVERSATION_MODEL,
        "input_usd_per_million": 1.0,
        "output_usd_per_million": 5.0,
        "thinking": "n/a",
        "source": "https://openrouter.ai/api/v1/models",
        "checked": "2026-11-18",
    },
}
PER_USER_DAILY_TURNS = 40
PER_USER_DAILY_USD = 0.50

# Injected fake transport for tests: (context_block, user_message) -> dict.
# Dict keys: message, tool_proposal, prompt_tokens, completion_tokens.
Transport = Callable[[str, str], dict[str, Any]]
_TRANSPORT: Transport | None = None


def set_coach_chat_transport(fn: Transport | None) -> None:
    global _TRANSPORT
    _TRANSPORT = fn


def coach_chat_enabled() -> bool:
    return os.getenv("COACH_CHAT_LLM_ENABLED", "0").strip().lower() in {
        "1", "true", "yes", "on",
    }


def global_daily_usd() -> float:
    try:
        return float(os.getenv("COACH_CHAT_GLOBAL_DAILY_USD", "0.50"))
    except ValueError:
        return 0.50


def coach_chat_provider() -> str:
    provider = os.getenv("INTERVIEW_CONVERSATION_PROVIDER", "openrouter").strip().lower()
    # TODO(gemini_paid): build the paid Gemini lane (gemini-2.5-flash-lite,
    # thinking off, GEMINI_PAID_TIER_CONFIRMED gate) per
    # docs/design/coach_chat_v1.md. Tonight only Haiku/openrouter is built;
    # any other provider is refused and the deterministic reply is served.
    return provider


def estimate_tokens(text: str) -> int:
    return len(text or "") // 4


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _fold(text: Any) -> str:
    return " ".join(str(text or "").lower().split())


def get_coach_role_target(user: dict[str, Any] | None) -> dict[str, Any]:
    """Role line for the context block, from the user's current target.

    TODO(role-target): switch to the role-only target (blueprint id plus the
    level stored on that target) once Phase 2 target storage lands. Tonight
    this reads the current company/role target via ``get_user_target`` and
    resolves it through ``get_blueprint``; the level falls back to ``junior``
    when no level is stored yet.
    """
    from backend.db.user_target import get_user_target
    from modules.role_blueprints import get_blueprint

    stub: dict[str, Any] = user if isinstance(user, dict) else {}
    target: dict[str, Any] = {"company_id": None, "role_id": None}
    try:
        target = get_user_target(stub) if stub.get("id") else target
    except Exception:
        target = {"company_id": None, "role_id": None}
    role_id = target.get("role_id") or stub.get("target_role_id") or stub.get("role_id")
    blueprint = None
    if role_id:
        try:
            blueprint = get_blueprint(str(role_id))
        except Exception:
            blueprint = None
    level = None
    try:
        from backend.db import get_database

        uid = stub.get("id")
        if uid:
            ctx = get_database()["target_contexts"].find_one({"user_id": str(uid)}) or {}
            level = ctx.get("level") or ctx.get("chosen_level")
    except Exception:
        level = None
    if level not in ("intern", "junior", "mid"):
        level = stub.get("level") if stub.get("level") in ("intern", "junior", "mid") else "junior"
    return {
        "company_id": target.get("company_id"),
        "role_id": str(role_id) if role_id else None,
        "blueprint_id": blueprint.get("id") if blueprint else (str(role_id) if role_id else None),
        "title": blueprint.get("title") if blueprint else None,
        "level": level,
    }


# ---------------------------------------------------------------------------
# Number rule
# ---------------------------------------------------------------------------

_LIST_MARKER = re.compile(r"(?m)^\s*\d+\s*[.)]\s+")
_NUMBER = re.compile(r"\d+(?:\.\d+)?%?")


def strip_list_markers(text: str) -> str:
    return _LIST_MARKER.sub("", text or "")


def extract_numbers(text: str) -> list[str]:
    return _NUMBER.findall(strip_list_markers(text or ""))


def _contains_number(haystack: str, needle: str) -> bool:
    return re.search(r"(?<!\d)" + re.escape(needle) + r"(?!\d)", haystack or "") is not None


def validate_number_rule(message: str, context_block: str, user_message: str = "") -> bool:
    """Every number in the reply must appear in context or the user message."""
    allowed_from = f"{context_block or ''}\n{user_message or ''}"
    return all(_contains_number(allowed_from, n) for n in extract_numbers(message or ""))


# ---------------------------------------------------------------------------
# Refusals (checked before any provider call)
# ---------------------------------------------------------------------------

def _is_assessment_session(session: dict[str, Any]) -> bool:
    mode = session.get("practice_mode")
    if mode is None:
        mode = (session.get("round_config") or {}).get("practice_mode")
    return str(mode or "").strip().lower() == "assessment"


def _session_open(session: dict[str, Any], round_doc: dict[str, Any], now: datetime) -> bool:
    if str(session.get("status") or "") in ("completed", "closed", "expired"):
        return False
    expires = _parse_dt(round_doc.get("expires_at"))
    return expires is None or expires > now


def recent_assessment_rounds(
    sessions: list[dict[str, Any]], *, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Assessment rounds opened in the last 3 hours in a live session."""
    now = now or datetime.now(timezone.utc)
    out = []
    for session in sessions or []:
        if not _is_assessment_session(session):
            continue
        for round_doc in session.get("rounds") or []:
            if round_doc.get("status") != "in_progress":
                continue
            started = _parse_dt(round_doc.get("started_at"))
            if started is None or not (timedelta(0) <= now - started <= timedelta(hours=3)):
                continue
            if _session_open(session, round_doc, now):
                out.append(round_doc)
    return out


def _open_round_questions(sessions: list[dict[str, Any]], *, now: datetime) -> list[str]:
    questions = []
    for session in sessions or []:
        for round_doc in session.get("rounds") or []:
            if round_doc.get("status") not in ("in_progress", "ready"):
                continue
            if not _session_open(session, round_doc, now):
                continue
            question = round_doc.get("question") or (round_doc.get("question_context") or {}).get("question")
            folded = _fold(question)
            if len(folded) >= 40:
                questions.append(folded)
    return questions


def refusal_reason(
    sessions: list[dict[str, Any]], user_text: str, *, now: datetime | None = None
) -> str | None:
    now = now or datetime.now(timezone.utc)
    if recent_assessment_rounds(sessions, now=now):
        return "assessment_open"
    folded = _fold(user_text)
    if folded and any(q in folded for q in _open_round_questions(sessions, now=now)):
        return "pasted_question"
    return None


def refusal_reply() -> dict[str, Any]:
    return {
        "kind": "planning",
        "mode": "deterministic",
        "message": REFUSAL_MESSAGE,
        "clarifying_questions": [],
        "actions": [],
        "tool_proposal": None,
        "refusal": True,
    }


# ---------------------------------------------------------------------------
# Tool proposals (validated against the context block before any card)
# ---------------------------------------------------------------------------

TOOLS = ("update_plan", "start_practice", "explain_last_interview")
_PRACTICE_MODES = ("coached_practice", "assessment")
_FLOW_PRESETS = ("legacy", "quick", "full")


def _in_context(context_block: str, value: Any) -> bool:
    needle = _fold(value)
    if not needle:
        return False
    return re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", _fold(context_block)) is not None


def validate_tool_proposal(
    proposal: Any, context_block: str
) -> dict[str, Any] | None:
    """Normalise a model tool proposal, or drop it (None) when invalid."""
    if not isinstance(proposal, dict):
        return None
    tool = proposal.get("tool") or proposal.get("type") or proposal.get("name")
    args = proposal.get("args") or proposal.get("arguments") or {}
    if not isinstance(args, dict):
        return None
    if tool == "update_plan":
        goal = args.get("goal")
        if goal is not None and not _in_context(context_block, goal):
            return None
        hours = args.get("hours_per_week", args.get("hours"))
        if hours is not None:
            try:
                hours = int(hours)
            except (TypeError, ValueError):
                return None
            if not 1 <= hours <= 40:
                return None
        skills = list(args.get("skills") or [])
        if any(not _in_context(context_block, s) for s in skills):
            return None
        return {"tool": tool, "args": {"goal": goal, "hours_per_week": hours, "skills": skills}}
    if tool == "start_practice":
        skills = [str(s) for s in (args.get("skills") or []) if str(s).strip()]
        if not skills or any(not _in_context(context_block, s) for s in skills):
            return None
        mode = str(args.get("practice_mode") or "coached_practice").lower()
        preset = str(args.get("flow_preset") or "legacy").lower()
        if mode not in _PRACTICE_MODES or preset not in _FLOW_PRESETS:
            return None
        return {"tool": tool, "args": {"skills": skills, "practice_mode": mode, "flow_preset": preset}}
    if tool == "explain_last_interview":
        session_id = args.get("session_id") or proposal.get("session_id")
        if not session_id or str(session_id) not in (context_block or ""):
            return None
        return {"tool": tool, "args": {"session_id": str(session_id)}, "note": EXPLAIN_24H_NOTE}
    return None


# ---------------------------------------------------------------------------
# Daily caps in the shared interview-LLM file journal
# ---------------------------------------------------------------------------

def journal_path() -> Path:
    raw = os.getenv("INTERVIEW_LLM_STATE_PATH") or os.getenv("COACH_CHAT_STATE_PATH")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[1] / "artifacts" / "interview_llm_limits.json"


def _empty_chat_section(day: int) -> dict[str, Any]:
    return {"day": day, "users": {}, "global": {"estimated_usd": 0.0, "turns": 0}, "rates": RATES}


def _read_state(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            state = json.loads(path.read_text())
            if isinstance(state, dict):
                return state
        except (OSError, ValueError):
            pass
    return {"version": 1, "host": socket.gethostname(), "accounts": {}}


def _cap_snapshot(user_id: str, *, path: Path | None = None, now: float | None = None) -> dict[str, Any]:
    path = path or journal_path()
    now = time.time() if now is None else now
    day = int(now // 86400)
    section = _read_state(path).get("coach_chat") or {}
    if section.get("day") != day:
        section = _empty_chat_section(day)
    user_row = (section.get("users") or {}).get(str(user_id)) or {}
    glob = section.get("global") or {}
    return {
        "day": day,
        "user_turns": int(user_row.get("turns") or 0),
        "user_usd": float(user_row.get("estimated_usd") or 0.0),
        "global_usd": float(glob.get("estimated_usd") or 0.0),
        "capped": int(user_row.get("turns") or 0) >= PER_USER_DAILY_TURNS
        or float(user_row.get("estimated_usd") or 0.0) >= PER_USER_DAILY_USD
        or float(glob.get("estimated_usd") or 0.0) >= global_daily_usd(),
    }


def is_capped(user_id: str, *, path: Path | None = None, now: float | None = None) -> bool:
    return bool(_cap_snapshot(user_id, path=path, now=now)["capped"])


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rate = RATES.get(model) or RATES[PAID_CONVERSATION_MODEL]
    return prompt_tokens / 1_000_000 * rate["input_usd_per_million"] + completion_tokens / 1_000_000 * rate["output_usd_per_million"]


def record_turn(
    user_id: str, *, prompt_tokens: int, completion_tokens: int,
    provider: str = COACH_CHAT_PROVIDER, model: str = PAID_CONVERSATION_MODEL,
    path: Path | None = None, now: float | None = None,
) -> float:
    """Append one turn to coach_chat counts. Never stores message text."""
    import fcntl

    path = path or journal_path()
    now = time.time() if now is None else now
    day = int(now // 86400)
    cost = estimate_cost_usd(model, prompt_tokens, completion_tokens)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = _read_state(path)
        section = state.get("coach_chat") or {}
        if section.get("day") != day:
            section = _empty_chat_section(day)
        section.setdefault("rates", RATES)
        users = section.setdefault("users", {})
        row = users.setdefault(str(user_id), {
            "turns": 0, "prompt_tokens": 0, "completion_tokens": 0,
            "estimated_usd": 0.0, "provider": provider, "model": model,
        })
        row["turns"] = int(row.get("turns") or 0) + 1
        row["prompt_tokens"] = int(row.get("prompt_tokens") or 0) + int(prompt_tokens)
        row["completion_tokens"] = int(row.get("completion_tokens") or 0) + int(completion_tokens)
        row["estimated_usd"] = float(row.get("estimated_usd") or 0.0) + cost
        row["provider"], row["model"] = provider, model
        glob = section.setdefault("global", {"estimated_usd": 0.0, "turns": 0})
        glob["estimated_usd"] = float(glob.get("estimated_usd") or 0.0) + cost
        glob["turns"] = int(glob.get("turns") or 0) + 1
        state["coach_chat"] = section
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as out:
            tmp = Path(out.name)
            try:
                json.dump(state, out, allow_nan=False, sort_keys=True)
                out.flush()
                os.fsync(out.fileno())
                os.replace(tmp, path)
            finally:
                tmp.unlink(missing_ok=True)
    return cost


# ---------------------------------------------------------------------------
# Context block
# ---------------------------------------------------------------------------

def _missed_concepts(round_doc: dict[str, Any]) -> list[str]:
    breakdown = round_doc.get("scoring_breakdown") or {}
    concepts = breakdown.get("concepts") or {}
    names: list[str] = []
    for key in ("missing", "missed_concepts"):
        names.extend(str(x) for x in (concepts.get(key) or []) if str(x).strip())
    statuses = concepts.get("concept_statuses") or breakdown.get("concept_statuses") or {}
    if isinstance(statuses, dict):
        names.extend(str(x) for x in (statuses.get("missed") or []) if str(x).strip())
    return list(dict.fromkeys(names))


def _fmt_num(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.1f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))
    return str(value)


def build_context_block(
    *,
    user: dict[str, Any] | None = None,
    user_id: str | None = None,
    conversation: dict[str, Any] | None = None,
    user_text: str = "",
    plan: dict[str, Any] | None = None,
    db: Any | None = None,
    sessions: list[dict[str, Any]] | None = None,
    resume_skills: list[str] | None = None,
    gap: dict[str, Any] | None = None,
    due_rows: list[dict[str, Any]] | None = None,
    role_target: dict[str, Any] | None = None,
) -> str:
    """Plain-text labelled context (~3000 tokens, hard stop 3200).

    Injectable data wins; otherwise the stored sources are read. No scorer
    is called and no new score is computed.
    """
    uid = str(user_id or (user or {}).get("id") or (conversation or {}).get("user_id") or "")
    if db is None and (sessions is None or resume_skills is None or due_rows is None):
        try:
            from backend.db import get_database

            db = get_database()
        except Exception:
            db = None
    if sessions is None:
        sessions = []
        if db is not None and uid:
            try:
                sessions = list(db["sessions"].find({"user_id": uid}))
            except Exception:
                sessions = []
    if resume_skills is None:
        resume_skills = []
        if db is not None and uid:
            try:
                cand = db["candidates"].find_one({"user_id": uid}) or {}
                resume_skills = list(cand.get("resume_skills") or [])[:12]
            except Exception:
                resume_skills = []
    if role_target is None:
        role_target = get_coach_role_target(user or {"id": uid})
    role_line = (
        f"Blueprint: {role_target.get('blueprint_id') or 'none'} "
        f"Title: {role_target.get('title') or 'none'} "
        f"Level: {role_target.get('level') or 'junior'} "
        f"Role: {role_target.get('role_id') or 'none'}"
    )
    refusal_rules = (
        "Never help with an open assessment question. Write counts as words. "
        "Only repeat numbers that appear in this block or the current message."
    )
    goals = (conversation or {}).get("goals") or {}
    history = list((conversation or {}).get("messages") or [])
    recent = [{"role": m.get("role"), "text": m.get("text")} for m in history[-(MAX_RECENT_MESSAGES - 1):]]
    recent.append({"role": "user", "text": user_text})
    completed = [s for s in sessions if str(s.get("status") or "") == "completed" or s.get("overall_readiness_score") is not None]
    debriefs = []
    for session in list(reversed(completed))[:3]:
        missed: list[str] = []
        for round_doc in session.get("rounds") or []:
            missed.extend(_missed_concepts(round_doc))
        debriefs.append({"session_id": session.get("session_id"), "missed": list(dict.fromkeys(missed))})
    last_score = None
    for session in reversed(sessions):
        if session.get("overall_readiness_score") is not None:
            last_score = session.get("overall_readiness_score")
            break
    if gap is None and role_target.get("role_id"):
        try:
            from modules.gap_analysis import GapAnalyzer

            gap = GapAnalyzer().compute_gap(uid, str(role_target["role_id"])).to_dict()
        except Exception:
            gap = None
    if plan is None and uid:
        try:
            from modules.roadmap_plans import get_active_plan

            plan = get_active_plan(uid, role_id=goals.get("role_id") or (conversation or {}).get("role_id"),
                                   confirmed_goal=goals.get("confirmed_goal"))
        except Exception:
            plan = None
    if due_rows is None:
        due_rows = []
        if db is not None and uid:
            try:
                from backend.review_schedule import is_due

                due_rows = [d for d in db["review_schedules"].find({"user_id": uid}) if is_due(d)][:8]
            except Exception:
                due_rows = []
    summary = str((conversation or {}).get("rolling_summary") or "")

    def render(summary_text: str, recent_rows: list, debrief_rows: list, task_rows: list) -> str:
        lines = ["[Role]", role_line, "[Refusal rules]", refusal_rules, "[Recent messages]"]
        lines += [f"{'User' if r['role'] == 'user' else 'Coach'}: {r['text'] or ''}" for r in recent_rows]
        lines += ["[Resume skills]", ", ".join(str(s) for s in resume_skills[:12]) or "none"]
        lines.append("[App scores]")
        if gap:
            lines.append(
                f"Overall readiness: {_fmt_num(gap.get('overall_readiness_percentage'))}% "
                f"Conservative: {_fmt_num(gap.get('overall_readiness_conservative'))}%"
            )
            for g in gap.get("per_skill_gap") or []:
                lvl = g.get("student_level")
                lines.append(f"{g.get('skill')}: level {_fmt_num(lvl) if lvl is not None else 'untested'} attempts {g.get('attempts', 0)}")
        else:
            lines.append("none")
        if last_score is not None:
            lines.append(f"Last completed session readiness: {_fmt_num(last_score)}")
        lines.append("[Recent debriefs]")
        lines += [f"Session {d['session_id']}: missed {', '.join(d['missed']) or 'none'}" for d in debrief_rows] or ["none"]
        lines.append("[Plan]")
        if plan:
            meta = plan.get("meta") or {}
            lines.append(f"Plan {plan.get('plan_id')} v{plan.get('version')} kind {meta.get('plan_kind')} goal {goals.get('confirmed_goal') or ''} hours {goals.get('hours_per_week') or ''}")
            lines += [f"Task {t.get('skill')}: {t.get('title')} — {t.get('rationale')} ({t.get('population')})" for t in task_rows]
        else:
            lines.append("none")
        lines.append("[Due reviews]")
        lines += [f"Item {d.get('item_id') or d.get('id')} skill {d.get('skill')} due {d.get('due_at')}" for d in due_rows[:8]] or ["none"]
        lines += ["[Summary]", summary_text or "none", "[Current user message]", user_text or ""]
        return "\n".join(lines)

    pending = [t for t in (plan or {}).get("tasks") or [] if t.get("status") != "completed"][:4]
    block = render(summary, recent, debriefs, pending)
    if estimate_tokens(block) <= MAX_CONTEXT_TOKENS:
        return block
    block = render("", recent, debriefs, pending)
    while estimate_tokens(block) > MAX_CONTEXT_TOKENS and len(recent) > 1:
        recent = recent[1:]
        block = render("", recent, debriefs, pending)
    if estimate_tokens(block) > MAX_CONTEXT_TOKENS and len(debriefs) > 1:
        block = render("", recent, debriefs[:1], pending)
        debriefs = debriefs[:1]
    while estimate_tokens(block) > MAX_CONTEXT_TOKENS and pending:
        pending = pending[:-1]
        block = render("", recent, debriefs, pending)
    return block[: MAX_CONTEXT_TOKENS * 4] if estimate_tokens(block) > MAX_CONTEXT_TOKENS else block


def updated_rolling_summary(old: str | None, validated_message: str) -> str:
    sentence = re.split(r"(?<=[.!?])\s+", (validated_message or "").strip())[0][:240]
    combined = f"{old or ''} {sentence}".strip()
    return combined[-1600:]


# ---------------------------------------------------------------------------
# explain_last_interview (stored debrief read + teaching exposure)
# ---------------------------------------------------------------------------

def explain_last_interview(db: Any, user_id: str, session_id: str | None = None) -> dict[str, Any]:
    """Explain the newest completed session from stored fields only.

    No scorer call. Records ``explanation`` exposure per round only when the
    Learning Hub gates pass: a submitted attempt exists and the item is not
    still open in an active session.
    """
    from modules.assistance_policy import item_identity_for_round
    from modules.teaching_exposures import record_teaching_exposure

    sessions = list(db["sessions"].find({"user_id": str(user_id)}))
    completed = [s for s in sessions if str(s.get("status") or "") == "completed" or s.get("overall_readiness_score") is not None]
    target = None
    if session_id:
        target = next((s for s in completed if str(s.get("session_id")) == str(session_id)), None)
    elif completed:
        target = completed[-1]
    if target is None:
        return {"available": False, "reason": "no_completed_session", "session_id": session_id}
    open_items = set()
    for session in sessions:
        if str(session.get("status") or "") == "completed":
            continue
        for round_doc in session.get("rounds") or []:
            if round_doc.get("status") in ("in_progress", "ready"):
                open_items.add(item_identity_for_round(round_doc))
    rounds_out, recorded = [], []
    for round_doc in target.get("rounds") or []:
        item_type, item_id = item_identity_for_round(round_doc)
        has_attempt = round_doc.get("final_score") is not None
        gated = bool(item_type and item_id and has_attempt and (item_type, item_id) not in open_items)
        if gated:
            exposure = record_teaching_exposure(
                db, kind="explanation", item_type=item_type, item_id=item_id,
                session=target, user_id=str(user_id),
                round_number=round_doc.get("round"), also_legacy_assistance=True,
            )
            if exposure:
                recorded.append(exposure.get("delivery_id") or exposure.get("id"))
        rounds_out.append({
            "round": round_doc.get("round"),
            "skill": round_doc.get("skill"),
            "score": round_doc.get("final_score"),
            "missed": _missed_concepts(round_doc),
            "exposure_recorded": gated,
        })
    return {
        "available": True,
        "session_id": target.get("session_id"),
        "rounds": rounds_out,
        "recorded_exposure_ids": recorded,
        "note": EXPLAIN_24H_NOTE,
    }


# ---------------------------------------------------------------------------
# Reply generation: full reply first, validated, only then streamed
# ---------------------------------------------------------------------------

def chunk_text(text: str, size: int = 48) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)] if text else []


def _log_usage(*, status: str, error: str | None, prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
    try:
        from modules.llm_usage import log_llm_usage

        log_llm_usage(provider=COACH_CHAT_PROVIDER, model=PAID_CONVERSATION_MODEL,
                      purpose=COACH_CHAT_PURPOSE, prompt_tokens=prompt_tokens,
                      completion_tokens=completion_tokens, status=status, error=error)
    except Exception:
        pass


def _default_transport(context_block: str, user_message: str) -> dict[str, Any]:
    import urllib.request

    from modules.interview_llm import CHAT_URL, enforce_coach_chat_outbound

    enforce_coach_chat_outbound(model=PAID_CONVERSATION_MODEL, provider=coach_chat_provider())
    key = os.getenv("OPENROUTER_API_KEY") or ""
    if not key:
        raise RuntimeError("provider key missing")
    system = (
        context_block
        + "\nReply as JSON with message and optional tool_proposal "
        + "(tool: update_plan, start_practice, or explain_last_interview). "
        + "Write counts as words. Only use numbers from the context or user message."
    )
    body = {
        "model": PAID_CONVERSATION_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 700,
        "temperature": 0.1,
    }
    request = urllib.request.Request(
        CHAT_URL, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read())
    content = (payload.get("choices") or [{}])[0].get("message", {}).get("content", "")
    usage = payload.get("usage") or {}
    try:
        parsed = json.loads(content)
    except (ValueError, TypeError):
        parsed = {"message": content}
    return {
        "message": parsed.get("message", ""),
        "tool_proposal": parsed.get("tool_proposal") or parsed.get("tool"),
        "actions": parsed.get("actions") or [],
        "prompt_tokens": int(usage.get("prompt_tokens") or estimate_tokens(context_block)),
        "completion_tokens": int(usage.get("completion_tokens") or estimate_tokens(str(parsed.get("message", "")))),
    }


def generate_coach_reply(
    *,
    user_id: str,
    user_text: str,
    context_block: str,
    deterministic: dict[str, Any],
    plan: dict[str, Any] | None = None,
    sessions: list[dict[str, Any]] | None = None,
    transport: Transport | None = None,
    state_path: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return the reply to show. Provider text is validated before return.

    Callers stream only the returned ``message``; rejected provider text is
    never included in the result.
    """
    from modules.coach_conversation import _validate_provider_output

    now = now or datetime.now(timezone.utc)
    if sessions is not None and refusal_reason(sessions, user_text, now=now):
        _log_usage(status="error", error="privacy")
        return refusal_reply()
    if not coach_chat_enabled():
        return {**deterministic, "tool_proposal": None}
    if is_capped(user_id, path=state_path):
        _log_usage(status="error", error="cap")
        return {**deterministic, "tool_proposal": None, "capped": True}
    send = transport or _TRANSPORT or _default_transport
    try:
        raw = send(context_block, user_text)
    except Exception as exc:
        from modules.interview_llm import PrivacyViolation

        code = "privacy" if isinstance(exc, PrivacyViolation) else "provider"
        _log_usage(status="error", error=code)
        return {**deterministic, "tool_proposal": None, "provider_error": code}
    if not isinstance(raw, dict):
        _log_usage(status="error", error="provider")
        return {**deterministic, "tool_proposal": None, "provider_rejected": True}
    prompt_tokens = int(raw.get("prompt_tokens") or estimate_tokens(context_block))
    completion_tokens = int(raw.get("completion_tokens") or estimate_tokens(str(raw.get("message") or "")))
    validated = _validate_provider_output(
        {"message": raw.get("message"), "actions": raw.get("actions") or [],
         "clarifying_questions": raw.get("clarifying_questions") or []},
        plan=plan,
    )
    message = (validated or {}).get("message") or ""
    if validated is None or not validate_number_rule(message, context_block, user_text):
        _log_usage(status="error", error="provider", prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
        return {**deterministic, "tool_proposal": None, "provider_rejected": True}
    record_turn(user_id, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, path=state_path)
    _log_usage(status="ok", error=None, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    proposal = raw.get("tool_proposal") or raw.get("tool")
    return {
        **validated,
        "tool_proposal": validate_tool_proposal(proposal, context_block),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }




