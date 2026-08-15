from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from backend.auth.security import create_access_token, decode_access_token, hash_password, verify_password
from backend.db import DatabaseConnectionError, get_database, is_database_exception

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


def _public_user(user: dict) -> dict[str, object]:
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name"),
        "target_company_id": user.get("target_company_id"),
        "target_role_id": user.get("target_role_id"),
        "created_at": user.get("created_at"),
        "last_active_at": user.get("last_active_at"),
    }


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expected Bearer token.")
    return token.strip()


def _normalize_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="A valid email is required.")
    return normalized


def _validate_password(password: str) -> None:
    if len(password or "") < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Password must be at least 8 characters.")
    if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Password must contain at least one letter and one number.",
        )


def get_user_from_authorization(authorization: str | None) -> dict | None:
    if not authorization:
        return None
    token = _bearer_token(authorization)
    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.") from exc
    user_id = str(payload.get("sub") or "")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject.")
    try:
        user = get_database()["users"].find_one({"id": user_id})
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        raise
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists.")
    return user


def require_user(authorization: str | None) -> dict:
    user = get_user_from_authorization(authorization)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
        )
    return user


def require_matching_user(user_id: str, authorization: str | None) -> dict | None:
    if not authorization:
        return None
    user = require_user(authorization)
    if str(user.get("id")) != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access another user's data.",
        )
    return user


@router.post("/signup")
def signup(request: SignupRequest) -> dict[str, object]:
    email = _normalize_email(request.email)
    _validate_password(request.password)
    now = datetime.now(timezone.utc)
    try:
        users = get_database()["users"]
        existing = users.find_one({"email": email})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.")

        user = {
            "id": str(uuid4()),
            "email": email,
            "name": request.name.strip() if request.name else None,
            "password_hash": hash_password(request.password),
            "target_company_id": None,
            "target_role_id": None,
            "created_at": now,
            "last_active_at": now,
        }
        users.insert_one(user)
    except HTTPException:
        raise
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        raise

    return {"access_token": create_access_token(user["id"]), "token_type": "bearer", "user": _public_user(user)}


@router.post("/login")
def login(request: LoginRequest) -> dict[str, object]:
    email = _normalize_email(request.email)
    try:
        users = get_database()["users"]
        user = users.find_one({"email": email})
        if not user or not verify_password(request.password, user.get("password_hash", "")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
        users.update_one({"id": user["id"]}, {"$set": {"last_active_at": datetime.now(timezone.utc)}})
        user = users.find_one({"id": user["id"]}) or user
    except HTTPException:
        raise
    except Exception as exc:
        if isinstance(exc, DatabaseConnectionError) or is_database_exception(exc):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        raise

    return {"access_token": create_access_token(user["id"]), "token_type": "bearer", "user": _public_user(user)}


@router.get("/me")
def me(authorization: str | None = Header(default=None)) -> dict[str, object]:
    user = get_user_from_authorization(authorization)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header.")
    return {"user": _public_user(user)}
