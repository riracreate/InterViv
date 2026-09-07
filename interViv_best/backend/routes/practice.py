"""Phase B practice presets and builder drafts (user-scoped, versioned)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from backend.db import DatabaseConnectionError, get_database, is_database_exception
from backend.models.blocks import (
    BUILDER_DRAFT_VERSION,
    PRESET_VERSION,
    normalize_blocks,
)
from backend.routes.auth import require_user

router = APIRouter(prefix="/practice", tags=["practice"])


class PresetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    version: int = PRESET_VERSION
    blocks: list[dict[str, Any]]


class PresetUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    version: int | None = None
    blocks: list[dict[str, Any]] | None = None


class BuilderDraftRequest(BaseModel):
    version: int = BUILDER_DRAFT_VERSION
    blocks: list[dict[str, Any]] = Field(default_factory=list)


def _validate_preset_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        return normalize_blocks(blocks)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _preset_key(preset_id: str) -> str:
    return str(preset_id or "").strip()


@router.get("/presets")
def list_presets(
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    user = require_user(authorization)
    try:
        rows = list(get_database()["practice_presets"].find(
            {"user_id": str(user["id"])}))
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    rows.sort(key=lambda r: str(r.get("updated_at") or r.get("created_at") or ""))
    return {"presets": [
        {"id": r.get("id"), "name": r.get("name"), "version": r.get("version"),
         "blocks": r.get("blocks") or [],
         "created_at": r.get("created_at"), "updated_at": r.get("updated_at")}
        for r in rows
    ]}


@router.post("/presets")
def create_preset(
    request: PresetCreateRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    user = require_user(authorization)
    if int(request.version) != PRESET_VERSION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported preset version {request.version}; "
                   f"expected {PRESET_VERSION}.",
        )
    blocks = _validate_preset_blocks(request.blocks)
    now = datetime.now(timezone.utc)
    preset_id = str(uuid4())
    doc = {"id": preset_id, "user_id": str(user["id"]),
           "name": request.name.strip(), "version": PRESET_VERSION,
           "blocks": blocks, "created_at": now, "updated_at": now}
    try:
        get_database()["practice_presets"].insert_one(doc)
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return {"id": preset_id, "name": doc["name"], "version": PRESET_VERSION,
            "blocks": blocks, "created_at": now.isoformat(),
            "updated_at": now.isoformat()}


@router.get("/presets/{preset_id}")
def get_preset(
    preset_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    user = require_user(authorization)
    try:
        row = get_database()["practice_presets"].find_one(
            {"id": _preset_key(preset_id)})
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    if not row or str(row.get("user_id")) != str(user["id"]):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Preset not found."
        )
    if int(row.get("version") or 0) != PRESET_VERSION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Stored preset uses an unsupported version.",
        )
    try:
        blocks = normalize_blocks(list(row.get("blocks") or []))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Stored preset is invalid: {exc}",
        ) from exc
    return {"id": row.get("id"), "name": row.get("name"),
            "version": row.get("version"), "blocks": blocks,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at")}


@router.put("/presets/{preset_id}")
def update_preset(
    preset_id: str,
    request: PresetUpdateRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    user = require_user(authorization)
    try:
        db = get_database()
        row = db["practice_presets"].find_one({"id": _preset_key(preset_id)})
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    if not row or str(row.get("user_id")) != str(user["id"]):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Preset not found."
        )
    patch: dict[str, Any] = {}
    if request.name is not None:
        patch["name"] = request.name.strip()
    if request.version is not None and int(request.version) != PRESET_VERSION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported preset version {request.version}; "
                   f"expected {PRESET_VERSION}.",
        )
    if request.blocks is not None:
        patch["blocks"] = _validate_preset_blocks(request.blocks)
    patch["version"] = PRESET_VERSION
    patch["updated_at"] = datetime.now(timezone.utc)
    try:
        db["practice_presets"].update_one({"id": _preset_key(preset_id)},
                                          {"$set": patch})
        updated = db["practice_presets"].find_one({"id": _preset_key(preset_id)})
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return {"id": preset_id, "name": (updated or {}).get("name"),
            "version": PRESET_VERSION,
            "blocks": (updated or {}).get("blocks") or [],
            "updated_at": (updated or {}).get("updated_at")}


@router.delete("/presets/{preset_id}")
def delete_preset(
    preset_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    user = require_user(authorization)
    try:
        db = get_database()
        row = db["practice_presets"].find_one({"id": _preset_key(preset_id)})
        if not row or str(row.get("user_id")) != str(user["id"]):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Preset not found.",
            )
        db["practice_presets"].delete_one({"id": _preset_key(preset_id)})
    except HTTPException:
        raise
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except Exception as exc:
        if is_database_exception(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Database operation failed: {exc}",
            ) from exc
        raise
    return {"deleted": True, "id": preset_id}


@router.get("/builder-draft")
def get_builder_draft(
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    user = require_user(authorization)
    try:
        row = get_database()["builder_drafts"].find_one(
            {"user_id": str(user["id"])})
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    if not row:
        return {"version": BUILDER_DRAFT_VERSION, "blocks": [],
                "updated_at": None}
    if int(row.get("version") or 0) != BUILDER_DRAFT_VERSION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Stored builder draft uses an unsupported version.",
        )
    raw_blocks = list(row.get("blocks") or [])
    if not raw_blocks:
        return {"version": BUILDER_DRAFT_VERSION, "blocks": [],
                "updated_at": row.get("updated_at")}
    try:
        blocks = normalize_blocks(raw_blocks)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Stored builder draft is invalid: {exc}",
        ) from exc
    return {"version": BUILDER_DRAFT_VERSION, "blocks": blocks,
            "updated_at": row.get("updated_at")}


@router.put("/builder-draft")
def save_builder_draft(
    request: BuilderDraftRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    user = require_user(authorization)
    if int(request.version) != BUILDER_DRAFT_VERSION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported draft version {request.version}; "
                   f"expected {BUILDER_DRAFT_VERSION}.",
        )
    blocks = (_validate_preset_blocks(request.blocks)
              if request.blocks else [])
    now = datetime.now(timezone.utc)
    try:
        get_database()["builder_drafts"].update_one(
            {"user_id": str(user["id"])},
            {"$set": {"user_id": str(user["id"]),
                      "version": BUILDER_DRAFT_VERSION, "blocks": blocks,
                      "updated_at": now}},
            upsert=True,
        )
    except DatabaseConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return {"version": BUILDER_DRAFT_VERSION, "blocks": blocks,
            "updated_at": now.isoformat()}
