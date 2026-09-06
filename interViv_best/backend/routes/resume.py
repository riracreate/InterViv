from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Header, HTTPException, UploadFile, status

from backend.config import get_settings
from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.integrations import (
    IntegrationError,
    load_module,
    map_skills_to_domains,
)
from backend.models.candidate import CandidateDocument
from backend.routes.auth import get_user_from_authorization
from modules.skill_graph import StudentSkillGraph

router = APIRouter(prefix="/resume", tags=["resume"])
LOGGER = logging.getLogger(__name__)
MAX_RESUME_BYTES = 5 * 1024 * 1024


def _normalize_skills(payload: object) -> list[str]:
    if isinstance(payload, dict):
        for key in ("skills", "resume_skills", "data"):
            if key in payload:
                return _normalize_skills(payload[key])
        return []
    if isinstance(payload, (list, tuple, set)):
        return [str(item).strip() for item in payload if str(item).strip()]
    if isinstance(payload, str):
        return [payload.strip()] if payload.strip() else []
    return []


@router.post("")
async def parse_resume(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume upload must be a PDF file.",
        )

    suffix = Path(file.filename).suffix or ".pdf"
    data = await file.read(MAX_RESUME_BYTES + 1)
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Resume file is too large (maximum 5 MB).",
        )

    settings = get_settings()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        temp_path = Path(handle.name)
        handle.write(data)

    try:
        parser_module = load_module("resume_parser", "resume_parser.py")
        if not hasattr(parser_module, "parse_resume"):
            raise IntegrationError(
                "resume_parser.py does not expose parse_resume(pdf_path)."
            )

        analysis: dict | None = None
        try:
            if hasattr(parser_module, "analyze_resume"):
                analysis = parser_module.analyze_resume(str(temp_path))
                parsed_skills = (analysis or {}).get("skills") or []
            else:
                parsed_skills = parser_module.parse_resume(str(temp_path))
        except Exception:
            LOGGER.warning("Resume parsing failed; using safe fallback skills.")
            parsed_skills = ["Python"]
            analysis = None

        skills = _normalize_skills(parsed_skills) or ["Python"]
        domain_profile = map_skills_to_domains(skills)
        candidate_id = str(uuid4())
        user = get_user_from_authorization(authorization) if authorization else None

        candidate = CandidateDocument(
            candidate_id=candidate_id,
            resume_skills=skills,
            sub_domain_profile=domain_profile,
            elo_ratings={skill: settings.initial_elo for skill in skills},
            session_history=[],
        )
        candidate_doc = candidate.to_mongo()
        if user:
            candidate_doc["user_id"] = user["id"]
        if analysis:
            candidate_doc["ats_snapshot"] = {
                "skills": analysis.get("skills") or skills,
                "sections": analysis.get("sections") or {},
                "section_order_ok": analysis.get("section_order_ok"),
                "experience_bullets": analysis.get("experience_bullets") or [],
                "extract_ok": analysis.get("extract_ok"),
                "likely_garbage": analysis.get("likely_garbage"),
                "layout_checked": analysis.get("layout_checked", False),
                "text_hash": analysis.get("text_hash"),
                "char_count": analysis.get("char_count"),
            }
        else:
            candidate_doc["ats_snapshot"] = {
                "skills": skills,
                "sections": {},
                "extract_ok": True,
                "layout_checked": False,
                "experience_bullets": [],
                "text_hash": None,
            }
        try:
            get_database()["candidates"].insert_one(candidate_doc)
            if user:
                StudentSkillGraph(user["id"]).initialize_from_resume(skills)
        except DatabaseConnectionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        except Exception as exc:
            if is_database_exception(exc):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"MongoDB operation failed: {exc}",
                ) from exc
            raise

        return {
            "candidate_id": candidate_id,
            "user_id": user["id"] if user else None,
            "skills": skills,
            "domain_profile": domain_profile,
        }
    except IntegrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    finally:
        if temp_path.exists():
            temp_path.unlink()
