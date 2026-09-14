"""Phase 1B: reference allowlist, server-side resolve, reviewed gate (OFF), drafts."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("INTERVIV_USE_MEMORY_DB", "true")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

from backend.auth.security import create_access_token, hash_password
from backend.config import get_settings
from backend.db import get_database
from backend.main import app
from backend.serializers.round_serializer import sanitize_round_for_client
from modules import bundle_store
from modules.bundle_scoring import (
    BundleReferenceUnavailable,
    candidate_technical_context,
    scoring_context_from_round,
)
from modules.bundle_selector import ReviewedInventoryUnavailable, select_reviewed_question
from modules.concept_evaluator_v2 import coverage_level, evaluate_answer
from modules.question_bundles import candidate_payload, validate_bundle_doc


IDEAL_SENTINEL = "SECRET_IDEAL_ANSWER_SENTINEL_PHASE1B"
KEYWORDS_SENTINEL = "SECRET_KEYWORDS_SENTINEL_PHASE1B"

PRIVATE_TECH_FIELDS = (
    "ideal_answer",
    "ideal_keywords",
    "ideal_keywords_list",
    "reference_answer",
    "required_concepts",
    "misconceptions",
    "rubric_descriptors",
    "calibration_examples",
)


def _clear_settings():
    get_settings.cache_clear()


def _make_user(prefix: str) -> dict[str, str]:
    db = get_database()
    user_id = str(uuid4())
    db["users"].insert_one(
        {
            "id": user_id,
            "email": f"{prefix}-{user_id[:8]}@example.com",
            "name": f"Test {prefix}",
            "password_hash": hash_password("passw0rd123"),
            "created_at": datetime.now(timezone.utc),
            "last_active_at": datetime.now(timezone.utc),
        }
    )
    return {"id": user_id, "token": create_access_token(user_id)}


def _assert_no_tech_leak(payload: object, surface: str) -> None:
    blob = json.dumps(payload, default=str)
    assert IDEAL_SENTINEL not in blob, f"{surface} leaked ideal sentinel"
    assert KEYWORDS_SENTINEL not in blob, f"{surface} leaked keywords sentinel"
    for field in PRIVATE_TECH_FIELDS:
        # Field names may appear in docs/tests; require JSON-key form.
        assert f'"{field}"' not in blob, f"{surface} exposed private field {field}"


def test_candidate_technical_context_allowlist_excludes_references():
    ctx = {
        "question": "What is a generator?",
        "ideal_answer": IDEAL_SENTINEL,
        "ideal_keywords": KEYWORDS_SENTINEL,
        "ideal_keywords_list": [KEYWORDS_SENTINEL],
        "reference_answer": IDEAL_SENTINEL,
        "required_concepts": ["generator"],
        "skill": "Python",
        "bundle_id": "python.generators",
        "version": 2,
        "content_hash": "abc",
        "source": "reviewed_bundle",
    }
    safe = candidate_technical_context(ctx)
    assert safe["question"] == "What is a generator?"
    assert safe["bundle_id"] == "python.generators"
    assert "ideal_answer" not in safe
    assert "required_concepts" not in safe
    cleaned = sanitize_round_for_client({
        "round": 1,
        "round_type": "technical_short_answer",
        "question": ctx["question"],
        "question_context": ctx,
        "status": "in_progress",
        "config_json": {},
    })
    _assert_no_tech_leak(cleaned, "serializer")


def test_scoring_context_resolves_pinned_bundle(memory_store_phase1b):
    doc = {
        "bundle_id": "python.phase1b-resolve",
        "version": 1,
        "skill": "Python",
        "topic": "Generators",
        "difficulty": "medium",
        "question": "What are generators?",
        "reference_answer": IDEAL_SENTINEL,
        "keywords": [KEYWORDS_SENTINEL],
        "required_concepts": [{"id": "generator", "descriptor": "yield-based iterator"}],
        "source": "human_authored",
        "author": "author-user",
        "attribution": {"note": "fixture"},
    }
    imported = bundle_store.import_bundle(doc, actor_id="cli")
    v = imported["version"]
    round_ctx = {
        "question": doc["question"],
        "bundle_id": v["bundle_id"],
        "version": v["version"],
        "content_hash": v["content_hash"],
        "source": "reviewed_bundle",
        "skill": "Python",
    }
    scored = scoring_context_from_round(round_ctx)
    assert scored["ideal_answer"] == IDEAL_SENTINEL
    assert KEYWORDS_SENTINEL in scored["ideal_keywords"]
    # Candidate view still clean
    _assert_no_tech_leak(candidate_technical_context(round_ctx), "candidate")

    with pytest.raises(BundleReferenceUnavailable, match="content_hash mismatch"):
        scoring_context_from_round({**round_ctx, "content_hash": "0" * 64})


def test_legacy_scoring_uses_server_snapshot_without_client_keys():
    ctx = {
        "question": "Explain GIL",
        "ideal_answer": IDEAL_SENTINEL,
        "ideal_keywords": KEYWORDS_SENTINEL,
        "source": "legacy",
    }
    scored = scoring_context_from_round(ctx)
    assert scored["ideal_answer"] == IDEAL_SENTINEL
    safe = sanitize_round_for_client({
        "round_type": "technical_short_answer",
        "question_context": ctx,
        "config_json": {},
    })
    _assert_no_tech_leak(safe, "legacy-sanitized")


def test_start_and_resume_strip_technical_references(monkeypatch):
    from backend.routes import session as session_routes

    def fake_next(**kwargs):
        return {
            "question": "What is the GIL?",
            "ideal_answer": IDEAL_SENTINEL,
            "ideal_keywords": KEYWORDS_SENTINEL,
            "ideal_keywords_list": [KEYWORDS_SENTINEL],
            "skill": "Python",
            "sub_domain": None,
            "topic": "GIL",
            "difficulty": "hard",
            "source": "test_bank",
        }

    monkeypatch.setattr(session_routes, "_get_next_question", fake_next)
    client = TestClient(app)
    user = _make_user("tech-leak")
    headers = {"Authorization": f"Bearer {user['token']}"}
    started = client.post(
        "/session/start",
        json={"candidate_id": "", "skills": ["Python"], "rounds_per_skill": 1},
        headers=headers,
    )
    assert started.status_code == 200, started.text
    body = started.json()
    _assert_no_tech_leak(body, "start")
    # Server still retained the reference for scoring.
    db = get_database()
    stored = db["sessions"].find_one({"session_id": body["session_id"]})["rounds"][0]
    assert stored["question_context"]["ideal_answer"] == IDEAL_SENTINEL

    resumed = client.get(f"/session/{body['session_id']}", headers=headers)
    assert resumed.status_code == 200
    _assert_no_tech_leak(resumed.json(), "resume")


def test_submit_rejects_client_grading_override_fields():
    client = TestClient(app)
    user = _make_user("override")
    headers = {"Authorization": f"Bearer {user['token']}"}
    # Extra grading fields are rejected by the request model.
    resp = client.post(
        "/session/answer",
        json={
            "session_id": "x",
            "round": 1,
            "answer_text": "hello",
            "ideal_answer": IDEAL_SENTINEL,
            "bundle_id": "python.generators",
            "content_hash": "abc",
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_reviewed_gate_default_off_and_on_unavailable(monkeypatch, memory_store_phase1b):
    monkeypatch.delenv("REVIEWED_BUNDLES_ONLY", raising=False)
    _clear_settings()
    assert get_settings().reviewed_bundles_only is False

    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    _clear_settings()
    assert get_settings().reviewed_bundles_only is True
    with pytest.raises(ReviewedInventoryUnavailable):
        select_reviewed_question(skill="Python", difficulty="medium")

    # Drafts are not eligible even if imported.
    bundle_store.import_bundle({
        "bundle_id": "python.phase1b-draft-only",
        "version": 1,
        "skill": "Python",
        "topic": "X",
        "difficulty": "medium",
        "question": "Q?",
        "reference_answer": "A",
        "required_concepts": [{"id": "generator", "descriptor": "g"}],
        "source": "human_authored",
        "author": "a",
        "attribution": {"note": "t"},
    }, actor_id="cli")
    with pytest.raises(ReviewedInventoryUnavailable):
        select_reviewed_question(skill="Python", difficulty="medium")
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    _clear_settings()


def test_reviewed_gate_on_selects_reviewed_without_reference_in_payload(
    monkeypatch, memory_store_phase1b
):
    from tests.test_phase1a_bundles import CHECK_OK, REASON, CALIB

    doc = {
        "bundle_id": "python.phase1b-reviewed",
        "version": 1,
        "skill": "Python",
        "topic": "Locks",
        "difficulty": "easy",
        "question": "Which construct releases a lock automatically?",
        "reference_answer": IDEAL_SENTINEL,
        "required_concepts": [{"id": "context_manager", "descriptor": "with releases lock"}],
        "source": "human_authored",
        "author": "author-user",
        "attribution": {"note": "synthetic reviewed fixture"},
    }
    bundle_store.import_bundle(doc, actor_id="cli")
    bundle_store.submit_for_review("python.phase1b-reviewed", 1, actor_id="admin")
    v = bundle_store.get_version("python.phase1b-reviewed", 1)
    for reviewer in ("reviewer-a", "reviewer-b"):
        bundle_store.record_decision(
            "python.phase1b-reviewed", 1,
            reviewer_id=reviewer, content_hash=v["content_hash"], decision="approve",
            checklist=CHECK_OK, reasons=REASON, calibration=CALIB,
        )
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "true")
    _clear_settings()
    payload = select_reviewed_question(skill="Python", difficulty="easy")
    assert payload["bundle_id"] == "python.phase1b-reviewed"
    assert "ideal_answer" not in payload
    assert IDEAL_SENTINEL not in json.dumps(payload)
    assert payload == candidate_payload(bundle_store.get_version("python.phase1b-reviewed", 1))

    from backend.routes.session import _get_next_question, _normalize_question_payload
    normalized = _get_next_question(
        skill="Python", sub_domain=None, difficulty="easy", asked=[]
    )
    assert normalized["bundle_id"] == "python.phase1b-reviewed"
    assert "ideal_answer" not in normalized
    scored = scoring_context_from_round(normalized)
    assert scored["ideal_answer"] == IDEAL_SENTINEL
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    _clear_settings()


def test_pilot_v2_drafts_have_concepts_and_remain_draft():
    from modules.question_bundles import iter_bundle_files, validate_bundle_doc

    v1_docs = []
    v2_docs = []
    for path, doc in iter_bundle_files():
        validated = validate_bundle_doc(doc)
        if validated["version"] == 1:
            v1_docs.append(validated)
        elif validated["version"] == 2:
            v2_docs.append(validated)
    assert len(v1_docs) == 12
    assert len(v2_docs) == 12
    for item in v2_docs:
        assert item["content"]["required_concepts"], item["content"]["bundle_id"]
        assert item["source"] == "human_authored"
    # Import v1 then v2; both remain draft (no fabricated reviews).
    bundle_store.reset_memory_store()
    os.environ["INTERVIV_USE_MEMORY_DB"] = "true"
    _clear_settings()
    by_bundle: dict[str, list] = {}
    for path, doc in iter_bundle_files():
        by_bundle.setdefault(doc["bundle_id"], []).append(doc)
    for bundle_id, docs in sorted(by_bundle.items()):
        for doc in sorted(docs, key=lambda d: int(d["version"])):
            result = bundle_store.import_bundle(doc, actor_id="phase1b")
            assert result["version"]["status"] == "draft", bundle_id


def test_concept_evaluator_states_and_coverage_boundaries():
    content = {
        "required_concepts": [
            {
                "id": "TCP",
                "descriptor": "Transmission Control Protocol",
                "aliases": ["tcp"],
                "expected_propositions": ["TCP is connection oriented"],
            },
            {
                "id": "handshake",
                "descriptor": "three-way handshake",
                "aliases": ["three way handshake"],
                "expected_propositions": ["TCP uses three way handshake"],
            },
            {
                "id": "reliability",
                "descriptor": "reliable delivery",
                "aliases": ["reliable"],
                "expected_propositions": ["TCP provides reliable delivery"],
            },
        ],
        "optional_concepts": [
            {"id": "UDP", "descriptor": "User Datagram Protocol", "aliases": ["udp"],
             "expected_propositions": ["UDP is connectionless"]},
        ],
        "misconceptions": [
            {"id": "tcp_connectionless", "description": "TCP is connectionless",
             "candidate_patterns": ["TCP is connectionless", "tcp connectionless"]},
        ],
        "depth_markers": ["three-way handshake", "retransmission"],
        "rubric_descriptors": {},
    }
    # Term-only / wrong proposition: mention TCP with connectionless claim
    wrong = evaluate_answer(
        answer_text="TCP is connectionless and that is fine.",
        bundle_content=content,
        bundle_content_hash="h1",
    )
    tcp = next(c for c in wrong["concepts"] if c["concept_id"] == "TCP")
    assert tcp["state"] in {"contradicted", "uncertain", "not_demonstrated"}
    assert wrong["headline_total"] is None
    assert any(m["matched"] for m in wrong["misconceptions"])

    # Refuted misconception should not alone prove support, but should mark refuted
    refuted = evaluate_answer(
        answer_text="Some people say TCP is connectionless, but TCP is not connectionless; "
                    "TCP is connection oriented and uses three way handshake for reliable delivery.",
        bundle_content=content,
        bundle_content_hash="h1",
    )
    assert refuted["coverage"]["k_supported"] >= 1
    assert any(m.get("refuted") for m in refuted["misconceptions"] if m["matched"])

    # Empty / missing required concepts → unassessable
    empty = evaluate_answer(answer_text="anything", bundle_content={"required_concepts": []})
    assert empty["assessable"] is False

    # Small-n coverage boundaries: n=1 → level 2 unreachable
    assert coverage_level(1, 0) == 0
    assert coverage_level(1, 1) == 3
    assert coverage_level(2, 1) == 1  # ceil(4/3)=2, so k=1 → level 1
    assert coverage_level(3, 2) == 2
    assert coverage_level(3, 3) == 3
    assert coverage_level(0, 0) is None

    # Keyword stuffing / unrelated
    stuffing = evaluate_answer(
        answer_text="TCP TCP TCP handshake handshake reliability reliability banana cosmology",
        bundle_content=content,
    )
    # Mentions without adequate propositions → not all supported
    assert stuffing["coverage"]["k_supported"] < stuffing["coverage"]["n_required"]

    # Clarity stays unassessed; no headline
    assert stuffing["criteria"]["clarity"] is None
    assert stuffing["headline_total"] is None


def test_experimental_evaluator_flag_default_off_and_isolated(monkeypatch):
    monkeypatch.delenv("EXPERIMENTAL_CONCEPT_EVALUATOR", raising=False)
    _clear_settings()
    from modules.concept_evaluator_v2 import experimental_concept_evaluator_enabled
    assert experimental_concept_evaluator_enabled() is False
    # Production scoring path must not import the experimental evaluator.
    import modules.scoring as scoring_mod
    from pathlib import Path

    src = Path(scoring_mod.__file__).read_text(encoding="utf-8")
    assert "concept_evaluator_v2" not in src
    # Mastery / readiness modules likewise
    from modules import concept_mastery
    mastery_src = Path(concept_mastery.__file__).read_text(encoding="utf-8")
    assert "concept_evaluator_v2" not in mastery_src


@pytest.fixture
def memory_store_phase1b(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("INTERVIV_USE_MEMORY_DB", "true")
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    _clear_settings()
    bundle_store.reset_memory_store()
    yield
    bundle_store.reset_memory_store()
    monkeypatch.setenv("REVIEWED_BUNDLES_ONLY", "false")
    _clear_settings()
