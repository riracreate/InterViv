from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.integrations import IntegrationError
from backend.scoring.pipeline import get_model_metadata

router = APIRouter(prefix="/admin", tags=["admin"])


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
