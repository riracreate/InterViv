"""Insert a parent users row before a test writes a child that references it."""

from __future__ import annotations

from datetime import datetime, timezone


def ensure_candidate(db, candidate_id: str, user_id: str | None = None) -> str:
    if user_id:
        ensure_user(db, user_id)
    if db["candidates"].find_one({"candidate_id": candidate_id}):
        return candidate_id
    db["candidates"].insert_one({
        "candidate_id": candidate_id,
        "user_id": user_id,
        "resume_skills": [],
        "sub_domain_profile": {},
        "elo_ratings": {},
        "session_history": [],
        "created_at": datetime.now(timezone.utc),
    })
    return candidate_id


def ensure_session_parents(db, doc: dict) -> None:
    user_id = doc.get("user_id")
    if user_id:
        ensure_user(db, str(user_id))
    candidate_id = doc.get("candidate_id")
    if candidate_id:
        ensure_candidate(db, str(candidate_id), str(user_id) if user_id else None)


def ensure_user(db, user_id: str) -> str:
    existing = db["users"].find_one({"id": user_id})
    if existing:
        return user_id
    now = datetime.now(timezone.utc)
    db["users"].insert_one({
        "id": user_id,
        "email": f"{user_id}@fk.example.com",
        "name": "Fixture",
        "password_hash": "fixture-not-a-login",
        "created_at": now,
        "last_active_at": now,
    })
    return user_id
