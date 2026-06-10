from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.config import get_settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def _load_bcrypt():
    try:
        import bcrypt

        return bcrypt
    except ModuleNotFoundError:
        return None


def hash_password(password: str) -> str:
    bcrypt = _load_bcrypt()
    if bcrypt is not None:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260_000)
    return "pbkdf2_sha256$260000$" + _b64url_encode(salt) + "$" + _b64url_encode(digest)


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash.startswith("$2"):
        bcrypt = _load_bcrypt()
        if bcrypt is None:
            return False
        return bool(bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8")))

    if password_hash.startswith("pbkdf2_sha256$"):
        try:
            _, rounds, salt_raw, digest_raw = password_hash.split("$", 3)
            salt = _b64url_decode(salt_raw)
            expected = _b64url_decode(digest_raw)
            actual = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt, int(rounds)
            )
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False
    return False


def _jwt_sign(signing_input: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return _b64url_encode(digest)


def _create_stdlib_jwt(payload: dict[str, Any], secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_raw = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_raw = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_raw}.{payload_raw}".encode("ascii")
    return f"{header_raw}.{payload_raw}.{_jwt_sign(signing_input, secret)}"


def _decode_stdlib_jwt(token: str, secret: str) -> dict[str, Any]:
    try:
        header_raw, payload_raw, signature = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("Malformed token.") from exc

    signing_input = f"{header_raw}.{payload_raw}".encode("ascii")
    expected = _jwt_sign(signing_input, secret)
    if not hmac.compare_digest(signature, expected):
        raise ValueError("Invalid token signature.")

    payload = json.loads(_b64url_decode(payload_raw).decode("utf-8"))
    exp = payload.get("exp")
    if exp is not None and datetime.now(timezone.utc).timestamp() > float(exp):
        raise ValueError("Token expired.")
    return payload


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_minutes
    )
    payload = {"sub": subject, "exp": int(expires_at.timestamp())}

    try:
        import jwt

        return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    except ModuleNotFoundError:
        return _create_stdlib_jwt(payload, settings.jwt_secret_key)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        import jwt

        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except ModuleNotFoundError:
        return _decode_stdlib_jwt(token, settings.jwt_secret_key)
