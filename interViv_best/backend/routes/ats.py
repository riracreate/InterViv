from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, model_validator

from backend.db import DatabaseConnectionError, get_database
from backend.routes.auth import require_authenticated, require_user
from modules.ats_scorer import (
    must_have_from_jd,
    must_have_from_role,
    score_ats,
)
from modules.ats_store import list_ats_runs, save_ats_run
from modules.company_graph import get_company_graph
from modules.resume_parser import analyze_resume_text


router = APIRouter(prefix="/ats", tags=["ats"], dependencies=[Depends(require_authenticated)])


class AtsScoreRequest(BaseModel):
    candidate_id: str
    role_id: str | None = None
    jd_text: str | None = None
    # Test/dev escape hatch: score fixture text without re-upload.
    resume_text: str | None = None

    @model_validator(mode="after")
    def _xor_role_or_jd(self) -> "AtsScoreRequest":
        has_role = bool(self.role_id and str(self.role_id).strip())
        has_jd = bool(self.jd_text and str(self.jd_text).strip())
        if has_role == has_jd:
            raise ValueError("Provide exactly one of role_id or jd_text.")
        if not self.candidate_id.strip():
            raise ValueError("candidate_id is required.")
        return self


def _analysis_from_candidate(candidate: dict, resume_text: str | None) -> dict[str, Any]:
    if resume_text and resume_text.strip():
        return analyze_resume_text(resume_text)
    snapshot = candidate.get("ats_snapshot") or {}
    if snapshot:
        # Ensure skills fall back to resume_skills
        skills = snapshot.get("skills") or candidate.get("resume_skills") or []
        return {**snapshot, "skills": skills}
    # Legacy candidates: skills only
    return {
        "skills": list(candidate.get("resume_skills") or []),
        "sections": {},
        "section_order_ok": None,
        "experience_bullets": [],
        "extract_ok": True,
        "likely_garbage": False,
        "layout_checked": False,
        "text_hash": None,
    }


@router.post("/score")
def post_ats_score(
    body: AtsScoreRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    user = require_user(authorization)
    try:
        db = get_database()
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    candidate = db["candidates"].find_one({"candidate_id": body.candidate_id.strip()})
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume/candidate not found.")
    owner = candidate.get("user_id")
    if owner and str(owner) != str(user["id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot score another user's resume.",
        )

    role_id = (body.role_id or "").strip() or None
    jd_text = (body.jd_text or "").strip() or None
    if role_id:
        if get_company_graph().find_role(role_id) is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown role_id: {role_id}",
            )
        must_have = must_have_from_role(role_id)
    else:
        must_have = must_have_from_jd(jd_text or "")

    analysis = _analysis_from_candidate(candidate, body.resume_text)
    result = score_ats(
        analysis=analysis,
        must_have=must_have,
        role_id=role_id,
        jd_text=jd_text,
    )

    saved = save_ats_run(
        {
            "user_id": str(user["id"]),
            "resume_id": body.candidate_id.strip(),
            "role_id": role_id,
            "jd_hash": result.get("jd_hash"),
            "parse_score": result["components"]["parse_health"],
            "section_score": result["components"]["section_complete"],
            "keyword_score": result["components"]["keyword_coverage"],
            "heuristic_score": result["components"]["content_heuristics"],
            "total": result["total"],
            "flags": result["flags"],
            "missing_skills": result["missing_skills"],
            "present_skills": result["present_skills"],
        }
    )

    return {
        **result,
        "run_id": saved.get("id"),
        "resume_id": body.candidate_id.strip(),
        "created_at": saved.get("created_at").isoformat()
        if hasattr(saved.get("created_at"), "isoformat")
        else saved.get("created_at"),
    }


@router.get("/runs")
def get_ats_runs(
    authorization: str | None = Header(default=None),
    limit: int = 20,
) -> dict[str, Any]:
    user = require_user(authorization)
    limit = max(1, min(int(limit or 20), 50))
    runs = list_ats_runs(str(user["id"]), limit=limit)
    serialized = []
    for run in runs:
        serialized.append(
            {
                **run,
                "created_at": run["created_at"].isoformat()
                if hasattr(run.get("created_at"), "isoformat")
                else run.get("created_at"),
            }
        )
    return {"runs": serialized, "count": len(serialized)}
