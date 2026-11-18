"""Capture the pre-step-1 flag-off contract on isolated storage, without network.

The fixture was captured at 3384dd0 before editing any application source.
Normalize only time/identities; retain scores, eligibility, prompts and feedback.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi.testclient import TestClient


def capture(monkeypatch, tmp_path: Path) -> dict:
    from backend import config
    from backend.db import get_database
    from backend.db.sqlalchemy_store import (
        _sessionmaker, create_all_for_smoke, get_engine, get_sqlalchemy_database,
    )
    from backend.main import app
    from modules import bundle_generator, bundle_store, llm_usage, role_skills
    from modules.llm_outbound_gate import question_source_health
    from tests.test_slice2_staged_flow import (
        _create_user_headers, _seed_single_reviewed_python_bundle,
    )

    for key, value in {
        "DATABASE_URL": f"sqlite:///{tmp_path / 'flag-off.sqlite3'}",
        "INTERVIV_DISABLE_DOTENV": "1", "INTERVIV_USE_MEMORY_DB": "false",
        "LLM_LIVE_FETCH": "0", "JOBS_LIVE_FETCH": "0",
        "AI_INTERVIEW_ROUTING_ENABLED": "0", "ALLOW_PAID_CONTENT_FALLBACK": "false",
        "REVIEWED_BUNDLES_ONLY": "true", "STAGED_INLINE_FOLLOW_UPS": "0",
        "JWT_SECRET_KEY": "test-secret-key-with-at-least-32-bytes!!",
        "QUESTION_GENERATION_MODE": "csv",
        "NEW_CANONICAL_SKILLS_AUDIT_PATH": str(tmp_path / "skills.jsonl"),
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("LLM_LIVE_CONSUMERS", raising=False)
    monkeypatch.setattr(bundle_generator.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Network forbidden")))
    for cache in (config.get_settings, get_engine, _sessionmaker, get_sqlalchemy_database):
        cache.cache_clear()
    create_all_for_smoke()
    bundle_store.reset_memory_store()
    role_skills.reset_role_skill_cache()
    try:
        db = get_database()
        _, headers = _create_user_headers(db, email="routing-transcript@example.test")
        _seed_single_reviewed_python_bundle()
        client = TestClient(app)
        transcript = {"source_health": question_source_health(), "steps": []}
        start = client.post("/session/start", headers=headers, json={
            "skills": ["Python"], "rounds_per_skill": 1,
            "round_type": "technical_short_answer", "practice_mode": "assessment",
        })
        assert start.status_code == 200, start.text
        sid = start.json()["session_id"]
        transcript["steps"].append(["start", start.status_code, start.json()])
        answer = client.post("/session/answer", headers=headers, json={
            "session_id": sid, "round": 1,
            "answer_text": "Coroutines yield control at await points so the single-threaded event loop can schedule non-blocking I/O cooperatively.",
        })
        assert answer.status_code == 200, answer.text
        transcript["steps"].append(["answer", answer.status_code, answer.json()])
        for name, url in (("session", f"/session/{sid}"),
                          ("feedback", f"/session/{sid}/rounds/1/feedback"),
                          ("report", f"/dashboard/{sid}")):
            response = client.get(url, headers=headers)
            assert response.status_code == 200, response.text
            transcript["steps"].append([name, response.status_code, response.json()])
        bundle_generator.set_bundle_llm_override(lambda **kw: "offline bundle completion")
        transcript["bundle_override"] = bundle_generator._call_bundle_llm(
            purpose="bundle_generation", provider="openrouter", model="fixture/model",
            messages=[{"role": "user", "content": "Generic bundle prompt"}],
        )
        role_skills.set_role_skills_llm_override(lambda **kw: {
            "role_title": "Backend engineer", "domain": "Software",
            "skills": [{"name": "Python", "topics": ["Concurrency"], "weight": 0.8}],
        })
        transcript["role_override"] = role_skills.extract_role_skills(role="Backend engineer")
        role_skills.set_role_skills_llm_override(None)
        transcript["role_cached"] = role_skills.extract_role_skills(role="Backend engineer")
        return normalize(transcript)
    finally:
        bundle_generator.set_bundle_llm_override(None)
        role_skills.set_role_skills_llm_override(None)
        get_engine().dispose()
        for cache in (config.get_settings, get_engine, _sessionmaker, get_sqlalchemy_database):
            cache.cache_clear()


def normalize(value):
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in sorted(value.items()) if key not in {
            "created_at", "updated_at", "started_at", "expires_at", "submitted_at",
            "completed_at", "cutoff_at", "server_time", "last_active_at", "digest",
            "delivered_at", "delivery_order", "latency_ms", "processing_time_ms",
        }}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, str):
        value = re.sub(r"test\.py\.reviewed\.[0-9a-f]{6}", "test.py.reviewed.<id>", value)
        value = re.sub(r"user-[0-9a-f]{10}", "user-<id>", value)
        value = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<uuid>", value)
        return re.sub(r"\b[0-9a-f]{32,64}\b", "<hash>", value)
    return value


if __name__ == "__main__":
    import tempfile
    import pytest
    with tempfile.TemporaryDirectory() as directory, pytest.MonkeyPatch.context() as patch:
        result = capture(patch, Path(directory))
    Path(__file__).with_name("fixtures").joinpath("ai_routing_flag_off.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
