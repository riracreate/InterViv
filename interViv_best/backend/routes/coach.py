"""Guidance coach routes — one-shot plan + multi-turn conversation (Phase 4B)."""

from __future__ import annotations

from typing import Any

import json

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from backend.db import get_database
from backend.db.user_target import get_user_target
from backend.routes.auth import require_authenticated, require_user
from backend.routes.session import StartSessionRequest, launch_planned_scope, start_session
from modules.coach_conversation import (
    MAX_MESSAGE_CHARS,
    clear_conversation,
    get_conversation,
    get_or_create_conversation,
    owner_key,
    post_message,
    update_goals,
)
from modules.guidance_coach import (
    MAX_INPUT_CHARS,
    build_coach_plan,
    cap_practice_skills,
)
from modules import coach_chat
from modules.jobs_explorer import build_practice_start_payload
from modules.roadmap_plans import ensure_plan


router = APIRouter(prefix="/coach", tags=["coach"], dependencies=[Depends(require_authenticated)])


class CoachPlanRequest(BaseModel):
    jd_text: str | None = None
    goal_text: str | None = None
    include_dashboard: bool = True
    role_id: str | None = None

    @model_validator(mode="after")
    def require_one_field(self) -> "CoachPlanRequest":
        jd = (self.jd_text or "").strip()
        goal = (self.goal_text or "").strip()
        if not jd and not goal:
            raise ValueError("Provide jd_text and/or goal_text.")
        if len(jd) > MAX_INPUT_CHARS or len(goal) > MAX_INPUT_CHARS:
            raise ValueError(f"Input exceeds {MAX_INPUT_CHARS} characters.")
        return self


_PRACTICE_MODES = {"coached_practice", "assessment"}
_FLOW_PRESETS = {"legacy", "quick", "full"}


class CoachStartPracticeRequest(BaseModel):
    skills: list[str] = Field(default_factory=list)
    round_plan: list[str] | None = None
    practice_mode: str | None = None
    flow_preset: str | None = None

    @model_validator(mode="after")
    def check_launch(self) -> "CoachStartPracticeRequest":
        if self.practice_mode is not None:
            mode = self.practice_mode.strip().lower()
            if mode not in _PRACTICE_MODES:
                raise ValueError("practice_mode must be coached_practice or assessment.")
            self.practice_mode = mode
        if self.flow_preset is not None:
            preset = self.flow_preset.strip().lower()
            if preset not in _FLOW_PRESETS:
                raise ValueError("flow_preset must be legacy, quick, or full.")
            self.flow_preset = preset
        return self


class ConversationGoalsRequest(BaseModel):
    confirmed_goal: str | None = None
    role_id: str | None = None
    hours_per_week: int | None = Field(default=None, ge=1, le=40)
    planning_context_skills: list[str] = Field(default_factory=list)
    adzuna_context: dict[str, Any] | None = None


class ConversationMessageRequest(BaseModel):
    text: str = ""
    action: str | None = None
    action_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bound_text(self) -> "ConversationMessageRequest":
        if len(self.text or "") > MAX_MESSAGE_CHARS:
            raise ValueError(f"Message exceeds {MAX_MESSAGE_CHARS} characters.")
        return self


@router.post("/plan")
def coach_plan(
    body: CoachPlanRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    role_id = body.role_id
    if not role_id:
        db = get_database()
        candidate = db["candidates"].find_one({"user_id": user["id"]})
        if candidate:
            role_id = candidate.get("target_role_id") or candidate.get("role_id")
        role_id = role_id or get_user_target(user)["role_id"]

    plan = build_coach_plan(
        jd_text=body.jd_text,
        goal_text=body.goal_text,
        user_id=str(user["id"]),
        role_id=str(role_id) if role_id else None,
        include_dashboard=bool(body.include_dashboard),
    )
    # What "Start practice" will actually ask: at most three free-text
    # questions, one per skill, so later skills are named as not covered.
    preview = plan.get("practice_preview") or {}
    if preview.get("skills"):
        preview["planned_scope"] = launch_planned_scope(
            {"skills": preview["skills"], "round_plan": preview.get("round_plan") or [],
             "rounds_per_skill": 1},
            list(preview["skills"]),
        )
    return plan


@router.post("/start-practice")
def coach_start_practice(
    body: CoachStartPracticeRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    skills = cap_practice_skills(body.skills)
    if not skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No recognizable skills to practice. Unsupported content is "
                "not silently substituted."
            ),
        )

    db = get_database()
    candidate = db["candidates"].find_one({"user_id": user["id"]})
    candidate_id = str(candidate["candidate_id"]) if candidate else ""

    start_body = build_practice_start_payload(skills=skills, candidate_id=candidate_id or None)
    preset = body.flow_preset or "legacy"
    if preset == "legacy":
        if body.round_plan:
            cleaned = [r for r in body.round_plan if r in {"technical_short_answer", "mcq", "sql"}]
            if cleaned:
                start_body["round_plan"] = cleaned[:8]
                start_body["round_type"] = cleaned[0]
    else:
        # Staged Quick/Full cannot carry a legacy round_plan.
        start_body.pop("round_plan", None)
        start_body.pop("round_type", None)
        start_body["preset"] = preset
        start_body["flow_version"] = "staged_v1"
    if body.practice_mode:
        start_body["practice_mode"] = body.practice_mode

    request = StartSessionRequest(**start_body)
    session = start_session(request, authorization=authorization)
    return {
        **session,
        "round_plan": start_body.get("round_plan"),
        "planned_scope": launch_planned_scope(start_body, skills),
        "navigate": f"/interview/{session.get('session_id')}",
        "skills": skills,
    }


@router.post("/conversations")
def create_conversation(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    user = require_user(authorization)
    doc = get_or_create_conversation(
        user_id=str(user["id"]),
        role_id=get_user_target(user)["role_id"],
    )
    return {"conversation": doc}


@router.get("/conversations/{conversation_id}")
def read_conversation(
    conversation_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    doc = get_conversation(conversation_id, owner=owner_key(str(user["id"])))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return {"conversation": doc}


@router.patch("/conversations/{conversation_id}/goals")
def patch_goals(
    conversation_id: str,
    body: ConversationGoalsRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        doc = update_goals(
            conversation_id,
            owner=owner_key(str(user["id"])),
            confirmed_goal=body.confirmed_goal,
            role_id=body.role_id or get_user_target(user)["role_id"],
            hours_per_week=body.hours_per_week,
            planning_context_skills=body.planning_context_skills,
            adzuna_context=body.adzuna_context,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"conversation": doc}


@router.post("/conversations/{conversation_id}/messages")
def send_message(
    conversation_id: str,
    body: ConversationMessageRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        result = post_message(
            conversation_id,
            owner=owner_key(str(user["id"])),
            user_id=str(user["id"]),
            text=body.text,
            action=body.action,
            action_payload=body.action_payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return result


class ToolConfirmRequest(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


@router.post("/conversations/{conversation_id}/messages/stream")
def send_message_stream(
    conversation_id: str,
    body: ConversationMessageRequest,
    authorization: str | None = Header(default=None),
):
    """Generate and validate the full reply first, then stream only it."""
    user = require_user(authorization)
    try:
        result = post_message(
            conversation_id,
            owner=owner_key(str(user["id"])),
            user_id=str(user["id"]),
            text=body.text,
            action=body.action,
            action_payload=body.action_payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    reply = result.get("reply") or {}

    def events():
        for chunk in coach_chat.chunk_text(str(reply.get("message") or "")):
            yield f"event: token\ndata: {json.dumps({'text': chunk})}\n\n"
        if reply.get("tool_proposal"):
            yield f"event: tool_proposal\ndata: {json.dumps(reply['tool_proposal'])}\n\n"
        yield (
            "event: done\n"
            f"data: {json.dumps({'mode': reply.get('mode'), 'provider_rejected': bool(reply.get('provider_rejected')), 'refusal': bool(reply.get('refusal')), 'conversation_id': conversation_id})}\n\n"
        )

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/conversations/{conversation_id}/tools/confirm")
def confirm_tool(
    conversation_id: str,
    body: ToolConfirmRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Run a proposed tool only after the user confirms its action card."""
    user = require_user(authorization)
    doc = get_conversation(conversation_id, owner=owner_key(str(user["id"])))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    goals = doc.get("goals") or {}
    args = body.args or {}
    if body.tool == "update_plan":
        plan = ensure_plan(
            str(user["id"]),
            role_id=goals.get("role_id") or doc.get("role_id"),
            days=30,
            hours_per_week=args.get("hours_per_week") or goals.get("hours_per_week"),
            confirmed_goal=args.get("goal") or goals.get("confirmed_goal"),
            planning_context_skills=args.get("skills") or goals.get("planning_context_skills"),
            regenerate=True,
        )
        return {"tool": body.tool, "plan": plan}
    if body.tool == "start_practice":
        return {
            "tool": body.tool,
            **coach_start_practice(
                CoachStartPracticeRequest(
                    skills=list(args.get("skills") or []),
                    practice_mode=args.get("practice_mode") or "coached_practice",
                    flow_preset=args.get("flow_preset") or "legacy",
                ),
                authorization=authorization,
            ),
        }
    if body.tool == "explain_last_interview":
        explanation = coach_chat.explain_last_interview(
            get_database(), str(user["id"]), args.get("session_id")
        )
        return {"tool": body.tool, "explanation": explanation, "note": coach_chat.EXPLAIN_24H_NOTE}
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown tool.")


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    ok = clear_conversation(conversation_id, owner=owner_key(str(user["id"])))
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return {"cleared": True}
