from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from backend.config import get_settings
from backend.integrations import IntegrationError
from backend.routes.auth import require_user
from backend.scoring.pipeline import get_model_metadata
from modules import bundle_store
from modules.bundle_store import BundleStoreError
from modules.question_bundles import reviewer_blind_view

router = APIRouter(prefix="/admin", tags=["admin"])

_STORE_STATUS = {
    "invalid": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "conflict": status.HTTP_409_CONFLICT,
    "not_found": status.HTTP_404_NOT_FOUND,
    "forbidden": status.HTTP_403_FORBIDDEN,
}


def require_admin(authorization: str | None) -> dict:
    """Authenticated user whose email is in ADMIN_USER_EMAILS (401 / 403).

    The router itself is only mounted when ENABLE_ADMIN_ENDPOINTS is on; this
    adds the per-identity check the review workflow needs (reviewer identity
    comes from the token, never from the request body).
    """
    user = require_user(authorization)
    if str(user.get("email") or "").lower() not in get_settings().admin_user_emails:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access is required.")
    return user


def _store(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except BundleStoreError as exc:
        raise HTTPException(status_code=_STORE_STATUS[exc.code], detail=str(exc)) from exc


@router.get("/model-metadata")
def model_metadata() -> dict[str, Any]:
    """Read-only model artifact metadata for viva/admin verification."""
    try:
        metadata = get_model_metadata()
        # Never expose machine-local filesystem paths through an HTTP response.
        for key in ("artifact_path", "metadata_path"):
            metadata.pop(key, None)
        return metadata
    except IntegrationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


# ─── Phase 1A: question bundles ─────────────────────────────────────────────

class ReasonBody(BaseModel):
    reason: str = ""


class DecisionBody(BaseModel):
    content_hash: str = Field(min_length=64, max_length=64)
    decision: str
    checklist: dict[str, Any]
    reasons: str
    calibration: dict[str, Any]


def _version_summary(v: dict) -> dict:
    return {
        "bundle_id": v["bundle_id"], "version": v["version"], "status": v["status"],
        "content_hash": v["content_hash"], "difficulty": v["difficulty"],
        "source": v["source"], "author_id": v["author_id"],
        "created_at": v["created_at"], "status_updated_at": v["status_updated_at"],
    }


@router.get("/bundles")
def list_bundles(skill: str | None = None, authorization: str | None = Header(default=None)) -> dict:
    require_admin(authorization)
    bundles = bundle_store.list_bundles(skill=skill)
    versions = bundle_store.list_versions()
    by_bundle: dict[str, list[dict]] = {}
    for v in versions:
        by_bundle.setdefault(v["bundle_id"], []).append(_version_summary(v))
    return {"bundles": [{**b, "versions": by_bundle.get(b["bundle_id"], [])} for b in bundles]}


@router.get("/bundles/inventory")
def bundle_inventory(authorization: str | None = Header(default=None)) -> dict:
    """Reviewed inventory by skill/topic/difficulty; drafts separately."""
    require_admin(authorization)
    return {**bundle_store.inventory(), "reviewed_only_enforced": get_settings().reviewed_bundles_only}


@router.get("/bundles/{bundle_id}/versions/{version}")
def bundle_version(bundle_id: str, version: int, authorization: str | None = Header(default=None)) -> dict:
    """Reviewer view: full content minus author labels, plus review history."""
    require_admin(authorization)
    history = _store(bundle_store.review_history, bundle_id, version)
    return {**reviewer_blind_view(history["version"]), **{k: v for k, v in history.items() if k != "version"}}


@router.post("/bundles/{bundle_id}/versions/{version}/submit")
def submit_for_review(bundle_id: str, version: int, body: ReasonBody | None = None,
                      authorization: str | None = Header(default=None)) -> dict:
    user = require_admin(authorization)
    v = _store(bundle_store.submit_for_review, bundle_id, version,
               actor_id=str(user["id"]), reason=(body.reason if body else ""))
    return _version_summary(v)


@router.post("/bundles/{bundle_id}/versions/{version}/decisions")
def record_decision(bundle_id: str, version: int, body: DecisionBody,
                    authorization: str | None = Header(default=None)) -> dict:
    """One independent decision. Reviewer identity is the authenticated admin."""
    user = require_admin(authorization)
    result = _store(
        bundle_store.record_decision, bundle_id, version,
        reviewer_id=str(user["id"]), content_hash=body.content_hash, decision=body.decision,
        checklist=body.checklist, reasons=body.reasons, calibration=body.calibration,
    )
    return {"decision": result["decision"], "version": _version_summary(result["version"])}


@router.post("/bundles/{bundle_id}/versions/{version}/retire")
def retire_version(bundle_id: str, version: int, body: ReasonBody,
                   authorization: str | None = Header(default=None)) -> dict:
    user = require_admin(authorization)
    return _version_summary(_store(bundle_store.retire, bundle_id, version,
                                   actor_id=str(user["id"]), reason=body.reason))
